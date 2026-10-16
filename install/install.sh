#!/bin/sh
# Instalador da Memória para macOS (e Linux). Não precisa de admin.
#
# Uso:
#   curl -fsSL <repo>/releases/download/<versão>/install.sh | sh
#
# Faz isto:
#   1. instala o uv (versão fixada) em ~/.local/bin, se faltar;
#   2. descarrega o wheel e o constraints.txt desta versão e verifica o SHA-256;
#   3. corre `uv tool install` com o Python 3.12 gerido pelo uv;
#   4. cria ~/Applications/Memória.app (Mac) ou um atalho .desktop (Linux).
#
# Repositório privado (só em desenvolvimento): exporta MEMORIA_DOWNLOAD_TOKEN.
# O token vai para o curl pelo stdin e nunca é impresso.
set -eu

# >>> config: gerado a partir de release.conf por scripts/render_installers.py. Não editar à mão.
[ -n "${MEMORY_APP_REPO_URL:-}" ] || MEMORY_APP_REPO_URL='https://github.com/cx-guilherme-pinto/claude-memory-app.git'
[ -n "${MEMORY_APP_VERSION:-}" ] || MEMORY_APP_VERSION='v0.4.1'
[ -n "${RELEASE_DOWNLOAD_URL:-}" ] || RELEASE_DOWNLOAD_URL='{repo}/releases/download/{version}/{file}'
[ -n "${UV_VERSION:-}" ] || UV_VERSION='0.13.1'
[ -n "${PYTHON_VERSION:-}" ] || PYTHON_VERSION='3.12'
BUILD_VERSION='v0.4.1'
WHEEL_SHA256=''
# <<< config

UV_INSTALLER_URL="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-installer.sh"
MEMORIA_DOWNLOAD_TOKEN="${MEMORIA_DOWNLOAD_TOKEN:-}"

diz() { printf '%s\n' "$*"; }
falha() { printf 'Error: %s\n' "$*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || falha "curl is missing."

repo="${MEMORY_APP_REPO_URL%/}"
repo="${repo%.git}"
host="$(printf '%s' "$repo" | sed -E 's#^[a-z]+://([^/]+).*#\1#')"
name="${repo##*/}"
owner="${repo%/*}"
owner="${owner##*/}"

url_asset() {
  printf '%s' "$RELEASE_DOWNLOAD_URL" | sed \
    -e "s#{repo}#$repo#g" -e "s#{host}#$host#g" -e "s#{owner}#$owner#g" \
    -e "s#{name}#$name#g" -e "s#{version}#$MEMORY_APP_VERSION#g" -e "s#{file}#$1#g"
}

baixar() {
  if [ -n "$MEMORIA_DOWNLOAD_TOKEN" ]; then
    printf 'header = "Authorization: token %s"\n' "$MEMORIA_DOWNLOAD_TOKEN" |
      curl --config - -fsSL --retry 3 --proto '=https' --proto-redir '=https' -o "$2" "$1"
  else
    curl -fsSL --retry 3 --proto '=https' --proto-redir '=https' -o "$2" "$1"
  fi || falha "could not download $1"
}

sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

# --- 1. uv -----------------------------------------------------------------
UV="$(command -v uv 2>/dev/null || true)"
if [ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ]; then
  UV="$HOME/.local/bin/uv"
fi
if [ -z "$UV" ]; then
  diz "Installing uv $UV_VERSION..."
  curl -fsSL --proto '=https' --proto-redir '=https' "$UV_INSTALLER_URL" | sh || falha "the uv install failed."
  UV="$HOME/.local/bin/uv"
  [ -x "$UV" ] || falha "uv not found at $UV."
fi
diz "uv: $("$UV" --version)"

# --- 2. download e verificação ----------------------------------------------
tmp="$(mktemp -d 2>/dev/null || mktemp -d -t memoria)"
trap 'rm -rf "$tmp"' EXIT INT TERM
wheel="memoria-${MEMORY_APP_VERSION#v}-py3-none-any.whl"

diz "Downloading Memória $MEMORY_APP_VERSION..."
baixar "$(url_asset SHA256SUMS)" "$tmp/SHA256SUMS"
for f in "$wheel" constraints.txt; do
  baixar "$(url_asset "$f")" "$tmp/$f"
  esperado="$(awk -v f="$f" '$2 == f || $2 == "*" f { print $1 }' "$tmp/SHA256SUMS")"
  [ -n "$esperado" ] || falha "$f is not in SHA256SUMS."
  [ "$(sha256 "$tmp/$f")" = "$esperado" ] || falha "SHA-256 mismatch: $f"
done
if [ -n "$WHEEL_SHA256" ] && [ "$MEMORY_APP_VERSION" = "$BUILD_VERSION" ]; then
  [ "$(sha256 "$tmp/$wheel")" = "$WHEEL_SHA256" ] || falha "the wheel SHA-256 is not the one this installer expects."
fi
diz "SHA-256 verified."

# --- 3. instalar ---------------------------------------------------------------
"$UV" tool install --force --managed-python --python "$PYTHON_VERSION" \
  "$tmp/$wheel" --constraints "$tmp/constraints.txt" || falha "uv tool install failed."
bin="$("$UV" tool dir --bin)"
memoria="$bin/memoria"
[ -x "$memoria" ] || falha "$memoria not found."

# --- 4. atalho -------------------------------------------------------------
case "$(uname -s)" in
  Darwin)
    app="$HOME/Applications/Memória.app"
    mkdir -p "$app/Contents/MacOS"
    cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Memória</string>
  <key>CFBundleDisplayName</key><string>Memória</string>
  <key>CFBundleIdentifier</key><string>pt.workshop.memoria</string>
  <key>CFBundleExecutable</key><string>memoria-app</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${MEMORY_APP_VERSION#v}</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
    cat > "$app/Contents/MacOS/memoria-app" <<LAUNCHER
#!/bin/sh
exec "$memoria" "\$@"
LAUNCHER
    chmod +x "$app/Contents/MacOS/memoria-app"
    diz "Shortcut: $app"
    ;;
  Linux)
    pasta="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$pasta"
    cat > "$pasta/memoria.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Memória
Comment=Claude Code memories
Exec="$memoria"
Terminal=false
Categories=Development;
DESKTOP
    diz "Shortcut: $pasta/memoria.desktop"
    ;;
esac

# --- verificação ---------------------------------------------------------
"$memoria" selftest >/dev/null || falha "selftest failed. Run: $memoria selftest"

diz ""
diz "Memória $MEMORY_APP_VERSION installed."
diz "To connect it to Claude Code:"
diz "  claude mcp add --scope user memoria -- \"$memoria\" mcp"
case ":$PATH:" in
  *":$bin:"*) ;;
  *) diz "Note: $bin is not on PATH. Open a new terminal or add it." ;;
esac
