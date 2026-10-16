"""Servidor MCP (stdio). Nunca escreve no stdout fora do protocolo."""

from __future__ import annotations

import sys
from typing import Annotated

from pydantic import Field

from memoria import __version__
from memoria.service import Memoria

INSTRUCOES = (
    "Memória local do participante, em Markdown. "
    "Antes de planear, usa memoria_procurar com o projeto atual e guarda as lições. "
    "Depois de uma tarefa, usa memoria_adicionar com uma lição curta e acionável. "
    "Tipos: licao, fazer, nao_fazer, historico. Nunca guardes segredos."
)


def _compacto(itens: list[dict]) -> list[dict]:
    """Tira campos vazios: menos tokens para o modelo."""
    return [{k: v for k, v in i.items() if v not in (None, "", [], {})} for i in itens]


def criar_servidor(memoria: Memoria | None = None):
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.types import ToolAnnotations

    mem = memoria or Memoria()
    servidor = MCPServer(name="memoria", version=__version__, instructions=INSTRUCOES)
    so_leitura = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @servidor.tool(
        name="memoria_procurar",
        description="Procura memórias por texto (FTS5). Filtra por projeto e tipo. Devolve as mais relevantes.",
        annotations=so_leitura,
    )
    def memoria_procurar(
        texto: Annotated[str, Field(description="Palavras a procurar. Vazio devolve as mais recentes.")],
        projeto: Annotated[str | None, Field(description="Só deste projeto.")] = None,
        tipo: Annotated[str | None, Field(description="licao, fazer, nao_fazer ou historico.")] = None,
        limite: Annotated[int, Field(ge=1, le=100, description="Máximo de resultados.")] = 10,
    ) -> dict:
        try:
            resultados = mem.procurar(texto, projeto=projeto, tipo=tipo, limite=limite)
        except ValueError as erro:
            raise ToolError(str(erro)) from erro
        return {"total": len(resultados), "resultados": _compacto(resultados)}

    @servidor.tool(
        name="memoria_adicionar",
        description=(
            "Guarda uma memória em Markdown e devolve o caminho do ficheiro. "
            "Os segredos (tokens, chaves, passwords) são redigidos antes de escrever."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )
    def memoria_adicionar(
        tipo: Annotated[str, Field(description="licao, fazer, nao_fazer ou historico.")],
        titulo: Annotated[str, Field(description="Título curto.")],
        texto: Annotated[str, Field(description="Corpo em Markdown. Pode ter ligações [[nome]].")],
        projeto: Annotated[str, Field(description="Nome do projeto, ex.: arena-de-seguranca.")],
        tarefa: Annotated[str | None, Field(description="Id da tarefa, ex.: ABC-123 ou #42.")] = None,
        ficheiros: Annotated[list[str] | None, Field(description="Caminhos de código relacionados.")] = None,
        ligacoes: Annotated[list[str] | None, Field(description="Nomes ou ids de outras memórias.")] = None,
        custo_usd: Annotated[float | None, Field(ge=0, description="Custo da tarefa em dólares.")] = None,
    ) -> str:
        try:
            resultado = mem.adicionar(
                tipo=tipo,
                titulo=titulo,
                texto=texto,
                projeto=projeto,
                tarefa=tarefa,
                ficheiros=ficheiros,
                ligacoes=ligacoes,
                custo_usd=custo_usd,
            )
        except ValueError as erro:
            raise ToolError(str(erro)) from erro
        return resultado["caminho"]

    @servidor.tool(
        name="memoria_relacionadas",
        description=(
            "Memórias ligadas a uma memória, da relação mais forte para a mais fraca: "
            "ligação explícita, mesma tarefa, mesmo projeto, ficheiros partilhados."
        ),
        annotations=so_leitura,
    )
    def memoria_relacionadas(
        id_ou_caminho: Annotated[str, Field(description="Id (projeto/AAAA-MM-DD-slug), nome, título ou caminho do .md.")],
        limite: Annotated[int, Field(ge=1, le=100, description="Máximo de resultados.")] = 10,
    ) -> dict:
        try:
            resultados = mem.relacionadas(id_ou_caminho, limite=limite)
        except LookupError as erro:
            raise ToolError(str(erro)) from erro
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
