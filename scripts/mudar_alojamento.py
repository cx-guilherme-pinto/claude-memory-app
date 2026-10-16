#!/usr/bin/env python3
"""Muda o alojamento e a versão da Memória de uma vez (sem commit).

Uso (normalmente através de scripts/mudar-alojamento.sh):
  mudar_alojamento.py --repo-url https://servidor/dono/claude-memory-app.git --provider github --versao v0.5.0 [--data AAAA-MM-DD]

Muda só estes ficheiros:
  release.conf          MEMORY_APP_REPO_URL, MEMORY_APP_VERSION, RELEASE_PROVIDER
  install/install.sh    bloco de configuração gerado (render_installers.py --escrever)
  install/install.ps1   idem
  README.md             bloco de instalação gerado (idem)
  pyproject.toml        version do projeto
  web/package.json      version do pacote
  web/package-lock.json version do próprio pacote (raiz e packages[""]), não das dependências
  uv.lock               versão do pacote memoria (uv lock), se o uv existir
  CHANGELOG.md          secção nova no topo: "## [X.Y.Z] - data" com "Publicação em <servidor>."

Não toca em mais nada (o docs/HANDOVER.md fala do Gitea como história). Não faz commit.
No fim diz o que mudou e onde ainda aparece o servidor antigo.
Só usa a biblioteca padrão (Python 3.9+).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parents[1]
VERSAO = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def falha(msg: str) -> None:
    print(f"Erro: {msg}", file=sys.stderr)
    sys.exit(2)


def ler(caminho: Path) -> str:
    return caminho.read_text("utf-8")


def escrever(caminho: Path, texto: str, mudados: list[str]) -> None:
    if not caminho.exists() or ler(caminho) != texto:
        caminho.write_text(texto, "utf-8", newline="\n")
        mudados.append(str(caminho.relative_to(RAIZ)))


def validar(args: argparse.Namespace) -> None:
    partes = urlsplit(args.repo_url)
    caminho = [p for p in partes.path.split("/") if p]
    if partes.scheme != "https" or not partes.hostname or len(caminho) < 2:
        falha(f"--repo-url tem de ser https://servidor/dono/nome(.git): {args.repo_url}")
    if "'" in args.repo_url or " " in args.repo_url or not args.repo_url.isascii():
        falha("--repo-url não pode ter espaços, plicas nem caracteres não ASCII.")
    if not VERSAO.match(args.versao):
        falha(f"--versao tem de ser vX.Y.Z (sem sufixos): {args.versao}")
    try:
        dt.date.fromisoformat(args.data)
    except ValueError:
        falha(f"--data tem de ser AAAA-MM-DD: {args.data}")


def conf_valor(texto: str, chave: str) -> str:
    m = re.search(rf"^{chave}=(.*)$", texto, re.M)
    return m.group(1).strip() if m else ""


def trocar_conf(texto: str, chave: str, valor: str) -> str:
    novo, n = re.subn(rf"^{chave}=.*$", f"{chave}={valor}", texto, count=1, flags=re.M)
    if n != 1:
        falha(f"release.conf não tem a chave {chave}.")
    return novo


def main() -> int:
    p = argparse.ArgumentParser(description="Muda o alojamento e a versão da Memória (sem commit).")
    p.add_argument("--repo-url", required=True, help="https://servidor/dono/claude-memory-app.git")
    p.add_argument("--provider", required=True, choices=["github", "gitea"])
    p.add_argument("--versao", required=True, help="vX.Y.Z")
    p.add_argument("--data", default=dt.date.today().isoformat(), help="AAAA-MM-DD (por omissão, hoje)")
    p.add_argument("--sem-lock", action="store_true", help="não correr o uv lock")
    args = p.parse_args()
    validar(args)

    numero = args.versao[1:]
    servidor = urlsplit(args.repo_url).hostname
    mudados: list[str] = []

    # 1. release.conf (a fonte de tudo o resto).
    conf_caminho = RAIZ / "release.conf"
    conf = ler(conf_caminho)
    url_antigo = conf_valor(conf, "MEMORY_APP_REPO_URL")
    servidor_antigo = urlsplit(url_antigo).hostname or ""
    conf = trocar_conf(conf, "MEMORY_APP_REPO_URL", args.repo_url)
    conf = trocar_conf(conf, "MEMORY_APP_VERSION", args.versao)
    conf = trocar_conf(conf, "RELEASE_PROVIDER", args.provider)
    escrever(conf_caminho, conf, mudados)

    # 2. pyproject.toml: a version da secção [project].
    py_caminho = RAIZ / "pyproject.toml"
    py = ler(py_caminho)
    secao = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", py, re.M | re.S)
    if not secao:
        falha("pyproject.toml sem secção [project].")
    corpo, n = re.subn(r'^version\s*=\s*"[^"]*"', f'version = "{numero}"', secao.group(1), count=1, flags=re.M)
    if n != 1:
        falha("pyproject.toml sem version em [project].")
    escrever(py_caminho, py[: secao.start(1)] + corpo + py[secao.end(1):], mudados)

    # 3. web/package.json e package-lock.json: só a versão do próprio pacote.
    pkg_caminho = RAIZ / "web" / "package.json"
    pkg = json.loads(ler(pkg_caminho))
    pkg["version"] = numero
    escrever(pkg_caminho, json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", mudados)
    lock_caminho = RAIZ / "web" / "package-lock.json"
    if lock_caminho.exists():
        lock = json.loads(ler(lock_caminho))
        lock["version"] = numero
        if "" in lock.get("packages", {}):
            lock["packages"][""]["version"] = numero
        escrever(lock_caminho, json.dumps(lock, ensure_ascii=False, indent=2) + "\n", mudados)

    # 4. CHANGELOG: secção nova no topo (uma só vez).
    cl_caminho = RAIZ / "CHANGELOG.md"
    cl = ler(cl_caminho)
    if not re.search(rf"^## \[{re.escape(numero)}\]", cl, re.M):
        secao_nova = f"## [{numero}] - {args.data}\n\n### Alterado\n\n- Publicação em {servidor}.\n\n"
        primeira = re.search(r"^## \[", cl, re.M)
        cl = cl[: primeira.start()] + secao_nova + cl[primeira.start():] if primeira else cl.rstrip() + "\n\n" + secao_nova
        escrever(cl_caminho, cl, mudados)
    else:
        print(f"CHANGELOG.md já tem a secção [{numero}]: fica como está.")

    # 5. install/*.sh/.ps1 e README: blocos gerados a partir do release.conf.
    antes = {f: ler(RAIZ / f) for f in ("install/install.sh", "install/install.ps1", "README.md")}
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "render_installers.py"), "--escrever"], capture_output=True, text=True)
    if r.returncode != 0:
        falha(f"render_installers.py falhou: {r.stderr.strip()}")
    mudados += [f for f, texto in antes.items() if ler(RAIZ / f) != texto]

    # 6. uv.lock (o CI corre `uv sync --locked`).
    if not args.sem_lock:
        uv = shutil.which("uv")
        if uv:
            antes_lock = ler(RAIZ / "uv.lock") if (RAIZ / "uv.lock").exists() else ""
            r = subprocess.run([uv, "lock", "--quiet"], cwd=RAIZ, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"Aviso: uv lock falhou ({r.stderr.strip()[:300]}). Corre-o à mão.", file=sys.stderr)
            elif ler(RAIZ / "uv.lock") != antes_lock:
                mudados.append("uv.lock")
        else:
            print("Aviso: sem uv; corre `uv lock` antes do commit (o CI usa --locked).", file=sys.stderr)

    # Resumo.
    print(f"Alojamento: {args.repo_url} ({args.provider}). Versão: {args.versao}.")
    if mudados:
        print("Mudou:")
        for f in dict.fromkeys(mudados):
            print(f"  {f}")
    else:
        print("Nada mudou (já estava assim).")
    if servidor_antigo and servidor_antigo != servidor:
        r = subprocess.run(
            ["git", "grep", "-n", "-I", "-F", servidor_antigo, "--", ".", ":!uv.lock", ":!tests/"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
        )
        if r.stdout.strip():
            print(f"Ainda mencionam {servidor_antigo} (rever à mão; o docs/HANDOVER.md é história):")
            for linha in r.stdout.strip().splitlines():
                print(f"  {linha[:160]}")
    print("Sem commit. A seguir: build da UI, uv run pytest, commit e push (ver docs/HANDOVER.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
