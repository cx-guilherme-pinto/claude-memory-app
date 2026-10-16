"""Índice SQLite: pesquisa FTS5 (título + corpo) e arestas do grafo.

O índice é descartável: `memoria reindex` reconstrói-o a partir dos Markdown.

Grafo:
- nós de memória: id = "<pasta do projeto>/<nome do ficheiro sem .md>";
- nós de contexto: "projeto:<p>", "tarefa:<p>:<t>", "ficheiro:<p>:<caminho>"
  (tarefas e ficheiros são relativos ao projeto, para não misturar "#12" de repos diferentes);
- arestas: memória↔memória (ligação explícita) e memória→contexto.

Força da relação entre duas memórias (por esta ordem):
ligação explícita [[...]]/ligacoes > mesma tarefa > mesmo projeto > ficheiros partilhados.
Os pesos garantem a ordem: cada nível vale mais do que todos os de baixo somados.

Extensão (embeddings): estão DESLIGADOS. Para os ligar no futuro, implementar
`Embeddings` (abaixo) e passar uma instância a `Indice(..., embeddings=...)`.
`procurar` combina então a pontuação FTS com a semelhança vetorial.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Protocol

from memoria import store

VERSAO_ESQUEMA = 1

PESOS = {"ligacao": 4.0, "tarefa": 2.0, "projeto": 1.0, "ficheiro": 0.25}
MAX_FICHEIROS = 0.5  # teto da contribuição dos ficheiros partilhados


class FTS5Indisponivel(RuntimeError):
    pass


class Embeddings(Protocol):
    """Ponto de extensão (não usado na v0.1). Deve devolver um vetor por texto."""

    def vetores(self, textos: list[str]) -> list[list[float]]: ...


_FTS5_OK = False


def verificar_fts5() -> None:
    """Falha com uma mensagem clara se o SQLite não tiver FTS5."""
    global _FTS5_OK
    if _FTS5_OK:
        return
    try:
        con = sqlite3.connect(":memory:")
        try:
            con.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='unicode61 remove_diacritics 2')")
        finally:
            con.close()
    except sqlite3.Error as erro:
        raise FTS5Indisponivel(
            "O SQLite deste Python não tem FTS5 "
            f"(sqlite {sqlite3.sqlite_version}, erro: {erro}). "
            "Reinstala com o Python gerido pelo uv: "
            "uv tool install --force --python 3.12 <wheel>"
        ) from erro
    _FTS5_OK = True


_ESQUEMA = f"""
CREATE TABLE IF NOT EXISTS meta(chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS notas(
    id TEXT PRIMARY KEY,
    caminho TEXT NOT NULL,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    projeto TEXT NOT NULL,
    tarefa TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL,
    custo_usd REAL,
    ficheiros TEXT NOT NULL DEFAULT '[]',
    ligacoes TEXT NOT NULL DEFAULT '[]',
    mtime_ns INTEGER NOT NULL,
    tamanho INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS notas_projeto ON notas(projeto);
CREATE VIRTUAL TABLE IF NOT EXISTS notas_fts USING fts5(
    id UNINDEXED, titulo, corpo, contexto,
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS arestas(
    origem TEXT NOT NULL,
    destino TEXT NOT NULL,
    tipo TEXT NOT NULL,
    peso REAL NOT NULL,
    PRIMARY KEY(origem, destino, tipo)
);
CREATE INDEX IF NOT EXISTS arestas_destino ON arestas(destino);
INSERT OR IGNORE INTO meta VALUES('versao_esquema', '{VERSAO_ESQUEMA}');
"""


def id_projeto(projeto: str) -> str:
    return f"projeto:{projeto}"


def id_tarefa(projeto: str, tarefa: str) -> str:
    return f"tarefa:{projeto}:{tarefa}"


def id_ficheiro(projeto: str, caminho: str) -> str:
    return f"ficheiro:{projeto}:{caminho.replace(chr(92), '/').lstrip('./')}"


def _consulta_fts(texto: str) -> str:
    termos = re.findall(r"\w+", texto, flags=re.UNICODE)
    return " OR ".join(f'"{t}"*' for t in termos[:32])


class Indice:
    def __init__(self, home: Path, caminho: Path | None = None, embeddings: Embeddings | None = None):
        self.home = Path(home)
        self.caminho = Path(caminho) if caminho else self.home / ".indice" / "memoria.sqlite"
        self.embeddings = embeddings  # sempre None na v0.1

    # ---------------------------------------------------------------- ligação
    @contextmanager
    def ligar(self):
        verificar_fts5()
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.caminho, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute("PRAGMA busy_timeout=15000")
            versao = con.execute(
                "SELECT name FROM sqlite_master WHERE name='meta'"
            ).fetchone() and con.execute(
                "SELECT valor FROM meta WHERE chave='versao_esquema'"
            ).fetchone()
            if versao and versao[0] != str(VERSAO_ESQUEMA):
                self._apagar_tabelas(con)
            con.executescript(_ESQUEMA)
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _apagar_tabelas(con: sqlite3.Connection) -> None:
        con.executescript(
            "DROP TABLE IF EXISTS notas_fts; DROP TABLE IF EXISTS notas;"
            "DROP TABLE IF EXISTS arestas; DROP TABLE IF EXISTS meta;"
        )

    # ---------------------------------------------------------- sincronizar
    def reindexar(self) -> dict:
        """Reconstrói tudo a partir dos Markdown."""
        with self.ligar() as con:
            self._apagar_tabelas(con)
            con.executescript(_ESQUEMA)
        return self.sincronizar()

    def sincronizar(self) -> dict:
        """Atualiza só o que mudou no disco (mtime/tamanho) e refaz as arestas."""
        inicio = time.perf_counter()
        erros: list[str] = []
        with self.ligar() as con:
            conhecidas = {
                r["id"]: (r["mtime_ns"], r["tamanho"])
                for r in con.execute("SELECT id, mtime_ns, tamanho FROM notas")
            }
            vistas: set[str] = set()
            alteradas = 0
            for ficheiro in store.listar_ficheiros(self.home):
                try:
                    st = ficheiro.stat()
                    nid = store.id_de(ficheiro, self.home)
                except (OSError, ValueError):
                    continue
                vistas.add(nid)
                if conhecidas.get(nid) == (st.st_mtime_ns, st.st_size):
                    continue
                try:
                    nota = store.ler_nota(ficheiro, self.home)
                except Exception as erro:  # ficheiro editado à mão e inválido
                    erros.append(f"{ficheiro}: {erro}")
                    vistas.discard(nid)
                    continue
                self._gravar(con, nota, st.st_mtime_ns, st.st_size)
                alteradas += 1
            removidas = set(conhecidas) - vistas
            for nid in removidas:
                con.execute("DELETE FROM notas WHERE id=?", (nid,))
                con.execute("DELETE FROM notas_fts WHERE id=?", (nid,))
            if alteradas or removidas or not conhecidas:
                self._refazer_arestas(con)
            total = con.execute("SELECT count(*) FROM notas").fetchone()[0]
        for erro in erros:
            print(f"Aviso: memória ignorada: {erro}", file=sys.stderr)
        return {
            "total": total,
            "alteradas": alteradas,
            "removidas": len(removidas),
            "erros": len(erros),
            "segundos": round(time.perf_counter() - inicio, 3),
        }

    def _gravar(self, con: sqlite3.Connection, nota: store.Nota, mtime_ns: int, tamanho: int) -> None:
        con.execute(
            "INSERT OR REPLACE INTO notas VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                nota.id,
                str(nota.caminho),
                nota.tipo,
                nota.titulo,
                nota.projeto,
                nota.tarefa,
                nota.data,
                nota.custo_usd,
                json.dumps(nota.ficheiros, ensure_ascii=False),
                json.dumps(nota.todas_ligacoes, ensure_ascii=False),
                mtime_ns,
                tamanho,
            ),
        )
        con.execute("DELETE FROM notas_fts WHERE id=?", (nota.id,))
        contexto = " ".join([nota.projeto, nota.tarefa, *nota.ficheiros])
        con.execute(
            "INSERT INTO notas_fts(id, titulo, corpo, contexto) VALUES(?,?,?,?)",
            (nota.id, nota.titulo, nota.corpo, contexto),
        )

    def _refazer_arestas(self, con: sqlite3.Connection) -> None:
        notas = con.execute("SELECT id, titulo, projeto, tarefa, ficheiros, ligacoes FROM notas").fetchall()
        resolver = _Resolvedor(notas)
        arestas: dict[tuple[str, str, str], float] = {}
        for n in notas:
            nid, projeto = n["id"], n["projeto"]
            arestas[(nid, id_projeto(projeto), "projeto")] = PESOS["projeto"]
            if n["tarefa"]:
                arestas[(nid, id_tarefa(projeto, n["tarefa"]), "tarefa")] = PESOS["tarefa"]
            for f in json.loads(n["ficheiros"]):
                arestas[(nid, id_ficheiro(projeto, f), "ficheiro")] = PESOS["ficheiro"]
            for alvo in json.loads(n["ligacoes"]):
                destino = resolver.resolver(alvo, projeto)
                if destino and destino != nid:
                    a, b = sorted((nid, destino))  # ligação explícita é simétrica
                    arestas[(a, b, "ligacao")] = PESOS["ligacao"]
        con.execute("DELETE FROM arestas")
        con.executemany(
            "INSERT INTO arestas VALUES(?,?,?,?)",
            [(o, d, t, p) for (o, d, t), p in arestas.items()],
        )

    # ------------------------------------------------------------- consultas
    def resolver(self, ref: str) -> str | None:
        """Aceita id, nome do ficheiro, caminho absoluto/relativo, título ou [[nome]]."""
        ref = store.limpar_ligacao(ref)
        if not ref:
            return None
        caminho = Path(ref).expanduser()
        if caminho.suffix == ".md":
            try:
                alvo = caminho if caminho.is_absolute() else self.home / caminho
                ref = store.id_de(alvo, self.home)
            except ValueError:
                pass
        with self.ligar() as con:
            notas = con.execute("SELECT id, titulo, projeto, tarefa, ficheiros, ligacoes FROM notas").fetchall()
        return _Resolvedor(notas).resolver(ref, None)

    def procurar(self, texto: str, projeto: str | None = None, tipo: str | None = None, limite: int = 10) -> list[dict]:
        limite = max(1, min(int(limite or 10), 200))
        filtros, args = [], []
        if projeto:
            filtros.append("n.projeto = ?")
            args.append(projeto)
        if tipo:
            filtros.append("n.tipo = ?")
            args.append(store.normalizar_tipo(tipo))
        consulta = _consulta_fts(texto or "")
        with self.ligar() as con:
            if consulta:
                where = " AND ".join(["notas_fts MATCH ?", *filtros])
                linhas = con.execute(
                    f"""SELECT n.*, bm25(notas_fts, 0, 6.0, 1.0, 2.0) AS rank,
                               snippet(notas_fts, 2, '«', '»', '…', 16) AS excerto
                        FROM notas_fts JOIN notas n ON n.id = notas_fts.id
                        WHERE {where} ORDER BY rank LIMIT ?""",
                    [consulta, *args, limite],
                ).fetchall()
            else:
                where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
                linhas = con.execute(
                    f"""SELECT n.*, 0 AS rank, substr(f.corpo, 1, 160) AS excerto
                        FROM notas n JOIN notas_fts f ON f.id = n.id {where}
                        ORDER BY n.data DESC LIMIT ?""",
                    [*args, limite],
                ).fetchall()
        return [
            {**_linha_resumo(r), "excerto": " ".join((r["excerto"] or "").split()), "pontuacao": round(-r["rank"], 4)}
            for r in linhas
        ]

    def nota(self, ref: str) -> dict | None:
        nid = self.resolver(ref)
        if not nid:
            return None
        with self.ligar() as con:
            r = con.execute("SELECT * FROM notas WHERE id=?", (nid,)).fetchone()
            corpo = con.execute("SELECT corpo FROM notas_fts WHERE id=?", (nid,)).fetchone()
        if not r:
            return None
        return {**_linha_resumo(r), "corpo": corpo["corpo"] if corpo else ""}

    def relacionadas(self, ref: str, limite: int = 10) -> list[dict]:
        nid = self.resolver(ref)
        if not nid:
            raise LookupError(f"Memória não encontrada: {ref}")
        limite = max(1, min(int(limite or 10), 200))
        with self.ligar() as con:
            minhas = con.execute(
                "SELECT destino, tipo FROM arestas WHERE origem=? AND tipo != 'ligacao'", (nid,)
            ).fetchall()
            explicitas = {
                r[0]
                for r in con.execute(
                    "SELECT destino FROM arestas WHERE origem=? AND tipo='ligacao' "
                    "UNION SELECT origem FROM arestas WHERE destino=? AND tipo='ligacao'",
                    (nid, nid),
                )
            }
            pontos: dict[str, dict] = {}

            def somar(outro: str, motivo: str, valor: float) -> None:
                p = pontos.setdefault(outro, {"forca": 0.0, "motivos": {}, "ficheiros": 0.0})
                if motivo == "ficheiro":
                    p["ficheiros"] = min(MAX_FICHEIROS, p["ficheiros"] + valor)
                else:
                    p["forca"] += valor
                p["motivos"][motivo] = p["motivos"].get(motivo, 0) + 1

            for outro in explicitas:
                somar(outro, "ligacao", PESOS["ligacao"])
            for contexto, tipo in minhas:
                for (outro,) in con.execute(
                    "SELECT origem FROM arestas WHERE destino=? AND origem != ?", (contexto, nid)
                ):
                    somar(outro, tipo, PESOS[tipo])
            ids = list(pontos)
            linhas = {}
            for i in range(0, len(ids), 500):
                bloco = ids[i : i + 500]
                for r in con.execute(
                    f"SELECT * FROM notas WHERE id IN ({','.join('?' * len(bloco))})", bloco
                ):
                    linhas[r["id"]] = r
        resultado = []
        for outro, p in pontos.items():
            if outro not in linhas:
                continue
            forca = p["forca"] + p["ficheiros"]
            resultado.append({**_linha_resumo(linhas[outro]), "forca": round(forca, 3), "motivos": p["motivos"]})
        resultado.sort(key=lambda x: x["data"], reverse=True)
        resultado.sort(key=lambda x: -x["forca"])  # estável: empate → mais recente primeiro
        return resultado[:limite]

    def grafo(self) -> dict:
        """Nós e arestas para a UI (sem o corpo das notas, para ser leve)."""
        with self.ligar() as con:
            notas = con.execute(
                "SELECT id, tipo, titulo, projeto, tarefa, data, custo_usd FROM notas"
            ).fetchall()
            arestas = con.execute("SELECT origem, destino, tipo FROM arestas").fetchall()
        nos: dict[str, dict] = {}
        for n in notas:
            nos[n["id"]] = {
                "id": n["id"],
                "tipo": n["tipo"],
                "rotulo": n["titulo"],
                "projeto": n["projeto"],
                "tarefa": n["tarefa"],
                "data": n["data"],
                "grau": 0,
            }
        projeto_de = {n["id"]: n["projeto"] for n in notas}
        data_de = {n["id"]: n["data"] for n in notas}
        links = []
        for a in arestas:
            origem, destino, tipo = a["origem"], a["destino"], a["tipo"]
            if destino not in nos:
                rotulo = destino.split(":", 2)[-1]
                nos[destino] = {
                    "id": destino,
                    "tipo": tipo,
                    "rotulo": rotulo,
                    "projeto": projeto_de.get(origem, ""),
                    "tarefa": "",
                    "data": data_de.get(origem, ""),
                    "grau": 0,
                }
            elif nos[destino]["tipo"] in store.TIPOS_CONTEXTO:
                nos[destino]["data"] = min(nos[destino]["data"], data_de.get(origem, "9999"))
            nos[origem]["grau"] += 1
            nos[destino]["grau"] += 1
            links.append({"source": origem, "target": destino, "tipo": tipo})
        projetos = sorted({n["projeto"] for n in notas})
        return {"nos": list(nos.values()), "ligacoes": links, "projetos": projetos, "total": len(notas)}

    def ids(self) -> Iterable[str]:
        with self.ligar() as con:
            return [r[0] for r in con.execute("SELECT id FROM notas ORDER BY data")]


def _linha_resumo(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "caminho": r["caminho"],
        "tipo": r["tipo"],
        "titulo": r["titulo"],
        "projeto": r["projeto"],
        "tarefa": r["tarefa"],
        "data": r["data"],
        "custo_usd": r["custo_usd"],
        "ficheiros": json.loads(r["ficheiros"]),
        "ligacoes": json.loads(r["ligacoes"]),
    }


class _Resolvedor:
    """Resolve o alvo de uma ligação: id, nome do ficheiro, nome sem data, título."""

    def __init__(self, notas: list[sqlite3.Row]):
        self.ids = {n["id"] for n in notas}
        self.por_nome: dict[str, list[tuple[str, str]]] = {}
        for n in notas:
            nid, projeto = n["id"], n["projeto"]
            nome = nid.rsplit("/", 1)[-1]
            chaves = {
                nome.lower(),
                re.sub(r"^\d{4}-\d{2}-\d{2}-", "", nome).lower(),
                n["titulo"].strip().lower(),
                store.slug(n["titulo"]),
            }
            for chave in chaves:
                self.por_nome.setdefault(chave, []).append((projeto, nid))

    def resolver(self, alvo: str, projeto: str | None) -> str | None:
        alvo = alvo.strip()
        if alvo.endswith(".md"):
            alvo = alvo[:-3]
        if alvo in self.ids:
            return alvo
        for chave in (alvo.lower(), store.slug(alvo)):
            candidatos = self.por_nome.get(chave)
            if candidatos:
                # Prefere o mesmo projeto; depois a mais recente (ids têm a data).
                mesmos = [c for c in candidatos if c[0] == projeto] or candidatos
                return sorted(mesmos, key=lambda c: c[1])[-1][1]
        return None
