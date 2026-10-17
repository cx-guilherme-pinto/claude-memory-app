"""`agent-memory update`: instala a release mais recente.

1. Descobre a tag mais recente com `git ls-remote --tags <MEMORY_APP_REPO_URL>` (sem API).
   Sem git no PATH, usa o git que o setup do kit deixa no perfil (ver _git_do_kit).
2. Descarrega SHA256SUMS, o wheel e constraints.txt para uma pasta temporária,
   pelo padrão RELEASE_DOWNLOAD_URL ({repo}/releases/download/{version}/{file}).
3. Verifica os SHA-256.
4. Corre `uv tool install --force --python <versão> <wheel> --constraints <ficheiro>`
   (num Mac sem as Command Line Tools, com um install_name_tool vazio no PATH: ver ambiente_uv).
   Na versão portátil, em vez disso, troca a pasta da app pelo zip novo (ver portatil.py).
5. Reconstrói o índice. Nunca toca nos ficheiros Markdown.

Repositório privado (só em desenvolvimento): se o download anónimo falhar com
401/403/404, usa AGENT_MEMORY_DOWNLOAD_TOKEN (ou a antiga MEMORIA_DOWNLOAD_TOKEN) ou o token que o git guarda para esse
servidor (`git credential fill`). O token nunca é impresso nem gravado.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from memoria import __version__, config
from memoria.i18n import t

_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_AMBIENTE_GIT = {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "", "SSH_ASKPASS": ""}


class ErroUpdate(RuntimeError):
    pass


def versao_tuplo(texto: str) -> tuple[int, int, int] | None:
    m = _TAG.match(texto.strip())
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def tags_de_ls_remote(saida: str) -> list[str]:
    """Extrai as tags estáveis vX.Y.Z da saída de `git ls-remote --tags`."""
    tags = set()
    for linha in saida.splitlines():
        partes = linha.split()
        if len(partes) != 2 or not partes[1].startswith("refs/tags/"):
            continue
        nome = partes[1][len("refs/tags/"):].removesuffix("^{}")
        if versao_tuplo(nome):
            tags.add(nome)
    return sorted(tags, key=lambda t: versao_tuplo(t))


def _clt_ok() -> bool:
    """macOS: as Command Line Tools (ou o Xcode) estão instaladas a sério?

    O `xcode-select -p` pode apontar para uma pasta que já não existe (ferramentas apagadas): nesse caso
    o /usr/bin/git e os outros "shims" da Apple abrem o diálogo de instalação. Igual ao ws_clt_ok do setup do kit.
    """
    try:
        r = subprocess.run(["xcode-select", "-p"], capture_output=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return False
    pasta = os.fsdecode(r.stdout).strip()
    if r.returncode != 0 or not pasta:
        return False
    git = Path(pasta) / "usr" / "bin" / "git"
    return git.is_file() and os.access(git, os.X_OK)


def _git_do_kit(windows: bool | None = None) -> str | None:
    """O git que o setup do kit deixa no perfil (sem admin), para quando não há git no PATH."""
    casa = Path.home()  # no Windows, %USERPROFILE%
    if windows is None:
        windows = os.name == "nt"
    if windows:
        candidatos = [casa / ".workshop-claude" / "git" / "cmd" / "git.exe"]
        # Onde o setup do kit também procura (Get-WsGit): o Git for Windows só para o utilizador e o do sistema.
        for base, partes in ((os.environ.get("LOCALAPPDATA"), ("Programs", "Git")), (os.environ.get("ProgramFiles"), ("Git",))):
            if base:
                candidatos.append(Path(base, *partes, "cmd", "git.exe"))
    else:
        # O wrapper do git portátil (dugite-native, em ~/.workshop-claude/git), sem as Command Line Tools.
        candidatos = [casa / ".workshop-claude" / "bin" / "git"]
    for c in candidatos:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def _git() -> str:
    git = shutil.which("git")
    # Sem as Command Line Tools, /usr/bin/git é só um "shim" que abre o diálogo de instalação: nunca o chamamos.
    shim = bool(git) and sys.platform == "darwin" and os.path.normpath(git) == "/usr/bin/git" and not _clt_ok()
    if git and not shim:
        return git
    do_kit = _git_do_kit()
    if do_kit:
        return do_kit
    raise ErroUpdate(t("up.sem_clt" if shim else "up.sem_git"))


def _correr_git(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    """Como subprocess.run, mas um timeout mata o git E os ajudantes dele (git-remote-https).

    O subprocess.run só mata o git: o git-remote-https ficava preso num proxy que não responde, depois de o
    agent-memory sair (e no Windows o run() esperava por ele para sempre, pelos pipes que ele ainda tem).
    """
    extra: dict = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, **_AMBIENTE_GIT},
        **extra,
    )
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
        p.kill()
        try:
            p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def _proxy() -> tuple[str, str] | None:
    """(variável, proxy sem utilizador nem palavra-passe) do proxy que o git usa, se houver."""
    for nome in ("https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY"):
        valor = os.environ.get(nome, "").strip()
        if valor:
            try:
                u = urlsplit(valor if "://" in valor else "http://" + valor)
                porta = f":{u.port}" if u.port else ""
            except ValueError:
                return nome, "?"
            return nome, f"{u.scheme}://{u.hostname or '?'}{porta}"  # nunca o utilizador:palavra-passe
    return None


def _explicar(erro: str, repo_url: str) -> str:
    """O stderr do git ls-remote numa frase com a causa e o passo seguinte."""
    px = _proxy()
    host = urlsplit(repo_url).hostname or repo_url
    if "xcrun: error" in erro or "invalid active developer path" in erro:
        return f"{t('up.sem_clt')} {t('up.dica_clt')}"
    if re.search(r"CONNECT tunnel failed, response 30\d|Received HTTP code 30\d", erro):
        return t("up.portal")
    if px and re.search(r"Failed to connect to|CONNECT tunnel failed|Received HTTP code|Could not resolve proxy|proxy", erro, re.I):
        return t("up.proxy", proxy=px[1], var=px[0])
    if re.search(r"Could not resolve host|Failed to connect to|Network is unreachable|Couldn't connect", erro):
        return t("up.sem_rede", host=host)
    return t("up.ls_remote", erro=erro[:300])


def ultima_tag(repo_url: str, timeout: float = 30) -> str | None:
    try:
        r = _correr_git([_git(), "ls-remote", "--tags", "--refs", repo_url], timeout)
    except subprocess.TimeoutExpired as erro:
        px = _proxy()
        host = urlsplit(repo_url).hostname or repo_url
        dica = t("up.proxy", proxy=px[1], var=px[0]) if px else t("up.sem_rede", host=host)
        raise ErroUpdate(f"{t('up.git_lento', s=f'{timeout:.0f}')} {dica}") from erro
    if r.returncode != 0:
        raise ErroUpdate(_explicar(r.stderr.strip(), repo_url))
    tags = tags_de_ls_remote(r.stdout)
    return tags[-1] if tags else None


def nome_wheel(versao: str) -> str:
    return f"memoria-{versao.lstrip('v')}-py3-none-any.whl"


def ler_sha256sums(texto: str) -> dict[str, str]:
    somas = {}
    for linha in texto.splitlines():
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", linha.strip())
        if m:
            somas[m.group(2).strip()] = m.group(1).lower()
    return somas


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _contexto_ssl() -> ssl.SSLContext:
    # Usa os certificados do sistema (proxies corporativos com CA própria).
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return ssl.create_default_context()


def _token_git(url: str) -> str | None:
    """Token que o git guarda para este servidor. Nunca é impresso."""
    partes = urlsplit(url)
    if not partes.hostname:
        return None
    pedido = f"protocol={partes.scheme}\nhost={partes.hostname}\n\n"
    try:
        r = subprocess.run(
            [_git(), "credential", "fill"],
            input=pedido,
            capture_output=True,
            text=True,
            timeout=20,
            env={**os.environ, **_AMBIENTE_GIT},
        )
    except (ErroUpdate, OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    for linha in r.stdout.splitlines():
        if linha.startswith("password="):
            return linha[len("password="):] or None
    return None


def descarregar(url: str, destino: Path, token: str | None = None, timeout: float = 120) -> None:
    config.validar_url(url)
    cabecalhos = {"User-Agent": f"agent-memory/{__version__}"}
    if token:
        cabecalhos["Authorization"] = f"token {token}"
    pedido = urllib.request.Request(url, headers=cabecalhos)
    contexto = _contexto_ssl() if url.startswith("https:") else None
    with urllib.request.urlopen(pedido, timeout=timeout, context=contexto) as resposta, open(destino, "wb") as f:
        shutil.copyfileobj(resposta, f)


class Descarregador:
    """Tenta sem autenticação; se o servidor recusar, tenta com token (dev)."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._tentou_token = False

    def obter(self, url: str, destino: Path) -> None:
        try:
            descarregar(url, destino, self._token)
            return
        except urllib.error.HTTPError as erro:
            if erro.code not in (401, 403, 404) or self._tentou_token:
                raise ErroUpdate(t("up.download_falhou", codigo=erro.code, url=url)) from None
        except urllib.error.URLError as erro:
            raise ErroUpdate(t("up.sem_ligacao", host=urlsplit(url).hostname, motivo=erro.reason)) from None
        self._tentou_token = True
        self._token = config.ambiente(config.ENV_TOKEN) or _token_git(url)
        if not self._token:
            raise ErroUpdate(t("up.sem_credenciais", url=url))
        try:
            descarregar(url, destino, self._token)
        except urllib.error.HTTPError as erro:
            raise ErroUpdate(t("up.download_falhou", codigo=erro.code, url=url)) from None


