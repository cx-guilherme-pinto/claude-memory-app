import hashlib
import json
import os
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from memoria import config, update

GITEA = "https://gitea.exemplo.pt/guilherme/claude-memory-app.git"
PADRAO = "{repo}/releases/download/{version}/{file}"


def test_ler_conf():
    texto = "# comentário\nA=1\n\nB = x=y\nsem_igual\n"
    assert config.ler_conf(texto) == {"A": "1", "B": "x=y"}


def test_release_conf_do_pacote_tem_as_chaves():
    conf = config.release_conf()
    for chave in ("MEMORY_APP_REPO_URL", "RELEASE_DOWNLOAD_URL", "MEMORY_APP_VERSION", "UV_VERSION", "PYTHON_VERSION"):
        assert conf.get(chave), chave


def test_precedencia_env_config_release(home: Path, monkeypatch):
    home.mkdir(parents=True, exist_ok=True)
    assert config.definicoes()["MEMORY_APP_REPO_URL"] == config.release_conf()["MEMORY_APP_REPO_URL"]
    (home / "config.json").write_text(json.dumps({"MEMORY_APP_REPO_URL": GITEA, "outra": {"x": 1}}), "utf-8")
    assert config.definicoes()["MEMORY_APP_REPO_URL"] == GITEA
    monkeypatch.setenv("MEMORY_APP_REPO_URL", "https://github.com/o/n.git")
    assert config.definicoes()["MEMORY_APP_REPO_URL"] == "https://github.com/o/n.git"


# ------------------------------------------------------------ pasta dos dados
@pytest.fixture
def sem_pasta_no_ambiente(monkeypatch, tmp_path):
    casa = tmp_path / "outra-casa"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("USERPROFILE", str(casa))
    monkeypatch.delenv("AGENT_MEMORY_HOME", raising=False)
    monkeypatch.delenv("MEMORIA_HOME", raising=False)
    return casa


def test_pasta_por_omissao_e_agent_memory(sem_pasta_no_ambiente):
    casa = sem_pasta_no_ambiente
    assert config.memoria_home() == casa / ".agent-memory"
    assert config.config_path() == casa / ".agent-memory" / "config.json"
    assert config.pasta_interna() == casa / ".agent-memory" / ".index"


def test_pasta_antiga_continua_se_a_nova_nao_existir(sem_pasta_no_ambiente):
    casa = sem_pasta_no_ambiente
    (casa / ".memoria").mkdir()
    assert config.memoria_home() == casa / ".memoria"  # nada se move
    (casa / ".agent-memory").mkdir()
    assert config.memoria_home() == casa / ".agent-memory"  # a nova, quando existe, ganha
    assert (casa / ".memoria").is_dir()


def test_variaveis_de_ambiente_da_pasta(sem_pasta_no_ambiente, monkeypatch, tmp_path):
    (sem_pasta_no_ambiente / ".memoria").mkdir()
    monkeypatch.setenv("MEMORIA_HOME", str(tmp_path / "antiga"))
    assert config.memoria_home() == tmp_path / "antiga"
    monkeypatch.setenv("AGENT_MEMORY_HOME", str(tmp_path / "nova"))
    assert config.memoria_home() == tmp_path / "nova"  # o nome novo ganha ao antigo


@pytest.mark.parametrize("nome", ["AGENT_MEMORY_NO_UPDATE", "MEMORIA_SEM_UPDATE"])
def test_sem_update_aceita_os_dois_nomes(monkeypatch, nome):
    monkeypatch.delenv("AGENT_MEMORY_NO_UPDATE", raising=False)
    monkeypatch.delenv("MEMORIA_SEM_UPDATE", raising=False)
    assert not config.sem_update()
    monkeypatch.setenv(nome, "1")
    assert config.sem_update()
    assert config.ambiente_sem_update() == {"AGENT_MEMORY_NO_UPDATE": "1", "MEMORIA_SEM_UPDATE": "1"}


def test_executavel_prefere_agent_memory(tmp_path: Path, monkeypatch):
    sufixo = ".exe" if sys.platform == "win32" else ""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    antigo = bin_ / f"memoria{sufixo}"
    antigo.write_text("")
    monkeypatch.setattr(update.sys, "argv", [str(antigo)])
    assert update.executavel_memoria() == str(antigo.resolve())  # só o antigo: usa-o
    novo = bin_ / f"agent-memory{sufixo}"
    novo.write_text("")
    assert update.executavel_memoria() == str(novo.resolve())


