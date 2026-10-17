"""Servidor MCP (stdio). Nunca escreve no stdout fora do protocolo.

Nome no Claude Code: `agent-memory` (`claude mcp add --scope user agent-memory -- <agent-memory> mcp`).
Ferramentas (desde a v0.5, nomes, argumentos e resultados em inglês):
    memory_search(text?, project?, task?, epic?, type?, limit=10)
    memory_add(type, title, text, project, task?, epic?, url?, tags?, files?, links?, cost_usd?) -> caminho
    memory_related(ref, limit=10)
Os nomes antigos (memoria_procurar, ...) já não são expostos: só as skills do kit os usavam.
"""

from __future__ import annotations

import io
import json
import re
import sqlite3
import sys
import time
from typing import Annotated

from pydantic import Field

from memoria import __version__, store
from memoria.service import Memoria

NOME_SERVIDOR = "agent-memory"
FERRAMENTAS = ("memory_search", "memory_add", "memory_related")

# Textos para o modelo (não para o participante): sempre em inglês, em qualquer língua da app.
# O modelo responde ao participante na língua dele.
INSTRUCOES = (
    "The participant's local memory, stored as Markdown. "
    "Before planning, call memory_search with the current project (and the task or epic, if any). "
    "After a task, call memory_add with one short, actionable lesson, written in the participant's language. "
    "If there is a ticket (Jira, GitHub), always pass task, epic and url: they become searchable. "
    "Types: lesson, do, dont (don't), history. Never store secrets."
)

TIPOS_DESCRICAO = "lesson, do, dont (don't) or history."

# Campos do índice (por dentro, em português) -> nomes nos resultados do MCP e do `--json` da CLI.
CAMPOS_EXTERNOS = {
    "id": "id",
    "caminho": "path",
    "tipo": "type",
    "titulo": "title",
    "projeto": "project",
    "tarefa": "task",
    "epico": "epic",
    "url": "url",
    "etiquetas": "tags",
    "ficheiros": "files",
    "data": "date",
    "custo_usd": "cost_usd",
    "ligacoes": "links",
    "excerto": "excerpt",
    "pontuacao": "score",
    "forca": "strength",
    "motivos": "reasons",
    "corpo": "body",
}
# Motivos de uma relação (memory_related).
MOTIVOS_EXTERNOS = {"ligacao": "link", "tarefa": "task", "epico": "epic", "projeto": "project", "ficheiro": "file"}


def externo(item: dict) -> dict:
    """Uma memória com os nomes de fora: chaves e tipo em inglês."""
    saida = {}
    for chave, valor in item.items():
        if chave == "tipo":
            valor = store.tipo_externo(valor)
        elif chave == "motivos" and isinstance(valor, dict):
            valor = {MOTIVOS_EXTERNOS.get(k, k): v for k, v in valor.items()}
        saida[CAMPOS_EXTERNOS.get(chave, chave)] = valor
    return saida


def _ms(inicio: float) -> int:
    return int((time.perf_counter() - inicio) * 1000)


def _compacto(itens: list[dict]) -> list[dict]:
    """Tira campos vazios: menos tokens para o modelo."""
    return [{k: v for k, v in externo(i).items() if v not in (None, "", [], {})} for i in itens]


# Erros que viram uma mensagem para o modelo (ToolError). Os outros chegavam como um
# "Error executing tool" sem explicação, e o modelo voltava a tentar (memórias duplicadas).
ERROS_FERRAMENTA = (ValueError, LookupError, OSError, RuntimeError, sqlite3.Error)


def mensagem_erro(erro: BaseException) -> str:
    from memoria.i18n import t
    from memoria.index import indice_ocupado

    if indice_ocupado(erro):
        return t("erro.indice_ocupado")
    if isinstance(erro, sqlite3.Error):
        return t("erro.indice", erro=erro)
    return str(erro)


