# Changelog

Todas as alterações relevantes ficam aqui. As versões seguem [SemVer](https://semver.org/lang/pt-PT/).

## [0.1.0] - 2026-10-16

Primeira versão.

### Adicionado

- Notas em Markdown em `$MEMORIA_HOME/<projeto>/<AAAA-MM-DD>-<slug>.md`, com cabeçalho YAML
  (`tipo`, `titulo`, `projeto`, `tarefa`, `ficheiros`, `data`, `custo_usd`, `ligacoes`).
- Índice SQLite com FTS5 e arestas, reconstruível com `memoria reindex`.
- Redação de segredos antes de gravar.
- Servidor MCP em stdio: `memoria_procurar`, `memoria_adicionar`, `memoria_relacionadas`.
- Janela nativa (pywebview) com grafo, filtros, linha temporal, painel da nota e formulário.
  No Windows sem WebView2, a interface abre no browser.
- `memoria update` por `git ls-remote` e SHA-256.
- Instaladores `install.sh` e `install.ps1`, sem admin.