def test_config_invalido_e_ignorado(home: Path, capsys):
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text("{nao é json", "utf-8")
    assert config.config_utilizador() == {}
    assert "inválido" in capsys.readouterr().err


@pytest.mark.parametrize(
    "repo,esperado",
    [
        (GITEA, "https://gitea.exemplo.pt/guilherme/claude-memory-app/releases/download/v0.2.0/SHA256SUMS"),
        ("https://github.com/org/claude-memory-app", "https://github.com/org/claude-memory-app/releases/download/v0.2.0/SHA256SUMS"),
        ("https://github.com/org/claude-memory-app.git/", "https://github.com/org/claude-memory-app/releases/download/v0.2.0/SHA256SUMS"),
    ],
)
def test_url_asset(repo, esperado):
    cfg = {"MEMORY_APP_REPO_URL": repo, "RELEASE_DOWNLOAD_URL": PADRAO}
    assert config.url_asset(cfg, "v0.2.0", "SHA256SUMS") == esperado


def test_url_com_marcadores_de_partes():
    cfg = {"MEMORY_APP_REPO_URL": GITEA, "RELEASE_DOWNLOAD_URL": "https://cdn.exemplo/{host}/{owner}/{name}/{version}/{file}"}
    assert config.url_asset(cfg, "v1.0.0", "a.whl") == "https://cdn.exemplo/gitea.exemplo.pt/guilherme/claude-memory-app/v1.0.0/a.whl"


@pytest.mark.parametrize("url", ["http://exemplo.pt/x", "file:///etc/passwd", "ftp://x/y", "javascript:alert(1)"])
def test_urls_recusados(url):
    with pytest.raises(ValueError):
        config.validar_url(url)


def test_marcador_desconhecido():
    with pytest.raises(ValueError, match="Marcador"):
        config.url_asset({"MEMORY_APP_REPO_URL": GITEA, "RELEASE_DOWNLOAD_URL": "{repo}/{nada}"}, "v1", "f")


def test_sem_url_mensagem_clara():
    with pytest.raises(ValueError, match="MEMORY_APP_REPO_URL"):
        config.url_asset({}, "v1", "f")


def test_nenhum_url_no_codigo_python():
    """Nenhum URL do alojamento pode estar escrito no código Python."""
    pacote = Path(config.__file__).parent
    for f in pacote.glob("*.py"):
        texto = f.read_text("utf-8")
        for proibido in ("gitea.", "github.com", "guilhermepinto"):
            assert proibido not in texto, f"{f.name} contém {proibido}"


def test_tags_de_ls_remote():
    saida = "\n".join(
        [
            "aaa\trefs/tags/v0.1.0",
            "bbb\trefs/tags/v0.10.0",
            "ccc\trefs/tags/v0.9.3",
            "ddd\trefs/tags/v0.9.3^{}",
            "eee\trefs/tags/v1.0.0-rc.1",
            "fff\trefs/tags/outra",
            "ggg\trefs/heads/main",
        ]
    )
    assert update.tags_de_ls_remote(saida) == ["v0.1.0", "v0.9.3", "v0.10.0"]


def test_ler_sha256sums():
    texto = f"{'a' * 64}  memoria.whl\n{'B' * 64} *constraints.txt\nlixo\n"
    assert update.ler_sha256sums(texto) == {"memoria.whl": "a" * 64, "constraints.txt": "b" * 64}


def test_comando_uv():
    cmd = update.comando_uv("/bin/uv", Path("/t/m.whl"), Path("/t/c.txt"), "3.12")
    assert cmd == ["/bin/uv", "tool", "install", "--force", "--python", "3.12", "/t/m.whl", "--constraints", "/t/c.txt"]


# ------------------------------------------------------------------ ponta a ponta
class _Servidor:
    """Servidor HTTP local que exige um token (como um repositório privado)."""

    def __init__(self, raiz: Path, token: str | None = None):
        exigido = token

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):  # noqa: N802
                if exigido and self.headers.get("Authorization") != f"token {exigido}":
                    self.send_error(404)
                    return
                super().do_GET()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(raiz)))
        self.porta = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def fechar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _repo_git_com_tags(pasta: Path, tags: list[str]) -> Path:
    repo = pasta / "claude-memory-app.git"
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    for t in tags:
        subprocess.run([*git, "-C", str(repo), "tag", t], check=True)
    return repo


