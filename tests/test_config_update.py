import hashlib
import json
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
        monkeypatch.setenv("MEMORIA_DOWNLOAD_TOKEN", "segredo-de-teste")
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
    script = (tmp_path / "instalar.ps1").read_bytes()
    assert script.startswith(b"\xef\xbb\xbf")  # BOM: o PowerShell 5.1 lê os acentos
    texto = script.decode("utf-8-sig")
    assert "Wait-Process -Id" in texto and "'tool' 'install' '--force'" in texto and "reindex" in texto
    assert "João" in texto
    assert lancados and lancados[0][0] == "powershell"
