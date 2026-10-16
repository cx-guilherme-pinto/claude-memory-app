"""Agent Memory: notas locais do Claude Code em Markdown, com grafo e servidor MCP."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("memoria")
except PackageNotFoundError:  # a correr a partir do código fonte sem instalar
    __version__ = "0.0.0"
