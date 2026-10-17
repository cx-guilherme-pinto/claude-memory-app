"""Registo das chamadas MCP do Claude (para a vista "Atividade" da app).

Cada chamada a uma ferramenta MCP grava:
- a ferramenta, a hora, quanto demorou, os filtros (projeto, tipo, tarefa, épico) e o
  texto pesquisado, redigido (nunca segredos) e cortado;
- as memórias que devolveu (id, título, projeto, tarefa, épico), uma linha por memória.
  Uma chamada sem resultados deixa uma linha sem memória, para se ver o que não se encontrou.

Fica em <pasta dos dados>/.index/activity.sqlite, separado do índice: `agent-memory reindex`
não o apaga. É local, como tudo o resto. Tem limite: as linhas mais antigas saem,
mas o total de chamadas é um contador à parte e não se perde.
Até à v0.4 ficava em .indice/registo.sqlite: na primeira vez, a v0.5 copia-o (não o move).

As ferramentas gravam-se com os nomes novos (memory_search, memory_add, memory_related);
as linhas antigas (memoria_procurar, ...) aparecem com os nomes novos.

Gravar nunca pode partir uma ferramenta MCP: os erros vão para o stderr e mais nada.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from memoria import config
from memoria.index import indice_estragado
from memoria.redact import redigir

NOME_FICHEIRO = "activity.sqlite"
NOME_FICHEIRO_ANTIGO = "registo.sqlite"
# Nomes das ferramentas até à v0.4 -> os de agora.
FERRAMENTAS_ANTIGAS = {
    "memoria_procurar": "memory_search",
    "memoria_adicionar": "memory_add",
    "memoria_relacionadas": "memory_related",
}

MAX_CHAMADAS = 20_000
MAX_RECORDADAS = 10_000
MAX_TEXTO = 200
JANELA_POR_MINUTO = 10 * 60  # média das chamadas por minuto nos últimos 10 minutos

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS chamadas(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando REAL NOT NULL,
    ferramenta TEXT NOT NULL,
    texto TEXT NOT NULL DEFAULT '',
    projeto TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT '',
    tarefa TEXT NOT NULL DEFAULT '',
    epico TEXT NOT NULL DEFAULT '',
    resultados INTEGER NOT NULL DEFAULT 0,
    erro TEXT NOT NULL DEFAULT '',
    duracao_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS chamadas_quando ON chamadas(quando);
CREATE TABLE IF NOT EXISTS recordadas(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chamada INTEGER NOT NULL,
    quando REAL NOT NULL,
    ferramenta TEXT NOT NULL,
    texto TEXT NOT NULL DEFAULT '',
    memoria TEXT,
    titulo TEXT NOT NULL DEFAULT '',
    projeto TEXT NOT NULL DEFAULT '',
    tarefa TEXT NOT NULL DEFAULT '',
    epico TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS contadores(chave TEXT PRIMARY KEY, valor INTEGER NOT NULL);
"""


def _limpo(valor, maximo: int = MAX_TEXTO) -> str:
    texto = " ".join(str(valor or "").split())
    texto, _ = redigir(texto)
    return texto if len(texto) <= maximo else texto[: maximo - 1] + "…"


def ferramenta_atual(nome: str) -> str:
    return FERRAMENTAS_ANTIGAS.get(nome, nome)


