# Portable version

**English** · [Português](portatil.pt.md)

Decision approved on 16 Oct 2026. The organizers asked for an app that just opens, with no installer.

## What it is

One zip per platform, with Python and every dependency inside:

| File | Contents | Size |
|---|---|---|
| `Memoria-<version>-macos-arm64.zip` | `Memoria.app` (Apple Silicon) | 37 MB |
| `Memoria-<version>-macos-x86_64.zip` | `Memoria.app` (Intel) | 37 MB |
| `Memoria-<version>-windows-x64.zip` | `Memoria` folder (double-click `Memoria.exe`) | 36 MB |

No installer, no uv and no PyPI on the workshop day. Just one download from the release server.
The uv install path (`install.sh`, `install.ps1`, wheel) stays as it is.

## Decisions

1. **Bundled Python, delivered by the setup.** The workshop setup downloads the zip with
   `curl` (Mac) or `Invoke-WebRequest` (Windows) and extracts it to a fixed folder.
   That way the file isn't marked as "downloaded from the Internet":
   no Gatekeeper, no SmartScreen, no warnings.
2. **Windows as a zip.** No single `.exe`: it would be an unsigned executable.
3. **python-build-standalone 3.12.15 in all three zips.** It's the same Python uv installs today.
   It has FTS5 and the security fixes. The `.exe` files aren't signed.
   The alternative (python.org's "embeddable" zip, signed by the PSF) stopped at 3.12.10.
4. **`update` swaps the folder in place.** The path doesn't change,
   so the Claude Code connection (MCP) stays valid.
5. **No Apple signing in the normal release** (the organizer's call: only if really needed).
   The setup doesn't need it: tested, a zip downloaded with `curl` isn't quarantined
   and the app opens with no questions. There's an optional script to sign and notarize
   (see "Optional signing").

Options set aside: PyInstaller and Briefcase (unsigned launchers, more antivirus false
positives; Briefcase needs a Windows machine for the build).

## How it works

macOS:

- `Memoria.app/Contents/MacOS/memoria` is an `sh` script that runs
  `Resources/python/bin/python3 -I -B -m memoria "$@"`.
- With no arguments it opens the window. With arguments it's the command line.
- The MCP command is `…/Memoria.app/Contents/MacOS/memoria mcp`.

Windows:

- `Memoria.exe` is a copy of `pythonw.exe`. `sitecustomize.py` opens the window
  when the executable is `Memoria.exe` and there are no arguments. Otherwise it does nothing.
- `python312._pth` pins the paths and ignores the user's `PYTHONPATH`/`PYTHONHOME`.
- The MCP command is `…\Memoria\python.exe -m memoria mcp`. In a console: `agent-memory.cmd selftest` (`memoria.cmd` is the old name and still works).
- If the zip came through a browser, the app removes the Internet mark from its files at startup.
  Without that, .NET refuses the pythonnet and WebView2 DLLs and the window doesn't open.

The `.pyc` files ship compiled (unchecked hash). The app never writes inside its own folder.
The build is reproducible: the same wheel gives the same zips, byte for byte.

## Build

```bash
scripts/build.sh                 # wheel, installers and the three zips
PORTATIL=0 scripts/build.sh      # without the zips
uv run --no-project --python 3.12 python scripts/build_portatil.py --wheel dist/memoria-X-py3-none-any.whl --plataforma macos-arm64
```

It runs on Mac and Linux (CI). Each platform's dependencies come as wheels
(`uv pip install --python-platform`). On a Mac, the build runs the `selftest` of each Mac zip
(Intel through Rosetta). The pinned Python (version, URL and SHA-256) is in `release.conf`.

## Workshop setup integration

A sketch. The setup already has `url_asset` and the `SHA256SUMS` check.

macOS (`hw.optional.arm64` is reliable even in a Terminal running under Rosetta):

```sh
arq=x86_64; [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = 1 ] && arq=arm64
zip="Memoria-${MEMORY_APP_VERSION#v}-macos-$arq.zip"
baixar "$(url_asset "$zip")" "$tmp/$zip"      # and check the SHA-256
mkdir -p "$HOME/Applications"
rm -rf "$HOME/Applications/Memoria.app"
ditto -x -k "$tmp/$zip" "$HOME/Applications"
app="$HOME/Applications/Memoria.app/Contents/MacOS/memoria"
"$app" selftest
claude mcp add --scope user agent-memory -- "$app" mcp
```

Windows (PowerShell 5.1; `Expand-Archive` is slow with thousands of files):

```powershell
$zip = 'Memoria-' + $version.TrimStart('v') + '-windows-x64.zip'
Get-Asset (Get-AssetUrl $zip) (Join-Path $tmp $zip)   # and check the SHA-256
$destino = Join-Path $env:LOCALAPPDATA 'Programs'
Remove-Item -Recurse -Force (Join-Path $destino 'Memoria') -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $tmp $zip), $destino)
$py = Join-Path $destino 'Memoria\python.exe'
& $py -m memoria selftest
claude mcp add --scope user agent-memory -- $py -m memoria mcp
# Start menu shortcut to Memoria\Memoria.exe (as install.ps1 already does).
```

The setup still installs WebView2 if it's missing. Without it, the app opens in the browser.

## Browser download (plan B)

macOS: Gatekeeper blocks the app (it isn't signed). On macOS 15 or later, right-click "Open"
is gone. Two ways out:

- in Terminal: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`;
- or System Settings → Privacy & Security → "Open Anyway" (asks for the password;
  described by Apple and others, not verified here).

Windows: SmartScreen shows "Windows protected your PC".
Click "More info", then "Run anyway".

Note for the release page (it's in the CHANGELOG, which is the release text):
"Install with the one-line command. Downloading through the browser needs approval in
System Settings → Privacy & Security."

## Optional signing (macOS)

Only for people who download through a browser, AirDrop or Mail, or for companies whose EDR
only accepts signed executables. It isn't part of the normal release. The organizer runs it,
on their Mac, with their Developer ID. No script stores credentials.

Once, on the organizer's Mac:

1. Create the "Developer ID Application" certificate (Xcode → Settings → Accounts →
   Manage Certificates → +). Only the account holder can create it.
2. Create an app-specific password at account.apple.com.
3. Save the notarytool profile in the Keychain (it asks for the password; nothing goes to files):

   ```bash
   xcrun notarytool store-credentials memoria-notary --apple-id <email> --team-id <TEAMID>
   ```

For each release, after `scripts/build.sh` and before `scripts/publish-release.sh`:

```bash
scripts/sign-macos.sh --identidade "Developer ID Application: <Name> (<TEAMID>)" --perfil memoria-notary \
  dist/Memoria-<version>-macos-arm64.zip dist/Memoria-<version>-macos-x86_64.zip
```

The script swaps the `sh` launcher for a compiled executable (`portatil/macos/lancador.c`,
arm64 and x86_64), signs each Mach-O and the app with the hardened runtime and
`portatil/macos/entitlements.plist`, notarizes, staples the ticket, checks with `spctl`,
rebuilds the zips and updates `SHA256SUMS`.
To test without an Apple account: `scripts/sign-macos.sh --adhoc --saida /tmp/teste <zip>`.

Tested in `--adhoc` mode (macOS 26.6, Apple Silicon): `codesign --verify --deep --strict`
passes after extracting with `ditto` and with the `memoria update` extractor; `selftest --gui`
passes with the hardened runtime (the Intel zip too, under Rosetta); running the app doesn't break the signature.
Not tested yet: notarization and `spctl` with a real Developer ID.

## Verified

On a Mac (Apple Silicon, macOS 26.6):

- The three zips build in about 25 s.
- Zip downloaded with `curl` and extracted with `unzip`: no quarantine.
  `memoria selftest --gui` passes (window ready in under 1 s). It opens from Finder (`open`).
- Nothing is written inside the app.
- Intel zip: `selftest` passes under Rosetta (no window).
- Quarantined copy (`0083;…;Google Chrome;…` and `0081;…;Safari;`): `ditto` and `unzip`
  carry the zip's quarantine over to the app. The app doesn't start. macOS shows the
  Gatekeeper warning (`spctl`: "rejected, no usable signature"). After `xattr -dr com.apple.quarantine`, it opens.
- `memoria update` against a local server: downloads, checks the SHA-256, runs the new version's
  `selftest`, swaps the folder and reindexes. Also tested in `~/Applications` and with the app renamed.
- MCP over stdio through the launcher (`memoria mcp`): all three tools answer.
- The Windows swap script passes the parser and runs in PowerShell 7 (on the Mac).
- The same Windows startup (Python under another name, no arguments, window opened
  by `sitecustomize`) works on the Mac.
- Uploading the 37 MB assets to Gitea: releases v0.2.2 to v0.4.0 were published with them.

## Not verified yet (Windows doesn't run here)

- Double-clicking `Memoria.exe` opens the window (pythonnet, WinForms and WebView2 in `._pth` mode).
- `python312._pth` is honored by the python-build-standalone Python
  (confirmed only by reading CPython 3.12's `getpath.py`).
- `pywin32.pth` and `pywin32_bootstrap` work in this mode.
- Removing the Internet mark (`Zone.Identifier`) fixes .NET error 0x80131515.
- SmartScreen's exact text for the unsigned `Memoria.exe`.
- The swap script in PowerShell 5.1 with files in use (MCP open in Claude Code).
- Company policies: AppLocker, Defender ASR rules, antivirus.
- Windows ARM (runs the x64 zip under emulation).

Also still to do: the app menu shows "Memoria" (no accent), the app has no icon,
and the new-version notice in the UI says `agent-memory update` (in the portable version it's the full path).