def _preparar_release(tmp_path: Path, versao: str, estragar: bool = False):
    pasta = tmp_path / "srv" / "claude-memory-app" / "releases" / "download" / versao
    pasta.mkdir(parents=True)
    wheel = pasta / update.nome_wheel(versao)
    wheel.write_bytes(b"wheel falso")
    (pasta / "constraints.txt").write_text("pyyaml==6.0.3\n")
    somas = [f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}" for f in (wheel, pasta / "constraints.txt")]
    if estragar:
        wheel.write_bytes(b"wheel adulterado")
    (pasta / "SHA256SUMS").write_text("\n".join(somas) + "\n")
    return tmp_path / "srv"


@pytest.fixture
def uv_falso(tmp_path: Path) -> tuple[Path, Path]:
    registo = tmp_path / "uv-args.json"
    script = tmp_path / "uv"
    script.write_text(
        f"#!{sys.executable}\nimport json, sys, pathlib\n"
        f"args = sys.argv[1:]\n"
        f"assert pathlib.Path(args[5]).read_bytes() == b'wheel falso'\n"
        f"pathlib.Path({str(registo)!r}).write_text(json.dumps(args))\n"
    )
    script.chmod(0o755)
    return script, registo


def _configurar(home: Path, repo: Path, porta: int, uv: Path):
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text(
        json.dumps(
            {
                "MEMORY_APP_REPO_URL": str(repo),
                "RELEASE_DOWNLOAD_URL": f"http://127.0.0.1:{porta}/{{name}}/releases/download/{{version}}/{{file}}",
                "UV": str(uv),
            }
        )
    )


@pytest.mark.skipif(sys.platform == "win32", reason="no Windows a instalação é adiada para depois de sair")
def test_update_ponta_a_ponta(tmp_path: Path, home: Path, mem, uv_falso, monkeypatch):
    nota = mem.adicionar(tipo="licao", titulo="Não tocar", texto="conteúdo", projeto="p")
    antes = Path(nota["caminho"]).read_bytes()
    repo = _repo_git_com_tags(tmp_path, ["v0.1.0", "v9.9.9", "v10.0.0-rc.1"])
    srv = _Servidor(_preparar_release(tmp_path, "v9.9.9"))
    uv, registo = uv_falso
    _configurar(home, repo, srv.porta, uv)
    reindex = []
    monkeypatch.setattr(update, "reindexar_com_nova_versao", lambda: reindex.append(True))
    try:
        assert update.verificar()["ultima"] == "v9.9.9"
        assert update.verificar()["disponivel"] is True
        assert update.atualizar() == 0
    finally:
        srv.fechar()
    args = json.loads(registo.read_text())
    assert args[:5] == ["tool", "install", "--force", "--python", "3.12"]
    assert args[5].endswith("memoria-9.9.9-py3-none-any.whl")
    assert args[6:7] == ["--constraints"] and args[7].endswith("constraints.txt")
    assert reindex == [True]
    assert Path(nota["caminho"]).read_bytes() == antes


def test_update_recusa_sha_errado(tmp_path: Path, home: Path, uv_falso, monkeypatch):
    repo = _repo_git_com_tags(tmp_path, ["v9.9.9"])
    srv = _Servidor(_preparar_release(tmp_path, "v9.9.9", estragar=True))
    uv, registo = uv_falso
    _configurar(home, repo, srv.porta, uv)
    monkeypatch.setattr(update, "reindexar_com_nova_versao", lambda: None)
    try:
        with pytest.raises(update.ErroUpdate, match="SHA-256 não confere"):
            update.atualizar()
    finally:
        srv.fechar()
    assert not registo.exists()


def test_update_repo_privado_usa_token(tmp_path: Path, home: Path, uv_falso, monkeypatch):
    repo = _repo_git_com_tags(tmp_path, ["v9.9.9"])
    srv = _Servidor(_preparar_release(tmp_path, "v9.9.9"), token="segredo-de-teste")
    uv, registo = uv_falso
    _configurar(home, repo, srv.porta, uv)
    monkeypatch.setattr(update, "reindexar_com_nova_versao", lambda: None)
    monkeypatch.setattr(update, "_token_git", lambda url: None)
    try:
        with pytest.raises(update.ErroUpdate, match="não há credenciais"):
            update.atualizar()
        monkeypatch.setenv("AGENT_MEMORY_DOWNLOAD_TOKEN", "segredo-de-teste")
        assert update.atualizar() == 0
    finally:
        srv.fechar()
    assert registo.exists()


