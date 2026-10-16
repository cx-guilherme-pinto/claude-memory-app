# Changelog

Todas as alterações relevantes ficam aqui. As versões seguem [SemVer](https://semver.org/lang/pt-PT/).

## [0.2.0] - 2026-10-16

### Adicionado

- Campos opcionais `epico`, `url` e `etiquetas` nas notas. As notas da v0.1 continuam válidas.
- Nó de épico no grafo; tarefas ligam ao seu épico. Uma nota sem épico herda o da sua tarefa.
- Pesquisa por nome, projeto, tarefa, épico e etiquetas. Uma chave (`ABC-123`) traz a tarefa,
  o seu épico e o resto do épico.
- MCP: `memoria_procurar` aceita `tarefa` e `epico`; `memoria_adicionar` aceita `epico`, `url` e `etiquetas`.
- Interface: procura com resultados agrupados (Memórias, Projetos, Tarefas e épicos) e filtros por épico e tarefa.
- CLI: `memoria add --epico --url --etiqueta` e `memoria procurar --tarefa --epico`.

### Alterado

- Força das relações: ligação explícita > mesma tarefa > mesmo épico > mesmo projeto > ficheiros.
- Chaves do Jira e do GitHub juntam notas de projetos diferentes. Chaves locais (`#12`) ficam no projeto.
- O índice passa a `.indice/memoria-v2.sqlite` e reconstrói-se sozinho. O da v0.1 é apagado no `reindex`.

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
