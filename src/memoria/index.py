"""Índice SQLite: pesquisa FTS5 e arestas do grafo.

O índice é descartável: `agent-memory reindex` reconstrói-o a partir dos Markdown.
Fica em <pasta dos dados>/.index/index-v<N>.sqlite (até à v0.4: .indice/memoria-v<N>.sqlite).
Cada versão do esquema usa o seu ficheiro, para uma versão antiga ainda aberta
(ex.: um `memoria mcp` do Claude Code) não estragar a nova.

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
import math
import re
import sqlite3
import sys
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Protocol

from memoria import config, store
from memoria.i18n import t

# v3: palavras com sinais combinantes (hindi) e uma coluna para o japonês e o chinês (ver _TOKENIZER).
VERSAO_ESQUEMA = 3
NOME_FICHEIRO = f"index-v{VERSAO_ESQUEMA}.sqlite"

# Espera por um lock de outro processo (segundos). As sincronizações de rotina esperam pouco:
# se outro processo está a escrever, a nota nova entra na sincronização seguinte.
ESPERA = 15.0
ESPERA_CURTA = 3.0
# O snippet() do FTS5 cresce com o quadrado das ocorrências numa nota: um log colado
# (dezenas de MB) prendia a pesquisa durante horas. Acima disto, o excerto é o início da nota.
LIMITE_EXCERTO = 32_000  # bytes do ficheiro
# O índice guarda (e pesquisa) só o início de uma nota enorme. O editor também recusa mais do que isto.
LIMITE_CORPO = store.TAMANHO_MAXIMO  # caracteres
# Uma pesquisa é uma frase, não um documento: o resto do texto não conta.
LIMITE_CONSULTA = 4000  # caracteres

PESOS = {"ligacao": 8.0, "tarefa": 4.0, "epico": 2.0, "projeto": 1.0, "ficheiro": 0.25}
MAX_FICHEIROS = 0.5  # teto da contribuição dos ficheiros partilhados
# Pontuação da pesquisa por chave de ticket (acima de qualquer pontuação FTS).
PONTOS_CHAVE = {"tarefa": 1000.0, "epico": 900.0, "mesmo_epico": 700.0}

_PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "em", "no", "na", "um", "uma", "para", "com", "por", "que"}
_CHAVE_NO_TEXTO = re.compile(r"(?<![\w/#-])([A-Za-z][A-Za-z0-9_]*-\d+|[\w.-]+/[\w.-]+#\d+)(?![\w-])")


class FTS5Indisponivel(RuntimeError):
    pass


def _codigo(erro: BaseException) -> int | None:
    codigo = getattr(erro, "sqlite_errorcode", None)
    return codigo & 0xFF if isinstance(codigo, int) else None


def indice_estragado(erro: BaseException) -> bool:
    """O ficheiro do índice está corrompido (SQLITE_CORRUPT, SQLITE_NOTADB). Nunca: lock, disco cheio, I/O."""
    if not isinstance(erro, sqlite3.DatabaseError):
        return False
    codigo = _codigo(erro)
    if codigo is not None:
        return codigo in (11, 26)
    texto = str(erro).lower()
    return "not a database" in texto or "malformed" in texto


def indice_ocupado(erro: BaseException) -> bool:
    """Outro processo tem o índice preso (SQLITE_BUSY, SQLITE_LOCKED)."""
    if not isinstance(erro, sqlite3.OperationalError):
        return False
    codigo = _codigo(erro)
    if codigo is not None:
        return codigo in (5, 6)
    texto = str(erro).lower()
    return "locked" in texto or "busy" in texto


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
            con.execute(f"CREATE VIRTUAL TABLE t USING fts5(x, tokenize={_TOKENIZER})")
        finally:
            con.close()
    except sqlite3.Error as erro:
        raise FTS5Indisponivel(t("erro.fts5", versao=sqlite3.sqlite_version, erro=erro)) from erro
    _FTS5_OK = True


# unicode61 corta as palavras nos sinais combinantes (categoria M): em hindi, "कैश" virava "क" e "श".
# Com M* nas categorias, os sinais ficam dentro da palavra (e remove_diacritics continua a tirar os acentos).
_TOKENIZER = "\"unicode61 remove_diacritics 2 categories 'L* N* Co M*'\""

# Japonês e chinês não separam as palavras: o unicode61 faz de uma frase inteira uma "palavra",
# e "キャッシュ" só se encontrava no início da frase. A coluna cjk guarda estes carateres um a um
# (procurados como frase, ou seja, como texto seguido). Entre dois trechos vai um separador que
# nenhuma pesquisa usa (uso privado), para uma frase não juntar o fim de um trecho ao início de outro.
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]+")
_SEPARADOR_CJK = "\ue000"

_TABELAS = {"meta", "notas", "notas_fts", "contexto", "arestas"}

_ESQUEMA = tuple(
    instrucao.strip()
    for instrucao in f"""
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
    id UNINDEXED, titulo, corpo, projeto, chaves, ficheiros, cjk,
    tokenize={_TOKENIZER}
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
""".split(";")
    if instrucao.strip()
)
_APAGAR = tuple(f"DROP TABLE IF EXISTS {tabela}" for tabela in ("notas_fts", "notas", "contexto", "arestas", "meta"))

# bm25: id, titulo, corpo, projeto, chaves, ficheiros, cjk
_PESOS_BM25 = "0, 8.0, 1.0, 3.0, 6.0, 1.0, 4.0"


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


def _palavras(texto: str) -> list[str]:
    """As palavras do texto: letras, números, _ e os sinais combinantes (o \\w do Python corta o hindi neles)."""
    return "".join(c if c == "_" or unicodedata.category(c)[0] in "LNM" else " " for c in texto).split()


def _cjk(texto: str) -> str:
    """Os carateres japoneses e chineses, um a um (ver _CJK)."""
    return f" {_SEPARADOR_CJK} ".join(" ".join(trecho) for trecho in _CJK.findall(texto or ""))


def _texto_fts(texto: str) -> str:
    # NFC: a mesma palavra escrita com ou sem carateres decompostos (macOS, hindi) dá os mesmos tokens.
    return unicodedata.normalize("NFC", texto or "")


def _consulta_fts(texto: str) -> str:
    """Chaves (ABC-123) viram frases exatas; as outras palavras, prefixos em OR."""
    texto = _texto_fts(texto)[:LIMITE_CONSULTA]
    partes = []
    for chave in chaves_no_texto(texto):
        termos = _palavras(chave)
        if termos:
            partes.append('"' + " ".join(termos) + '"')
    resto = _CHAVE_NO_TEXTO.sub(" ", texto)
    palavras = _palavras(resto)
    # Uma letra sozinha não conta, exceto em japonês e chinês (猫 é uma palavra).
    validas = [p for p in palavras if len(p) > 1 or _CJK.fullmatch(p)]
    uteis = [p for p in validas if p.lower() not in _PALAVRAS_VAZIAS] or validas
    uteis = list(dict.fromkeys(p.lower() for p in uteis))[:32]  # repetidas não contam (o snippet() pagava por cada uma)
    partes += [f'"{p}"*' for p in uteis]
    partes += [f'cjk : "{_cjk(p)}"' for p in uteis if _CJK.search(p)]
    return " OR ".join(partes)


def _normal(texto: str) -> str:
    return store.sem_acentos(str(texto or "")).lower().strip()


class Indice:
    def __init__(self, home: Path, caminho: Path | None = None, embeddings: Embeddings | None = None):
        self.home = Path(home)
        self.caminho = Path(caminho) if caminho else config.pasta_interna(self.home) / NOME_FICHEIRO
        self.embeddings = embeddings  # sempre None

    # ---------------------------------------------------------------- ligação
    @contextmanager
    def ligar(self, espera: float | None = None):
        """Uma ligação ao índice; grava no fim. `espera`: segundos à espera de um lock de outro processo."""
        verificar_fts5()
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        con = self._abrir(ESPERA if espera is None else espera)
        try:
            yield con
            con.commit()
        except BaseException:
            try:
                con.rollback()
            except sqlite3.Error:
                pass  # ficheiro estragado: o erro que interessa é o de cima
            raise
        finally:
            con.close()

    def _abrir(self, espera: float) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho, timeout=espera)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute(f"PRAGMA busy_timeout={int(espera * 1000)}")
            tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            versao = con.execute("SELECT valor FROM meta WHERE chave='versao_esquema'").fetchone() if "meta" in tabelas else None
            if versao and versao[0] != str(VERSAO_ESQUEMA):
                self._apagar_tabelas(con)
                versao = None
            # Só cria o esquema se faltar: o INSERT do esquema precisa do lock de escrita, e uma pesquisa
            # ficava à espera (15 s) de quem estivesse a escrever noutro processo.
            if not versao or not _TABELAS <= tabelas:
                self._criar_esquema(con)
                con.commit()
        except BaseException:
            con.close()
            raise
        return con

    @staticmethod
    def _criar_esquema(con: sqlite3.Connection) -> None:
        # execute() e não executescript(): este faz COMMIT antes, e o reindex corre numa só transação.
        for instrucao in _ESQUEMA:
            con.execute(instrucao)

    @staticmethod
    def _apagar_tabelas(con: sqlite3.Connection) -> None:
        for instrucao in _APAGAR:
            con.execute(instrucao)

    def _tirar_ficheiros(self) -> bool:
        """Tira de cena um índice estragado: o ficheiro fica ao lado (.corrupt) e os -wal/-shm saem.

        Devolve False se não deu (no Windows, outro processo ainda o tem aberto). As notas não mudam.
        """
        estragado = self.caminho.with_name(self.caminho.name + ".corrupt")
        for f in (self.caminho.with_name(self.caminho.name + "-wal"), self.caminho.with_name(self.caminho.name + "-shm"), self.caminho):
            try:
                if f == self.caminho:
                    f.replace(estragado)
                else:
                    f.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                try:
                    f.unlink()
                except OSError:
                    pass
        # Um -wal antigo ao lado de um ficheiro novo seria aplicado a esse ficheiro: tem de sair tudo.
        return not any(f.exists() for f in (self.caminho, self.caminho.with_name(self.caminho.name + "-wal")))

    def _apagar_indices_antigos(self) -> None:
        """Índices de esquemas anteriores e os da pasta .indice (até à v0.4). Melhor esforço.

        Só apaga ficheiros do índice (descartáveis): nunca as notas nem o registo MCP.
        """
        pasta = self.caminho.parent
        antiga = self.home / config.PASTA_INTERNA_ANTIGA
        candidatos = [*pasta.glob("index-v*.sqlite*"), *pasta.glob("memoria.sqlite*"), *pasta.glob("memoria-v*.sqlite*")]
        if antiga != pasta:
            candidatos += [*antiga.glob("memoria.sqlite*"), *antiga.glob("memoria-v*.sqlite*")]
        for f in candidatos:
            if f.parent != pasta or not f.name.startswith(self.caminho.name):
                try:
                    f.unlink()
                except OSError:
                    pass  # no Windows, um processo antigo ainda o pode ter aberto

    # ---------------------------------------------------------- sincronizar
    def reindexar(self, estragado: bool = False) -> dict:
        """Reconstrói tudo a partir dos Markdown.

        Numa só transação: durante o reindex, os outros processos continuam a ver o índice anterior.
        Um índice estragado (ou `estragado=True`) é posto de lado e refeito num ficheiro novo.
        """
        if estragado and self._tirar_ficheiros():
            estado = self.sincronizar()
        else:
            try:
                estado = self.sincronizar(do_zero=True)
            except sqlite3.DatabaseError as erro:
                if not indice_estragado(erro) or not self._tirar_ficheiros():
                    raise
                estado = self.sincronizar()
        self._apagar_indices_antigos()
        return estado

    def sincronizar(self, espera: float | None = None, do_zero: bool = False) -> dict:
        """Atualiza só o que mudou no disco (mtime/tamanho) e refaz as arestas. `do_zero`: refaz tudo."""
        inicio = time.perf_counter()
        erros: list[str] = []
        problemas: list[tuple[Path, str]] = []
        ficheiros = list(store.listar_ficheiros(self.home, problemas))
        ilegiveis = [caminho for caminho, motivo in problemas if motivo == "pasta_ilegivel"]
        if self.home in ilegiveis:
            do_zero = False  # sem ler a pasta dos dados, refazer tudo seria apagar o índice inteiro
        with self.ligar(espera) as con:
            if do_zero:
                con.execute("BEGIN IMMEDIATE")
                guardadas = self._linhas_das_pastas(con, ilegiveis)
                self._apagar_tabelas(con)
                self._criar_esquema(con)
                self._repor_linhas(con, guardadas)
            conhecidas = {r["id"]: (r["mtime_ns"], r["tamanho"]) for r in con.execute("SELECT id, mtime_ns, tamanho FROM notas")}
            vistas: set[str] = set()
            alteradas = 0
            for ficheiro in ficheiros:
                try:
                    st = ficheiro.stat()
                except OSError:
                    continue
                try:
                    nid = store.id_de(ficheiro, self.home)
                except ValueError:  # ligação simbólica para fora da pasta (ex.: Dropbox, OneDrive)
                    erros.append(f"{ficheiro}: {t('aviso.fora_da_pasta')}")
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
            for caminho, motivo in problemas:
                aviso = t("aviso.pasta_ilegivel") if motivo == "pasta_ilegivel" else t("aviso.fora_de_projeto")
                erros.append(f"{caminho}: {aviso}")
                if motivo == "pasta_ilegivel":
                    # Sem permissão para ler a pasta: as memórias dela ficam como estavam (não foram apagadas).
                    if caminho == self.home:
                        vistas |= set(conhecidas)
                    else:
                        prefixo = unicodedata.normalize("NFC", caminho.name) + "/"
                        vistas |= {i for i in conhecidas if i.startswith(prefixo)}
            removidas = set(conhecidas) - vistas
            for nid in removidas:
                con.execute("DELETE FROM notas WHERE id=?", (nid,))
                con.execute("DELETE FROM notas_fts WHERE id=?", (nid,))
            if alteradas or removidas or not conhecidas:
                self._refazer_arestas(con)
            total = con.execute("SELECT count(*) FROM notas").fetchone()[0]
        for erro in erros:
            print(t("aviso.memoria_ignorada", erro=erro), file=sys.stderr)
        return {
            "total": total,
            "alteradas": alteradas,
            "removidas": len(removidas),
            "erros": len(erros),
            "segundos": round(time.perf_counter() - inicio, 3),
        }

    @staticmethod
    def _linhas_das_pastas(con: sqlite3.Connection, pastas: list[Path]) -> tuple[list, list]:
        """As linhas do índice das notas destas pastas (sem permissão de leitura): o reindex mantém-nas."""
        notas: list = []
        fts: list = []
        for pasta in pastas:
            prefixo = unicodedata.normalize("NFC", pasta.name).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "/%"
            notas += [tuple(r) for r in con.execute("SELECT * FROM notas WHERE id LIKE ? ESCAPE '\\'", (prefixo,))]
            fts += [
                tuple(r)
                for r in con.execute(
                    "SELECT id, titulo, corpo, projeto, chaves, ficheiros, cjk FROM notas_fts WHERE id LIKE ? ESCAPE '\\'", (prefixo,)
                )
            ]
        return notas, fts

    @staticmethod
    def _repor_linhas(con: sqlite3.Connection, guardadas: tuple[list, list]) -> None:
        notas, fts = guardadas
        if notas:
            con.executemany(f"INSERT INTO notas VALUES({','.join('?' * len(notas[0]))})", notas)
        if fts:
            con.executemany("INSERT INTO notas_fts(id, titulo, corpo, projeto, chaves, ficheiros, cjk) VALUES(?,?,?,?,?,?,?)", fts)

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
        titulo = _texto_fts(nota.titulo)
        corpo = _texto_fts(nota.corpo)
        if len(corpo) > LIMITE_CORPO:  # um log colado numa nota: o índice guarda só o início
            corpo = corpo[:LIMITE_CORPO] + "\n\n…"
        con.execute(
            "INSERT INTO notas_fts(id, titulo, corpo, projeto, chaves, ficheiros, cjk) VALUES(?,?,?,?,?,?,?)",
            (
                nota.id,
                titulo,
                corpo,
                _texto_fts(f"{nota.projeto} {store.pasta_projeto(nota.projeto)}"),
                _texto_fts(chaves),
                _texto_fts(" ".join(nota.ficheiros)),
                _cjk(f"{titulo}\n{corpo}"),
            ),
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
        excertos: bool = True,
    ) -> list[dict]:
        """`excertos=False` não calcula os excertos (a UI não os mostra)."""
        limite = max(1, min(int(limite or 10), 500))
        filtros, args = self._filtros(projeto, tipo, tarefa, epico)
        e_filtros = (" AND " + " AND ".join(filtros)) if filtros else ""
        texto = _texto_fts(texto)[:LIMITE_CONSULTA]
        consulta = _consulta_fts(texto)
        chaves = chaves_no_texto(texto)
        pontos: dict[str, float] = {}
        com_fts: set[str] = set()
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
            # 2) Texto (FTS5). Só o bm25 aqui: o snippet() é caro e só se faz para os resultados finais.
            if consulta:
                for r in con.execute(
                    f"""SELECT n.id, bm25(notas_fts, {_PESOS_BM25}) AS rank
                        FROM notas_fts JOIN notas n ON n.id = notas_fts.id
                        WHERE notas_fts MATCH ?{e_filtros} ORDER BY rank LIMIT ?""",
                    [consulta, *args, max(limite, 200)],
                ):
                    pontos[r["id"]] = pontos.get(r["id"], 0.0) + max(0.0, -r["rank"])
                    com_fts.add(r["id"])
            elif not chaves:
                for (nid,) in con.execute(
                    f"SELECT n.id FROM notas n WHERE 1=1{e_filtros} ORDER BY n.data DESC LIMIT ?", [*args, limite]
                ):
                    pontos[nid] = 0.0
            linhas = self._linhas(con, list(pontos))
            # Bónus pelo nome da memória: desempata quando o BM25 não distingue
            # (poucas notas, ou todas com as mesmas palavras no projeto).
            palavras = [p for p in _palavras(_normal(_CHAVE_NO_TEXTO.sub(" ", texto))) if len(p) > 1 or _CJK.fullmatch(p)]
            palavras = list(dict.fromkeys(p for p in palavras if p not in _PALAVRAS_VAZIAS)) or palavras
            if palavras:
                for nid, r in linhas.items():
                    titulo = _normal(r["titulo"])
                    pontos[nid] += sum(1.0 for p in palavras if p in titulo)
            finais = [nid for nid in pontos if nid in linhas]
            finais.sort(key=lambda nid: linhas[nid]["data"], reverse=True)
            finais.sort(key=lambda nid: -pontos[nid])
            finais = finais[:limite]
            excerto_de: dict[str, str] = {}
            if excertos:
                excerto_de = self._excertos(con, consulta, [i for i in finais if i in com_fts])
                excerto_de.update(self._corpos(con, [i for i in finais if not excerto_de.get(i)], 160))
        resultado = []
        for nid in finais:
            excerto = excerto_de.get(nid) or ""
            resultado.append({**_linha_resumo(linhas[nid]), "excerto": " ".join(excerto.split()), "pontuacao": round(pontos[nid], 4)})
        return resultado

    @staticmethod
    def _excertos(con: sqlite3.Connection, consulta: str, ids: list[str]) -> dict[str, str]:
        """O excerto à volta das palavras encontradas, só para estas notas (e só para as que não são enormes)."""
        excertos: dict[str, str] = {}
        if not consulta or not ids:
            return excertos
        for r in con.execute(
            f"""SELECT notas_fts.id AS id,
                       CASE WHEN n.tamanho <= ? THEN snippet(notas_fts, 2, '«', '»', '…', 16) END AS excerto
                FROM notas_fts JOIN notas n ON n.id = notas_fts.id
                WHERE notas_fts MATCH ? AND notas_fts.id IN ({','.join('?' * len(ids))})""",
            [LIMITE_EXCERTO, consulta, *ids],
        ):
            if r["excerto"]:
                excertos[r["id"]] = r["excerto"]
        return excertos

    def procurar_agrupado(self, texto: str, limite: int = 8) -> dict:
        """Pesquisa para a UI: memórias, projetos e tarefas/épicos, mais os nós a destacar."""
        texto = _texto_fts(texto).strip()[:LIMITE_CONSULTA]
        if not texto:
            return {"memorias": [], "projetos": [], "chaves": [], "ids": [], "nos": []}
        memorias = self.procurar(texto, limite=200, excertos=False)
        alvo = _normal(texto)
        alvo_slug = _slug_real(texto) or ""
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
    def _corpos(con: sqlite3.Connection, ids: list[str], maximo: int) -> dict[str, str]:
        """O início do corpo de cada nota (`maximo` carateres)."""
        corpos = {}
        for i in range(0, len(ids), 500):
            bloco = ids[i : i + 500]
            sql = f"SELECT id, substr(corpo, 1, ?) AS corpo FROM notas_fts WHERE id IN ({','.join('?' * len(bloco))})"
            for r in con.execute(sql, [maximo, *bloco]):
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
            raise LookupError(t("erro.memoria_nao_encontrada", ref=ref))
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
        # Infinity/NaN não são JSON: partiam o painel da UI (Response.json() recusa-os).
        "custo_usd": r["custo_usd"] if r["custo_usd"] is None or math.isfinite(r["custo_usd"]) else None,
        "ficheiros": json.loads(r["ficheiros"]),
        "ligacoes": json.loads(r["ligacoes"]),
    }


def _slug_real(texto: str) -> str | None:
    """O slug, ou None quando não sobra nada (títulos só em hindi, hebraico, '[[]]'...).

    store.slug() devolve então "note", e todas essas memórias tinham o mesmo nome.
    """
    return store.slug(texto) if re.search(r"[a-z0-9]", store.sem_acentos(str(texto or "")).lower()) else None


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
                unicodedata.normalize("NFC", n["titulo"]).strip().lower(),
                _slug_real(n["titulo"]),
                _slug_real(nome),
            }
            chaves.discard(None)
            chaves.discard("")
            for chave in chaves:
                self.por_nome.setdefault(chave, []).append((projeto, nid))

    def resolver(self, alvo: str, projeto: str | None) -> str | None:
        alvo = unicodedata.normalize("NFC", alvo.strip())
        if alvo.endswith(".md"):
            alvo = alvo[:-3]
        if alvo in self.ids:
            return alvo
        for chave in (alvo.lower(), _slug_real(alvo)):
            candidatos = self.por_nome.get(chave) if chave else None
            if candidatos:
                # Prefere o mesmo projeto; depois a mais recente (ids têm a data).
                mesmos = [c for c in candidatos if c[0] == projeto] or candidatos
                return sorted(mesmos, key=lambda c: c[1])[-1][1]
        return None
