#!/usr/bin/env bash
# Muda o alojamento e a versão da Memória de uma vez. Não faz commit.
#
# Uso:
#   scripts/mudar-alojamento.sh --repo-url https://servidor/dono/claude-memory-app.git \
#     --provider github|gitea --versao vX.Y.Z [--data AAAA-MM-DD] [--sem-lock]
#
# Muda: release.conf, install/install.sh, install/install.ps1, README.md (blocos gerados),
# pyproject.toml, web/package.json, web/package-lock.json (só o próprio pacote), uv.lock
# e acrescenta a secção da versão no topo do CHANGELOG.md. Detalhes em scripts/mudar_alojamento.py.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/mudar_alojamento.py "$@"
