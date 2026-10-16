# Memória: instruções para o Claude

## O que é

App local que guarda as lições do Claude Code em ficheiros Markdown.
Mostra-as num grafo (janela nativa ou browser) e serve-as ao Claude Code por MCP (stdio).
Faz parte do kit do workshop "Orquestração de Agentes com Claude" (repositório `workshop-claude`).
Tudo fica no computador do participante. Estado, pendentes e riscos: [docs/HANDOVER.md](docs/HANDOVER.md).

## Estrutura

- `src/memoria/`: o pacote Python (3.12).
  - `store.py`: ficheiros Markdown e frontmatter (o contrato com o kit).
  - `index.py`: índice SQLite FTS5, arestas do grafo e pesquisa. `service.py` junta tudo.
  - `redact.py`: redação de segredos. `registo.py`: registo das chamadas MCP.
  - `mcp_server.py`: as 3 ferramentas MCP. `cli.py`: os comandos.
  - `webui.py`: API da UI e servidor em 127.0.0.1. `window.py`: janela pywebview ou browser.
  - `update.py` e `portatil.py`: `memoria update` (uv ou versão portátil). `selftest.py`.
  - `i18n.py` e `mensagens.py`: línguas da CLI e das mensagens. `config.py`: config.json e release.conf.
- `web/`: UI React + Vite. Catálogos em `web/src/locales/*.json`, ajudas em `web/src/i18n.jsx`.
  O build vai para `src/memoria/web_dist/` (no `.gitignore`; o wheel inclui-o).
- `portatil/`: modelos da versão portátil (`macos/`, `windows/`). Ver `docs/portatil.md`.
- `scripts/`: `build.sh`, `publish-release.sh`, `mudar-alojamento.sh` (alojamento e versão de uma vez),
  `render_installers.py`, `build_portatil.py`, `lock.sh`, `sign-macos.sh`.
- `install/`: `install.sh` e `install.ps1`. O bloco de configuração no topo é gerado.
- `release.conf`: URLs e versões. A única fonte.
- `tests/`: pytest. `test_browser.py` usa Playwright. `test_gui.py` abre a janela nativa (só macOS com ecrã).

## Correr e testar

```bash
uv sync
(cd web && npm ci && npm run build) && rm -rf src/memoria/web_dist && cp -R web/dist src/memoria/web_dist
uv run playwright install chromium
uv run pytest                 # sem ecrã ou fora do macOS: uv run pytest -m "not gui"
MEMORIA_HOME=$(mktemp -d) uv run memoria --browser
```

- Usa sempre um `MEMORIA_HOME` temporário. Os testes já o fazem (`tests/conftest.py`) e fixam `MEMORIA_LANG=pt`.
- Lint: `uvx ruff@0.14.0 check --select E,F,W,I,B --ignore B008,B904 --line-length 140 src tests scripts`.
- `scripts/lock.sh` regenera o `constraints.txt` e confirma que há wheels para Mac e Windows.

## Regras

- **`release.conf` é a única fonte de URLs e versões.** Nenhum URL do alojamento no código Python (há um teste).
  Depois de mudar o `release.conf`, corre `python3 scripts/render_installers.py --escrever`.
- **Uma só função fala com a API do alojamento:** `create_release()` em `scripts/publish-release.sh`.
  Os downloads usam sempre `{repo}/releases/download/{version}/{file}`.
- **Sem segredos.** Tudo o que se grava passa pelo `redact.redigir` (notas, edição na app, registo MCP).
  Nunca imprimir nem gravar tokens.
- **4 línguas: pt, en, hi, he.** Texto novo da UI vai para os 4 `web/src/locales/*.json` (`t('chave')`).
  Mensagens Python vão para `src/memoria/mensagens.py` (`t("chave")`).
  Localizar, não traduzir à letra. Termos técnicos ficam em inglês: MCP, token, prompt, agent, swarm,
  nomes das ferramentas, chaves de tickets. Hindi e hebraico no registo de quem programa.
  O hebraico é RTL: usar propriedades CSS lógicas (`inset-inline-*`, `text-align: start`).
  Os testes falham se faltar uma chave ou um marcador numa língua.
- **Descrições das ferramentas MCP em inglês** (são lidas pelo modelo). Nomes e parâmetros não mudam.
- **Design:** tokens do DESIGN.md do workshop (`web/src/styles.css`), cantos retos, sem sombras nem
  gradientes, Bricolage Grotesque local, cor de destaque só na ação principal.
- **SemVer.** Cada versão tem secção no `CHANGELOG.md`; o `build.sh` confirma.
- Docs e UI em português de Portugal, frases curtas.

## Contrato com o kit (não mudar sem avisar o workshop)

- Notas em `$MEMORIA_HOME/<pasta do projeto>/<AAAA-MM-DD>-<slug>.md`. `MEMORIA_HOME` por omissão: `~/.memoria`.
- Frontmatter: `tipo` (`licao` | `fazer` | `nao_fazer` | `historico`), `titulo`, `projeto`,
  `tarefa`?, `epico`?, `url`?, `etiquetas`?, `ficheiros: []`, `data` (ISO), `custo_usd`?, `ligacoes: []`.
  O corpo pode ter `[[nome]]`. Campos novos são sempre opcionais.
- Servidor MCP `memoria`, em stdio: `memoria mcp`.
  - `memoria_procurar(texto, projeto?, tipo?, tarefa?, epico?, limite=10)`
  - `memoria_adicionar(tipo, titulo, texto, projeto, tarefa?, epico?, url?, ficheiros?, ligacoes?, etiquetas?, custo_usd?)` devolve o caminho
  - `memoria_relacionadas(id_ou_caminho, limite=10)`
- Registo no Claude Code: `claude mcp add --scope user memoria -- <caminho absoluto do memoria> mcp`.
- `memoria selftest [--gui]`: código de saída 0 ok, 1 falhou, 3 sem janela nativa. O texto segue a língua.
- `$MEMORIA_HOME/config.json` (escrito pelo setup): `MEMORY_APP_REPO_URL`, `RELEASE_DOWNLOAD_URL`, opcionais `PYTHON_VERSION`, `UV`.
- Variáveis: `MEMORIA_HOME`, `MEMORIA_LANG`, `MEMORIA_SEM_UPDATE`, `MEMORIA_DOWNLOAD_TOKEN` (só em desenvolvimento).

## Releases

Passo a passo em [docs/HANDOVER.md](docs/HANDOVER.md#publicar-uma-versão).
Nunca publicar uma release sem o pedido explícito de quem gere o workshop.
