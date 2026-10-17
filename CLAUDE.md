# Agent Memory: instructions for Claude

## What it is

A local app that stores Claude Code's lessons as Markdown files.
It shows them as a graph (native window or browser) and serves them to Claude Code over MCP (stdio).
It's part of the workshop kit "Orquestração de Agentes com Claude" (repository `workshop-claude`).
Everything stays on the participant's computer. Status, open work and risks: [docs/HANDOVER.md](docs/HANDOVER.md).

Code, internal identifiers and code comments are in Portuguese (European). Everything a user or Claude Code
sees is in English or translated: commands, options, MCP names and results, note headers, file and folder names
(since v0.5; the old Portuguese names are accepted as aliases). Docs are English first,
with translations next to them (`*.pt.md`, and the READMEs also in Hindi and Hebrew).

## Layout

- `src/memoria/`: the Python package (3.12).
  - `store.py`: Markdown files and frontmatter (the contract with the kit).
  - `index.py`: SQLite FTS5 index, graph edges and search. `service.py` ties them together.
  - `redact.py`: secret redaction. `registo.py`: MCP call log.
  - `mcp_server.py`: the 3 MCP tools. `cli.py`: the commands.
  - `webui.py`: UI API and server on 127.0.0.1. `window.py`: pywebview window or browser.
  - `update.py` and `portatil.py`: `agent-memory update` (uv or portable). `selftest.py`.
  - `i18n.py` and `mensagens.py`: languages for the CLI and messages. `config.py`: config.json and release.conf.
- `web/`: React + Vite UI. Catalogs in `web/src/locales/*.json`, helpers in `web/src/i18n.jsx`.
  The build goes to `src/memoria/web_dist/` (in `.gitignore`; the wheel includes it).
- `portatil/`: templates for the portable version (`macos/`, `windows/`). See `docs/portatil.md`.
- `scripts/`: `build.sh`, `publish-release.sh`, `mudar-alojamento.sh` (hosting and version in one go),
  `render_installers.py`, `build_portatil.py`, `lock.sh`, `sign-macos.sh`.
- `install/`: `install.sh` and `install.ps1`. The config block at the top is generated.
- `release.conf`: URLs and versions. The single source.
- `tests/`: pytest. `test_browser.py` uses Playwright. `test_gui.py` opens the native window (macOS with a display only).

## Run and test

```bash
uv sync
(cd web && npm ci && npm run build) && rm -rf src/memoria/web_dist && cp -R web/dist src/memoria/web_dist
uv run playwright install chromium
uv run pytest                 # no display or not macOS: uv run pytest -m "not gui"
AGENT_MEMORY_HOME=$(mktemp -d) uv run agent-memory --browser
```

- Always use a temporary `AGENT_MEMORY_HOME`. The tests already do (`tests/conftest.py`) and pin `AGENT_MEMORY_LANG=pt`.
- Lint: `uvx ruff@0.14.0 check --select E,F,W,I,B --ignore B008,B904 --line-length 140 src tests scripts`.
- `scripts/lock.sh` regenerates `constraints.txt` and checks there are wheels for Mac and Windows.

## Rules

- **`release.conf` is the single source of URLs and versions.** No hosting URL in the Python code (a test checks).
  After changing `release.conf`, run `python3 scripts/render_installers.py --escrever`
  (it rewrites the generated blocks in `install/*` and in every `README*.md`).
- **Only one function talks to the hosting API:** `create_release()` in `scripts/publish-release.sh`.
  Downloads always use `{repo}/releases/download/{version}/{file}`.
- **No secrets.** Everything written goes through `redact.redigir` (notes, in-app edits, MCP log).
  Never print or store tokens.
- **4 app languages: pt, en, hi, he.** New UI text goes into all 4 `web/src/locales/*.json` (`t('key')`).
  Python messages go into `src/memoria/mensagens.py` (`t("key")`).
  Localize, don't translate word for word. Technical terms stay in English: MCP, token, prompt, agent,
  swarm, tool names, ticket keys. Hindi and Hebrew in a developer's register.
  Hebrew is RTL: use logical CSS properties (`inset-inline-*`, `text-align: start`).
  Tests fail if a key or a placeholder is missing in any language.