def test_update_ja_atualizado(tmp_path: Path, home: Path, uv_falso, capsys):
    from memoria import __version__

    repo = _repo_git_com_tags(tmp_path, [f"v{__version__}"])
    uv, registo = uv_falso
    _configurar(home, repo, 1, uv)
    assert update.atualizar() == 0
    assert "mais recente" in capsys.readouterr().err
    assert not registo.exists()


def test_script_windows_espera_e_instala(tmp_path: Path, monkeypatch):
    lancados = []
    monkeypatch.setattr(update.subprocess, "Popen", lambda cmd, **kw: lancados.append(cmd))
    cmd = ["C:\\Users\\João\\.local\\bin\\uv.exe", "tool", "install", "--force", "--python", "3.12", "C:\\t\\m.whl"]
    assert update._instalar_depois_de_sair(cmd, tmp_path) == 0
    script = (tmp_path / "install.ps1").read_bytes()
    assert script.startswith(b"\xef\xbb\xbf")  # BOM: o PowerShell 5.1 lê os acentos
    texto = script.decode("utf-8-sig")
    assert "Wait-Process -Id" in texto and "'tool' 'install' '--force'" in texto and "reindex" in texto
    assert "João" in texto
    assert lancados and lancados[0][0] == "powershell"


# ------------------------------------------- git e Command Line Tools (macOS sem CLT)
POSIX = pytest.mark.skipif(sys.platform == "win32", reason="scripts /bin/sh falsos")
_WHICH = update.shutil.which


def _executavel(caminho: Path, texto: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto)
    caminho.chmod(0o755)
    return caminho


def _xcode_select_falso(tmp_path: Path, monkeypatch, corpo: str) -> Path:
    """Um xcode-select no PATH (só ele) que regista os argumentos e corre `corpo`."""
    pasta = tmp_path / "bin-xcode"
    registo = tmp_path / "xcode-select-args.txt"
    _executavel(pasta / "xcode-select", f'#!/bin/sh\necho "$@" >> "{registo}"\n{corpo}\n')
    monkeypatch.setenv("PATH", str(pasta))
    return registo


def _which(**fixos):
    """shutil.which com respostas fixas para alguns nomes (o resto procura de verdade)."""
    return lambda nome, *a, **k: fixos[nome] if nome in fixos else _WHICH(nome, *a, **k)


def _git_do_kit_mac(casa: Path) -> Path:
    return _executavel(casa / ".workshop-claude" / "bin" / "git", "#!/bin/sh\nexit 0\n")


@POSIX
def test_clt_ok_sem_ferramentas(tmp_path: Path, monkeypatch):
    registo = _xcode_select_falso(tmp_path, monkeypatch, "echo 'xcode-select: error: unable to get active developer directory' >&2\nexit 2")
    assert update._clt_ok() is False
    assert registo.read_text().split() == ["-p"]  # só -p: nunca o --install


@POSIX
def test_clt_ok_pasta_apagada(tmp_path: Path, monkeypatch):
    # xcode-select -p aponta para uma pasta sem git (ferramentas apagadas): os shims abririam o diálogo.
    ferramentas = tmp_path / "CommandLineTools"
    (ferramentas / "usr" / "bin").mkdir(parents=True)
    _xcode_select_falso(tmp_path, monkeypatch, f"echo '{ferramentas}'")
    assert update._clt_ok() is False


@POSIX
def test_clt_ok_com_ferramentas(tmp_path: Path, monkeypatch):
    ferramentas = tmp_path / "Command Line Tools"
    _executavel(ferramentas / "usr" / "bin" / "git", "#!/bin/sh\nexit 0\n")
    _xcode_select_falso(tmp_path, monkeypatch, f"echo '{ferramentas}'")
    assert update._clt_ok() is True


