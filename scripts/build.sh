#!/usr/bin/env bash
# Build da release. Corre igual no Mac (local) e no CI (Linux).
#
#   1. confirma que a versão do pyproject.toml bate com release.conf;
#   2. compila a UI (npm ci + vite build) e copia-a para src/memoria/web_dist;
#   3. gera o wheel com o uv;
#   4. gera os zips da versão portátil (scripts/build_portatil.py; PORTATIL=0 salta);
#   5. gera install.sh e install.ps1 com o SHA-256 do wheel;
#   6. escreve SHA256SUMS.
#
# Resultado em dist/:
#   memoria-<versão>-py3-none-any.whl  constraints.txt  install.sh  install.ps1  SHA256SUMS
#   Memoria-<versão>-macos-arm64.zip  Memoria-<versão>-macos-x86_64.zip  Memoria-<versão>-windows-x64.zip
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

if [ "${PORTATIL:-1}" != "0" ]; then
  echo "== versão portátil"
  # Os .pyc têm de ser gerados pelo mesmo Python (3.12) que vai dentro dos zips.
  python_portatil="$(grep -m1 '^PORTATIL_PYTHON=' release.conf | cut -d= -f2 | cut -d. -f1,2)"
  uv run --no-project --python "$python_portatil" python scripts/build_portatil.py --wheel "$wheel" --dist dist
fi

echo "== instaladores e SHA256SUMS"
cp constraints.txt dist/
python3 scripts/render_installers.py --dist dist --wheel "$wheel"
python3 scripts/render_installers.py --somas dist

echo
cat dist/SHA256SUMS