def encontrar_uv(cfg: dict[str, str]) -> str:
    candidatos = [cfg.get("UV"), shutil.which("uv")]
    casa = Path.home()
    exe = "uv.exe" if os.name == "nt" else "uv"
    candidatos += [str(casa / ".local" / "bin" / exe), str(casa / ".cargo" / "bin" / exe)]
    for c in candidatos:
        if c and Path(c).is_file():
            return c
    raise ErroUpdate(t("up.sem_uv"))


def comando_uv(uv: str, wheel: Path, constraints: Path, python: str) -> list[str]:
    return [uv, "tool", "install", "--force", "--python", python, str(wheel), "--constraints", str(constraints)]


def ambiente_uv(pasta: Path) -> dict[str, str] | None:
    """Ambiente do `uv tool install`. None: o do processo, sem mudanças.

    macOS sem as Command Line Tools: depois de descarregar um Python novo, o uv corre `install_name_tool`
    (procurado no PATH), e /usr/bin/install_name_tool é um "shim" da Apple que abre o diálogo
    "instalar ferramentas de programador". Só neste comando, um install_name_tool vazio (em `pasta`)
    fica primeiro no PATH; o acerto da libpython só serve para compilar extensões em C.
    Como o ws_uv_tool_install do setup do kit; também quando o which não encontra nenhum (o uv só o
    procuraria ao executar), porque o falso é inofensivo. Um install_name_tool a sério no PATH fica.
    """
    if sys.platform != "darwin":
        return None
    encontrado = shutil.which("install_name_tool")
    if encontrado and os.path.normpath(encontrado) != "/usr/bin/install_name_tool":
        return None
    if _clt_ok():
        return None
    falsos = pasta / "no-clt"
    try:
        falsos.mkdir(parents=True, exist_ok=True)
        falso = falsos / "install_name_tool"
        falso.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        falso.chmod(0o755)
    except OSError:
        return None
    caminho = os.environ.get("PATH")
    return {**os.environ, "PATH": os.pathsep.join([str(falsos), caminho] if caminho else [str(falsos)])}


