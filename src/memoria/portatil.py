"""Versão portátil: um zip com o Python e as dependências, sem instalador.

O build (scripts/build_portatil.py) escreve portatil.json em sys.prefix.
Sem esse ficheiro, nada aqui é usado e a app comporta-se como a instalação com o uv.

A "raiz" é a pasta que o update substitui:
  macOS    Memoria.app                      raiz
           Memoria.app/Contents/MacOS/memoria   lançador (janela, CLI e MCP)
           Memoria.app/Contents/Resources/python   sys.prefix
  Windows  Memoria                          raiz e sys.prefix
           Memoria/Memoria.exe              cópia do pythonw.exe (duplo clique)
           Memoria/python.exe -m memoria    CLI e MCP
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from memoria.i18n import t

MARCADOR = "portatil.json"

# Plataforma -> triplo do python-build-standalone e do `uv pip install --python-platform`.
PLATAFORMAS = {
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
    "windows-x64": "x86_64-pc-windows-msvc",
}

# Ficheiro do pythonnet que o .NET recusa carregar se tiver a marca da Internet.
DLL_SENTINELA = Path("Lib", "site-packages", "pythonnet", "runtime", "Python.Runtime.dll")


def nome_zip(versao: str, plataforma: str) -> str:
    return f"Memoria-{versao.lstrip('v')}-{plataforma}.zip"


def info(prefixo: Path | None = None) -> dict | None:
    """Conteúdo de portatil.json, ou None fora da versão portátil."""
    try:
        dados = json.loads((Path(prefixo or sys.prefix) / MARCADOR).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict) or dados.get("plataforma") not in PLATAFORMAS:
        return None
    return dados


def raiz(prefixo: Path | None = None) -> Path:
    prefixo = Path(prefixo or sys.prefix).resolve()
    niveis = len(Path(info(prefixo)["prefixo"]).parts)
    return prefixo.parents[niveis - 1] if niveis else prefixo


def comando(prefixo: Path | None = None) -> list[str]:
    """Comando absoluto que corre `memoria` nesta versão portátil."""
    exe, *resto = info(prefixo)["comando"]
    return [str(raiz(prefixo) / exe), *resto]


def comando_claude(prefixo: Path | None = None) -> str:
    """O comando para ligar ao Claude Code, pronto a copiar."""
    partes = ["claude", "mcp", "add", "--scope", "user", "memoria", "--", *comando(prefixo), "mcp"]
    return subprocess.list2cmdline(partes) if os.name == "nt" else shlex.join(partes)


def translocada(caminho: Path | None = None) -> bool:
    """macOS: uma app em quarentena aberta sem ser movida corre de uma cópia temporária."""
    return "/AppTranslocation/" in str(caminho or raiz())


def desbloquear(pasta: Path | None = None) -> int:
    """Windows: tira a marca "transferido da Internet" (Zone.Identifier) dos ficheiros da app.

    O Explorador copia essa marca do zip para cada ficheiro extraído. Com ela, o .NET
    recusa as DLL do pythonnet e do WebView2 (erro 0x80131515) e a janela falha.
    Não precisa de admin: os ficheiros são do próprio utilizador. Devolve quantos limpou.
    """
    if os.name != "nt":
        return 0
    pasta = Path(pasta or raiz())
    if not os.path.exists(f"{pasta / DLL_SENTINELA}:Zone.Identifier"):
        return 0
    limpos = 0
    for base, _, nomes in os.walk(pasta):
        for nome in nomes:
            try:
                os.remove(os.path.join(base, nome) + ":Zone.Identifier")
                limpos += 1
            except OSError:
                pass
    return limpos


def arrancar_janela() -> int:
    """Entrada de Memoria.exe (Windows). Chamada pelo sitecustomize.py da versão portátil."""
    try:
        desbloquear()
    except OSError:
        pass
    from memoria.cli import main_gui

    try:
        return main_gui()
    except BaseException:  # sem consola: o erro fica no log
        import traceback

        if sys.stderr:
            traceback.print_exc()
        return 1
    finally:
        for fluxo in (sys.stdout, sys.stderr):
            try:
                fluxo.flush()
            except Exception:
                pass


# --- update ------------------------------------------------------------------


def extrair(zip_: Path, destino: Path) -> None:
    """Extrai o zip mantendo permissões e ligações simbólicas (o zipfile não as repõe)."""
    destino = destino.resolve()
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_) as z:
        for membro in z.infolist():
            alvo = (destino / membro.filename).resolve()
            if alvo != destino and destino not in alvo.parents:
                raise ValueError(t("erro.zip_caminho", ficheiro=membro.filename))
            modo = membro.external_attr >> 16
            if membro.is_dir():
                alvo.mkdir(parents=True, exist_ok=True)
            elif stat.S_ISLNK(modo) and os.name != "nt":
                ligacao = z.read(membro).decode("utf-8")
                if os.path.isabs(ligacao) or destino not in (alvo.parent / ligacao).resolve().parents:
                    raise ValueError(t("erro.zip_ligacao", ficheiro=membro.filename))
                alvo.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(ligacao, alvo)
            else:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with z.open(membro) as origem, open(alvo, "wb") as f:
                    shutil.copyfileobj(origem, f)
                if modo and os.name != "nt":
                    os.chmod(alvo, stat.S_IMODE(modo))


def _verificar_nova(versao: str, comando_nova: list[str]) -> None:
    from memoria.update import ErroUpdate

    r = subprocess.run(
        [*comando_nova, "selftest"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "MEMORIA_SEM_UPDATE": "1"},
    )
    if r.returncode != 0:
        raise ErroUpdate(t("pt.selftest_falhou", versao=versao) + "\n" + (r.stdout + r.stderr)[-1500:])


def atualizar(cfg: dict[str, str], tag: str, baixar, prefixo: Path | None = None) -> int:
    """Descarrega o zip da versão `tag`, verifica-o e troca a pasta da app no mesmo sítio.

    O caminho não muda, por isso o Claude Code continua ligado sem refazer o `claude mcp add`.
    """
    from memoria import config
    from memoria.update import ErroUpdate, _info, ler_sha256sums, sha256

    dados = info(prefixo)
    atual = raiz(prefixo)
    if translocada(atual):
        raise ErroUpdate(t("pt.copia_temporaria"))
    nome = nome_zip(tag, dados["plataforma"])
    try:
        pasta = Path(tempfile.mkdtemp(prefix=".memoria-update-", dir=atual.parent))
    except OSError as erro:
        raise ErroUpdate(t("st.sem_escrita", pasta=atual.parent, erro=erro)) from None
    entregue = False
    try:
        somas_ficheiro = pasta / "SHA256SUMS"
        baixar.obter(config.url_asset(cfg, tag, "SHA256SUMS"), somas_ficheiro)
        somas = ler_sha256sums(somas_ficheiro.read_text("utf-8"))
        if nome not in somas:
            raise ErroUpdate(t("up.falta_soma", nome=nome, tag=tag))
        zip_ = pasta / nome
        _info(t("up.a_descarregar", nome=nome))
        baixar.obter(config.url_asset(cfg, tag, nome), zip_)
        if sha256(zip_) != somas[nome]:
            raise ErroUpdate(t("pt.sha", nome=nome))
        try:
            extrair(zip_, pasta / "nova")
        except (OSError, ValueError, zipfile.BadZipFile) as erro:
            raise ErroUpdate(t("pt.extrair", nome=nome, erro=erro)) from None
        zip_.unlink()
        # O zip tem uma só pasta (Memoria.app ou Memoria). A troca mantém o nome
        # atual, mesmo que o utilizador tenha mudado o nome da app.
        topo = list((pasta / "nova").iterdir())
        nova = topo[0] if len(topo) == 1 else pasta / "nova"
        dados_nova = info(nova / dados["prefixo"])
        if not dados_nova or dados_nova.get("plataforma") != dados["plataforma"]:
            raise ErroUpdate(t("pt.plataforma", nome=nome, plataforma=dados["plataforma"]))
        _info(t("pt.a_verificar"))
        exe, *resto = dados_nova["comando"]
        _verificar_nova(tag, [str(nova / exe), *resto])

        if os.name == "nt":
            entregue = True
            return _trocar_depois_de_sair(atual, nova, pasta, [str(atual / exe), *resto])

        antiga = pasta / "antiga"
        os.rename(atual, antiga)
        try:
            os.rename(nova, atual)
        except OSError:
            os.rename(antiga, atual)
            raise
        r = subprocess.run([*comando(prefixo), "reindex"], stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            _info(t("up.reindex_falhou"))
        _info(t("pt.atualizado", versao=tag.lstrip("v"), pasta=atual))
        _info(t("pt.reabrir"))
        return 0
    finally:
        if not entregue:
            shutil.rmtree(pasta, ignore_errors=True)


def script_troca(atual: Path, nova: Path, pasta: Path, pid: int, reindex: list[str]) -> str:
    """PowerShell que espera pelo fim deste processo e troca a pasta (Windows)."""

    def ps(texto: str) -> str:
        return "'" + str(texto).replace("'", "''") + "'"

    return "\r\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"Wait-Process -Id {pid} -ErrorAction SilentlyContinue",
            f"$atual = {ps(atual)}",
            f"$antiga = {ps(pasta / 'antiga')}",
            "$movida = $false",
            "for ($i = 0; $i -lt 90; $i++) {",
            "    try { Move-Item -LiteralPath $atual -Destination $antiga; $movida = $true; break }",
            "    catch {",
            f"        if ($i -eq 0) {{ Write-Host {ps(t('ps.fecha'))} }}",
            "        Start-Sleep -Seconds 2",
            "    }",
            "}",
            f"if (-not $movida) {{ Write-Host {ps(t('ps.nao_substituiu'))}; Read-Host {ps(t('ps.enter'))}; exit 1 }}",
            f"Move-Item -LiteralPath {ps(nova)} -Destination $atual",
            "& " + " ".join(ps(c) for c in reindex) + " reindex",
            f"Remove-Item -Recurse -Force -LiteralPath {ps(pasta)} -ErrorAction SilentlyContinue",
            f"Write-Host {ps(t('ps.atualizada'))}",
            "Start-Sleep -Seconds 3",
            "",
        ]
    )


def _trocar_depois_de_sair(atual: Path, nova: Path, pasta: Path, reindex: list[str]) -> int:
    """Windows: não se pode mover a pasta enquanto este processo (ou o MCP) a usa."""
    from memoria.update import _info

    script = pasta / "trocar.ps1"
    # Com BOM: o PowerShell 5.1 lê UTF-8 corretamente (caminhos com acentos).
    script.write_text(script_troca(atual, nova, pasta, os.getpid(), reindex), encoding="utf-8-sig")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        close_fds=True,
    )
    _info(t("up.nova_janela"))
    return 0
