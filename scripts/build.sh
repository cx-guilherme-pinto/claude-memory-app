#!/usr/bin/env bash
# Build da release. Corre igual no Mac (local) e no CI (Linux).
#
#   1. confirma que a versão do pyproject.toml bate com release.conf;
#   2. compila a UI (npm ci + vite build) e copia-a para src/memoria/web_dist;
#   3. gera o wheel com o uv;
#   4. gera install.sh e install.ps1 com o SHA-256 do wheel;
#   5. escreve SHA256SUMS.
#
# Resultado em dist/:
#   memoria-<versão>-py3-none-any.whl  constraints.txt  install.sh  install.ps1  SHA256SUMS
set -euo pipefail
cd "$(dirname "$0")/.."

versao="$(grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2)"
conf="$(grep -m1 '^MEMORY_APP_VERSION=' release.conf | cut -d= -f2)"
if [ "v$versao" != "$conf" ]; then
  echo "pyproject.toml tem $versao mas release.conf tem $conf." >&2
  exit 1
fi
if ! grep -q "^## \[$versao\]" CHANGELOG.md; then
  echo "Falta a secção [$versao] no CHANGELOG.md." >&2
  exit 1
fi
python3 scripts/render_installers.py --verificar

echo "== UI"
(cd web && npm ci --no-audit --no-fund --loglevel=error && npm run --silent build)
rm -rf src/memoria/web_dist
cp -R web/dist src/memoria/web_dist

echo "== wheel"
rm -rf dist
uv build --wheel --out-dir dist --quiet
wheel="dist/memoria-$versao-py3-none-any.whl"
[ -f "$wheel" ] || { echo "Não encontrei $wheel" >&2; exit 1; }

# O wheel tem de levar a UI e o release.conf.
python3 - "$wheel" <<'PY'
import sys, zipfile
nomes = set(zipfile.ZipFile(sys.argv[1]).namelist())
for obrigatorio in ("memoria/web_dist/index.html", "memoria/release.conf", "memoria/cli.py"):
    if obrigatorio not in nomes:
        sys.exit(f"Falta {obrigatorio} no wheel")
PY

echo "== instaladores e SHA256SUMS"
cp constraints.txt dist/
python3 scripts/render_installers.py --dist dist --wheel "$wheel"
python3 scripts/render_installers.py --somas dist

echo
cat dist/SHA256SUMS
