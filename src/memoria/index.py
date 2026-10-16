"""Índice SQLite: pesquisa FTS5 e arestas do grafo.

O índice é descartável: `memoria reindex` reconstrói-o a partir dos Markdown.
Cada versão do esquema usa o seu ficheiro (memoria-v<N>.sqlite), para uma versão
antiga ainda aberta (ex.: um `memoria mcp` do Claude Code) não estragar a nova.

Pesquisa (FTS5): título (nome da memória), corpo, projeto, chaves (tarefa, épico,
etiquetas) e ficheiros. Uma chave de ticket no texto (ABC-123, dono/repo#12)
encontra também tudo o que tem essa tarefa ou esse épico, e o resto do épico.

Grafo:
- nós de memória: id = "<pasta do projeto>/<nome do ficheiro sem .md>";
- nós de contexto: "projeto:<p>", "epico:<chave>", "tarefa:<chave>", "ficheiro:<p>:<caminho>".
  Chaves globais (ABC-123, dono/repo#12) juntam projetos; as outras ("#12", "T1")
  ficam no projeto: "tarefa:<p>:<chave>". Uma chave usada como épico é um nó "epico".
- arestas: memória↔memória (ligação explícita), memória→contexto e tarefa→épico.

Força da relação entre duas memórias (por esta ordem):
ligação explícita > mesma tarefa > mesmo épico > mesmo projeto > ficheiros partilhados.
Os pesos garantem a ordem: cada nível vale mais do que todos os de baixo somados.
Uma memória sem épico herda o épico da sua tarefa, se outra nota o indicar.

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

VERSAO_ESQUEMA = 2
NOME_FICHEIRO = f"memoria-v{VERSAO_ESQUEMA}.sqlite"

PESOS = {"ligacao": 8.0, "tarefa": 4.0, "epico": 2.0, "projeto": 1.0, "ficheiro": 0.25}
MAX_FICHEIROS = 0.5  # teto da contribuição dos ficheiros partilhados
# Pontuação da pesquisa por chave de ticket (acima de qualquer pontuação FTS).
PONTOS_CHAVE = {"tarefa": 1000.0, "epico": 900.0, "mesmo_epico": 700.0}

_PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "em", "no", "na", "um", "uma", "para", "com", "por", "que"}
_CHAVE_NO_TEXTO = re.compile(r"(?<![\w/#-])([A-Za-z][A-Za-z0-9_]*-\d+|[\w.-]+/[\w.-]+#\d+)(?![\w-])")


class FTS5Indisponivel(RuntimeError):
    pass


class Embeddings(Protocol):
    """Ponto de extensão (não usado). Deve devolver um vetor por texto."""

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
            "uv tool install --force --managed-python --python 3.12 <wheel>"
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
    epico TEXT NOT NULL DEFAULT '',
    epico_efetivo TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    etiquetas TEXT NOT NULL DEFAULT '[]',
    data TEXT NOT NULL,
    custo_usd REAL,
    ficheiros TEXT NOT NULL DEFAULT '[]',
    ligacoes TEXT NOT NULL DEFAULT '[]',
    mtime_ns INTEGER NOT NULL,
    tamanho INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS notas_projeto ON notas(projeto);
CREATE INDEX IF NOT EXISTS notas_tarefa ON notas(tarefa COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS notas_epico ON notas(epico_efetivo COLLATE NOCASE);
CREATE VIRTUAL TABLE IF NOT EXISTS notas_fts USING fts5(
    id UNINDEXED, titulo, corpo, projeto, chaves, ficheiros,
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS contexto(
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    rotulo TEXT NOT NULL,
    projeto TEXT NOT NULL,
    chave TEXT NOT NULL DEFAULT ''
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

# bm25: id, titulo, corpo, projeto, chaves, ficheiros
_PESOS_BM25 = "0, 8.0, 1.0, 3.0, 6.0, 1.0"


def id_projeto(projeto: str) -> str:
    return f"projeto:{projeto}"


def id_chave(tipo: str, projeto: str, chave: str) -> str:
    """Nó de tarefa ou épico. Chaves globais não levam o projeto."""
    chave = store.normalizar_chave(chave)
    return f"{tipo}:{chave}" if store.chave_global(chave) else f"{tipo}:{projeto}:{chave}"


def id_tarefa(projeto: str, tarefa: str) -> str:
    return id_chave("tarefa", projeto, tarefa)


def id_epico(projeto: str, epico: str) -> str:
    return id_chave("epico", projeto, epico)


def id_ficheiro(projeto: str, caminho: str) -> str:
    return f"ficheiro:{projeto}:{caminho.replace(chr(92), '/').lstrip('./')}"


def chaves_no_texto(texto: str) -> list[str]:
    return [store.normalizar_chave(m.group(1)) for m in _CHAVE_NO_TEXTO.finditer(texto or "")]


def _consulta_fts(texto: str) -> str:
    """Chaves (ABC-123) viram frases exatas; as outras palavras, prefixos em OR."""
    texto = texto or ""
    partes = []
    for chave in chaves_no_texto(texto):
        termos = re.findall(r"\w+", chave, flags=re.UNICODE)
        if termos:
            partes.append('"' + " ".join(termos) + '"')
    resto = _CHAVE_NO_TEXTO.sub(" ", texto)
    palavras = re.findall(r"\w+", resto, flags=re.UNICODE)
    uteis = [p for p in palavras if len(p) > 1 and p.lower() not in _PALAVRAS_VAZIAS] or [p for p in palavras if len(p) > 1]
    partes += [f'"{p}"*' for p in uteis[:32]]
    return " OR ".join(partes)


def _normal(texto: str) -> str:
    return store.sem_acentos(str(texto or "")).lower().strip()


class Indice:
    def __init__(self, home: Path, caminho: Path | None = None, embeddings: Embeddings | None = None):
        self.home = Path(home)
        self.caminho = Path(caminho) if caminho else self.home / ".indice" / NOME_FICHEIRO
        self.embeddings = embeddings  # sempre None

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
            versao = con.execute("SELECT name FROM sqlite_master WHERE name='meta'").fetchone() and con.execute(
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
            "DROP TABLE IF EXISTS notas_fts; DROP TABLE IF EXISTS notas; DROP TABLE IF EXISTS contexto;"
            "DROP TABLE IF EXISTS arestas; DROP TABLE IF EXISTS meta;"
        )

    def _apagar_indices_antigos(self) -> None:
        """Índices de esquemas anteriores (ex.: memoria.sqlite da v0.1). Melhor esforço."""
        pasta = self.caminho.parent
        for f in [*pasta.glob("memoria.sqlite*"), *pasta.glob("memoria-v*.sqlite*")]:
            if not f.name.startswith(self.caminho.name):
                try:
                    f.unlink()
                except OSError:
                    pass  # no Windows, um processo antigo ainda o pode ter aberto

    # ---------------------------------------------------------- sincronizar
    def reindexar(self) -> dict:
        """Reconstrói tudo a partir dos Markdown."""
        with self.ligar() as con:
            self._apagar_tabelas(con)
            con.executescript(_ESQUEMA)
        self._apagar_indices_antigos()
        return self.sincronizar()

    def sincronizar(self) -> dict:
        """Atualiza só o que mudou no disco (mtime/tamanho) e refaz as arestas."""
        inicio = time.perf_counter()
        erros: list[str] = []
        with self.ligar() as con:
            conhecidas = {r["id"]: (r["mtime_ns"], r["tamanho"]) for r in con.execute("SELECT id, mtime_ns, tamanho FROM notas")}
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
            """INSERT OR REPLACE INTO notas(id, caminho, tipo, titulo, projeto, tarefa, epico, epico_efetivo,
                   url, etiquetas, data, custo_usd, ficheiros, ligacoes, mtime_ns, tamanho)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                nota.id,
                str(nota.caminho),
                nota.tipo,
                nota.titulo,
                nota.projeto,
                nota.tarefa,
                nota.epico,
                nota.epico,
                nota.url,
                json.dumps(nota.etiquetas, ensure_ascii=False),
                nota.data,
                nota.custo_usd,
                json.dumps(nota.ficheiros, ensure_ascii=False),
                json.dumps(nota.todas_ligacoes, ensure_ascii=False),
                mtime_ns,
                tamanho,
            ),
        )
        con.execute("DELETE FROM notas_fts WHERE id=?", (nota.id,))
        chaves = " ".join([nota.tarefa, nota.epico, *nota.etiquetas])
        con.execute(
            "INSERT INTO notas_fts(id, titulo, corpo, projeto, chaves, ficheiros) VALUES(?,?,?,?,?,?)",
            (nota.id, nota.titulo, nota.corpo, f"{nota.projeto} {store.pasta_projeto(nota.projeto)}", chaves, " ".join(nota.ficheiros)),
        )

    def _refazer_arestas(self, con: sqlite3.Connection) -> None:
        notas = con.execute("SELECT id, titulo, projeto, tarefa, epico, data, ficheiros, ligacoes FROM notas ORDER BY data").fetchall()

        def ambito(projeto: str, chave: str) -> tuple[str, str]:
            return ("", chave) if store.chave_global(chave) else (projeto, chave)

        # Épico de cada tarefa (a nota mais recente que o indica ganha) e o conjunto dos épicos.
        epico_da_tarefa: dict[tuple[str, str], str] = {}
        epicos: set[tuple[str, str]] = set()
        for n in notas:
            if n["epico"]:
                epicos.add(ambito(n["projeto"], n["epico"]))
                if n["tarefa"]:
                    epico_da_tarefa[ambito(n["projeto"], n["tarefa"])] = n["epico"]

        def no_chave(projeto: str, chave: str) -> str:
            tipo = "epico" if ambito(projeto, chave) in epicos else "tarefa"
            return id_chave(tipo, projeto, chave)

        resolver = _Resolvedor(notas)
        arestas: dict[tuple[str, str, str], float] = {}
        contexto: dict[str, tuple[str, str, str, str]] = {}
        efetivos: list[tuple[str, str]] = []
        for n in notas:
            nid, projeto = n["id"], n["projeto"]
            pid = id_projeto(projeto)
            contexto[pid] = ("projeto", projeto, projeto, "")
            arestas[(nid, pid, "projeto")] = PESOS["projeto"]
            epico = n["epico"] or (epico_da_tarefa.get(ambito(projeto, n["tarefa"]), "") if n["tarefa"] else "")
            if epico == n["tarefa"]:
                epico = ""
            efetivos.append((epico, nid))
            if n["tarefa"]:
                tid = no_chave(projeto, n["tarefa"])
                contexto.setdefault(tid, (tid.split(":", 1)[0], n["tarefa"], projeto, n["tarefa"]))
                arestas[(nid, tid, "tarefa")] = PESOS["tarefa"]
            if epico:
                eid = id_chave("epico", projeto, epico)
                contexto.setdefault(eid, ("epico", epico, projeto, epico))
                arestas[(nid, eid, "epico")] = PESOS["epico"]
                if n["tarefa"]:
                    arestas[(no_chave(projeto, n["tarefa"]), eid, "subtarefa")] = 0.0
            for f in json.loads(n["ficheiros"]):
                fid = id_ficheiro(projeto, f)
                contexto.setdefault(fid, ("ficheiro", fid.split(":", 2)[-1], projeto, ""))
                arestas[(nid, fid, "ficheiro")] = PESOS["ficheiro"]
            for alvo in json.loads(n["ligacoes"]):
                destino = resolver.resolver(alvo, projeto)
                if destino and destino != nid:
                    a, b = sorted((nid, destino))  # ligação explícita é simétrica
                    arestas[(a, b, "ligacao")] = PESOS["ligacao"]
        con.executemany("UPDATE notas SET epico_efetivo=? WHERE id=?", efetivos)
        con.execute("DELETE FROM contexto")
        con.executemany("INSERT INTO contexto VALUES(?,?,?,?,?)", [(k, *v) for k, v in contexto.items()])
        con.execute("DELETE FROM arestas")
        con.executemany("INSERT INTO arestas VALUES(?,?,?,?)", [(o, d, t, p) for (o, d, t), p in arestas.items()])

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
            notas = con.execute("SELECT id, titulo, projeto FROM notas").fetchall()
        return _Resolvedor(notas).resolver(ref, None)

    @staticmethod
    def _filtros(projeto, tipo, tarefa, epico) -> tuple[list[str], list]:
        filtros, args = [], []
        if projeto:
            filtros.append("(n.projeto = ? COLLATE NOCASE OR n.id LIKE ? ESCAPE '\\')")
            pasta = store.pasta_projeto(projeto).replace("_", "\\_").replace("%", "\\%")
            args += [projeto, f"{pasta}/%"]
        if tipo:
            filtros.append("n.tipo = ?")
            args.append(store.normalizar_tipo(tipo))
        if tarefa:
            filtros.append("n.tarefa = ? COLLATE NOCASE")
            args.append(store.normalizar_chave(tarefa))
        if epico:
            e = store.normalizar_chave(epico)
            filtros.append("(n.epico_efetivo = ? COLLATE NOCASE OR n.tarefa = ? COLLATE NOCASE)")
            args += [e, e]
        return filtros, args

    def procurar(
        self,
        texto: str,
        projeto: str | None = None,
        tipo: str | None = None,
        limite: int = 10,
        tarefa: str | None = None,
        epico: str | None = None,
    ) -> list[dict]:
        limite = max(1, min(int(limite or 10), 500))
        filtros, args = self._filtros(projeto, tipo, tarefa, epico)
        e_filtros = (" AND " + " AND ".join(filtros)) if filtros else ""
        consulta = _consulta_fts(texto or "")
        chaves = chaves_no_texto(texto or "")
        pontos: dict[str, float] = {}
        excertos: dict[str, str] = {}
        with self.ligar() as con:
            # 1) Chaves de tickets: a tarefa, o épico e o resto do épico.
            for chave in chaves:
                for sql, valor in (
                    ("n.tarefa = ? COLLATE NOCASE", PONTOS_CHAVE["tarefa"]),
                    ("n.epico_efetivo = ? COLLATE NOCASE", PONTOS_CHAVE["epico"]),
                ):
                    for (nid,) in con.execute(f"SELECT n.id FROM notas n WHERE {sql}{e_filtros}", [chave, *args]):
                        pontos[nid] = max(pontos.get(nid, 0.0), valor)
                epicos_da_chave = [
                    r[0]
                    for r in con.execute(
                        "SELECT DISTINCT epico_efetivo FROM notas WHERE tarefa = ? COLLATE NOCASE AND epico_efetivo != ''",
                        (chave,),
                    )
                ]
                for e in epicos_da_chave:
                    for (nid,) in con.execute(
                        f"SELECT n.id FROM notas n WHERE (n.tarefa = ? COLLATE NOCASE OR n.epico_efetivo = ? COLLATE NOCASE){e_filtros}",
                        [e, e, *args],
                    ):
                        pontos[nid] = max(pontos.get(nid, 0.0), PONTOS_CHAVE["mesmo_epico"])
            # 2) Texto (FTS5).
            if consulta:
                for r in con.execute(
                    f"""SELECT n.id, bm25(notas_fts, {_PESOS_BM25}) AS rank,
                               snippet(notas_fts, 2, '«', '»', '…', 16) AS excerto
                        FROM notas_fts JOIN notas n ON n.id = notas_fts.id
                        WHERE notas_fts MATCH ?{e_filtros} ORDER BY rank LIMIT ?""",
                    [consulta, *args, max(limite, 200)],
                ):
                    pontos[r["id"]] = pontos.get(r["id"], 0.0) + max(0.0, -r["rank"])
                    excertos[r["id"]] = r["excerto"]
            elif not chaves:
                for (nid,) in con.execute(
                    f"SELECT n.id FROM notas n WHERE 1=1{e_filtros} ORDER BY n.data DESC LIMIT ?", [*args, limite]
                ):
                    pontos[nid] = 0.0
            linhas = self._linhas(con, list(pontos))
            corpos = self._corpos(con, [i for i in pontos if i not in excertos])
        # Bónus pelo nome da memória: desempata quando o BM25 não distingue
        # (poucas notas, ou todas com as mesmas palavras no projeto).
        palavras = [p for p in re.findall(r"\w+", _normal(_CHAVE_NO_TEXTO.sub(" ", texto or ""))) if len(p) > 1]
        palavras = [p for p in palavras if p not in _PALAVRAS_VAZIAS] or palavras
        if palavras:
            for nid, r in linhas.items():
                titulo = _normal(r["titulo"])
                pontos[nid] += sum(1.0 for p in palavras if p in titulo)
        resultado = []
        for nid, valor in pontos.items():
            if nid not in linhas:
                continue
            excerto = excertos.get(nid) or corpos.get(nid, "")[:160]
            resultado.append({**_linha_resumo(linhas[nid]), "excerto": " ".join(excerto.split()), "pontuacao": round(valor, 4)})
        resultado.sort(key=lambda x: x["data"], reverse=True)
        resultado.sort(key=lambda x: -x["pontuacao"])
        return resultado[:limite]

    def procurar_agrupado(self, texto: str, limite: int = 8) -> dict:
        """Pesquisa para a UI: memórias, projetos e tarefas/épicos, mais os nós a destacar."""
        texto = (texto or "").strip()
        if not texto:
            return {"memorias": [], "projetos": [], "chaves": [], "ids": [], "nos": []}
        memorias = self.procurar(texto, limite=200)
        alvo = _normal(texto)
        alvo_slug = store.slug(texto) if re.search(r"\w", texto) else ""
        chaves_texto = set(chaves_no_texto(texto))
        with self.ligar() as con:
            projetos = []
            for r in con.execute("SELECT projeto, count(*) AS total FROM notas GROUP BY projeto ORDER BY projeto"):
                if alvo in _normal(r["projeto"]) or (alvo_slug and alvo_slug in store.pasta_projeto(r["projeto"])):
                    projetos.append({"id": id_projeto(r["projeto"]), "nome": r["projeto"], "total": r["total"]})
            epicos_ligados = {
                r[0].lower()
                for chave in chaves_texto
                for r in con.execute(
                    "SELECT DISTINCT epico_efetivo FROM notas WHERE tarefa = ? COLLATE NOCASE AND epico_efetivo != ''", (chave,)
                )
            }
            chaves = []
            for r in con.execute(
                """SELECT c.id, c.tipo, c.chave, c.projeto, count(a.origem) AS total
                   FROM contexto c LEFT JOIN arestas a ON a.destino = c.id AND a.tipo IN ('tarefa', 'epico')
                   WHERE c.tipo IN ('tarefa', 'epico') GROUP BY c.id ORDER BY c.tipo, c.chave"""
            ):
                if alvo in r["chave"].lower() or r["chave"].lower() in epicos_ligados:
                    chaves.append({"id": r["id"], "tipo": r["tipo"], "chave": r["chave"], "projeto": r["projeto"], "total": r["total"]})
            ids = {m["id"] for m in memorias}
            for p in projetos:
                ids |= {row[0] for row in con.execute("SELECT origem FROM arestas WHERE destino=? AND tipo='projeto'", (p["id"],))}
            for c in chaves:
                ids |= {
                    row[0] for row in con.execute("SELECT origem FROM arestas WHERE destino=? AND tipo IN ('tarefa','epico')", (c["id"],))
                }
        # Memórias cujo nome contém o texto aparecem primeiro na lista.
        memorias.sort(key=lambda m: 0 if alvo in _normal(m["titulo"]) else 1)
        campos = ("id", "titulo", "projeto", "tipo", "tarefa")
        resumo = [{k: m[k] for k in campos} for m in memorias]
        return {
            "memorias": resumo[:limite],
            "total_memorias": len(memorias),
            "projetos": projetos[:limite],
            "chaves": chaves[:limite],
            "ids": sorted(ids),
            "nos": [p["id"] for p in projetos] + [c["id"] for c in chaves],
        }

    @staticmethod
    def _linhas(con: sqlite3.Connection, ids: list[str]) -> dict[str, sqlite3.Row]:
        linhas = {}
        for i in range(0, len(ids), 500):
            bloco = ids[i : i + 500]
            for r in con.execute(f"SELECT * FROM notas WHERE id IN ({','.join('?' * len(bloco))})", bloco):
                linhas[r["id"]] = r
        return linhas

    @staticmethod
    def _corpos(con: sqlite3.Connection, ids: list[str]) -> dict[str, str]:
        corpos = {}
        for i in range(0, len(ids), 500):
            bloco = ids[i : i + 500]
            for r in con.execute(f"SELECT id, corpo FROM notas_fts WHERE id IN ({','.join('?' * len(bloco))})", bloco):
                corpos[r["id"]] = r["corpo"]
        return corpos

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
                "SELECT destino, tipo FROM arestas WHERE origem=? AND tipo NOT IN ('ligacao', 'subtarefa')", (nid,)
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

            def somar(outro: str, motivo: str) -> None:
                p = pontos.setdefault(outro, {"forca": 0.0, "motivos": {}, "ficheiros": 0.0, "contextos": set()})
                if motivo == "ficheiro":
                    p["ficheiros"] = min(MAX_FICHEIROS, p["ficheiros"] + PESOS[motivo])
                else:
                    p["forca"] += PESOS[motivo]
                p["motivos"][motivo] = p["motivos"].get(motivo, 0) + 1

            for outro in explicitas:
                somar(outro, "ligacao")
            # Tarefa e épico partilham o nó de uma chave: o motivo é o mais fraco dos dois lados
            # (a minha tarefa ABC-100 é o épico da outra nota → "mesmo épico").
            vistos: dict[str, dict[str, str]] = {}
            for contexto, meu in minhas:
                for outro, deles in con.execute(
                    "SELECT origem, tipo FROM arestas WHERE destino=? AND origem != ? AND tipo != 'subtarefa'", (contexto, nid)
                ):
                    motivo = meu if PESOS[meu] <= PESOS[deles] else deles
                    anterior = vistos.setdefault(outro, {})
                    # Um par conta cada motivo uma vez, exceto ficheiros (somam até ao teto).
                    if motivo != "ficheiro" and motivo in anterior.values():
                        continue
                    anterior[contexto] = motivo
                    somar(outro, motivo)
            linhas = self._linhas(con, list(pontos))
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
            notas = con.execute("SELECT id, tipo, titulo, projeto, tarefa, epico_efetivo, data FROM notas").fetchall()
            contexto = con.execute("SELECT * FROM contexto").fetchall()
            arestas = con.execute("SELECT origem, destino, tipo FROM arestas").fetchall()
        nos: dict[str, dict] = {}
        for n in notas:
            nos[n["id"]] = {
                "id": n["id"],
                "tipo": n["tipo"],
                "rotulo": n["titulo"],
                "projeto": n["projeto"],
                "tarefa": n["tarefa"],
                "epico": n["epico_efetivo"],
                "data": n["data"],
                "grau": 0,
            }
        for c in contexto:
            nos[c["id"]] = {
                "id": c["id"],
                "tipo": c["tipo"],
                "rotulo": c["rotulo"],
                "projeto": c["projeto"],
                "tarefa": c["chave"] if c["tipo"] == "tarefa" else "",
                "epico": c["chave"] if c["tipo"] == "epico" else (_epico_de(notas, c["chave"]) if c["tipo"] == "tarefa" else ""),
                "data": "",
                "grau": 0,
            }
        links = []
        for a in arestas:
            origem, destino, tipo = a["origem"], a["destino"], a["tipo"]
            if origem not in nos or destino not in nos:
                continue
            data = nos[origem]["data"]
            if data and nos[destino]["tipo"] in store.TIPOS_CONTEXTO:
                atual = nos[destino]["data"]
                nos[destino]["data"] = min(atual, data) if atual else data
            nos[origem]["grau"] += 1
            nos[destino]["grau"] += 1
            links.append({"source": origem, "target": destino, "tipo": tipo})
        # Nós ainda sem data (ex.: um épico só com subtarefas) herdam a data mais antiga das origens.
        origens: dict[str, list[str]] = {}
        for lig in links:
            origens.setdefault(lig["target"], []).append(lig["source"])
        for n in nos.values():
            if not n["data"]:
                n["data"] = min((nos[o]["data"] for o in origens.get(n["id"], []) if nos[o]["data"]), default="")
        epicos = sorted({c["chave"] for c in contexto if c["tipo"] == "epico"})
        tarefas = sorted({n["tarefa"] for n in notas if n["tarefa"]})
        return {
            "nos": list(nos.values()),
            "ligacoes": links,
            "projetos": sorted({n["projeto"] for n in notas}),
            "epicos": epicos,
            "tarefas": [{"chave": t, "epico": _epico_de(notas, t)} for t in tarefas],
            "total": len(notas),
        }

    def ids(self) -> Iterable[str]:
        with self.ligar() as con:
            return [r[0] for r in con.execute("SELECT id FROM notas ORDER BY data")]


def _epico_de(notas: list[sqlite3.Row], tarefa: str) -> str:
    for n in notas:
        if n["tarefa"] == tarefa and n["epico_efetivo"]:
            return n["epico_efetivo"]
    return ""


def _linha_resumo(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "caminho": r["caminho"],
        "tipo": r["tipo"],
        "titulo": r["titulo"],
        "projeto": r["projeto"],
        "tarefa": r["tarefa"],
        "epico": r["epico_efetivo"],
        "url": r["url"],
        "etiquetas": json.loads(r["etiquetas"]),
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
