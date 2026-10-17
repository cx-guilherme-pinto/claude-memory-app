# Changelog

[English](CHANGELOG.md) · **Português**

Todas as alterações relevantes ficam aqui. As versões seguem [SemVer](https://semver.org/lang/pt-PT/).

## [0.5.0] - 2026-10-17

### Alterado

- A app passa a chamar-se **Agent Memory** em todas as línguas (janela, título da página, menus, mensagens, atalhos e docs). Até à v0.4 chamava-se *Memória*.
- Os instaladores criam `~/Applications/Agent Memory.app` (Mac) e "Agent Memory" no menu Iniciar (Windows), e removem o atalho antigo *Memória*.
- **Nomes técnicos em inglês**, para um workshop em inglês não mostrar nem uma palavra em português
  (os termos técnicos ficam em inglês em todas as línguas):
  - comando `agent-memory` (e `agent-memory-gui`), com `search` e `language` e as opções
    `--type`, `--title`, `--project`, `--text`, `--task`, `--epic`, `--tag`, `--file`, `--link`, `--cost`, `--limit`,
    e `update --check/--force/--version`;
  - servidor MCP `agent-memory` com as ferramentas `memory_search(text?, project?, task?, epic?, type?, limit)`,
    `memory_add(type, title, text, project, task?, epic?, url?, tags?, files?, links?, cost_usd?)` e
    `memory_related(ref, limit)`. Os resultados usam chaves em inglês (`results`, `path`, `title`, `type`, `task`,
    `excerpt`, `score`, `strength`, `reasons`, ...). As instruções para o modelo usam os nomes novos;
  - tipos `lesson`, `do`, `dont` e `history`;
  - as notas novas levam o cabeçalho em inglês (`type`, `title`, `project`, `task`, `epic`, `url`, `tags`,
    `files`, `date`, `cost_usd`, `links`);
  - pasta dos dados `~/.agent-memory` (`AGENT_MEMORY_HOME`), com `.index/index-v3.sqlite`, `.index/activity.sqlite`
    e `preferences.json`;
  - variáveis `AGENT_MEMORY_LANG`, `AGENT_MEMORY_NO_UPDATE` e `AGENT_MEMORY_DOWNLOAD_TOKEN`;
  - a marca da redação é `[REDACTED:<tipo>]`;
  - o zip portátil do Windows traz `agent-memory.cmd` e `README.pt.txt` (era `LEIA-ME.txt`).
- As respostas de erro do servidor web são em inglês (`{"error": "not found"}`).

### Corrigido

Encontrado por um teste de caos do kit do workshop (ambientes estragados de propósito):

- Um índice de pesquisa estragado (uma cópia mal feita, um problema do disco ou do antivírus) refaz-se sozinho a partir
  das notas. O `reindex` já não abre o ficheiro estragado. Se não der para o refazer (no Windows, outro processo tem o
  ficheiro aberto), a CLI, as ferramentas MCP e o `selftest` dizem-no numa linha: fecha o Claude Code e a app e corre
  `agent-memory reindex`. O registo da atividade recupera da mesma maneira.
- Outro processo a escrever no índice já não prende as pesquisas (abrir o índice escrevia nele sempre), e uma nota
  gravada nunca aparece como falhada (o modelo tentava outra vez e criava duplicados). O `reindex` corre numa só
  transação: entretanto, os outros processos continuam a ver o índice anterior. Um índice ocupado dá "o índice está
  ocupado" em vez de um traceback.
- Pesquisa em hindi (os sinais das vogais partiam as palavras) e em japonês e chinês (sem espaços entre as palavras).
  O índice passa para `index-v3.sqlite` e é refeito a partir das notas na primeira utilização.
- Uma nota enorme (um log colado) já não prende a pesquisa, o servidor MCP nem a janela: os excertos só se calculam para
  os resultados finais e para notas com menos de 32 KB, o índice guarda o primeiro 1 MB, e o `add` e o editor recusam
  mais de 1 MB com uma mensagem.
- A redação de segredos é linear: 40 KB sem espaços levavam um minuto e prendiam o servidor MCP.
- Um surrogate solto numa linha JSON-RPC (`\ud83d`) ficava sem resposta; agora vira U+FFFD.
- As notas que a app não consegue usar são avisadas em vez de desaparecerem: uma pasta sem permissão de leitura (as
  memórias dela ficam no índice), uma ligação simbólica para fora da pasta, um `.md` fora da pasta de um projeto, um
  ficheiro que não está em UTF-8. Os ficheiros UTF-16 com BOM (Bloco de Notas do Windows) são lidos.
- Um `cost_usd: .inf` escrito à mão estragava o painel da nota na app (JSON inválido); um `type: tarefa` escrito à mão
  (o nome de um nó de contexto) escondia a nota. `[[]]` e ligações com um título não latino já não resolvem para uma
  nota qualquer. Os nomes de ficheiro decompostos (NFD) do macOS resolvem a partir das ligações.
- Uma escrita falhada (disco cheio, um surrogate de um terminal Latin-1) já não deixa um `.md` vazio ou cortado.
  Os erros do disco na CLI são uma linha, não um traceback.
- Com um `LC_ALL` antigo (ISO-8859-1) no Mac/Linux, o texto que entra no `add` por um pipe é lido como UTF-8, a saída é
  UTF-8 e o `search --json` é JSON só com ASCII.
- `agent-memory update` num Mac sem as Command Line Tools do Xcode: quando o uv descarrega um Python novo, já não
  abre o diálogo "instalar as ferramentas de programador" (um `install_name_tool` vazio fica primeiro no PATH,
  só nesse `uv tool install`, como faz o setup do kit).
- `agent-memory update` sem git no PATH (ou só com o `/usr/bin/git` de fachada da Apple) usa o git que o setup do kit
  instala: `~/.workshop-claude/bin/git` no Mac; no Windows `%USERPROFILE%\.workshop-claude\git\cmd\git.exe`
  ou o Git for Windows (`%LOCALAPPDATA%\Programs\Git`, `%ProgramFiles%\Git`). A verificação das Command Line Tools
  também exige que `<xcode-select -p>/usr/bin/git` exista (ferramentas apagadas ainda abrem o diálogo).

### Compatibilidade

Nada muda de sítio e nenhuma nota é reescrita:

- O `memoria` (e o `memoria-gui`) continuam a funcionar, tal como `procurar`, `lingua` e as opções em português (`--tipo`, `--projeto`, `--verificar`, ...). Não aparecem na ajuda.
- Se `~/.memoria` existir e `~/.agent-memory` não, a app continua a usar `~/.memoria`. `MEMORIA_HOME`, `MEMORIA_LANG`, `MEMORIA_SEM_UPDATE` e `MEMORIA_DOWNLOAD_TOKEN` continuam a funcionar (os nomes novos ganham).
- As notas com o cabeçalho antigo em português (`tipo: licao`, `titulo`, `projeto`, `tarefa`, ...) são lidas como estão. Os filtros de tipo aceitam os dois nomes.
- O registo de atividade antigo (`.indice/registo.sqlite`) é copiado uma vez, nunca movido; as linhas antigas aparecem com os nomes novos das ferramentas. A língua guardada em `preferencias.json` é lida.
- Os nomes antigos das ferramentas MCP (`memoria_procurar`, `memoria_adicionar`, `memoria_relacionadas`) **saíram**: as skills do kit usam os novos. Volta a registar o servidor como `agent-memory` (`claude mcp remove --scope user memoria` e depois `claude mcp add --scope user agent-memory -- <agent-memory> mcp`).
- O wheel (`memoria-<versão>-py3-none-any.whl`), o nome da ferramenta no uv (`memoria`), o pacote Python e os zips e pastas portáteis (`Memoria-…zip`, `Memoria.app`, `Memoria\Memoria.exe`) mantêm o nome, para as instalações e as atualizações continuarem a funcionar.

## [0.4.1] - 2026-10-16

### Alterado

- Publicação em github.com.

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
