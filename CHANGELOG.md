# Changelog

**English** · [Português](CHANGELOG.pt.md)

All notable changes are listed here. Versions follow [SemVer](https://semver.org/).

## [0.5.0] - 2026-10-17

### Changed

- The app is now called **Agent Memory** in every language (window, page title, menus, messages, shortcuts and docs). It was *Memória* until v0.4.
- The installers create `~/Applications/Agent Memory.app` (Mac) and "Agent Memory" in the Start menu (Windows), and remove the old *Memória* shortcut.
- **Technical names in English**, so that an English workshop shows no Portuguese word:
  - command `agent-memory` (and `agent-memory-gui`), with `search` and `language` and the options
    `--type`, `--title`, `--project`, `--text`, `--task`, `--epic`, `--tag`, `--file`, `--link`, `--cost`, `--limit`,
    and `update --check/--force/--version`;
  - MCP server `agent-memory` with the tools `memory_search(text?, project?, task?, epic?, type?, limit)`,
    `memory_add(type, title, text, project, task?, epic?, url?, tags?, files?, links?, cost_usd?)` and
    `memory_related(ref, limit)`. Results use English keys (`results`, `path`, `title`, `type`, `task`, `excerpt`,
    `score`, `strength`, `reasons`, ...). The instructions for the model use the new names;
  - types `lesson`, `do`, `dont` and `history`;
  - new notes are written with an English header (`type`, `title`, `project`, `task`, `epic`, `url`, `tags`,
    `files`, `date`, `cost_usd`, `links`);
  - data folder `~/.agent-memory` (`AGENT_MEMORY_HOME`), with `.index/index-v2.sqlite`, `.index/activity.sqlite`
    and `preferences.json`;
  - variables `AGENT_MEMORY_LANG`, `AGENT_MEMORY_NO_UPDATE` and `AGENT_MEMORY_DOWNLOAD_TOKEN`;
  - the redaction mark is `[REDACTED:<kind>]`;
  - the portable Windows zip has `agent-memory.cmd` and `README.pt.txt` (was `LEIA-ME.txt`).
- The web server's error answers are in English (`{"error": "not found"}`).

### Compatibility

Nothing moves and no note is rewritten:

- `memoria` (and `memoria-gui`) still work, and so do `procurar`, `lingua` and the Portuguese options (`--tipo`, `--projeto`, `--verificar`, ...). They don't show in the help.
- If `~/.memoria` exists and `~/.agent-memory` doesn't, the app keeps using `~/.memoria`. `MEMORIA_HOME`, `MEMORIA_LANG`, `MEMORIA_SEM_UPDATE` and `MEMORIA_DOWNLOAD_TOKEN` still work (the new names win).
- Notes with the old Portuguese header (`tipo: licao`, `titulo`, `projeto`, `tarefa`, ...) are read as they are. The type filters accept both names.
- The old activity log (`.indice/registo.sqlite`) is copied once, never moved; old rows show the new tool names. The language saved in `preferencias.json` is read.
- The old MCP tool names (`memoria_procurar`, `memoria_adicionar`, `memoria_relacionadas`) are **gone**: the kit's skills use the new ones. Re-register the server as `agent-memory` (`claude mcp remove --scope user memoria`, then `claude mcp add --scope user agent-memory -- <agent-memory> mcp`).
- The wheel (`memoria-<version>-py3-none-any.whl`), the uv tool name (`memoria`), the Python package and the portable zips and folders (`Memoria-…zip`, `Memoria.app`, `Memoria\Memoria.exe`) keep their names, so installs and updates keep working.

## [0.4.1] - 2026-10-16

### Changed

- Published on github.com.

## [0.4.0] - 2026-10-16

### Added

- **Claude activity** view: what Claude called over MCP. Four numbers (calls today, total calls,
  calls per minute and unique memories recalled) and the last 100 recalled memories, with time, tool,
  title, project and task. Clicking opens the memory on the map. It refreshes on its own.
- Local, capped log of MCP calls in `$MEMORIA_HOME/.indice/registo.sqlite`.
  The searched text is redacted and cut short; note contents are never logged. `reindex` keeps it.

### Changed

- Hindi and Hebrew reworded in a developer's register: technical terms stay in English
  (tokens, MCP, ticket, version, etc.), the way people actually say them.

## [0.3.0] - 2026-10-16

### Added

- Languages: Portuguese, English, Hindi and Hebrew. The app follows the system language
  (macOS: AppleLanguages; Windows: display language; fallback: English).
- Language picker at the top of the column; the choice is saved in `$MEMORIA_HOME/preferencias.json`.
  `memoria lingua [pt|en|hi|he]` does the same from the command line. `MEMORIA_LANG` overrides it.
- Hebrew runs right to left; each note's content keeps its own direction.
- Noto Sans Devanagari and Noto Sans Hebrew (OFL), bundled, for Hindi and Hebrew.
- Command-line, selftest, update and error messages in all four languages.

### Changed

- MCP tool descriptions and server instructions are now in English (the model reads them).
  Tool and parameter names don't change.
- Selftest text follows the app language. The result is still the exit code.

## [0.2.3] - 2026-10-16

### Added

- Edit a memory inside the app: the "Edit" button in the panel opens the Markdown file
  (header and text) in an editor in the window. Save with the button or ⌘S / Ctrl+S.
  Before saving, it checks the header, redacts secrets and never overwrites a change made
  in the meantime (for example, by Claude Code). The index and the map update at once.

### Changed

- The panel no longer opens the system's external editor.

## [0.2.2] - 2026-10-16

### Added

- Portable version: `Memoria-<version>-macos-arm64.zip`, `-macos-x86_64.zip` and `-windows-x64.zip`,
  with Python 3.12 and all dependencies inside. Unzip and open, no installer and no admin rights.
- `memoria update` in the portable version: downloads the zip, checks the SHA-256, tests it and swaps the folder in place.
- `memoria selftest` in the portable version prints the `claude mcp add` command for that folder.
- `scripts/sign-macos.sh` (optional, run by the organizer): signs and notarizes the Mac zips
  with a Developer ID. Not part of the normal release.

### Changed

- Interface built with the workshop design skill (`design-taste-frontend`, house rules and DESIGN.md):
  a column on the left with the name, counts, search, filters and latest memories by title;
  the map on the right, with the timeline ("Watch it grow") below.
- Period as segments; types (the map legend) in the column; dates like "21 Jun".
- Monospace only for real code (paths and commands).

### Notes

- Install with the one-line command. Downloading through the browser needs approval in
  System Settings → Privacy & Security.

## [0.2.1] - 2026-10-16

### Fixed

- Browser mode (the Windows fallback without WebView2) showed an empty graph: the printed URL
  didn't carry the session key and the page waited for the window bridge.
  The URL is now `http://127.0.0.1:<port>/?t=<key>`; the key becomes a session cookie
  (HttpOnly, SameSite=Strict) and the server tells the page which mode it's in.
  Without the key, the page explains what to open. In the window, if the bridge never shows up, the page uses HTTP.

### Changed

- Look aligned with the Arena and the slides (workshop DESIGN.md): color tokens, square corners,
  Bricolage Grotesque font (bundled, OFL license), blue primary button.
- Type colors from the status palette: lesson yellow, do green, don't red (drawn as a ring,
  so it doesn't depend on color), history neutral; context nodes in neutral tones.
- Search: words in the memory's name count more (breaks BM25 ties with few notes).

## [0.2.0] - 2026-10-16

### Added

- Optional `epico`, `url` and `etiquetas` fields in notes. v0.1 notes stay valid.
- Epic node in the graph; tasks link to their epic. A note without an epic inherits its task's.
- Search by name, project, task, epic and tags. A key (`ABC-123`) returns the task,
  its epic and the rest of the epic.
- MCP: `memoria_procurar` accepts `tarefa` and `epico`; `memoria_adicionar` accepts `epico`, `url` and `etiquetas`.
- Interface: grouped search results (Memories, Projects, Tasks and epics) and filters by epic and task.
- CLI: `memoria add --epico --url --etiqueta` and `memoria procurar --tarefa --epico`.

### Changed

- Relation strength: explicit link > same task > same epic > same project > files.
- Jira and GitHub keys join notes across projects. Local keys (`#12`) stay within the project.
- The index moves to `.indice/memoria-v2.sqlite` and rebuilds itself. The v0.1 one is deleted on `reindex`.

## [0.1.0] - 2026-10-16

First release.

### Added

- Markdown notes in `$MEMORIA_HOME/<project>/<YYYY-MM-DD>-<slug>.md`, with a YAML header
  (`tipo`, `titulo`, `projeto`, `tarefa`, `ficheiros`, `data`, `custo_usd`, `ligacoes`).
- SQLite index with FTS5 and edges, rebuildable with `memoria reindex`.
- Secret redaction before saving.
- MCP server over stdio: `memoria_procurar`, `memoria_adicionar`, `memoria_relacionadas`.
- Native window (pywebview) with the graph, filters, timeline, note panel and form.
  On Windows without WebView2, the interface opens in the browser.
- `memoria update` via `git ls-remote` and SHA-256.
- `install.sh` and `install.ps1` installers, no admin rights needed.
