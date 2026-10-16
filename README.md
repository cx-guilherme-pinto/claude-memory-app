# Memória

**English** · [Português](README.pt.md) · [हिन्दी](README.hi.md) · [עברית](README.he.md)

Memória keeps what Claude Code learns as Markdown files on your computer.
It shows those notes as a graph and gives them back to Claude Code through an MCP server.

- **Lessons**, rules (**do**, **don't**) and task **history**.
- Each note can be linked to a ticket (Jira, GitHub) and its epic.
- Fast search (SQLite FTS5) by name, project, ticket, epic, tags and text.
- A window with the graph, filters, a timeline, a form for new notes and Claude's MCP activity.
- In English, Portuguese, Hindi and Hebrew.
- Everything stays on your computer. Nothing is sent anywhere.

## Install

No administrator rights needed.

<!-- >>> instalar: gerado a partir de release.conf por scripts/render_installers.py -->
**macOS** (Intel and Apple Silicon) and Linux, in Terminal:

```bash
curl -fsSL https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.4.1/install.sh | sh
```

**Windows 10/11**, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.4.1/install.ps1 | iex"
```
<!-- <<< instalar -->

The installer:

1. installs [uv](https://docs.astral.sh/uv/) (pinned version) if it's missing;
2. downloads the wheel and `constraints.txt` and checks their SHA-256;
3. installs the app with the uv-managed Python 3.12;
4. on Windows, installs the WebView2 Runtime (per user) if it's missing;
5. creates a shortcut: `~/Applications/Memória.app` on Mac, "Memória" in the Start menu on Windows.

The commands go to `~/.local/bin` (Mac/Linux) or `%USERPROFILE%\.local\bin` (Windows).

### Portable version (no install)

Every release also has one zip per platform, with Python inside:

| File | Open |
|---|---|
| `Memoria-<version>-macos-arm64.zip` (Apple Silicon) | `Memoria.app` |
| `Memoria-<version>-macos-x86_64.zip` (Intel) | `Memoria.app` |
| `Memoria-<version>-windows-x64.zip` | `Memoria\Memoria.exe` |

Unzip and open. No admin rights and no network needed. The workshop setup does this for you.

- Connect it to Claude Code: `memoria selftest` prints the right `claude mcp add` command.
  On Mac, `…/Memoria.app/Contents/MacOS/memoria selftest`; on Windows, `memoria.cmd selftest`.
- Prefer the one-line install command. A zip downloaded in a browser needs approval in
  System Settings → Privacy & Security: macOS blocks the app because it isn't signed.
  To unblock it in Terminal: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`.
  On Windows, at "Windows protected your PC", click "More info" and then "Run anyway".
- Once it's connected to Claude Code, don't move the app.

Details and decisions: [docs/portatil.md](docs/portatil.md).

## Connect to Claude Code

```bash
claude mcp add --scope user memoria -- "$HOME/.local/bin/memoria" mcp
```

On Windows: `claude mcp add --scope user memoria -- "%USERPROFILE%\.local\bin\memoria.exe" mcp`.

MCP tools:

| Tool | Purpose |
|---|---|
| `memoria_procurar(texto, projeto?, tipo?, tarefa?, epico?, limite=10)` | Search notes. A ticket key (`ABC-123`) returns the task and its epic. |
| `memoria_adicionar(tipo, titulo, texto, projeto, tarefa?, epico?, url?, ficheiros?, ligacoes?, etiquetas?, custo_usd?)` | Save a note and return its path. |
| `memoria_relacionadas(id_ou_caminho, limite=10)` | Linked notes, strongest relation first. |

Tool and parameter names are in Portuguese and never change; their descriptions are in English.

## Use

| Command | What it does |
|---|---|
| `memoria` | Opens the window. |
| `memoria --browser` | Opens the same interface in the browser. |
| `memoria add --tipo licao --projeto p --titulo "..." --texto "..." [--tarefa ABC-123 --epico ABC-100 --url ...]` | Saves a note. |
| `memoria procurar "text" [--tarefa ABC-123] [--epico ABC-100]` | Searches from the command line. |
| `memoria reindex` | Rebuilds the index from the Markdown files. |
| `memoria update` | Installs the latest version. |
| `memoria selftest [--gui]` | Checks the installation. With `--gui`, opens and closes the window. |
| `memoria lingua [pt\|en\|hi\|he]` | Shows or sets the language. |
| `memoria mcp` | MCP server (used by Claude Code). |

In the window, click a node to see the note. Press `/` to search and `Esc` to close.
Search shows memories, projects and tasks/epics; pick one to focus it.
Filters choose the project, epic, task and period. The type list filters the map.
The timeline's play button shows the graph growing.

On Windows, if WebView2 is missing, the interface opens in the browser at `127.0.0.1`.
The terminal prints the session address (`http://127.0.0.1:<port>/?t=<key>`).
The key is local and only works while the app is open.

## Claude activity

The **Claude activity** button at the top of the column shows what Claude asked Memória for over MCP:

- four numbers: calls today, total calls, calls per minute (average of the last 10 minutes)
  and memories recalled (unique);
- the last 100 recalled memories, with time, tool, title, project and task.
  A search with no results also shows up, with what was searched. Click a title to open the memory.

The view refreshes on its own. It isn't split by session.

The log lives in `~/.memoria/.indice/registo.sqlite`, on your computer, separate from the index
(`memoria reindex` keeps it). The searched text goes through the same secret redaction and is cut short.
Note contents are never logged. Old rows are dropped automatically; the total call count is kept.

## Languages

The app speaks English, Portuguese, Hindi and Hebrew. By default it follows the system language:

- **macOS:** the first supported language in System Settings › General › Language & Region;
- **Windows:** the Windows display language;
- **others:** `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` or `LANG`.

If none is supported, it uses English.
The picker at the top of the column switches the language at once and saves it in `~/.memoria/preferencias.json`.
From the command line: `memoria lingua he`. The `MEMORIA_LANG` variable overrides everything.

- Hebrew opens right to left. Each note's text keeps its own direction.
- Hindi and Hebrew use Noto Sans Devanagari and Noto Sans Hebrew, bundled with the app.
- Technical terms stay in English in every language (MCP, token, ticket, tool names).

## Where memories live

In `~/.memoria` (or the folder set in `MEMORIA_HOME`):

```text
~/.memoria/
  <project>/<YYYY-MM-DD>-<slug>.md   one note per file
  config.json                        update URLs (optional)
  .indice/memoria-v2.sqlite          index; safe to delete
  .indice/registo.sqlite             MCP call log ("Claude activity" view)
  preferencias.json                  language chosen in the picker
```

Each note has a YAML header. The field names are Portuguese and are part of the contract:

```markdown
---
tipo: licao            # licao (lesson) | fazer (do) | nao_fazer (don't) | historico (history)
titulo: Use the build cache
projeto: arena-de-seguranca
tarefa: ARENA-12       # optional: ticket key (or owner/repo#12)
epico: ARENA-1         # optional: epic or parent
url: https://company.atlassian.net/browse/ARENA-12   # optional
etiquetas: [ci, cache] # optional: tags
ficheiros: [orquestrador/plan.mjs]
data: '2026-10-16T13:25:33+01:00'
custo_usd: 1.25        # optional
ligacoes: [Avoid retries]
---

The build is 3x faster with the cache. See [[Avoid retries]].
```

You can edit the files by hand. The app picks up the changes.
`memoria reindex` rebuilds the index at any time.
`epico`, `url` and `etiquetas` came in v0.2 and are optional: v0.1 notes are still valid.

Tickets:

- Jira keys are upper-cased (`abc-123` → `ABC-123`); GitHub keys look like `owner/repo#12`.
- Without `tarefa`, the app takes it from `url` when it's a Jira ticket or an issue/PR.
- A note without `epico` inherits its task's epic, if another note names it.
- Searching `ABC-123` finds that task's notes, its epic's notes and notes that mention it.

Link strength, strongest first:
explicit link (`[[...]]` or `ligacoes`), same task, same epic, same project, shared files.

## Update

```bash
memoria update
```

1. Finds the latest version with `git ls-remote --tags` (no API).
2. Downloads the wheel and `constraints.txt` and checks `SHA256SUMS`.
3. Reinstalls with `uv tool install --force`.
4. Rebuilds the index. **It never touches your notes.**

On Windows, the install finishes in a new window. Close Claude Code first.

In the portable version, update downloads the new zip, checks it and swaps the app folder in place.
The connection to Claude Code keeps working.

URLs come from `~/.memoria/config.json` and, if missing, from the package's `release.conf`.
Keys read (an environment variable with the same name overrides them):

| Key | Example |
|---|---|
| `MEMORY_APP_REPO_URL` | `https://<server>/<owner>/claude-memory-app.git` |
| `RELEASE_DOWNLOAD_URL` | `{repo}/releases/download/{version}/{file}` |
| `PYTHON_VERSION` | `3.12` (optional) |
| `UV` | path to the `uv` executable (optional) |

## Privacy

- Notes, the index and the interface stay on your computer.
- Before saving, the app redacts tokens, API keys (`sk-ant-…`, `ghp_…`, `AKIA…`, `xox…`),
  JWTs, private keys and patterns like `password=…`.
- The interface only listens on `127.0.0.1`, with a random session key.
- The only network use is the version check (`git ls-remote`) and `memoria update`.
  To turn it off: `MEMORIA_SEM_UPDATE=1`.
- No embeddings and no models. Search is plain text (SQLite FTS5).

## Troubleshooting

- **"This Python's SQLite has no FTS5"**: reinstall with uv's Python
  (`uv tool install --force --managed-python --python 3.12 <wheel>`).
- **Company proxy**: uv and `memoria update` use `HTTPS_PROXY` and the system certificates.
  For uv, also set `UV_SYSTEM_CERTS=1`.
- **The window doesn't open**: `memoria --browser` opens the same interface in the browser.

## Development

You need `uv` and Node.js 22 or newer.

```bash
uv sync
(cd web && npm ci && npm run build) && rm -rf src/memoria/web_dist && cp -R web/dist src/memoria/web_dist
uv run playwright install chromium
uv run pytest
```

- `scripts/build.sh`: UI, wheel, installers, portable zips and `SHA256SUMS` in `dist/`.
- `scripts/build_portatil.py`: the portable zips (`PORTATIL=0 scripts/build.sh` skips them).
- `scripts/publish-release.sh`: tag, release and assets. Calls to the hosting API
  live only in `create_release()` (Gitea or GitHub, from `RELEASE_PROVIDER`).
- `scripts/mudar-alojamento.sh`: changes the hosting and the version in one go.
- `scripts/lock.sh`: regenerates `constraints.txt` and checks there are wheels for Mac and Windows.
- `release.conf`: the single source of URLs and versions.

Instructions for Claude: [CLAUDE.md](CLAUDE.md). Status, risks and how to publish: [docs/HANDOVER.md](docs/HANDOVER.md).
Versions follow [SemVer](https://semver.org/). See the [CHANGELOG](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
The Bricolage Grotesque, Noto Sans Devanagari and Noto Sans Hebrew fonts ship with the interface
under the SIL Open Font License 1.1 (`web/public/fonts/`).
