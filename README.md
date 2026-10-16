# Memória

A Memória guarda o que o Claude Code aprende, em ficheiros Markdown no teu computador.
Mostra essas notas num grafo e dá-as ao Claude Code por um servidor MCP.

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
curl -fsSL https://gitea.guilhermepinto.pt/guilherme/claude-memory-app/releases/download/v0.4.0/install.sh | sh
```

**Windows 10/11**, no PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://gitea.guilhermepinto.pt/guilherme/claude-memory-app/releases/download/v0.4.0/install.ps1 | iex"
```
<!-- <<< instalar -->

O instalador:

1. instala o [uv](https://docs.astral.sh/uv/) (versão fixada), se faltar;
2. descarrega o wheel e o `constraints.txt` e verifica o SHA-256;
3. instala a app com o Python 3.12 gerido pelo uv;
4. no Windows, instala o WebView2 Runtime (por utilizador), se faltar;
5. cria um atalho: `~/Applications/Memória.app` no Mac, "Memória" no menu Iniciar no Windows.

Os comandos ficam em `~/.local/bin` (Mac/Linux) ou `%USERPROFILE%\.local\bin` (Windows).

### Versão portátil (sem instalar)

Cada release traz também um zip por plataforma, com o Python lá dentro:

| Ficheiro | Abrir |
|---|---|
| `Memoria-<versão>-macos-arm64.zip` (Apple Silicon) | `Memoria.app` |
| `Memoria-<versão>-macos-x86_64.zip` (Intel) | `Memoria.app` |
| `Memoria-<versão>-windows-x64.zip` | `Memoria\Memoria.exe` |

Extrai e abre. Não precisa de admin nem de rede. O setup do workshop faz isto sozinho.

- Ligar ao Claude Code: `memoria selftest` mostra o comando `claude mcp add` certo.
  No Mac, `…/Memoria.app/Contents/MacOS/memoria selftest`; no Windows, `memoria.cmd selftest`.
- Instala com o comando de uma linha. Descarregar pelo browser exige aprovação em
  Definições do Sistema → Privacidade e Segurança: o Mac bloqueia a app (não tem assinatura).
  Desbloqueia no Terminal: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`.
  No Windows, em "O Windows protegeu o computador", clica em "Mais informações" e "Executar mesmo assim".
- Depois de ligar ao Claude Code, não movas a app.

Detalhes e decisões: [docs/portatil.md](docs/portatil.md).

## Ligar ao Claude Code

```bash
claude mcp add --scope user memoria -- "$HOME/.local/bin/memoria" mcp
```

No Windows: `claude mcp add --scope user memoria -- "%USERPROFILE%\.local\bin\memoria.exe" mcp`.

Ferramentas MCP:

| Ferramenta | Para quê |
|---|---|
| `memoria_procurar(texto, projeto?, tipo?, tarefa?, epico?, limite=10)` | Procura notas. Uma chave (`ABC-123`) traz a tarefa e o seu épico. |
| `memoria_adicionar(tipo, titulo, texto, projeto, tarefa?, epico?, url?, ficheiros?, ligacoes?, etiquetas?, custo_usd?)` | Guarda uma nota e devolve o caminho. |
| `memoria_relacionadas(id_ou_caminho, limite=10)` | Notas ligadas, da relação mais forte para a mais fraca. |

## Usar

| Comando | O que faz |
|---|---|
| `memoria` | Abre a janela. |
| `memoria --browser` | Abre a mesma interface no browser. |
| `memoria add --tipo licao --projeto p --titulo "..." --texto "..." [--tarefa ABC-123 --epico ABC-100 --url ...]` | Guarda uma nota. |
| `memoria procurar "texto" [--tarefa ABC-123] [--epico ABC-100]` | Procura na linha de comandos. |
| `memoria reindex` | Reconstrói o índice a partir dos Markdown. |
| `memoria update` | Instala a versão mais recente. |
| `memoria selftest [--gui]` | Verifica a instalação. Com `--gui`, abre e fecha a janela. |
| `memoria lingua [pt\|en\|hi\|he]` | Mostra ou escolhe a língua. |
| `memoria mcp` | Servidor MCP (usado pelo Claude Code). |

Na janela, clica num nó para ver a nota. Usa `/` para procurar e `Esc` para fechar.
A procura mostra memórias, projetos e tarefas/épicos; escolhe um para o focar.
Os filtros escolhem projeto, épico, tarefa e período. A legenda filtra por tipo.
O botão de reprodução da linha temporal mostra o grafo a crescer.

No Windows, se o WebView2 faltar, a interface abre no browser, em `127.0.0.1`.
O terminal mostra o endereço da sessão (`http://127.0.0.1:<porta>/?t=<chave>`).
A chave é local e só vale enquanto a app está aberta.

## Atividade do Claude

O botão **Atividade do Claude**, no topo da coluna, mostra o que o Claude pediu à Memória pelo MCP:

- quatro números: chamadas hoje, chamadas no total, chamadas por minuto (média dos últimos 10 minutos)
  e memórias recordadas (sem repetir);
- as últimas 100 memórias recordadas, com a hora, a ferramenta, o título, o projeto e a tarefa.
  Uma pesquisa sem resultados também aparece, com o texto procurado. Clica no título para abrir a memória.

A vista atualiza-se sozinha. Não separa por sessão.

O registo fica em `~/.memoria/.indice/registo.sqlite`, no teu computador, separado do índice
(o `memoria reindex` não o apaga). O texto pesquisado passa pela mesma redação de segredos e é cortado.
Nunca guarda o conteúdo das notas. As linhas mais antigas saem sozinhas; o total de chamadas mantém-se.

## Línguas

A app fala português, inglês, hindi e hebraico. Por omissão, segue a língua do sistema:

- **macOS:** a primeira língua suportada em Definições › Geral › Idioma e região;
- **Windows:** a língua da interface do Windows;
- **outros:** `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` ou `LANG`.

Se nenhuma for suportada, usa inglês.
O seletor no topo da coluna muda a língua na hora e guarda a escolha em `~/.memoria/preferencias.json`.
Na linha de comandos: `memoria lingua he`. A variável `MEMORIA_LANG` sobrepõe-se a tudo.

- O hebraico abre da direita para a esquerda. O texto de cada nota segue a sua própria direção.
- O hindi e o hebraico usam Noto Sans Devanagari e Noto Sans Hebrew, incluídas na app.
- As descrições das ferramentas MCP ficam em inglês, porque são lidas pelo modelo.
  O Claude responde na língua do participante.

## Onde ficam as memórias

Em `~/.memoria` (ou na pasta indicada por `MEMORIA_HOME`):

```text
~/.memoria/
  <projeto>/<AAAA-MM-DD>-<slug>.md   uma nota por ficheiro
  config.json                        URLs de atualização (opcional)
  .indice/memoria-v2.sqlite          índice; pode ser apagado
  .indice/registo.sqlite             registo das chamadas MCP (vista "Atividade do Claude")
  preferencias.json                  língua escolhida no seletor
```

Cada nota tem um cabeçalho YAML:

```markdown
---
tipo: licao            # licao | fazer | nao_fazer | historico
titulo: Usar cache no build
projeto: arena-de-seguranca
tarefa: ARENA-12       # opcional: chave do ticket (ou dono/repo#12)
epico: ARENA-1         # opcional: épico ou pai
url: https://empresa.atlassian.net/browse/ARENA-12   # opcional
etiquetas: [ci, cache] # opcional
ficheiros: [orquestrador/plan.mjs]
data: '2026-10-16T13:25:33+01:00'
custo_usd: 1.25        # opcional
ligacoes: [Evitar retries]
---

O build fica 3x mais rápido com cache. Ver [[Evitar retries]].
```

Podes editar os ficheiros à mão. A app deteta as alterações.
`memoria reindex` reconstrói o índice a qualquer momento.
Os campos `epico`, `url` e `etiquetas` são da v0.2 e opcionais: as notas da v0.1 continuam válidas.

Tickets:

- Chaves do Jira ficam em maiúsculas (`abc-123` → `ABC-123`); do GitHub, `dono/repo#12`.
- Sem `tarefa`, a app tira-a do `url` quando é um ticket do Jira ou um issue/PR.
- Uma nota sem `epico` herda o épico da sua tarefa, se outra nota o indicar.
- Procurar `ABC-123` encontra as notas dessa tarefa, as do seu épico e as que a citam.

Força das ligações, da mais forte para a mais fraca:
ligação explícita (`[[...]]` ou `ligacoes`), mesma tarefa, mesmo épico, mesmo projeto, ficheiros em comum.

## Atualizar

```bash
memoria update
```

1. Descobre a última versão com `git ls-remote --tags` (sem API).
2. Descarrega o wheel e o `constraints.txt` e verifica o `SHA256SUMS`.
3. Reinstala com `uv tool install --force`.
4. Reconstrói o índice. **Nunca toca nas notas.**

No Windows, a instalação termina numa janela nova. Fecha o Claude Code antes.

Na versão portátil, o update descarrega o zip novo, verifica-o e troca a pasta da app no mesmo sítio.
A ligação ao Claude Code continua válida.

Os URLs vêm de `~/.memoria/config.json` e, se faltarem, do `release.conf` do pacote.
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
- A única ligação à rede é a verificação de versões (`git ls-remote`) e o `memoria update`.
  Para a desligar: `MEMORIA_SEM_UPDATE=1`.
- Não há embeddings nem modelos. A pesquisa é texto (SQLite FTS5).

## Problemas comuns

- **"O SQLite deste Python não tem FTS5"**: reinstala com o Python do uv
  (`uv tool install --force --managed-python --python 3.12 <wheel>`).
- **Proxy da empresa**: o uv e o `memoria update` usam `HTTPS_PROXY` e os certificados do sistema.
  Para o uv, define também `UV_SYSTEM_CERTS=1`.
- **A janela não abre**: `memoria --browser` abre a mesma interface no browser.

## Desenvolvimento

Precisas de `uv` e Node.js 22 ou mais recente.

```bash
uv sync
(cd web && npm ci && npm run build) && cp -R web/dist src/memoria/web_dist
uv run pytest
```

- `scripts/build.sh`: UI, wheel, instaladores, zips portáteis e `SHA256SUMS` em `dist/`.
- `scripts/build_portatil.py`: os zips portáteis (`PORTATIL=0 scripts/build.sh` salta-os).
- `scripts/publish-release.sh`: tag, release e assets. As chamadas à API do alojamento
  estão só em `create_release()` (Gitea ou GitHub, por `RELEASE_PROVIDER`).
- `scripts/lock.sh`: gera o `constraints.txt` e confirma que há wheels para Mac e Windows.
- `release.conf`: a única fonte dos URLs e versões.

As versões seguem [SemVer](https://semver.org/lang/pt-PT/). Ver o [CHANGELOG](CHANGELOG.md).

## Licença

MIT. Ver [LICENSE](LICENSE).
As letras Bricolage Grotesque, Noto Sans Devanagari e Noto Sans Hebrew vão incluídas na interface
com a licença SIL OFL 1.1 (`web/public/fonts/`).
