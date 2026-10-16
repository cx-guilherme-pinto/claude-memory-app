#!/usr/bin/env python3
"""Gera o bloco de configuração dos instaladores a partir de release.conf.

Uso:
  render_installers.py --escrever              # atualiza install/install.{sh,ps1} (sem SHA do wheel)
  render_installers.py --verificar             # falha se install/ não estiver em sincronia
  render_installers.py --dist DIR --wheel W    # escreve DIR/install.{sh,ps1} com o SHA-256 do wheel
  render_installers.py --somas DIR             # escreve DIR/SHA256SUMS dos assets da release

Só usa a biblioteca padrão (corre antes de haver venv).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CHAVES = ("MEMORY_APP_REPO_URL", "MEMORY_APP_VERSION", "RELEASE_DOWNLOAD_URL", "UV_VERSION", "PYTHON_VERSION")
NOMES_PS = {
    "MEMORY_APP_REPO_URL": "MemoryAppRepoUrl",
    "MEMORY_APP_VERSION": "MemoryAppVersion",
    "RELEASE_DOWNLOAD_URL": "ReleaseDownloadUrl",
    "UV_VERSION": "UvVersion",
    "PYTHON_VERSION": "PythonVersion",
}
ASSETS = ("constraints.txt", "install.sh", "install.ps1")


def ler_conf(caminho: Path) -> dict[str, str]:
    valores = {}
    for linha in caminho.read_text("utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            valores[k.strip()] = v.strip()
    falta = [k for k in CHAVES if not valores.get(k)]
    if falta:
        sys.exit(f"release.conf: faltam {', '.join(falta)}")
    for k in CHAVES:
        if "'" in valores[k] or not valores[k].isascii():
            sys.exit(f"release.conf: {k} tem de ser ASCII e sem plicas")
    return valores


def bloco_sh(conf: dict[str, str], sha: str) -> str:
    linhas = ["# >>> config: gerado a partir de release.conf por scripts/render_installers.py. Não editar à mão."]
    for k in CHAVES:
        linhas.append(f"[ -n \"${{{k}:-}}\" ] || {k}='{conf[k]}'")
    linhas.append(f"BUILD_VERSION='{conf['MEMORY_APP_VERSION']}'")
    linhas.append(f"WHEEL_SHA256='{sha}'")
    linhas.append("# <<< config")
    return "\n".join(linhas)


def bloco_ps(conf: dict[str, str], sha: str) -> str:
    linhas = ["# >>> config: gerado a partir de release.conf por scripts/render_installers.py. Nao editar a mao."]
    for k in CHAVES:
        linhas.append(f"${NOMES_PS[k]} = '{conf[k]}'")
    linhas.append(f"$BuildVersion = '{conf['MEMORY_APP_VERSION']}'")
    linhas.append(f"$WheelSha256 = '{sha}'")
    linhas.append("# <<< config")
    return "\n".join(linhas)


def substituir(texto: str, bloco: str) -> str:
    inicio = texto.index("# >>> config")
    fim = texto.index("# <<< config") + len("# <<< config")
    return texto[:inicio] + bloco + texto[fim:]


def render(conf: dict[str, str], sha: str) -> dict[str, str]:
    sh = (RAIZ / "install" / "install.sh").read_text("utf-8")
    ps = (RAIZ / "install" / "install.ps1").read_text("utf-8")
    ps_novo = substituir(ps, bloco_ps(conf, sha))
    if not ps_novo.isascii():
        sys.exit("install.ps1 tem caracteres não ASCII")
    return {"install.sh": substituir(sh, bloco_sh(conf, sha)), "install.ps1": ps_novo}


def bloco_readme(conf: dict[str, str]) -> str:
    repo = conf["MEMORY_APP_REPO_URL"].rstrip("/").removesuffix(".git")
    url = conf["RELEASE_DOWNLOAD_URL"].replace("{repo}", repo).replace("{version}", conf["MEMORY_APP_VERSION"])
    return "\n".join(
        [
            "<!-- >>> instalar: gerado a partir de release.conf por scripts/render_installers.py -->",
            "**macOS** (Intel e Apple Silicon) e Linux, no Terminal:",
            "",
            "```bash",
            f"curl -fsSL {url.replace('{file}', 'install.sh')} | sh",
            "```",
            "",
            "**Windows 10/11**, no PowerShell:",
            "",
            "```powershell",
            f'powershell -ExecutionPolicy Bypass -c "irm {url.replace("{file}", "install.ps1")} | iex"',
            "```",
            "<!-- <<< instalar -->",
        ]
    )


def readme(conf: dict[str, str]) -> str:
    texto = (RAIZ / "README.md").read_text("utf-8")
    inicio = texto.index("<!-- >>> instalar")
    fim = texto.index("<!-- <<< instalar -->") + len("<!-- <<< instalar -->")
    return texto[:inicio] + bloco_readme(conf) + texto[fim:]


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--conf", type=Path, default=RAIZ / "release.conf")
    p.add_argument("--escrever", action="store_true")
    p.add_argument("--verificar", action="store_true")
    p.add_argument("--dist", type=Path)
    p.add_argument("--wheel", type=Path)
    p.add_argument("--somas", type=Path)
    a = p.parse_args()
    conf = ler_conf(a.conf)

    if a.escrever or a.verificar:
        diferentes = []
        ficheiros = {RAIZ / "install" / n: t for n, t in render(conf, "").items()}
        ficheiros[RAIZ / "README.md"] = readme(conf)
        for destino, texto in ficheiros.items():
            nome = destino.name
            if destino.read_text("utf-8") != texto:
                diferentes.append(nome)
                if a.escrever:
                    destino.write_text(texto, "utf-8", newline="\n")
        if a.verificar and diferentes:
            print(f"Fora de sincronia com release.conf: {', '.join(diferentes)}. Corre --escrever.", file=sys.stderr)
            return 1
    if a.dist:
        if not a.wheel or not a.wheel.is_file():
            sys.exit("--dist precisa de --wheel <ficheiro>")
        esperado = f"memoria-{conf['MEMORY_APP_VERSION'].lstrip('v')}-py3-none-any.whl"
        if a.wheel.name != esperado:
            sys.exit(f"O wheel {a.wheel.name} não corresponde a MEMORY_APP_VERSION ({esperado}).")
        a.dist.mkdir(parents=True, exist_ok=True)
        for nome, texto in render(conf, sha256(a.wheel)).items():
            (a.dist / nome).write_text(texto, "utf-8", newline="\n")
            if nome == "install.sh":
                (a.dist / nome).chmod(0o755)
    if a.somas:
        wheels = sorted(a.somas.glob("memoria-*.whl"))
        if len(wheels) != 1:
            sys.exit(f"Esperava um wheel em {a.somas}, encontrei {len(wheels)}.")
        versao = conf["MEMORY_APP_VERSION"].lstrip("v")
        portateis = sorted(a.somas.glob(f"Memoria-{versao}-*.zip"))
        linhas = [f"{sha256(f)}  {f.name}" for f in [wheels[0], *(a.somas / n for n in ASSETS), *portateis]]
        (a.somas / "SHA256SUMS").write_text("\n".join(linhas) + "\n", "utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