def verificar(timeout: float = 10) -> dict:
    """Só verifica (usado pela UI, em segundo plano)."""
    cfg = config.definicoes()
    repo = cfg.get("MEMORY_APP_REPO_URL")
    if not repo:
        return {"atual": __version__, "disponivel": False, "erro": "no MEMORY_APP_REPO_URL"}
    try:
        tag = ultima_tag(repo, timeout=timeout)
    except ErroUpdate as erro:
        return {"atual": __version__, "disponivel": False, "erro": str(erro)}
    atual = versao_tuplo(__version__) or (0, 0, 0)
    nova = versao_tuplo(tag) if tag else None
    return {
        "atual": __version__,
        "ultima": tag,
        "disponivel": bool(nova and nova > atual),
    }


def _info(msg: str) -> None:
    if sys.stderr:
        print(msg, file=sys.stderr)


def atualizar(forcar: bool = False, versao: str | None = None, so_verificar: bool = False) -> int:
    cfg = config.definicoes()
    repo = cfg.get("MEMORY_APP_REPO_URL")
    if not repo:
        raise ErroUpdate(t("up.falta_repo", caminho=config.config_path()))
    tag = versao or ultima_tag(repo)
    if not tag:
        raise ErroUpdate(t("up.sem_versoes"))
    atual = versao_tuplo(__version__) or (0, 0, 0)
    nova = versao_tuplo(tag)
    if not nova:
        raise ErroUpdate(t("up.versao_invalida", tag=tag))
    if not tag.startswith("v"):
        tag = "v" + tag
    _info(t("up.versoes", atual=__version__, ultima=tag.lstrip("v")))
    if so_verificar:
        return 0
    if nova <= atual and not forcar:
        _info(t("up.ja_recente"))
        return 0

    from memoria import portatil

    if portatil.info():
        return portatil.atualizar(cfg, tag, Descarregador())

    uv = encontrar_uv(cfg)
    python = cfg.get("PYTHON_VERSION") or "3.12"
    pasta = Path(tempfile.mkdtemp(prefix="agent-memory-update-"))
    try:
        baixar = Descarregador()
        somas_ficheiro = pasta / "SHA256SUMS"
        baixar.obter(config.url_asset(cfg, tag, "SHA256SUMS"), somas_ficheiro)
        somas = ler_sha256sums(somas_ficheiro.read_text("utf-8"))
        ficheiros = {}
        for nome in (nome_wheel(tag), "constraints.txt"):
            if nome not in somas:
                raise ErroUpdate(t("up.falta_soma", nome=nome, tag=tag))
            destino = pasta / nome
            _info(t("up.a_descarregar", nome=nome))
            baixar.obter(config.url_asset(cfg, tag, nome), destino)
            if sha256(destino) != somas[nome]:
                raise ErroUpdate(t("up.sha_instalado", nome=nome))
            ficheiros[nome] = destino
        cmd = comando_uv(uv, ficheiros[nome_wheel(tag)], ficheiros["constraints.txt"], python)
        if os.name == "nt":
            return _instalar_depois_de_sair(cmd, pasta)
        _info(t("up.a_instalar"))
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, env=ambiente_uv(pasta))
        if r.returncode != 0:
            raise ErroUpdate(t("up.uv_falhou", codigo=r.returncode))
    finally:
        if os.name != "nt":
            shutil.rmtree(pasta, ignore_errors=True)
    reindexar_com_nova_versao()
    _info(t("up.atualizado", versao=tag.lstrip("v")))
    return 0