def test_clt_ok_sem_xcode_select(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert update._clt_ok() is False


def test_git_do_path_tem_prioridade(home: Path, monkeypatch):
    _git_do_kit_mac(Path.home())
    monkeypatch.setattr(update.shutil, "which", _which(git="/opt/homebrew/bin/git"))
    monkeypatch.setattr(update, "_clt_ok", lambda: pytest.fail("só se pergunta pelas CLT com /usr/bin/git"))
    assert update._git() == "/opt/homebrew/bin/git"


@POSIX
def test_git_sem_git_no_path_usa_o_do_kit(home: Path, monkeypatch):
    kit = _git_do_kit_mac(Path.home())
    monkeypatch.setattr(update.shutil, "which", _which(git=None))
    assert update._git() == str(kit)


@POSIX
def test_git_shim_da_apple_usa_o_do_kit(home: Path, monkeypatch):
    kit = _git_do_kit_mac(Path.home())
    monkeypatch.setattr(update.sys, "platform", "darwin")
    monkeypatch.setattr(update.shutil, "which", _which(git="/usr/bin/git"))
    monkeypatch.setattr(update, "_clt_ok", lambda: False)
    assert update._git() == str(kit)


def test_git_shim_da_apple_sem_git_do_kit(home: Path, monkeypatch):
    monkeypatch.setattr(update.sys, "platform", "darwin")
    monkeypatch.setattr(update.shutil, "which", _which(git="/usr/bin/git"))
    monkeypatch.setattr(update, "_clt_ok", lambda: False)
    with pytest.raises(update.ErroUpdate, match="Command Line Tools"):
        update._git()


def test_git_com_clt_usa_usr_bin_git(home: Path, monkeypatch):
    _git_do_kit_mac(Path.home())
    monkeypatch.setattr(update.sys, "platform", "darwin")
    monkeypatch.setattr(update.shutil, "which", _which(git="/usr/bin/git"))
    monkeypatch.setattr(update, "_clt_ok", lambda: True)
    assert update._git() == "/usr/bin/git"


def test_git_usr_bin_fora_do_mac_nao_pergunta_pelas_clt(home: Path, monkeypatch):
    monkeypatch.setattr(update.sys, "platform", "linux")
    monkeypatch.setattr(update.shutil, "which", _which(git="/usr/bin/git"))
    monkeypatch.setattr(update, "_clt_ok", lambda: pytest.fail("só no macOS"))
    assert update._git() == "/usr/bin/git"


def test_git_nenhum(home: Path, monkeypatch):
    monkeypatch.setattr(update.shutil, "which", _which(git=None))
    with pytest.raises(update.ErroUpdate, match="não está instalado. É preciso"):
        update._git()


def test_git_do_kit_ignora_ficheiro_nao_executavel(home: Path):
    if sys.platform == "win32":
        pytest.skip("no Windows todos os ficheiros contam como executáveis")
    git = _git_do_kit_mac(Path.home())
    git.chmod(0o644)
    assert update._git_do_kit(windows=False) is None


def test_git_do_kit_windows(home: Path, tmp_path: Path, monkeypatch):
    local = tmp_path / "AppData Local"
    programas = tmp_path / "Program Files"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("ProgramFiles", str(programas))
    assert update._git_do_kit(windows=True) is None
    sistema = _executavel(programas / "Git" / "cmd" / "git.exe", "")
    assert update._git_do_kit(windows=True) == str(sistema)
    do_utilizador = _executavel(local / "Programs" / "Git" / "cmd" / "git.exe", "")
    assert update._git_do_kit(windows=True) == str(do_utilizador)
    # O do kit (%USERPROFILE%\.workshop-claude\git\cmd\git.exe) vem primeiro.
    kit = _executavel(Path.home() / ".workshop-claude" / "git" / "cmd" / "git.exe", "")
    assert update._git_do_kit(windows=True) == str(kit)


@POSIX
def test_ultima_tag_com_o_git_do_kit(tmp_path: Path, home: Path, monkeypatch):
    repo = _repo_git_com_tags(tmp_path, ["v0.1.0", "v0.2.0"])
    git_real = os.path.realpath(_WHICH("git"))
    # O wrapper do kit, como o setup o escreve (aqui chama o git real); e um PATH sem git.
    _executavel(Path.home() / ".workshop-claude" / "bin" / "git", f'#!/bin/sh\nexec "{git_real}" "$@"\n')
    vazio = tmp_path / "path-sem-git"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))
    assert update.ultima_tag(str(repo)) == "v0.2.0"


def _como_mac_sem_clt(monkeypatch, install_name_tool: str | None = "/usr/bin/install_name_tool", clt: bool = False):
    monkeypatch.setattr(update.sys, "platform", "darwin")
    monkeypatch.setattr(update.shutil, "which", _which(install_name_tool=install_name_tool))
    monkeypatch.setattr(update, "_clt_ok", lambda: clt)