- **Docs:** English first. Keep the Portuguese file next to it in sync (`README.pt.md`, `CHANGELOG.pt.md`,
  `docs/*.pt.md`). The READMEs also exist in Hindi and Hebrew. Short sentences.
- **MCP in English**: tool names, parameters, results and descriptions (the model reads them). They don't change without telling the workshop.
- **No Portuguese in the English path.** Anything new that a user or Claude Code sees (output, file names, keys) is English
  or goes through `t()`. Internal names may stay Portuguese. `tests/test_browser.py::test_ingles_sem_portugues` checks the UI.
- **Design:** workshop DESIGN.md tokens (`web/src/styles.css`), square corners, no shadows or gradients,
  bundled Bricolage Grotesque, accent color only on the primary action.
- **SemVer.** Every version has a section in `CHANGELOG.md` (English; the release notes come from it)
  and in `CHANGELOG.pt.md`. `build.sh` checks `CHANGELOG.md`.

## Contract with the kit (don't change without telling the workshop)

- Data folder: `AGENT_MEMORY_HOME`; else the old `MEMORIA_HOME`; else `~/.memoria` if it exists and `~/.agent-memory`
  doesn't (nothing is ever moved); else `~/.agent-memory`.
- Notes in `<data folder>/<project folder>/<YYYY-MM-DD>-<slug>.md`.
- Frontmatter written by v0.5: `type` (`lesson` | `do` | `dont` | `history`), `title`, `project`,
  `task`?, `epic`?, `url`?, `tags`?, `files: []`, `date` (ISO), `cost_usd`?, `links: []`.
  Old notes (`tipo: licao|fazer|nao_fazer|historico`, `titulo`, `projeto`, `tarefa`, `epico`, `etiquetas`, `ficheiros`,
  `data`, `custo_usd`, `ligacoes`) are still read. The body may contain `[[name]]`. New fields are always optional.
- MCP server `agent-memory`, over stdio: `agent-memory mcp`.
  - `memory_search(text?, project?, task?, epic?, type?, limit=10)` returns `{total, results: [...]}`
  - `memory_add(type, title, text, project, task?, epic?, url?, tags?, files?, links?, cost_usd?)` returns the path
  - `memory_related(ref, limit=10)` returns `{total, results: [...]}` with `strength` and `reasons`
  - result keys: `id`, `path`, `type`, `title`, `project`, `task`, `epic`, `url`, `tags`, `files`, `date`, `cost_usd`,
    `links`, `excerpt`, `score` (empty ones are left out). The old `memoria_*` tools are not exposed.
- Registration in Claude Code: `claude mcp add --scope user agent-memory -- <absolute path to agent-memory> mcp`.
- Commands: `agent-memory` (and the old `memoria`), `agent-memory-gui` (and `memoria-gui`). The wheel and the uv tool
  keep the name `memoria` (`memoria-<version>-py3-none-any.whl`).
- `agent-memory selftest [--gui]`: exit code 0 ok, 1 failed, 3 no native window. The text follows the language.
  The first line is `Agent Memory <version> · Python <version> · <system>`.
- `<data folder>/config.json` (written by the setup): `MEMORY_APP_REPO_URL`, `RELEASE_DOWNLOAD_URL`, optional `PYTHON_VERSION`, `UV`.
- Variables: `AGENT_MEMORY_HOME`, `AGENT_MEMORY_LANG`, `AGENT_MEMORY_NO_UPDATE`, `AGENT_MEMORY_DOWNLOAD_TOKEN`
  (development only). The old `MEMORIA_*` names still work; the new ones win.

## Releases

Step by step in [docs/HANDOVER.md](docs/HANDOVER.md#publishing-a-version).
Never publish a release without an explicit request from whoever runs the workshop.
