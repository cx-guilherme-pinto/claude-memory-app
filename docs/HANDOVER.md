# Handover: Agent Memory

**English** · [Português](HANDOVER.pt.md)

To carry on the work on another machine (for example, the company one, with a corporate GitHub).
Day-to-day rules are in [CLAUDE.md](../CLAUDE.md).

## Status at v0.4.0

Released on the organizer's Gitea (`gitea.guilhermepinto.pt/guilherme/claude-memory-app`) on 16 Oct 2026.
There is a private copy at `github.com/cx-guilherme-pinto/claude-memory-app`; the organizer's `origin`
pushes to both. Releases v0.1.0 to v0.4.0 are being copied there by the workshop kit.

| Version | What it brought |
|---|---|
| 0.1.0 | Markdown notes, FTS5 index, graph, MCP server, secret redaction, `memoria update`, installers |
| 0.2.0 | Epic, url and tags; search by name, project and ticket key |
| 0.2.1 | Browser mode fixed (session cookie); workshop look |
| 0.2.2 | Portable version (Mac arm64/x86_64 and Windows x64 zips) and the new interface |
| 0.2.3 | Edit a memory inside the app |
| 0.3.0 | 4 languages (pt, en, hi, he), Hebrew RTL, language picker |
| 0.4.0 | "Claude activity" view (MCP call log) |
| 0.5.0 (not released yet) | Name *Agent Memory*; English technical names: `agent-memory` command, `agent-memory` MCP server with `memory_search`/`memory_add`/`memory_related`, English note headers and `~/.agent-memory`. Old names still accepted (see the CHANGELOG) |

Assets in each release: the wheel, `constraints.txt`, `install.sh`, `install.ps1`, `SHA256SUMS`
and the 3 portable zips.

Since v0.4.0 (on `main`, not released): English-first docs (READMEs in 4 languages, `*.pt.md` translations),
English installer messages and Windows readme, `scripts/mudar-alojamento.sh`, and `publish-release.sh`
support for GitHub Enterprise.

Verified:

- 236 tests on macOS (Apple Silicon), including Playwright and the native window.
- Real updates with `memoria update`: uv install 0.2.1 → 0.4.0 and portable 0.2.3 → 0.3.0 → 0.4.0.
  Notes were not touched.
- The Mac portable zip running as `memoria mcp` (the way Claude Code launches it).

## Open work

1. **Test on real Windows.** Only static checks so far: `install.ps1`, the portable zip,
   WebView2, pythonnet, `agent-memory-gui.exe` and the folder swap in `agent-memory update`.
2. **Test on an Intel Mac and on Windows ARM.** The wheels exist (see `scripts/lock.sh`), but nothing was run there.
3. **Have native speakers review Hindi and Hebrew:** `web/src/locales/hi.json`, `he.json`,
   `src/memoria/mensagens.py`, `README.hi.md` and `README.he.md`.
4. **Installer messages in other languages.** `install.sh` and `install.ps1` speak English only
   (the `.ps1` must stay ASCII). The Windows zip has `README.txt` (English) and `README.pt.txt` (Portuguese).
5. **Run the CI workflow for the first time** (`.github/workflows/release.yml`). Gitea had no runner:
   every release was made by hand with the same scripts.
6. **Real Apple signing** (Developer ID + notarization): only ad hoc signing was tested.

## Risks

- **Private or internal repository.** The installers, the kit's setup and `agent-memory update` download from
  `{repo}/releases/download/<tag>/<file>`. On GitHub that URL only works without login on a public
  repository. With a private or internal repository, participants can't install or update.
  Fixes: publish releases on a public repository, or add an API download (with a token) to `update.py`
  and the installers.
- **Gatekeeper, SmartScreen and EDR.** The zips aren't signed. Through the setup (curl or Invoke-WebRequest)
  they aren't quarantined. Downloaded in a browser, macOS blocks them.
- **TLS-inspecting proxies.** uv needs `UV_SYSTEM_CERTS=1`. `agent-memory update` uses the system certificates
  (truststore). Its `git ls-remote` uses the git configuration.