@POSIX
def test_ambiente_uv_sem_clt_tem_install_name_tool_vazio(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("OUTRA_VARIAVEL", "fica")
    _como_mac_sem_clt(monkeypatch)
    env = update.ambiente_uv(tmp_path)
    falso = tmp_path / "no-clt" / "install_name_tool"
    assert env is not None
    assert env["PATH"] == f"{falso.parent}{os.pathsep}/usr/bin:/bin"
    assert env["OUTRA_VARIAVEL"] == "fica"
    assert os.environ["PATH"] == "/usr/bin:/bin"  # só para o subprocesso do uv
    # O uv procura install_name_tool no PATH: encontra o vazio, que não faz nada e sai com 0.
    assert _WHICH("install_name_tool", path=env["PATH"]) == str(falso)
    r = subprocess.run([str(falso), "-id", "/x/libpython3.12.dylib", "/x/libpython3.12.dylib"], capture_output=True)
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""


def test_ambiente_uv_sem_clt_e_sem_install_name_tool_visivel(tmp_path: Path, monkeypatch):
    # O which não o vê (PATH sem /usr/bin, ou um sandbox que nega o shim): o falso vai na mesma, é inofensivo.
    monkeypatch.setenv("PATH", "/x/bin")
    _como_mac_sem_clt(monkeypatch, install_name_tool=None)
    env = update.ambiente_uv(tmp_path)
    assert env is not None and env["PATH"] == f"{tmp_path / 'no-clt'}{os.pathsep}/x/bin"
    monkeypatch.delenv("PATH")
    assert update.ambiente_uv(tmp_path)["PATH"] == str(tmp_path / "no-clt")


def test_ambiente_uv_sem_mudancas(tmp_path: Path, monkeypatch):
    _como_mac_sem_clt(monkeypatch, clt=True)
    assert update.ambiente_uv(tmp_path) is None  # Command Line Tools instaladas
    _como_mac_sem_clt(monkeypatch, install_name_tool="/opt/homebrew/opt/cctools/bin/install_name_tool")
    assert update.ambiente_uv(tmp_path) is None  # um install_name_tool a sério primeiro no PATH
    _como_mac_sem_clt(monkeypatch, install_name_tool=None, clt=True)
    assert update.ambiente_uv(tmp_path) is None
    _como_mac_sem_clt(monkeypatch)
    monkeypatch.setattr(update.sys, "platform", "linux")
    assert update.ambiente_uv(tmp_path) is None  # só no macOS
    assert not (tmp_path / "no-clt").exists()


@POSIX
def test_update_sem_clt_uv_ve_install_name_tool_vazio(tmp_path: Path, home: Path, monkeypatch):
    repo = _repo_git_com_tags(tmp_path, ["v9.9.9"])
    git_real = _WHICH("git")
    srv = _Servidor(_preparar_release(tmp_path, "v9.9.9"))
    # Um uv falso que, como o verdadeiro depois de descarregar um Python, corre o install_name_tool do PATH.
    registo = tmp_path / "uv-env.json"
    uv = _executavel(
        tmp_path / "uv",
        f"#!{sys.executable}\nimport json, os, shutil, subprocess, pathlib\n"
        f"itl = shutil.which('install_name_tool')\n"
        f"rc = subprocess.run([itl, '-id', 'a', 'b']).returncode\n"
        f"pathlib.Path({str(registo)!r}).write_text(json.dumps({{'itl': itl, 'rc': rc, 'path': os.environ['PATH']}}))\n",
    )
    _configurar(home, repo, srv.porta, uv)
    monkeypatch.setattr(update, "reindexar_com_nova_versao", lambda: None)
    monkeypatch.setattr(update, "_git", lambda: git_real)
    _como_mac_sem_clt(monkeypatch)
    path_antes = os.environ.get("PATH")
    try:
        assert update.atualizar() == 0
    finally:
        srv.fechar()
    visto = json.loads(registo.read_text())
    assert Path(visto["itl"]).name == "install_name_tool" and Path(visto["itl"]).parent.name == "no-clt"
    assert visto["rc"] == 0
    assert visto["path"].startswith(str(Path(visto["itl"]).parent) + os.pathsep)
    assert os.environ.get("PATH") == path_antes
    assert not Path(visto["itl"]).exists()  # a pasta temporária do update foi apagada