def criar_servidor(memoria: Memoria | None = None):
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.types import ToolAnnotations

    from memoria.registo import Registo

    mem = memoria or Memoria()
    registo = Registo(mem.home)  # o que o Claude chama, para a vista "Atividade" da app
    servidor = MCPServer(name=NOME_SERVIDOR, version=__version__, instructions=INSTRUCOES)
    so_leitura = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @servidor.tool(
        name="memory_search",
        description=(
            "Search memories by title, body, project, task, epic and tags. "
            "A ticket key (e.g. ABC-123) returns everything for that task and its epic. "
            "Filters: project, type, task and epic."
        ),
        annotations=so_leitura,
    )
    def memory_search(
        text: Annotated[str, Field(description="Words to search for. Empty returns the most recent.")] = "",
        project: Annotated[str | None, Field(description="Only this project.")] = None,
        task: Annotated[str | None, Field(description="Only this task, e.g. ABC-123 or owner/repo#12.")] = None,
        epic: Annotated[str | None, Field(description="Only this epic (includes its tasks), e.g. ABC-100.")] = None,
        type: Annotated[str | None, Field(description=TIPOS_DESCRICAO)] = None,  # noqa: A002
        limit: Annotated[int, Field(ge=1, le=100, description="Maximum number of results.")] = 10,
    ) -> dict:
        inicio = time.perf_counter()
        texto = text or ""
        filtros = {"projeto": project, "tipo": type, "tarefa": task, "epico": epic}
        try:
            resultados = mem.procurar(texto, projeto=project, tipo=type, limite=limit, tarefa=task, epico=epic)
        except ERROS_FERRAMENTA as erro:
            registo.gravar("memory_search", texto=texto, filtros=filtros, erro=mensagem_erro(erro), duracao_ms=_ms(inicio))
            raise ToolError(mensagem_erro(erro)) from erro
        registo.gravar("memory_search", texto=texto, filtros=filtros, memorias=resultados, duracao_ms=_ms(inicio))
        return {"total": len(resultados), "results": _compacto(resultados)}

    @servidor.tool(
        name="memory_add",
        description=(
            "Save a memory as Markdown and return the file path. "
            "Secrets (tokens, keys, passwords) are redacted before writing."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )
    def memory_add(
        type: Annotated[str, Field(description=TIPOS_DESCRICAO)],  # noqa: A002
        title: Annotated[str, Field(description="Short title.")],
        text: Annotated[str, Field(description="Body in Markdown. May contain [[name]] links.")],
        project: Annotated[str, Field(description="Project name, e.g. security-arena.")],
        task: Annotated[str | None, Field(description="Ticket key, e.g. ABC-123 or owner/repo#12.")] = None,
        epic: Annotated[str | None, Field(description="Epic or parent key, e.g. ABC-100.")] = None,
        url: Annotated[str | None, Field(description="Link to the ticket or PR (http/https).")] = None,
        tags: Annotated[list[str] | None, Field(description="Search words, e.g. ['ci', 'cache'].")] = None,
        files: Annotated[list[str] | None, Field(description="Related code paths.")] = None,
        links: Annotated[list[str] | None, Field(description="Names or ids of other memories.")] = None,
        cost_usd: Annotated[float | None, Field(ge=0, description="Task cost in US dollars.")] = None,
    ) -> str:
        try:
            resultado = mem.adicionar(
                tipo=type,
                titulo=title,
                texto=text,
                projeto=project,
                tarefa=task,
                epico=epic,
                url=url,
                ficheiros=files,
                ligacoes=links,
                etiquetas=tags,
                custo_usd=cost_usd,
            )
        except ERROS_FERRAMENTA as erro:
            registo.gravar("memory_add", texto=title, filtros={"projeto": project, "tarefa": task}, erro=mensagem_erro(erro))
            raise ToolError(mensagem_erro(erro)) from erro
        # A memória já está gravada: daqui em diante, nada pode fazer parecer que falhou.
        try:
            nova = mem.nota(resultado["id"])
        except ERROS_FERRAMENTA:
            nova = None
        nova = nova or {"id": resultado["id"], "titulo": title, "projeto": project}
        registo.gravar(
            "memory_add",
            texto=nova.get("titulo", ""),
            filtros={"projeto": project, "tipo": type, "tarefa": task, "epico": epic},
            memorias=[nova],
        )
        return resultado["caminho"]

    @servidor.tool(
        name="memory_related",
        description=(
            "Memories related to a memory, strongest relation first: "
            "explicit link, same task, same epic, same project, shared files."
        ),
        annotations=so_leitura,
    )
    def memory_related(
        ref: Annotated[
            str, Field(description="The memory: the path memory_add returned, or the id (project/YYYY-MM-DD-slug), name or title.")
        ],
        limit: Annotated[int, Field(ge=1, le=100, description="Maximum number of results.")] = 10,
    ) -> dict:
        inicio = time.perf_counter()
        origem = ref
        try:
            # No registo fica o id da memória de partida (não o caminho completo do disco).
            origem = mem.resolver(ref) or ref
            resultados = mem.relacionadas(ref, limite=limit)
        except ERROS_FERRAMENTA as erro:
            registo.gravar("memory_related", texto=origem, erro=mensagem_erro(erro), duracao_ms=_ms(inicio))
            raise ToolError(mensagem_erro(erro)) from erro
        registo.gravar("memory_related", texto=origem, memorias=resultados, duracao_ms=_ms(inicio))
        return {"total": len(resultados), "results": _compacto(resultados)}

    return servidor


# --- stdin sem surrogates soltos ------------------------------------------------
# O JSON.stringify do Node escreve um surrogate solto como "\ud83d". O SDK do MCP (pydantic) recusa
# essa linha e deita o pedido fora sem responder: o Claude Code ficava à espera da ferramenta.
# Estas linhas passam pelo json do Python (que as aceita) e o surrogate vira U+FFFD.
_ESCAPE_SURROGATE = re.compile(r"\\u[dD][89a-fA-F][0-9a-fA-F]{2}")


def _sem_surrogates(valor):
    if isinstance(valor, str):
        return store.sem_surrogates(valor)
    if isinstance(valor, list):
        return [_sem_surrogates(v) for v in valor]
    if isinstance(valor, dict):
        return {_sem_surrogates(k): _sem_surrogates(v) for k, v in valor.items()}
    return valor


def linha_limpa(linha: str) -> str:
    if not _ESCAPE_SURROGATE.search(linha):  # o caso normal: nada a fazer
        return linha
    try:
        return json.dumps(_sem_surrogates(json.loads(linha)), ensure_ascii=False) + "\n"
    except ValueError:
        return linha  # não é JSON: o SDK trata dela como antes


class _EntradaLimpa:
    """As linhas do stdin, já sem surrogates soltos (ver linha_limpa)."""

    def __init__(self, entrada):
        self._entrada = entrada

    async def __aiter__(self):
        async for linha in self._entrada:
            yield linha_limpa(linha)


class _TextoSemFechar(io.TextIOWrapper):
    """Fechar este wrapper não fecha o sys.stdin.buffer (igual ao do SDK)."""

    def close(self) -> None:
        try:
            self.detach()
        except ValueError:
            pass


async def _servir_stdio(servidor) -> None:
    import anyio
    from mcp.server.stdio import stdio_server

    interno = getattr(servidor, "_lowlevel_server", None)
    if interno is None:  # outra versão do SDK: o caminho normal
        await servidor.run_stdio_async()
        return
    entrada = anyio.wrap_file(_TextoSemFechar(sys.stdin.buffer, encoding="utf-8", errors="replace"))
    async with stdio_server(stdin=_EntradaLimpa(entrada)) as (leitura, escrita):
        await interno.run(leitura, escrita, interno.create_initialization_options())


def correr_stdio() -> int:
    """Arranca o servidor em stdio. Mensagens para humanos vão para o stderr."""
    import anyio

    from memoria.i18n import t
    from memoria.index import ESPERA_CURTA, FTS5Indisponivel, verificar_fts5

    # Antes do protocolo arrancar, tudo vai explicitamente para o stderr.
    # Durante o protocolo, o stdio_server do mcp desvia o fd 1 para o stderr:
    # um print acidental nunca chega ao canal do protocolo.
    try:
        verificar_fts5()
    except FTS5Indisponivel as erro:
        print(f"agent-memory mcp: {erro}", file=sys.stderr)
        return 2
    mem = Memoria()
    try:
        # Espera pouco por um lock: o Claude Code desiste de um servidor que não responde em 30 s.
        mem.sincronizar(forcar=True, espera=ESPERA_CURTA)
    except Exception as erro:  # o servidor arranca na mesma; o erro aparece nas ferramentas
        print(f"agent-memory mcp: {t('aviso.indexar', erro=erro)}", file=sys.stderr)
    servidor = criar_servidor(mem)
    try:
        anyio.run(_servir_stdio, servidor)
    except KeyboardInterrupt:
        pass
    return 0


__all__ = ["criar_servidor", "correr_stdio", "externo", "FERRAMENTAS", "NOME_SERVIDOR"]