- **`cryptography` pinned to 46.0.3** (`constraints.in`): the last version with wheels for Intel Mac
  and Windows ARM. It comes from `mcp`; the stdio server doesn't use it.
- **Updating on Windows with Claude Code open.** `agent-memory mcp` locks the files. The swap script waits up
  to 3 minutes and asks to close Agent Memory and Claude Code.
- **Canvas tests in headless Chromium.** Animation frames don't always run. The tests use the value seen
  at drawing time (`tests/test_browser.py`, `_esperar_desenho`).

## Publishing a version

### Change hosting and version (one command)

```bash
scripts/mudar-alojamento.sh --repo-url https://<server>/<org>/claude-memory-app.git \
  --provider github --versao vX.Y.Z [--data YYYY-MM-DD]
```

It changes only: `release.conf` (URL, version and `RELEASE_PROVIDER`), the generated blocks in
`install/install.sh`, `install/install.ps1` and every `README*.md`, `pyproject.toml`, `web/package.json`,
`web/package-lock.json` (the package itself only), `uv.lock`, and it adds `## [X.Y.Z] - date` at the top of
`CHANGELOG.md` and `CHANGELOG.pt.md`. It doesn't commit. At the end it lists what changed and where the
old server still appears. Running it again with the same arguments changes nothing.
`RELEASE_DOWNLOAD_URL` stays as it is.

To change only the version on the same hosting, pass the current URL and provider.
By hand, without the script: edit `release.conf`, `pyproject.toml`, `CHANGELOG.md` and `CHANGELOG.pt.md`,
then run `python3 scripts/render_installers.py --escrever` and `uv lock`.

### Publish

1. `scripts/mudar-alojamento.sh …` (above).
2. UI and tests:
   ```bash
   uv sync
   (cd web && npm ci && npm run build) && rm -rf src/memoria/web_dist && cp -R web/dist src/memoria/web_dist
   uv run playwright install chromium && uv run pytest
   ```
3. Commit and push `main` to the new server. The remote must be called `origin`:
   `publish-release.sh` pushes the tag to `origin`.
   **Don't create the tag by hand.** `publish-release.sh` creates it (annotated, on `HEAD`, with the version
   from `release.conf`) and pushes it. If it already exists, it uses it; it must point at the commit you built.
4. `scripts/build.sh`. It writes to `dist/` the wheel, `constraints.txt`, `install.sh` and `install.ps1` with
   the wheel's SHA-256, the 3 portable zips and `SHA256SUMS`. `PORTATIL=0 scripts/build.sh` skips the zips.
5. Log in: `gh auth login --hostname <server>` (or `GH_ENTERPRISE_TOKEN`). The server comes from
   `MEMORY_APP_REPO_URL`: `GH_HOST` isn't needed (and doesn't hurt).
   `scripts/publish-release.sh --so-token` checks the login.
6. `scripts/publish-release.sh`: creates and pushes the tag, creates the release, uploads the assets with `gh`
   (the only place that talks to the API), verifies them through the API and then through the public URL.
   On a private or internal repository, the public URL gives a warning (see "Risks").
7. Tell the kit to bump `MEMORY_APP_VERSION` in `repos.conf`.

**Watch out for CI.** A `v*` tag pushed to the server triggers `.github/workflows/release.yml`,
which also publishes. Pick one path:
- local publishing (steps 4 to 6): turn off the repository's Actions, or the workflow, before step 6;
- CI publishing: after step 3, create and push the tag (`git tag -a vX.Y.Z -m "Agent Memory vX.Y.Z"` and
  `git push origin vX.Y.Z`) and skip steps 4 to 6. The runner needs access to PyPI, npm and the
  python-build-standalone downloads.

The workflow runs build, tests and publishing. The tag must equal `MEMORY_APP_VERSION`.

## Optional Mac signing

`scripts/sign-macos.sh` signs and notarizes the Mac zips with a Developer ID. Only the organizer runs it,
on their Mac, after `build.sh` and before `publish-release.sh`. It isn't part of the normal release.
Instructions and decisions in [docs/portatil.md](portatil.md#optional-signing-macos).
