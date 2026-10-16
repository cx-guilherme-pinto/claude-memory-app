#!/usr/bin/env python3
"""Gera a versão portátil da Memória: um zip por plataforma, sem instalador.

  Memoria-<versão>-macos-arm64.zip    Memoria.app (Apple Silicon)
  Memoria-<versão>-macos-x86_64.zip   Memoria.app (Intel)
  Memoria-<versão>-windows-x64.zip    pasta Memoria (duplo clique em Memoria.exe)

Cada zip leva o Python do python-build-standalone (versão e SHA-256 em release.conf),
o wheel e as dependências fixadas em constraints.txt, já compiladas (.pyc).
Corre no Mac e no Linux (CI): as dependências de cada plataforma vêm em wheels
(`uv pip install --python-platform`), por isso nada é compilado em C.

Uso (com o Python 3.12, para os .pyc serem da versão certa):
  uv run --no-project --python 3.12 python scripts/build_portatil.py --wheel dist/memoria-X-py3-none-any.whl
  ... --plataforma macos-arm64      # só esta (pode repetir)

No Mac, no fim, extrai cada zip do Mac com o ditto e corre o selftest.
Só usa a biblioteca padrão, o uv e o curl. Pastas de trabalho em build/portatil/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from memoria import portatil  # noqa: E402  (nomes e plataformas partilhados com a app)
from memoria.config import ler_conf  # noqa: E402

MODELOS = RAIZ / "portatil"
TRABALHO = RAIZ / "build" / "portatil"

# O que a app não usa (relativo a sys.prefix). Poupa cerca de 30 MB por plataforma.
APARAR = {
    "macos": [
        "include", "share", "lib/pkgconfig", "lib/itcl*", "lib/tcl*", "lib/tk*", "lib/thread*",
        "lib/libtcl*", "lib/libtk*", "lib/libpython*.dylib",  # o python3.12 do PBS é estático
        "bin/2to3*", "bin/idle*", "bin/pip*", "bin/pydoc*", "bin/python3*-config", "bin/python",
        "lib/python3.*/idlelib", "lib/python3.*/tkinter", "lib/python3.*/turtledemo",
        "lib/python3.*/turtle.py", "lib/python3.*/ensurepip", "lib/python3.*/lib2to3",
        "lib/python3.*/lib-dynload/_tkinter*", "lib/python3.*/site-packages/pip*",
    ],
    "windows": [
        "include", "libs", "Scripts", "tcl",
        "Lib/idlelib", "Lib/tkinter", "Lib/turtledemo", "Lib/turtle.py", "Lib/ensurepip", "Lib/lib2to3",
        "Lib/site-packages/pip*",
        "DLLs/_tkinter.pyd", "DLLs/tcl*.dll", "DLLs/tk*.dll", "DLLs/_test*.pyd", "DLLs/_ctypes_test.pyd",
    ],
}
# Depois de instalar as dependências (relativo a site-packages).
APARAR_SITE = ["bin", "PyObjCTest", "PyWin32.chm"]


def falha(msg: str) -> None:
    sys.exit(f"build_portatil: {msg}")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def obter_python(c: dict[str, str], plataforma: str) -> Path:
    """Descarrega (ou reutiliza da cache) o Python e confirma o SHA-256 fixado."""
    triplo = portatil.PLATAFORMAS[plataforma]
    nome = f"cpython-{c['PORTATIL_PYTHON']}+{c['PORTATIL_PBS_TAG']}-{triplo}-install_only_stripped.tar.gz"
    esperado = c[f"PORTATIL_SHA256_{plataforma.replace('-', '_').upper()}"].lower()
    destino = TRABALHO / "cache" / nome
    if destino.is_file() and sha256(destino) == esperado:
        return destino
    url = c["PORTATIL_PBS_URL"].replace("{tag}", c["PORTATIL_PBS_TAG"]).replace("{file}", nome.replace("+", "%2B"))
    print(f"  a descarregar {nome}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(nome + ".parcial")
    r = subprocess.run(["curl", "-fsSL", "--retry", "3", "--proto", "=https", "--proto-redir", "=https", "-o", str(parcial), url])
    if r.returncode != 0:
        falha(f"não consegui descarregar {url}")
    real = sha256(parcial)
    if real != esperado:
        parcial.unlink()
        falha(f"SHA-256 não confere: {nome}\n  esperado {esperado}\n  obtido   {real}")
    parcial.replace(destino)
    return destino


def aparar(base: Path, padroes: list[str]) -> None:
    for padrao in padroes:
        for caminho in base.glob(padrao):
            if caminho.is_dir() and not caminho.is_symlink():
                shutil.rmtree(caminho)
            else:
                caminho.unlink()


def instalar(wheel: Path, site: Path, plataforma: str, c: dict[str, str], menor: str) -> None:
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        falha("falta o uv.")
    env = dict(os.environ)
    if plataforma.startswith("macos"):
        # Sem isto, o uv escolhe wheels para o macOS mais antigo ainda suportado (13).
        env["MACOSX_DEPLOYMENT_TARGET"] = c["PORTATIL_MACOS_MINIMO"]
    cmd = [
        uv, "pip", "install", "--quiet", "--target", str(site), "--python", sys.executable,
        "--python-platform", portatil.PLATAFORMAS[plataforma], "--python-version", menor,
        "--only-binary", ":all:", "--no-binary", "proxy-tools", "--link-mode", "copy",
        "--constraints", str(RAIZ / "constraints.txt"), str(wheel),
    ]
    if subprocess.run(cmd, env=env).returncode != 0:
        falha(f"uv pip install falhou para {plataforma}.")


def copiar_crlf(origem: Path, destino: Path, bom: bool = False, **marcadores: str) -> None:
    texto = origem.read_text("utf-8")
    for chave, valor in marcadores.items():
        texto = texto.replace("{" + chave + "}", valor)
    destino.write_text(texto, encoding="utf-8-sig" if bom else "utf-8", newline="\r\n")


def modelos_macos(app: Path, versao: str, c: dict[str, str]) -> None:
    pasta = app / "Contents" / "MacOS"
    pasta.mkdir(parents=True)
    lancador = pasta / "memoria"
    shutil.copyfile(MODELOS / "macos" / "memoria", lancador)
    lancador.chmod(0o755)
    plist = (MODELOS / "macos" / "Info.plist").read_text("utf-8")
    plist = plist.replace("{versao}", versao).replace("{macos_minimo}", c["PORTATIL_MACOS_MINIMO"])
    (app / "Contents" / "Info.plist").write_text(plist, "utf-8")
    (app / "Contents" / "PkgInfo").write_text("APPL????", "ascii")


def modelos_windows(pasta: Path, site: Path, versao: str, menor: str) -> None:
    dll = "python" + menor.replace(".", "")
    if not (pasta / f"{dll}.dll").is_file():
        falha(f"não encontrei {dll}.dll no Python para Windows.")
    # Memoria.exe é o pythonw.exe (sem consola); o sitecustomize.py abre a janela.
    (pasta / "pythonw.exe").rename(pasta / "Memoria.exe")
    copiar_crlf(MODELOS / "windows" / "python._pth", pasta / f"{dll}._pth")
    shutil.copyfile(MODELOS / "windows" / "sitecustomize.py", site / "sitecustomize.py")
    copiar_crlf(MODELOS / "windows" / "memoria.cmd", pasta / "memoria.cmd")
    for leia in ("README.txt", "LEIA-ME.txt"):
        copiar_crlf(MODELOS / "windows" / leia, pasta / leia, bom=True, versao=versao)


def compilar(prefixo: Path) -> None:
    """Gera os .pyc com hash, sem verificação: a app nunca precisa de os reescrever.

    Os .pyc normais comparam datas, que o zip não guarda com precisão. Iam ser
    recompilados em cada arranque (o lançador não deixa escrever dentro da app).
    """
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "-f", "-j", "0", "--invalidation-mode", "unchecked-hash", str(prefixo)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        falha(f"compileall falhou:\n{(r.stdout + r.stderr)[-3000:]}")


def montar(plataforma: str, tarball: Path, wheel: Path, versao: str, c: dict[str, str], menor: str) -> tuple[Path, str]:
    """Monta a app em build/portatil/<plataforma>/ e devolve (pasta, nome da raiz)."""
    so = plataforma.split("-")[0]
    base = TRABALHO / plataforma
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    with tarfile.open(tarball) as t:
        t.extractall(base, filter="data")
    if so == "macos":
        raiz = base / "Memoria.app"
        prefixo = raiz / "Contents" / "Resources" / "python"
        prefixo.parent.mkdir(parents=True)
        (base / "python").rename(prefixo)
        site = prefixo / "lib" / f"python{menor}" / "site-packages"
        rel_prefixo, comando = "Contents/Resources/python", ["Contents/MacOS/memoria"]
    else:
        raiz = prefixo = base / "Memoria"
        (base / "python").rename(prefixo)
        site = prefixo / "Lib" / "site-packages"
        rel_prefixo, comando = ".", ["python.exe", "-m", "memoria"]
    if not site.is_dir():
        falha(f"não encontrei {site}")

    aparar(prefixo, APARAR[so])
    instalar(wheel, site, plataforma, c, menor)
    aparar(site, APARAR_SITE)
    if so == "macos":
        modelos_macos(raiz, versao, c)
    else:
        modelos_windows(prefixo, site, versao, menor)
    marcador = {
        "formato": 1,
        "versao": versao,
        "plataforma": plataforma,
        "python": c["PORTATIL_PYTHON"],
        "prefixo": rel_prefixo,
        "comando": comando,
    }
    (prefixo / portatil.MARCADOR).write_text(json.dumps(marcador, indent=2) + "\n", "utf-8")
    compilar(prefixo)
    return base, raiz.name


def zipar(base: Path, raiz: str, destino: Path, data: tuple[int, ...]) -> None:
    """Zip com permissões e ligações simbólicas (o Finder, o ditto e o unzip respeitam-nas).

    Ordem e datas fixas: o mesmo conteúdo dá o mesmo zip.
    """
    caminhos = sorted((base / raiz).rglob("*"), key=lambda p: p.relative_to(base).as_posix())
    parcial = destino.with_name(destino.name + ".parcial")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED) as z:
        for caminho in [base / raiz, *caminhos]:
            nome = caminho.relative_to(base).as_posix()
            if caminho.is_symlink():
                info = zipfile.ZipInfo(nome, data)
                info.external_attr = (stat.S_IFLNK | 0o755) << 16
                info.create_system = 3
                z.writestr(info, os.readlink(caminho), compress_type=zipfile.ZIP_STORED)
            elif caminho.is_dir():
                info = zipfile.ZipInfo(nome + "/", data)
                info.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
                info.create_system = 3
                z.writestr(info, b"")
            else:
                modo = 0o755 if caminho.stat().st_mode & stat.S_IXUSR else 0o644
                info = zipfile.ZipInfo(nome, data)
                info.external_attr = (stat.S_IFREG | modo) << 16
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(caminho, "rb") as f, z.open(info, "w") as saida:
                    shutil.copyfileobj(f, saida, 1 << 20)
    parcial.replace(destino)


def data_fixa() -> tuple[int, ...]:
    epoca = os.environ.get("SOURCE_DATE_EPOCH")
    if not epoca:
        r = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=RAIZ, capture_output=True, text=True)
        epoca = r.stdout.strip() if r.returncode == 0 else ""
    return time.gmtime(int(epoca or time.time()))[:6]


def testar(zip_: Path, plataforma: str) -> None:
    """No Mac: extrai como o setup (ditto) e corre o selftest com uma MEMORIA_HOME temporária."""
    if platform.system() != "Darwin" or not plataforma.startswith("macos"):
        return
    if plataforma == "macos-x86_64" and platform.machine() == "arm64":
        if subprocess.run(["arch", "-x86_64", "/usr/bin/true"], capture_output=True).returncode != 0:
            print("  selftest saltado: sem Rosetta neste Mac.")
            return
    with tempfile.TemporaryDirectory(prefix="memoria-portatil-") as tmp:
        subprocess.run(["ditto", "-x", "-k", str(zip_), tmp], check=True)
        lancador = Path(tmp) / "Memoria.app" / "Contents" / "MacOS" / "memoria"
        env = {**os.environ, "MEMORIA_HOME": str(Path(tmp) / "home"), "MEMORIA_SEM_UPDATE": "1"}
        r = subprocess.run([str(lancador), "selftest"], env=env, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            falha(f"selftest de {zip_.name} falhou:\n{r.stdout}{r.stderr}")
        print(f"  selftest: OK ({plataforma})")


def main() -> int:
    p = argparse.ArgumentParser(description="Gera os zips da versão portátil.")
    p.add_argument("--wheel", type=Path, required=True)
    p.add_argument("--dist", type=Path, default=RAIZ / "dist")
    p.add_argument("--plataforma", action="append", choices=list(portatil.PLATAFORMAS))
    p.add_argument("--sem-teste", action="store_true", help="não correr o selftest no fim (Mac)")
    a = p.parse_args()

    c = ler_conf((RAIZ / "release.conf").read_text("utf-8"))
    menor = ".".join(c["PORTATIL_PYTHON"].split(".")[:2])
    if f"{sys.version_info.major}.{sys.version_info.minor}" != menor:
        falha(f"corre com o Python {menor}: uv run --no-project --python {menor} python {Path(__file__).name} ...")
    nome = a.wheel.name
    if not a.wheel.is_file() or not nome.startswith("memoria-") or not nome.endswith("-py3-none-any.whl"):
        falha(f"wheel inválido: {a.wheel}")
    versao = nome.removeprefix("memoria-").removesuffix("-py3-none-any.whl")

    data = data_fixa()
    for plataforma in a.plataforma or list(portatil.PLATAFORMAS):
        print(f"== portátil: {plataforma}")
        tarball = obter_python(c, plataforma)
        base, raiz = montar(plataforma, tarball, a.wheel.resolve(), versao, c, menor)
        destino = a.dist / portatil.nome_zip(versao, plataforma)
        zipar(base, raiz, destino, data)
        print(f"  {destino.name}: {destino.stat().st_size / 1e6:.1f} MB")
        if not a.sem_teste:
            testar(destino, plataforma)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
