# Agent Memory

**English** · [Português](README.pt.md) · [हिन्दी](README.hi.md) · [עברית](README.he.md)

Agent Memory keeps what Claude Code learns as Markdown files on your computer.
It shows those notes as a graph and gives them back to Claude Code through an MCP server.

Until v0.4 the app was called *Memória*. Since v0.5 the names are in English too: the `agent-memory` command,
the `agent-memory` MCP server with the `memory_search`, `memory_add` and `memory_related` tools, and the `~/.agent-memory` folder.
The old names still work (see [Coming from v0.4](#coming-from-v04)).

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
curl -fsSL https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.5.0/install.sh | sh
```

**Windows 10/11**, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.5.0/install.ps1 | iex"
```
<!-- <<< instalar -->

The installer:

1. installs [uv](https://docs.astral.sh/uv/) (pinned version) if it's missing;
2. downloads the wheel and `constraints.txt` and checks their SHA-256;
3. installs the app with the uv-managed Python 3.12;
4. on Windows, installs the WebView2 Runtime (per user) if it's missing;
5. creates a shortcut: `~/Applications/Agent Memory.app` on Mac, "Agent Memory" in the Start menu on Windows.

The commands go to `~/.local/bin` (Mac/Linux) or `%USERPROFILE%\.local\bin` (Windows).

### Portable version (no install)

Every release also has one zip per platform, with Python inside:

| File | Open |
|---|---|
| `Memoria-<version>-macos-arm64.zip` (Apple Silicon) | `Memoria.app` |
| `Memoria-<version>-macos-x86_64.zip` (Intel) | `Memoria.app` |
| `Memoria-<version>-windows-x64.zip` | `Memoria\Memoria.exe` |

Unzip and open. No admin rights and no network needed. The workshop setup does this for you.

- Connect it to Claude Code: `selftest` prints the right `claude mcp add` command.
  On Mac, `…/Memoria.app/Contents/MacOS/memoria selftest` (the portable app keeps its old file name and shows as Agent Memory);
  on Windows, `agent-memory.cmd selftest`. After the one-line install, it's just `agent-memory selftest`.
- Prefer the one-line install command. A zip downloaded in a browser needs approval in
  System Settings → Privacy & Security: macOS blocks the app because it isn't signed.
  To unblock it in Terminal: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`.
  On Windows, at "Windows protected your PC", click "More info" and then "Run anyway".
- Once it's connected to Claude Code, don't move the app.
- The zips, the app folder and its launchers keep the `Memoria` name: older portable copies can still update in place.

Details and decisions: [docs/portatil.md](docs/portatil.md).

## Connect to Claude Code

```bash
claude mcp add --scope user agent-memory -- "$HOME/.local/bin/agent-memory" mcp
```

On Windows: `claude mcp add --scope user agent-memory -- "%USERPROFILE%\.local\bin\agent-memory.exe" mcp`.

MCP tools (in Claude Code: `mcp__agent-memory__memory_search` and so on):

| Tool | Purpose |
|---|---|
| `memory_search(text?, project?, task?, epic?, type?, limit=10)` | Search notes. A ticket key (`ABC-123`) returns the task and its epic. Empty `text` returns the latest. |
| `memory_add(type, title, text, project, task?, epic?, url?, tags?, files?, links?, cost_usd?)` | Save a note and return its path. |
| `memory_related(ref, limit=10)` | Linked notes, strongest relation first. `ref` is the path `memory_add` returned, or a note id, name or title. |

`type` is `lesson`, `do`, `dont` or `history`.
Results use the same English names: `{"total": 1, "results": [{"id", "path", "type", "title", "project", "task", "epic", "url", "tags", "files", "date", "cost_usd", "links", "excerpt", "score"}]}`
(`memory_related` adds `strength` and `reasons`, for example `{"link": 1, "task": 1}`). Empty fields are left out.

## Use

| Command | What it does |
|---|---|
| `agent-memory` | Opens the window. |
| `agent-memory --browser` | Opens the same interface in the browser. |
| `agent-memory add --type lesson --project p --title "..." --text "..." [--task ABC-123 --epic ABC-100 --url ... --tag ci --file a.py --link "Other note" --cost 1.25]` | Saves a note. |
| `agent-memory search "text" [--project p] [--type dont] [--task ABC-123] [--epic ABC-100] [--limit 10] [--json]` | Searches from the command line. |
| `agent-memory reindex` | Rebuilds the index from the Markdown files. |
| `agent-memory update [--check] [--force] [--version vX.Y.Z]` | Installs the latest version. |
| `agent-memory selftest [--gui]` | Checks the installation. With `--gui`, opens and closes the window. |
| `agent-memory language [pt\|en\|hi\|he]` | Shows or sets the language. |
| `agent-memory mcp` | MCP server (used by Claude Code). |

In the window, click a node to see the note. Press `/` to search and `Esc` to close.
Search shows memories, projects and tasks/epics; pick one to focus it.
Filters choose the project, epic, task and period. The type list filters the map.
The timeline's play button shows the graph growing.

On Windows, if WebView2 is missing, the interface opens in the browser at `127.0.0.1`.
The terminal prints the session address (`http://127.0.0.1:<port>/?t=<key>`).
The key is local and only works while the app is open.

## Claude activity

The **Claude activity** button at the top of the column shows what Claude asked Agent Memory for over MCP:

- four numbers: calls today, total calls, calls per minute (average of the last 10 minutes)
  and memories recalled (unique);
- the last 100 recalled memories, with time, tool, title, project and task.
  A search with no results also shows up, with what was searched. Click a title to open the memory.

The view refreshes on its own. It isn't split by session.

The log lives in `~/.agent-memory/.index/activity.sqlite`, on your computer, separate from the index
(`agent-memory reindex` keeps it). The searched text goes through the same secret redaction and is cut short.
Note contents are never logged. Old rows are dropped automatically; the total call count is kept.

## Languages

The app speaks English, Portuguese, Hindi and Hebrew. By default it follows the system language:

- **macOS:** the first supported language in System Settings › General › Language & Region;
- **Windows:** the Windows display language;
- **others:** `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` or `LANG`.

If none is supported, it uses English.
The picker at the top of the column switches the language at once and saves it in `~/.agent-memory/preferences.json`.
From the command line: `agent-memory language he`. The `AGENT_MEMORY_LANG` variable overrides everything.

- Hebrew opens right to left. Each note's text keeps its own direction.
- Hindi and Hebrew use Noto Sans Devanagari and Noto Sans Hebrew, bundled with the app.
- Technical terms stay in English in every language (MCP, token, ticket, tool names).

## Where memories live

In `~/.agent-memory` (or the folder set in `AGENT_MEMORY_HOME`):

```text
~/.agent-memory/
  <project>/<YYYY-MM-DD>-<slug>.md   one note per file
  config.json                        update URLs (optional)
  .index/index-v3.sqlite             index; safe to delete
  .index/activity.sqlite             MCP call log ("Claude activity" view)
  preferences.json                   language chosen in the picker
```

Each note has a YAML header. The field names are part of the contract:

```markdown
---
type: lesson           # lesson | do | dont | history
title: Use the build cache
project: security-arena
task: ARENA-12         # optional: ticket key (or owner/repo#12)
epic: ARENA-1          # optional: epic or parent
url: https://company.atlassian.net/browse/ARENA-12   # optional
tags: [ci, cache]      # optional
files: [orchestrator/plan.mjs]
date: '2026-10-16T13:25:33+01:00'
cost_usd: 1.25         # optional
links: [Avoid retries]
---

The build is 3x faster with the cache. See [[Avoid retries]].
```

You can edit the files by hand. The app picks up the changes.
`agent-memory reindex` rebuilds the index at any time.
`epic`, `url` and `tags` came in v0.2 and are optional: v0.1 notes are still valid.

Tickets:

- Jira keys are upper-cased (`abc-123` → `ABC-123`); GitHub keys look like `owner/repo#12`.
- Without `task`, the app takes it from `url` when it's a Jira ticket or an issue/PR.
- A note without `epic` inherits its task's epic, if another note names it.
- Searching `ABC-123` finds that task's notes, its epic's notes and notes that mention it.

Link strength, strongest first:
explicit link (`[[...]]` or `links`), same task, same epic, same project, shared files.

## Coming from v0.4

Nothing moves and nothing is rewritten. The old names keep working:

| Until v0.4 | Since v0.5 |
|---|---|
| `memoria` command (and `memoria-gui`) | `agent-memory` (and `agent-memory-gui`); `memoria` still works |
| `procurar`, `lingua`, `--tipo`, `--titulo`, `--projeto`, `--texto`, `--tarefa`, `--epico`, `--etiqueta`, `--ficheiro`, `--ligacao`, `--custo`, `--limite`, `--verificar`, `--forcar`, `--versao` | `search`, `language`, `--type`, `--title`, `--project`, `--text`, `--task`, `--epic`, `--tag`, `--file`, `--link`, `--cost`, `--limit`, `--check`, `--force`, `--version` (the old ones are still accepted) |
| MCP server `memoria`: `memoria_procurar`, `memoria_adicionar`, `memoria_relacionadas` | MCP server `agent-memory`: `memory_search`, `memory_add`, `memory_related` (the old tool names are gone) |
| `~/.memoria`, `MEMORIA_HOME` | `~/.agent-memory`, `AGENT_MEMORY_HOME`. If `~/.memoria` exists and `~/.agent-memory` doesn't, the app keeps using `~/.memoria`. `MEMORIA_HOME` still works. |
| `MEMORIA_LANG`, `MEMORIA_SEM_UPDATE`, `MEMORIA_DOWNLOAD_TOKEN` | `AGENT_MEMORY_LANG`, `AGENT_MEMORY_NO_UPDATE`, `AGENT_MEMORY_DOWNLOAD_TOKEN` (the old ones still work) |
| Header `tipo: licao`, `titulo`, `projeto`, `tarefa`, `epico`, `etiquetas`, `ficheiros`, `data`, `custo_usd`, `ligacoes` | `type: lesson`, `title`, `project`, `task`, `epic`, `tags`, `files`, `date`, `cost_usd`, `links`. Old notes are read as they are. |
| `.indice/`, `registo.sqlite`, `preferencias.json` | `.index/`, `activity.sqlite`, `preferences.json`. The old activity log is copied once; the old language choice is read. |
| `[REDIGIDO:…]` | `[REDACTED:…]` |

To use the new MCP name in Claude Code: `claude mcp remove --scope user memoria`, then the `claude mcp add` above.

## Update

```bash
agent-memory update
```

1. Finds the latest version with `git ls-remote --tags` (no API).
2. Downloads the wheel and `constraints.txt` and checks `SHA256SUMS`.
3. Reinstalls with `uv tool install --force`.
4. Rebuilds the index. **It never touches your notes.**

On Windows, the install finishes in a new window. Close Claude Code first.

In the portable version, update downloads the new zip, checks it and swaps the app folder in place.
The connection to Claude Code keeps working.

URLs come from `~/.agent-memory/config.json` and, if missing, from the package's `release.conf`.
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
- The only network use is the version check (`git ls-remote`) and `agent-memory update`.
  To turn it off: `AGENT_MEMORY_NO_UPDATE=1`.
- No embeddings and no models. Search is plain text (SQLite FTS5).

## Troubleshooting

- **"This Python's SQLite has no FTS5"**: reinstall with uv's Python
  (`uv tool install --force --managed-python --python 3.12 <wheel>`).
- **Company proxy**: uv and `agent-memory update` use `HTTPS_PROXY` and the system certificates.
  For uv, also set `UV_SYSTEM_CERTS=1`.
- **The window doesn't open**: `agent-memory --browser` opens the same interface in the browser.
- **"The search index of your memories is damaged"**: the app rebuilds the index from the notes by itself.
  If the message stays (on Windows, another process still has the file open), close Claude Code and the app,
  then run `agent-memory reindex`. The notes are never touched.
- **"Warning: memory skipped"**: a note the app can't read (an error in the YAML header, not UTF-8, outside a
  project folder, a symlink to outside the folder). Fix the file: the app picks it up by itself.

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
