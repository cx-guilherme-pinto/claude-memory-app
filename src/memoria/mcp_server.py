"""Servidor MCP (stdio). Nunca escreve no stdout fora do protocolo."""

from __future__ import annotations

import sys
import time
from typing import Annotated

from pydantic import Field

from memoria import __version__
from memoria.service import Memoria

# Textos para o modelo (não para o participante): sempre em inglês, em qualquer língua da app.
# O modelo responde ao participante na língua dele.
INSTRUCOES = (
    "The participant's local memory, stored as Markdown. "
    "Before planning, call memoria_procurar with the current project (and the task or epic, if any). "
    "After a task, call memoria_adicionar with one short, actionable lesson, written in the participant's language. "
    "If there is a ticket (Jira, GitHub), always pass tarefa, epico and url: they become searchable. "
    "Types: licao (lesson), fazer (do), nao_fazer (don't), historico (history). Never store secrets."
)


def _ms(inicio: float) -> int:
    return int((time.perf_counter() - inicio) * 1000)


def _compacto(itens: list[dict]) -> list[dict]:
    """Tira campos vazios: menos tokens para o modelo."""
    return [{k: v for k, v in i.items() if v not in (None, "", [], {})} for i in itens]


def criar_servidor(memoria: Memoria | None = None):
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.types import ToolAnnotations

    from memoria.registo import Registo

    mem = memoria or Memoria()
    registo = Registo(mem.home)  # o que o Claude chama, para a vista "Atividade" da app
    servidor = MCPServer(name="memoria", version=__version__, instructions=INSTRUCOES)
    so_leitura = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @servidor.tool(
        name="memoria_procurar",
        description=(
            "Search memories by title, body, project, task, epic and tags. "
            "A ticket key (e.g. ABC-123) returns everything for that task and its epic. "
            "Filters: project, type, task and epic."
        ),
        annotations=so_leitura,
    )
    def memoria_procurar(
        texto: Annotated[str, Field(description="Words to search for. Empty returns the most recent.")],
        projeto: Annotated[str | None, Field(description="Only this project.")] = None,
        tipo: Annotated[str | None, Field(description="licao (lesson), fazer (do), nao_fazer (don't) or historico (history).")] = None,
        tarefa: Annotated[str | None, Field(description="Only this task, e.g. ABC-123 or owner/repo#12.")] = None,
        epico: Annotated[str | None, Field(description="Only this epic (includes its tasks), e.g. ABC-100.")] = None,
        limite: Annotated[int, Field(ge=1, le=100, description="Maximum number of results.")] = 10,
    ) -> dict:
        inicio = time.perf_counter()
        filtros = {"projeto": projeto, "tipo": tipo, "tarefa": tarefa, "epico": epico}
        try:
            resultados = mem.procurar(texto, projeto=projeto, tipo=tipo, limite=limite, tarefa=tarefa, epico=epico)
        except ValueError as erro:
            registo.gravar("memoria_procurar", texto=texto, filtros=filtros, erro=str(erro), duracao_ms=_ms(inicio))
            raise ToolError(str(erro)) from erro
        registo.gravar("memoria_procurar", texto=texto, filtros=filtros, memorias=resultados, duracao_ms=_ms(inicio))
        return {"total": len(resultados), "resultados": _compacto(resultados)}

    @servidor.tool(
        name="memoria_adicionar",
        description=(
            "Save a memory as Markdown and return the file path. "
            "Secrets (tokens, keys, passwords) are redacted before writing."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )
    def memoria_adicionar(
        tipo: Annotated[str, Field(description="licao (lesson), fazer (do), nao_fazer (don't) or historico (history).")],
        titulo: Annotated[str, Field(description="Short title.")],
        texto: Annotated[str, Field(description="Body in Markdown. May contain [[name]] links.")],
        projeto: Annotated[str, Field(description="Project name, e.g. arena-de-seguranca.")],
        tarefa: Annotated[str | None, Field(description="Ticket key, e.g. ABC-123 or owner/repo#12.")] = None,
        epico: Annotated[str | None, Field(description="Epic or parent key, e.g. ABC-100.")] = None,
        url: Annotated[str | None, Field(description="Link to the ticket or PR (http/https).")] = None,
        ficheiros: Annotated[list[str] | None, Field(description="Related code paths.")] = None,
        ligacoes: Annotated[list[str] | None, Field(description="Names or ids of other memories.")] = None,
        etiquetas: Annotated[list[str] | None, Field(description="Search words, e.g. ['ci', 'cache'].")] = None,
        custo_usd: Annotated[float | None, Field(ge=0, description="Task cost in US dollars.")] = None,
    ) -> str:
        try:
            resultado = mem.adicionar(
                tipo=tipo,
                titulo=titulo,
                texto=texto,
                projeto=projeto,
                tarefa=tarefa,
                epico=epico,
                url=url,
                ficheiros=ficheiros,
                ligacoes=ligacoes,
                etiquetas=etiquetas,
                custo_usd=custo_usd,
            )
        except ValueError as erro:
            registo.gravar("memoria_adicionar", texto=titulo, filtros={"projeto": projeto, "tarefa": tarefa}, erro=str(erro))
            raise ToolError(str(erro)) from erro
        nova = mem.nota(resultado["id"]) or {"id": resultado["id"], "titulo": titulo, "projeto": projeto}
        registo.gravar(
            "memoria_adicionar",
            texto=nova.get("titulo", ""),
            filtros={"projeto": projeto, "tipo": tipo, "tarefa": tarefa, "epico": epico},
            memorias=[nova],
        )
        return resultado["caminho"]

    @servidor.tool(
        name="memoria_relacionadas",
        description=(
            "Memories related to a memory, strongest relation first: "
            "explicit link, same task, same epic, same project, shared files."
        ),
        annotations=so_leitura,
    )
    def memoria_relacionadas(
        id_ou_caminho: Annotated[str, Field(description="Id (project/YYYY-MM-DD-slug), name, title or path of the .md file.")],
        limite: Annotated[int, Field(ge=1, le=100, description="Maximum number of results.")] = 10,
    ) -> dict:
        inicio = time.perf_counter()
        # No registo fica o id da memória de partida (não o caminho completo do disco).
        origem = mem.indice.resolver(id_ou_caminho) or id_ou_caminho
        try:
            resultados = mem.relacionadas(id_ou_caminho, limite=limite)
        except LookupError as erro:
            registo.gravar("memoria_relacionadas", texto=origem, erro=str(erro), duracao_ms=_ms(inicio))
            raise ToolError(str(erro)) from erro
        registo.gravar("memoria_relacionadas", texto=origem, memorias=resultados, duracao_ms=_ms(inicio))
        return {"total": len(resultados), "resultados": _compacto(resultados)}

    return servidor


def correr_stdio() -> int:
    """Arranca o servidor em stdio. Mensagens para humanos vão para o stderr."""
    import anyio

    from memoria.index import FTS5Indisponivel, verificar_fts5

    # Antes do protocolo arrancar, tudo vai explicitamente para o stderr.
    # Durante o protocolo, o stdio_server do mcp desvia o fd 1 para o stderr:
    # um print acidental nunca chega ao canal do protocolo.
    try:
        verificar_fts5()
    except FTS5Indisponivel as erro:
        print(f"memoria mcp: {erro}", file=sys.stderr)
        return 2
    mem = Memoria()
    try:
        mem.sincronizar(forcar=True)
    except Exception as erro:  # o servidor arranca na mesma; o erro aparece nas ferramentas
        print(f"memoria mcp: aviso ao indexar: {erro}", file=sys.stderr)
    servidor = criar_servidor(mem)
    try:
        anyio.run(servidor.run_stdio_async)
    except KeyboardInterrupt:
        pass
    return 0


__all__ = ["criar_servidor", "correr_stdio"]