EXECUTAVEIS = ("agent-memory", "memoria")  # o nome de agora e o antigo (os dois instalados pelo uv)


def executavel_memoria() -> str | None:
    """O executável `agent-memory` instalado pelo uv (o novo, depois do update).

    Ao lado do que está a correr, primeiro: o update pode vir de uma versão antiga, só com `memoria`.
    """
    sufixo = ".exe" if os.name == "nt" else ""
    aqui = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    if aqui and aqui.is_file() and aqui.name in {f"{n}{sufixo}" for n in EXECUTAVEIS}:
        for nome in EXECUTAVEIS:
            vizinho = aqui.with_name(f"{nome}{sufixo}")
            if vizinho.is_file():
                return str(vizinho)
        return str(aqui)
    for nome in EXECUTAVEIS:
        encontrado = shutil.which(nome)
        if encontrado:
            return encontrado
    return None


def reindexar_com_nova_versao() -> None:
    exe = executavel_memoria()
    cmd = [exe, "reindex"] if exe else [sys.executable, "-m", "memoria", "reindex"]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        _info(t("up.reindex_falhou"))


def _instalar_depois_de_sair(cmd: list[str], pasta: Path) -> int:
    """Windows: não se pode substituir o venv enquanto este processo corre.

    Lança um PowerShell que espera que este processo termine, instala e reindexa.
    Aviso: feche também o Claude Code (que corre `agent-memory mcp`) antes de atualizar.
    """

    def ps(texto: str) -> str:
        return "'" + texto.replace("'", "''") + "'"

    exe = executavel_memoria() or "agent-memory"
    linhas = [
        "$ErrorActionPreference = 'Stop'",
        f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue",
        f"Write-Host {ps(t('ps.a_instalar'))}",
        "& " + " ".join(ps(c) for c in cmd),
        f"if ($LASTEXITCODE -ne 0) {{ Write-Host {ps(t('ps.uv_falhou'))}; Read-Host {ps(t('ps.enter'))}; exit 1 }}",
        f"& {ps(exe)} reindex",
        f"Remove-Item -Recurse -Force {ps(str(pasta))} -ErrorAction SilentlyContinue",
        f"Write-Host {ps(t('ps.atualizada'))}",
        "Start-Sleep -Seconds 3",
    ]
    script = pasta / "install.ps1"
    # Com BOM: o PowerShell 5.1 lê UTF-8 corretamente (caminhos com acentos).
    script.write_text("\r\n".join(linhas) + "\r\n", encoding="utf-8-sig")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        close_fds=True,
    )
    _info(t("up.nova_janela"))
    return 0
