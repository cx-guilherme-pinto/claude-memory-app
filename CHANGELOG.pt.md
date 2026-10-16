# Changelog

[English](CHANGELOG.md) · **Português**

Todas as alterações relevantes ficam aqui. As versões seguem [SemVer](https://semver.org/lang/pt-PT/).

## [0.4.0] - 2026-10-16

### Adicionado

- Vista **Atividade do Claude**: o que o Claude chamou pelo MCP. Quatro números (chamadas hoje, no total,
  por minuto e memórias recordadas sem repetir) e as últimas 100 memórias recordadas, com hora, ferramenta,
  título, projeto e tarefa. Clicar abre a memória no mapa. Atualiza-se sozinha.
- Registo local das chamadas MCP em `$MEMORIA_HOME/.indice/registo.sqlite`, com limite.
  O texto pesquisado é redigido e cortado; o conteúdo das notas nunca é guardado. O `reindex` não o apaga.

### Alterado

- Hindi e hebraico revistos para o registo de quem programa: termos técnicos em inglês
  (tokens, MCP, ticket, versão, etc.), como se diz no dia a dia.

## [0.3.0] - 2026-10-16

### Adicionado

- Línguas: português, inglês, hindi e hebraico. A app segue a língua do sistema
  (macOS: AppleLanguages; Windows: língua da interface; reserva: inglês).
- Seletor de línguas no topo da coluna; a escolha fica em `$MEMORIA_HOME/preferencias.json`.
  `memoria lingua [pt|en|hi|he]` faz o mesmo na linha de comandos. `MEMORIA_LANG` sobrepõe-se.
- Hebraico da direita para a esquerda; o conteúdo de cada nota segue a sua própria direção.
- Noto Sans Devanagari e Noto Sans Hebrew (OFL), locais, para o hindi e o hebraico.
- Mensagens da linha de comandos, do selftest, do update e dos erros nas quatro línguas.

### Alterado

- As descrições das ferramentas MCP e as instruções do servidor passam a inglês
  (são lidas pelo modelo). Os nomes das ferramentas e dos parâmetros não mudam.
- O texto do selftest segue a língua da app. O resultado continua no código de saída.

## [0.2.3] - 2026-10-16

### Adicionado

- Editar uma memória dentro da app: o botão "Editar" no painel abre o ficheiro Markdown
  (cabeçalho e texto) num editor da própria janela. Guardar com o botão ou ⌘S / Ctrl+S.
  Antes de gravar, confirma o cabeçalho, redige segredos e não escreve por cima de uma edição
  feita entretanto (por exemplo, pelo Claude Code). O índice e o mapa atualizam logo.

### Alterado

- O painel deixa de abrir o editor externo do sistema.

## [0.2.2] - 2026-10-16

### Adicionado

- Versão portátil: `Memoria-<versão>-macos-arm64.zip`, `-macos-x86_64.zip` e `-windows-x64.zip`,
  com o Python 3.12 e as dependências lá dentro. Extrai e abre, sem instalador nem admin.
- `memoria update` na versão portátil: descarrega o zip, verifica o SHA-256, testa e troca a pasta no mesmo sítio.
- `memoria selftest` na versão portátil mostra o comando `claude mcp add` para essa pasta.
- `scripts/sign-macos.sh` (opcional, corrido pelo organizador): assina e notariza os zips do Mac
  com o Developer ID. Não faz parte da release normal.

### Alterado

- Interface com a skill de design do workshop (`design-taste-frontend`, regras da casa e DESIGN.md):
  coluna à esquerda com o nome, as contas, a procura, os filtros e as últimas memórias pelo título;
  mapa à direita, com a linha temporal ("Ver crescer") por baixo.
- Período em segmentos; tipos (a legenda do mapa) na coluna; datas como "21 jun.".
- Monospace só em código real (caminhos e comandos).

### Notas

- Instala com o comando de uma linha. Descarregar pelo browser exige aprovação em
  Definições do Sistema → Privacidade e Segurança.

## [0.2.1] - 2026-10-16

### Corrigido

- Modo browser (o recurso do Windows sem WebView2) mostrava um grafo vazio: o URL impresso
  não levava a chave da sessão e a página ficava à espera da ponte da janela.
  Agora o URL é `http://127.0.0.1:<porta>/?t=<chave>`; a chave passa a um cookie de sessão
  (HttpOnly, SameSite=Strict) e o servidor diz à página em que modo está.
  Sem a chave, a página explica o que abrir. Na janela, se a ponte não aparecer, a página usa HTTP.

### Alterado

- Visual alinhado com a Arena e os slides (DESIGN.md do workshop): tokens de cor, cantos retos,
  letra Bricolage Grotesque (local, licença OFL), botão principal azul.
- Cores dos tipos da paleta de estado: lição amarelo, fazer verde, não fazer vermelho (desenhado
  como anel, para não depender da cor), histórico neutro; nós de contexto em tons neutros.
- Pesquisa: palavras no nome da memória contam mais (desempata o BM25 com poucas notas).

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