class Registo:
    def __init__(self, home: Path, caminho: Path | None = None):
        self._antigo: Path | None = None
        if caminho:
            self.caminho = Path(caminho)
        else:
            self.caminho = config.pasta_interna(home) / NOME_FICHEIRO
            self._antigo = Path(home) / config.PASTA_INTERNA_ANTIGA / NOME_FICHEIRO_ANTIGO

    def _copiar_antigo(self) -> None:
        """Primeira vez na v0.5: copia o registo da v0.4 (a cópia do SQLite é segura com escritas a decorrer)."""
        antigo, self._antigo = self._antigo, None
        if not antigo or self.caminho.exists() or not antigo.is_file():
            return
        temporario = self.caminho.with_name(f".{self.caminho.name}.{os.getpid()}.copy")
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            # Ligação normal (não "ro"): ao fechar, o SQLite apaga os -wal/-shm que abriu e a pasta antiga fica como estava.
            origem = sqlite3.connect(antigo, timeout=5)
            try:
                destino = sqlite3.connect(temporario)
                try:
                    origem.backup(destino)
                finally:
                    destino.close()
            finally:
                origem.close()
            if not self.caminho.exists():
                temporario.replace(self.caminho)
        except (sqlite3.Error, OSError):
            pass  # sem histórico antigo: começa vazio
        finally:
            try:
                temporario.unlink()
            except OSError:
                pass

    def _abrir(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA busy_timeout=5000")
            con.executescript(_ESQUEMA)
        except BaseException:
            con.close()
            raise
        return con

    def _repor(self) -> None:
        """Registo estragado (ficheiro corrompido): começa de novo. É acessório; as notas não mudam."""
        for sufixo in ("-wal", "-shm", ""):
            try:
                self.caminho.with_name(self.caminho.name + sufixo).unlink()
            except OSError:
                pass

    @contextmanager
    def _ligar(self):
        if self._antigo:
            self._copiar_antigo()
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        try:
            con = self._abrir()
        except sqlite3.DatabaseError as erro:
            if not indice_estragado(erro):
                raise
            self._repor()
            con = self._abrir()
        estragado = False
        try:
            yield con
            con.commit()
        except BaseException as erro:
            estragado = indice_estragado(erro)
            raise
        finally:
            con.close()
            if estragado:
                self._repor()  # a próxima chamada já encontra um registo novo

    def gravar(
        self,
        ferramenta: str,
        *,
        texto: str = "",
        filtros: dict | None = None,
        memorias: list[dict] | None = None,
        erro: str = "",
        duracao_ms: int = 0,
        quando: float | None = None,
    ) -> None:
        """Grava uma chamada. Nunca lança exceções (o MCP tem de responder na mesma)."""
        try:
            quando = time.time() if quando is None else quando
            filtros = {k: _limpo(v, 120) for k, v in (filtros or {}).items() if v not in (None, "")}
            memorias = list(memorias or [])
            texto = _limpo(texto)
            with self._ligar() as con:
                cur = con.execute(
                    """INSERT INTO chamadas(quando, ferramenta, texto, projeto, tipo, tarefa, epico, resultados, erro, duracao_ms)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        quando,
                        ferramenta,
                        texto,
                        filtros.get("projeto", ""),
                        filtros.get("tipo", ""),
                        filtros.get("tarefa", ""),
                        filtros.get("epico", ""),
                        len(memorias),
                        _limpo(erro),
                        int(duracao_ms),
                    ),
                )
                chamada = cur.lastrowid
                linhas = [
                    (
                        chamada,
                        quando,
                        ferramenta,
                        texto,
                        str(m.get("id") or ""),
                        _limpo(m.get("titulo"), 160),
                        _limpo(m.get("projeto"), 120),
                        _limpo(m.get("tarefa"), 80),
                        _limpo(m.get("epico"), 80),
                    )
                    for m in memorias
                ]
                if not linhas:  # sem resultados: uma linha sem memória, para se ver o que faltou
                    linhas = [(chamada, quando, ferramenta, texto, None, "", *(filtros.get(k, "") for k in ("projeto", "tarefa", "epico")))]
                con.executemany(
                    """INSERT INTO recordadas(chamada, quando, ferramenta, texto, memoria, titulo, projeto, tarefa, epico)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    linhas,
                )
                con.execute(
                    "INSERT INTO contadores VALUES('chamadas', 1) ON CONFLICT(chave) DO UPDATE SET valor = valor + 1"
                )
                if chamada % 200 == 0:  # podar de vez em quando, não em cada chamada
                    con.execute("DELETE FROM chamadas WHERE id <= ?", (chamada - MAX_CHAMADAS,))
                    ultima = con.execute("SELECT max(id) FROM recordadas").fetchone()[0] or 0
                    con.execute("DELETE FROM recordadas WHERE id <= ?", (ultima - MAX_RECORDADAS,))
        except Exception as e:  # o registo é acessório
            try:
                print(f"agent-memory: MCP activity log: {type(e).__name__}: {e}", file=sys.stderr)
            except Exception:
                pass

    def resumo(self, limite: int = 100, agora: float | None = None) -> dict:
        """Os números do topo e as últimas memórias recordadas (mais recentes primeiro)."""
        agora = time.time() if agora is None else agora
        meia_noite = datetime.fromtimestamp(agora).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        if self._antigo:
            self._copiar_antigo()
        vazio = {"hoje": 0, "total": 0, "por_minuto": 0.0, "distintas": 0, "ultima": None, "recordadas": []}
        if not self.caminho.exists():
            return vazio
        try:
            return self._resumo(limite, agora, meia_noite)
        except sqlite3.DatabaseError as erro:
            if not indice_estragado(erro):
                raise
            return vazio  # o _ligar já o repôs: a vista "Atividade" volta a funcionar

    def _resumo(self, limite: int, agora: float, meia_noite: float) -> dict:
        with self._ligar() as con:
            total = con.execute("SELECT valor FROM contadores WHERE chave='chamadas'").fetchone()
            hoje = con.execute("SELECT count(*) FROM chamadas WHERE quando >= ?", (meia_noite,)).fetchone()[0]
            recentes = con.execute("SELECT count(*) FROM chamadas WHERE quando >= ?", (agora - JANELA_POR_MINUTO,)).fetchone()[0]
            distintas = con.execute("SELECT count(DISTINCT memoria) FROM recordadas WHERE memoria IS NOT NULL").fetchone()[0]
            ultima = con.execute("SELECT max(quando) FROM chamadas").fetchone()[0]
            linhas = con.execute(
                """SELECT quando, ferramenta, texto, memoria, titulo, projeto, tarefa, epico
                   FROM recordadas ORDER BY id DESC LIMIT ?""",
                (max(1, min(int(limite), 500)),),
            ).fetchall()
        return {
            "hoje": hoje,
            "total": total[0] if total else 0,
            "por_minuto": round(recentes / (JANELA_POR_MINUTO / 60), 1),
            "distintas": distintas,
            "ultima": ultima,
            "recordadas": [
                {
                    "quando": r["quando"],
                    "ferramenta": ferramenta_atual(r["ferramenta"]),
                    "texto": r["texto"],
                    "memoria": r["memoria"],
                    "titulo": r["titulo"],
                    "projeto": r["projeto"],
                    "tarefa": r["tarefa"],
                    "epico": r["epico"],
                }
                for r in linhas
            ],
        }
