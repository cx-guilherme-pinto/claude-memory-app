#!/usr/bin/env bash
# Gera constraints.txt (versões exatas de todas as dependências, para todas as
# plataformas) e confirma que há wheels para Mac Intel/ARM e Windows x64/ARM.
# Só o proxy-tools (puro Python, dependência do pywebview) é sdist.
set -euo pipefail
cd "$(dirname "$0")/.."

uv pip compile pyproject.toml --universal --python-version 3.12 \
  --constraint constraints.in --no-header --no-annotate --quiet -o constraints.txt

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
for plataforma in x86_64-apple-darwin aarch64-apple-darwin x86_64-pc-windows-msvc aarch64-pc-windows-msvc; do
  if ! uv pip compile pyproject.toml --python-version 3.12 --python-platform "$plataforma" \
      --only-binary :all: --no-binary proxy-tools --constraint constraints.txt --quiet -o "$tmp/out.txt"; then
    echo "Falta um wheel para $plataforma (ver acima)." >&2
    exit 1
  fi
  echo "wheels ok: $plataforma"
done
