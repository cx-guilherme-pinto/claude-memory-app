# Agent Memory

[English](README.md) · **Português** · [हिन्दी](README.hi.md) · [עברית](README.he.md)

A Agent Memory guarda o que o Claude Code aprende, em ficheiros Markdown no teu computador.
Mostra essas notas num grafo e dá-as ao Claude Code por um servidor MCP.

Até à v0.4, a app chamava-se *Memória*. Desde a v0.5, os nomes técnicos também são em inglês: o comando `agent-memory`,
o servidor MCP `agent-memory` com as ferramentas `memory_search`, `memory_add` e `memory_related`, e a pasta `~/.agent-memory`.
Os nomes antigos continuam a funcionar (ver [Vindo da v0.4](#vindo-da-v04)).

- **Lições** e regras (**fazer**, **não fazer**) e **histórico** de tarefas.
- Cada nota pode ficar ligada a um ticket (Jira, GitHub) e ao seu épico.
- Pesquisa rápida (SQLite FTS5) por nome, projeto, ticket, épico, etiquetas e texto.
- Uma janela com o grafo, filtros, linha temporal e um formulário para notas novas.
- Tudo fica no teu computador. Nada é enviado para fora.

## Instalar

Não precisa de permissões de administrador.

<!-- >>> instalar: gerado a partir de release.conf por scripts/render_installers.py -->
**macOS** (Intel e Apple Silicon) e Linux, no Terminal:

```bash
curl -fsSL https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.5.0/install.sh | sh
```

**Windows 10/11**, no PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.5.0/install.ps1 | iex"
```
<!-- <<< instalar -->

O instalador:

1. instala o [uv](https://docs.astral.sh/uv/) (versão fixada), se faltar;
2. descarrega o wheel e o `constraints.txt` e verifica o SHA-256;
3. instala a app com o Python 3.12 gerido pelo uv;
4. no Windows, instala o WebView2 Runtime (por utilizador), se faltar;
5. cria um atalho: `~/Applications/Agent Memory.app` no Mac, "Agent Memory" no menu Iniciar no Windows.

Os comandos ficam em `~/.local/bin` (Mac/Linux) ou `%USERPROFILE%\.local\bin` (Windows).

### Versão portátil (sem instalar)

Cada release traz também um zip por plataforma, com o Python lá dentro:

| Ficheiro | Abrir |
|---|---|
| `Memoria-<versão>-macos-arm64.zip` (Apple Silicon) | `Memoria.app` |
| `Memoria-<versão>-macos-x86_64.zip` (Intel) | `Memoria.app` |
| `Memoria-<versão>-windows-x64.zip` | `Memoria\Memoria.exe` |

Extrai e abre. Não precisa de admin nem de rede. O setup do workshop faz isto sozinho.

- Ligar ao Claude Code: o `selftest` mostra o comando `claude mcp add` certo.
  No Mac, `…/Memoria.app/Contents/MacOS/memoria selftest`; no Windows, `agent-memory.cmd selftest`.
- Instala com o comando de uma linha. Descarregar pelo browser exige aprovação em
  Definições do Sistema → Privacidade e Segurança: o Mac bloqueia a app (não tem assinatura).
  Desbloqueia no Terminal: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`.
  No Windows, em "O Windows protegeu o computador", clica em "Mais informações" e "Executar mesmo assim".
- Depois de ligar ao Claude Code, não movas a app.
- Os zips, a pasta da app e os seus lançadores mantêm o nome `Memoria`: as cópias portáteis antigas continuam a atualizar-se no mesmo sítio.

Detalhes e decisões: [docs/portatil.pt.md](docs/portatil.pt.md).

## Ligar ao Claude Code

```bash
claude mcp add --scope user agent-memory -- "$HOME/.local/bin/agent-memory" mcp
```

No Windows: `claude mcp add --scope user agent-memory -- "%USERPROFILE%\.local\bin\agent-memory.exe" mcp`.

Ferramentas MCP (no Claude Code: `mcp__agent-memory__memory_search`, etc.):

| Ferramenta | Para quê |
|---|---|
| `memory_search(text?, project?, task?, epic?, type?, limit=10)` | Procura notas. Uma chave (`ABC-123`) traz a tarefa e o seu épico. Sem `text`, traz as mais recentes. |
| `memory_add(type, title, text, project, task?, epic?, url?, tags?, files?, links?, cost_usd?)` | Guarda uma nota e devolve o caminho. |
| `memory_related(ref, limit=10)` | Notas ligadas, da relação mais forte para a mais fraca. `ref` é o caminho que o `memory_add` devolveu, ou o id, o nome ou o título de uma nota. |

O `type` é `lesson` (lição), `do` (fazer), `dont` (não fazer) ou `history` (histórico).
Os resultados usam os mesmos nomes em inglês: `{"total": 1, "results": [{"id", "path", "type", "title", "project", "task", "epic", "url", "tags", "files", "date", "cost_usd", "links", "excerpt", "score"}]}`
(o `memory_related` junta `strength` e `reasons`, por exemplo `{"link": 1, "task": 1}`). Os campos vazios não aparecem.

## Usar

| Comando | O que faz |
|---|---|
| `agent-memory` | Abre a janela. |
| `agent-memory --browser` | Abre a mesma interface no browser. |
| `agent-memory add --type lesson --project p --title "..." --text "..." [--task ABC-123 --epic ABC-100 --url ... --tag ci --file a.py --link "Outra nota" --cost 1.25]` | Guarda uma nota. |
| `agent-memory search "texto" [--project p] [--type dont] [--task ABC-123] [--epic ABC-100] [--limit 10] [--json]` | Procura na linha de comandos. |
| `agent-memory reindex` | Reconstrói o índice a partir dos Markdown. |
| `agent-memory update [--check] [--force] [--version vX.Y.Z]` | Instala a versão mais recente. |
| `agent-memory selftest [--gui]` | Verifica a instalação. Com `--gui`, abre e fecha a janela. |
| `agent-memory language [pt\|en\|hi\|he]` | Mostra ou escolhe a língua. |
| `agent-memory mcp` | Servidor MCP (usado pelo Claude Code). |

Na janela, clica num nó para ver a nota. Usa `/` para procurar e `Esc` para fechar.
A procura mostra memórias, projetos e tarefas/épicos; escolhe um para o focar.
Os filtros escolhem projeto, épico, tarefa e período. A legenda filtra por tipo.
O botão de reprodução da linha temporal mostra o grafo a crescer.

No Windows, se o WebView2 faltar, a interface abre no browser, em `127.0.0.1`.
O terminal mostra o endereço da sessão (`http://127.0.0.1:<porta>/?t=<chave>`).
A chave é local e só vale enquanto a app está aberta.

## Atividade do Claude

O botão **Atividade do Claude**, no topo da coluna, mostra o que o Claude pediu à Agent Memory pelo MCP:

- quatro números: chamadas hoje, chamadas no total, chamadas por minuto (média dos últimos 10 minutos)
  e memórias recordadas (sem repetir);
- as últimas 100 memórias recordadas, com a hora, a ferramenta, o título, o projeto e a tarefa.
  Uma pesquisa sem resultados também aparece, com o texto procurado. Clica no título para abrir a memória.

A vista atualiza-se sozinha. Não separa por sessão.

O registo fica em `~/.agent-memory/.index/activity.sqlite`, no teu computador, separado do índice
(o `agent-memory reindex` não o apaga). O texto pesquisado passa pela mesma redação de segredos e é cortado.
Nunca guarda o conteúdo das notas. As linhas mais antigas saem sozinhas; o total de chamadas mantém-se.

## Línguas

A app fala português, inglês, hindi e hebraico. Por omissão, segue a língua do sistema:

- **macOS:** a primeira língua suportada em Definições › Geral › Idioma e região;
- **Windows:** a língua da interface do Windows;
- **outros:** `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` ou `LANG`.

Se nenhuma for suportada, usa inglês.
O seletor no topo da coluna muda a língua na hora e guarda a escolha em `~/.agent-memory/preferences.json`.
Na linha de comandos: `agent-memory language he`. A variável `AGENT_MEMORY_LANG` sobrepõe-se a tudo.

- O hebraico abre da direita para a esquerda. O texto de cada nota segue a sua própria direção.
- O hindi e o hebraico usam Noto Sans Devanagari e Noto Sans Hebrew, incluídas na app.
- As descrições das ferramentas MCP ficam em inglês, porque são lidas pelo modelo.
  O Claude responde na língua do participante.

## Onde ficam as memórias

Em `~/.agent-memory` (ou na pasta indicada por `AGENT_MEMORY_HOME`):

```text
~/.agent-memory/
  <projeto>/<AAAA-MM-DD>-<slug>.md   uma nota por ficheiro
  config.json                        URLs de atualização (opcional)
  .index/index-v2.sqlite             índice; pode ser apagado
  .index/activity.sqlite             registo das chamadas MCP (vista "Atividade do Claude")
  preferences.json                   língua escolhida no seletor
```

Cada nota tem um cabeçalho YAML. Os nomes dos campos são técnicos (em inglês) e fazem parte do contrato:

```markdown
---
type: lesson           # lesson (lição) | do (fazer) | dont (não fazer) | history (histórico)
title: Usar cache no build
project: security-arena
task: ARENA-12         # opcional: chave do ticket (ou dono/repo#12)
epic: ARENA-1          # opcional: épico ou pai
url: https://empresa.atlassian.net/browse/ARENA-12   # opcional
tags: [ci, cache]      # opcional
files: [orchestrator/plan.mjs]
date: '2026-10-16T13:25:33+01:00'
cost_usd: 1.25         # opcional
links: [Evitar retries]
---

O build fica 3x mais rápido com cache. Ver [[Evitar retries]].
```

Podes editar os ficheiros à mão. A app deteta as alterações.
`agent-memory reindex` reconstrói o índice a qualquer momento.
Os campos `epic`, `url` e `tags` são da v0.2 e opcionais: as notas da v0.1 continuam válidas.

Tickets:

- Chaves do Jira ficam em maiúsculas (`abc-123` → `ABC-123`); do GitHub, `dono/repo#12`.
- Sem `task`, a app tira-a do `url` quando é um ticket do Jira ou um issue/PR.
- Uma nota sem `epic` herda o épico da sua tarefa, se outra nota o indicar.
- Procurar `ABC-123` encontra as notas dessa tarefa, as do seu épico e as que a citam.

Força das ligações, da mais forte para a mais fraca:
ligação explícita (`[[...]]` ou `links`), mesma tarefa, mesmo épico, mesmo projeto, ficheiros em comum.

## Vindo da v0.4

Nada muda de sítio e nenhuma nota é reescrita. Os nomes antigos continuam a funcionar:

| Até à v0.4 | Desde a v0.5 |
|---|---|
| Comando `memoria` (e `memoria-gui`) | `agent-memory` (e `agent-memory-gui`); o `memoria` continua a funcionar |
| `procurar`, `lingua`, `--tipo`, `--titulo`, `--projeto`, `--texto`, `--tarefa`, `--epico`, `--etiqueta`, `--ficheiro`, `--ligacao`, `--custo`, `--limite`, `--verificar`, `--forcar`, `--versao` | `search`, `language`, `--type`, `--title`, `--project`, `--text`, `--task`, `--epic`, `--tag`, `--file`, `--link`, `--cost`, `--limit`, `--check`, `--force`, `--version` (os antigos continuam aceites) |
| Servidor MCP `memoria`: `memoria_procurar`, `memoria_adicionar`, `memoria_relacionadas` | Servidor MCP `agent-memory`: `memory_search`, `memory_add`, `memory_related` (os nomes antigos das ferramentas saíram) |
| `~/.memoria`, `MEMORIA_HOME` | `~/.agent-memory`, `AGENT_MEMORY_HOME`. Se `~/.memoria` existir e `~/.agent-memory` não, a app continua a usar `~/.memoria`. O `MEMORIA_HOME` continua a funcionar. |
| `MEMORIA_LANG`, `MEMORIA_SEM_UPDATE`, `MEMORIA_DOWNLOAD_TOKEN` | `AGENT_MEMORY_LANG`, `AGENT_MEMORY_NO_UPDATE`, `AGENT_MEMORY_DOWNLOAD_TOKEN` (os antigos continuam a funcionar) |
| Cabeçalho `tipo: licao`, `titulo`, `projeto`, `tarefa`, `epico`, `etiquetas`, `ficheiros`, `data`, `custo_usd`, `ligacoes` | `type: lesson`, `title`, `project`, `task`, `epic`, `tags`, `files`, `date`, `cost_usd`, `links`. As notas antigas são lidas como estão. |
| `.indice/`, `registo.sqlite`, `preferencias.json` | `.index/`, `activity.sqlite`, `preferences.json`. O registo antigo é copiado uma vez; a língua escolhida antes é lida. |
| `[REDIGIDO:…]` | `[REDACTED:…]` |

Para o Claude Code usar o nome MCP novo: `claude mcp remove --scope user memoria` e depois o `claude mcp add` acima.

## Atualizar

```bash
agent-memory update
```

1. Descobre a última versão com `git ls-remote --tags` (sem API).
2. Descarrega o wheel e o `constraints.txt` e verifica o `SHA256SUMS`.
3. Reinstala com `uv tool install --force`.
4. Reconstrói o índice. **Nunca toca nas notas.**

No Windows, a instalação termina numa janela nova. Fecha o Claude Code antes.

Na versão portátil, o update descarrega o zip novo, verifica-o e troca a pasta da app no mesmo sítio.
A ligação ao Claude Code continua válida.

Os URLs vêm de `~/.agent-memory/config.json` e, se faltarem, do `release.conf` do pacote.
Chaves lidas (uma variável de ambiente com o mesmo nome sobrepõe-se):

| Chave | Exemplo |
|---|---|
| `MEMORY_APP_REPO_URL` | `https://<servidor>/<dono>/claude-memory-app.git` |
| `RELEASE_DOWNLOAD_URL` | `{repo}/releases/download/{version}/{file}` |
| `PYTHON_VERSION` | `3.12` (opcional) |
| `UV` | caminho do executável `uv` (opcional) |

## Privacidade

- As notas, o índice e a interface ficam no teu computador.
- Antes de gravar, a app redige tokens, chaves de API (`sk-ant-…`, `ghp_…`, `AKIA…`, `xox…`),
  JWTs, chaves privadas e padrões como `password=…`.
- A interface só escuta em `127.0.0.1`, com um token de sessão aleatório.
- A única ligação à rede é a verificação de versões (`git ls-remote`) e o `agent-memory update`.
  Para a desligar: `AGENT_MEMORY_NO_UPDATE=1`.
- Não há embeddings nem modelos. A pesquisa é texto (SQLite FTS5).

## Problemas comuns

- **"O SQLite deste Python não tem FTS5"**: reinstala com o Python do uv
  (`uv tool install --force --managed-python --python 3.12 <wheel>`).
- **Proxy da empresa**: o uv e o `agent-memory update` usam `HTTPS_PROXY` e os certificados do sistema.
  Para o uv, define também `UV_SYSTEM_CERTS=1`.
- **A janela não abre**: `agent-memory --browser` abre a mesma interface no browser.

## Desenvolvimento

Precisas de `uv` e Node.js 22 ou mais recente.

```bash
uv sync
(cd web && npm ci && npm run build) && rm -rf src/memoria/web_dist && cp -R web/dist src/memoria/web_dist
uv run playwright install chromium
uv run pytest
```

- `scripts/build.sh`: UI, wheel, instaladores, zips portáteis e `SHA256SUMS` em `dist/`.
- `scripts/build_portatil.py`: os zips portáteis (`PORTATIL=0 scripts/build.sh` salta-os).
- `scripts/publish-release.sh`: tag, release e assets. As chamadas à API do alojamento
  estão só em `create_release()` (Gitea ou GitHub, por `RELEASE_PROVIDER`).
- `scripts/mudar-alojamento.sh`: muda o alojamento e a versão de uma vez.
- `scripts/lock.sh`: gera o `constraints.txt` e confirma que há wheels para Mac e Windows.
- `release.conf`: a única fonte dos URLs e versões.

Instruções para o Claude: [CLAUDE.md](CLAUDE.md) (em inglês). Estado, riscos e como publicar:
[docs/HANDOVER.pt.md](docs/HANDOVER.pt.md).
As versões seguem [SemVer](https://semver.org/lang/pt-PT/). Ver o [CHANGELOG](CHANGELOG.pt.md).

## Licença

MIT. Ver [LICENSE](LICENSE).
As letras Bricolage Grotesque, Noto Sans Devanagari e Noto Sans Hebrew vão incluídas na interface
com a licença SIL OFL 1.1 (`web/public/fonts/`).
