"""Versão portátil: deteção, zip, extração e update por troca de pasta.

O build completo (com o Python embutido) verifica-se com scripts/build_portatil.py,
que no Mac corre o selftest de cada zip. Aqui só se testa a lógica.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import runpy
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from memoria import config, portatil, selftest, update

RAIZ = Path(__file__).resolve().parents[1]
MODELOS = RAIZ / "portatil"
CFG = {
    "MEMORY_APP_REPO_URL": "https://gitea.exemplo.pt/guilherme/claude-memory-app.git",
    "RELEASE_DOWNLOAD_URL": "{repo}/releases/download/{version}/{file}",
}
posix = pytest.mark.skipif(os.name == "nt", reason="permissões e ligações POSIX")


def _build_portatil():
    spec = importlib.util.spec_from_file_location("build_portatil", RAIZ / "scripts" / "build_portatil.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _app_mac(base: Path, versao: str, selftest_ok: bool = True) -> Path:
    """Uma Memoria.app falsa: marcador e um lançador que regista os comandos."""
    app = base / "Memoria.app"
    prefixo = app / "Contents" / "Resources" / "python"
    prefixo.mkdir(parents=True)
    marcador = {"formato": 1, "versao": versao, "plataforma": "macos-arm64", "prefixo": "Contents/Resources/python", "comando": ["Contents/MacOS/memoria"]}
    (prefixo / portatil.MARCADOR).write_text(json.dumps(marcador), "utf-8")
    (prefixo / "bin").mkdir()
    (prefixo / "bin" / "python3.12").write_text("binário", "utf-8")
    os.symlink("python3.12", prefixo / "bin" / "python3")
    lancador = app / "Contents" / "MacOS" / "memoria"
    lancador.parent.mkdir(parents=True)
    codigo = "0" if selftest_ok else '$([ "$1" = selftest ] && echo 1 || echo 0)'
    lancador.write_text(f'#!/bin/sh\necho "{versao} $*" >> "$REGISTO"\nexit {codigo}\n', "utf-8")
    lancador.chmod(0o755)
    return app


class _Servidor:
    """Faz de Descarregador: serve ficheiros locais pelo nome."""

    def __init__(self, ficheiros: dict[str, Path]):
        self.ficheiros = ficheiros
        self.urls: list[str] = []

    def obter(self, url: str, destino: Path) -> None:
        self.urls.append(url)
        shutil.copyfile(self.ficheiros[url.rsplit("/", 1)[1]], destino)


def _release(tmp: Path, versao: str, selftest_ok: bool = True, sha_errado: bool = False) -> _Servidor:
    origem = tmp / f"release-{versao}"
    _app_mac(origem, versao, selftest_ok)
    zip_ = tmp / portatil.nome_zip(versao, "macos-arm64")
    _build_portatil().zipar(origem, "Memoria.app", zip_, (2026, 10, 16, 12, 0, 0))
    soma = "0" * 64 if sha_errado else hashlib.sha256(zip_.read_bytes()).hexdigest()
    somas = tmp / "SHA256SUMS"
    somas.write_text(f"{soma}  {zip_.name}\n", "utf-8")
    return _Servidor({"SHA256SUMS": somas, zip_.name: zip_})


# --- deteção --------------------------------------------------------------------


def test_sem_marcador_nao_e_portatil(tmp_path: Path):
    assert portatil.info(tmp_path) is None
    assert portatil.info() is None  # a correr os testes, não é a versão portátil


def test_marcador_invalido_e_ignorado(tmp_path: Path):
    (tmp_path / portatil.MARCADOR).write_text("{não é json", "utf-8")
    assert portatil.info(tmp_path) is None
    (tmp_path / portatil.MARCADOR).write_text(json.dumps({"plataforma": "linux-arm"}), "utf-8")
    assert portatil.info(tmp_path) is None


def test_raiz_e_comandos_no_mac(tmp_path: Path):
    app = _app_mac(tmp_path / "Aplicações com espaço", "0.2.0")
    prefixo = app / "Contents" / "Resources" / "python"
    assert portatil.raiz(prefixo) == app.resolve()
    lancador = str(app.resolve() / "Contents" / "MacOS" / "memoria")
    assert portatil.comando(prefixo) == [lancador]
    claude = portatil.comando_claude(prefixo)
    assert claude.startswith("claude mcp add --scope user memoria -- ")
    assert claude.endswith(" mcp")
    if os.name != "nt":
        assert f"'{lancador}'" in claude  # caminho com espaços vem entre plicas


def test_raiz_e_comandos_no_windows(tmp_path: Path):
    pasta = tmp_path / "Memoria"
    pasta.mkdir()
    marcador = {"plataforma": "windows-x64", "prefixo": ".", "comando": ["python.exe", "-m", "memoria"]}
    (pasta / portatil.MARCADOR).write_text(json.dumps(marcador), "utf-8")
    assert portatil.raiz(pasta) == pasta.resolve()
    assert portatil.comando(pasta) == [str(pasta.resolve() / "python.exe"), "-m", "memoria"]


def test_nome_zip():
    assert portatil.nome_zip("v0.2.0", "macos-arm64") == "Memoria-0.2.0-macos-arm64.zip"
    assert portatil.nome_zip("0.2.0", "windows-x64") == "Memoria-0.2.0-windows-x64.zip"


def test_translocada():
    assert portatil.translocada(Path("/private/var/folders/x/T/AppTranslocation/ABC/d/Memoria.app"))
    assert not portatil.translocada(Path("/Users/ana/Applications/Memoria.app"))


def test_desbloquear_so_no_windows(tmp_path: Path):
    if os.name != "nt":
        assert portatil.desbloquear(tmp_path) == 0


def test_plataformas_tem_python_fixado_no_release_conf():
    conf = config.ler_conf((RAIZ / "release.conf").read_text("utf-8"))
    for plataforma in portatil.PLATAFORMAS:
        assert len(conf[f"PORTATIL_SHA256_{plataforma.replace('-', '_').upper()}"]) == 64
    assert conf["PORTATIL_PBS_URL"].startswith("https://")


# --- zip e extração --------------------------------------------------------


@posix
def test_zipar_e_extrair_mantem_permissoes_e_ligacoes(tmp_path: Path):
    app = _app_mac(tmp_path / "origem", "0.2.0")
    zip_ = tmp_path / "a.zip"
    _build_portatil().zipar(tmp_path / "origem", "Memoria.app", zip_, (2026, 1, 1, 0, 0, 0))
    portatil.extrair(zip_, tmp_path / "destino")
    nova = tmp_path / "destino" / "Memoria.app"
    assert os.access(nova / "Contents" / "MacOS" / "memoria", os.X_OK)
    ligacao = nova / "Contents" / "Resources" / "python" / "bin" / "python3"
    assert ligacao.is_symlink() and os.readlink(ligacao) == "python3.12"
    assert not os.access(nova / "Contents" / "Resources" / "python" / portatil.MARCADOR, os.X_OK)
    assert sorted(p.name for p in nova.rglob("*")) == sorted(p.name for p in app.rglob("*"))


def test_zip_e_reproduzivel(tmp_path: Path):
    _app_mac(tmp_path / "origem", "0.2.0")
    zipar = _build_portatil().zipar
    zipar(tmp_path / "origem", "Memoria.app", tmp_path / "a.zip", (2026, 1, 1, 0, 0, 0))
    zipar(tmp_path / "origem", "Memoria.app", tmp_path / "b.zip", (2026, 1, 1, 0, 0, 0))
    assert (tmp_path / "a.zip").read_bytes() == (tmp_path / "b.zip").read_bytes()


def test_extrair_recusa_caminhos_para_fora(tmp_path: Path):
    zip_ = tmp_path / "mau.zip"
    with zipfile.ZipFile(zip_, "w") as z:
        z.writestr("../fora.txt", "x")
    with pytest.raises(ValueError):
        portatil.extrair(zip_, tmp_path / "destino")
    assert not (tmp_path / "fora.txt").exists()


@posix
def test_extrair_recusa_ligacao_para_fora(tmp_path: Path):
    zip_ = tmp_path / "mau.zip"
    with zipfile.ZipFile(zip_, "w") as z:
        info = zipfile.ZipInfo("Memoria.app/ligacao")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, "/etc/passwd")
    with pytest.raises(ValueError):
        portatil.extrair(zip_, tmp_path / "destino")


# --- update ----------------------------------------------------------------


@posix
def test_update_troca_a_app_no_mesmo_sitio(tmp_path: Path, monkeypatch):
    registo = tmp_path / "registo.txt"
    monkeypatch.setenv("REGISTO", str(registo))
    apps = tmp_path / "Applications"
    app = _app_mac(apps, "0.2.0")
    servidor = _release(tmp_path, "9.9.9")

    assert portatil.atualizar(CFG, "v9.9.9", servidor, prefixo=app / "Contents" / "Resources" / "python") == 0

    dados = json.loads((app / "Contents" / "Resources" / "python" / portatil.MARCADOR).read_text("utf-8"))
    assert dados["versao"] == "9.9.9"
    assert sorted(p.name for p in apps.iterdir()) == ["Memoria.app"]  # sem restos
    # O selftest correu na nova antes da troca; o reindex depois, já no sítio certo.
    assert registo.read_text("utf-8").splitlines() == ["9.9.9 selftest", "9.9.9 reindex"]
    assert servidor.urls == [
        "https://gitea.exemplo.pt/guilherme/claude-memory-app/releases/download/v9.9.9/SHA256SUMS",
        "https://gitea.exemplo.pt/guilherme/claude-memory-app/releases/download/v9.9.9/Memoria-9.9.9-macos-arm64.zip",
    ]


@posix
def test_update_mantem_o_nome_se_a_app_foi_renomeada(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("REGISTO", str(tmp_path / "registo.txt"))
    apps = tmp_path / "Applications"
    app = _app_mac(apps, "0.2.0").rename(apps / "Memória (cópia).app")
    servidor = _release(tmp_path, "9.9.9")

    assert portatil.atualizar(CFG, "v9.9.9", servidor, prefixo=app / "Contents" / "Resources" / "python") == 0

    assert sorted(p.name for p in apps.iterdir()) == ["Memória (cópia).app"]
    assert json.loads((app / "Contents" / "Resources" / "python" / portatil.MARCADOR).read_text("utf-8"))["versao"] == "9.9.9"


@posix
@pytest.mark.parametrize("problema", ["sha", "selftest"])
def test_update_com_problema_nao_mexe_na_app(tmp_path: Path, monkeypatch, problema):
    monkeypatch.setenv("REGISTO", str(tmp_path / "registo.txt"))
    apps = tmp_path / "Applications"
    app = _app_mac(apps, "0.2.0")
    servidor = _release(tmp_path, "9.9.9", selftest_ok=problema != "selftest", sha_errado=problema == "sha")

    with pytest.raises(update.ErroUpdate, match="Nada foi alterado"):
        portatil.atualizar(CFG, "v9.9.9", servidor, prefixo=app / "Contents" / "Resources" / "python")

    dados = json.loads((app / "Contents" / "Resources" / "python" / portatil.MARCADOR).read_text("utf-8"))
    assert dados["versao"] == "0.2.0"
    assert sorted(p.name for p in apps.iterdir()) == ["Memoria.app"]


def test_update_recusa_app_translocada(tmp_path: Path, monkeypatch):
    app = _app_mac(tmp_path / "AppTranslocation" / "X", "0.2.0")
    with pytest.raises(update.ErroUpdate, match="Aplicações"):
        portatil.atualizar(CFG, "v9.9.9", _Servidor({}), prefixo=app / "Contents" / "Resources" / "python")


def test_memoria_update_usa_a_troca_na_versao_portatil(monkeypatch):
    monkeypatch.setenv("MEMORY_APP_REPO_URL", CFG["MEMORY_APP_REPO_URL"])
    monkeypatch.setattr(portatil, "info", lambda prefixo=None: {"plataforma": "macos-arm64"})
    chamadas = []
    monkeypatch.setattr(portatil, "atualizar", lambda cfg, tag, baixar: chamadas.append(tag) or 0)
    monkeypatch.setattr(update, "encontrar_uv", lambda cfg: pytest.fail("não deve usar o uv"))
    assert update.atualizar(versao="v9.9.9") == 0
    assert chamadas == ["v9.9.9"]


def test_script_troca_windows(tmp_path: Path):
    atual = Path("C:/Users/Zé d'Ávila/AppData/Local/Programs/Memoria")
    pasta = Path("C:/Users/Zé d'Ávila/AppData/Local/Programs/.memoria-update-x")
    texto = portatil.script_troca(atual, pasta / "nova" / "Memoria", pasta, 4242, [str(atual / "python.exe"), "-m", "memoria"])
    assert "Wait-Process -Id 4242" in texto
    assert "Zé d''Ávila" in texto and "d'Á" not in texto  # plicas escapadas para o PowerShell
    assert texto.count("Move-Item") == 2 and "reindex" in texto
    assert "\r\n" in texto
    # As mensagens seguem a língua da app (aqui pt); o ficheiro é gravado com BOM (UTF-8),
    # que o PowerShell 5.1 lê bem. Os comandos em si são ASCII.
    from memoria.i18n import t

    assert f"Write-Host '{t('ps.atualizada')}'" in texto
    comandos = texto.replace("Zé d''Ávila", "")
    for chave in ("ps.atualizada", "ps.fecha", "ps.nao_substituiu", "ps.enter"):
        comandos = comandos.replace(t(chave), "")
    assert comandos.isascii()


@pytest.mark.skipif(not shutil.which("pwsh"), reason="pwsh não instalado: análise do script só estática")
def test_script_troca_sintaxe_com_pwsh(tmp_path: Path):
    script = tmp_path / "trocar.ps1"
    texto = portatil.script_troca(Path("C:/a b/Memoria"), Path("C:/a b/.x/nova/Memoria"), Path("C:/a b/.x"), 1, ["C:/a b/Memoria/python.exe", "-m", "memoria"])
    script.write_text(texto, encoding="utf-8-sig")
    cmd = (
        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$e) | Out-Null; if ($e.Count) {{ $e; exit 1 }}"
    )
    assert subprocess.run(["pwsh", "-NoProfile", "-Command", cmd]).returncode == 0


def test_selftest_mostra_o_comando_do_claude(monkeypatch, capsys):
    monkeypatch.setattr(selftest, "verificar_base", lambda: True)
    monkeypatch.setattr(portatil, "info", lambda prefixo=None: {"plataforma": "macos-arm64"})
    monkeypatch.setattr(portatil, "comando_claude", lambda prefixo=None: "claude mcp add --scope user memoria -- /x/memoria mcp")
    assert selftest.correr() == 0
    assert "claude mcp add --scope user memoria -- /x/memoria mcp" in capsys.readouterr().out


# --- modelos ---------------------------------------------------------------


def test_modelos_windows_ascii():
    for nome in ("python._pth", "memoria.cmd"):
        assert (MODELOS / "windows" / nome).read_bytes().isascii(), nome
    linhas = [linha.partition("#")[0].strip() for linha in (MODELOS / "windows" / "python._pth").read_text().splitlines()]
    assert [linha for linha in linhas if linha] == ["Lib", "DLLs", ".", "import site"]


@pytest.mark.parametrize(
    "executavel,argv,abre",
    [
        (r"C:\Apps\Memoria\Memoria.exe", [r"C:\Apps\Memoria\Memoria.exe"], True),
        (r"C:\Apps\Memoria\Memoria.exe", [r"C:\Apps\Memoria\Memoria.exe", "-m", "memoria", "reindex"], False),
        (r"C:\Apps\Memoria\python.exe", [r"C:\Apps\Memoria\python.exe"], False),
    ],
)
def test_sitecustomize_so_abre_a_janela_no_duplo_clique(monkeypatch, executavel, argv, abre):
    monkeypatch.setattr(sys, "executable", executavel.replace("\\", os.sep))
    monkeypatch.setattr(sys, "orig_argv", argv)
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    monkeypatch.setattr(portatil, "arrancar_janela", lambda: 7)

    def sair(codigo):
        raise SystemExit(codigo)

    monkeypatch.setattr(os, "_exit", sair)
    if abre:
        with pytest.raises(SystemExit) as e:
            runpy.run_path(str(MODELOS / "windows" / "sitecustomize.py"))
        assert e.value.code == 7
    else:
        runpy.run_path(str(MODELOS / "windows" / "sitecustomize.py"))
    assert sys.dont_write_bytecode is True


def test_lancador_macos():
    lancador = MODELOS / "macos" / "memoria"
    texto = lancador.read_text("utf-8")
    assert texto.startswith("#!/bin/sh\n")
    assert 'exec "$pasta/Resources/python/bin/python3" -I -B -m memoria "$@"' in texto
    if os.name != "nt":
        assert os.access(lancador, os.X_OK)
        assert subprocess.run(["sh", "-n", str(lancador)]).returncode == 0
    plist = (MODELOS / "macos" / "Info.plist").read_text("utf-8")
    assert "<key>CFBundleExecutable</key><string>memoria</string>" in plist


def test_sign_macos_sem_credenciais():
    script = RAIZ / "scripts" / "sign-macos.sh"
    texto = script.read_text("utf-8")
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0
    assert "--keychain-profile" in texto and "--options runtime" in texto and "stapler staple" in texto
    # Nunca recebe nem guarda segredos: só o nome do perfil do Keychain.
    for proibido in ("--password", "--apple-id", "app-specific", "set -x"):
        assert proibido not in texto.replace("# ", "#").split("set -euo pipefail", 1)[1], proibido
    # Não faz parte do build normal.
    assert "sign-macos" not in (RAIZ / "scripts" / "build.sh").read_text("utf-8")


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("clang"), reason="só no Mac com clang")
def test_lancador_compilado(tmp_path: Path):
    exe = tmp_path / "Memoria.app" / "Contents" / "MacOS" / "memoria"
    exe.parent.mkdir(parents=True)
    r = subprocess.run(["clang", "-O2", "-Wall", "-Werror", "-o", str(exe), str(MODELOS / "macos" / "lancador.c")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # Um "python3" falso que mostra os argumentos que recebeu.
    python = tmp_path / "Memoria.app" / "Contents" / "Resources" / "python" / "bin" / "python3"
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nprintf "%s|" "$@"\n', "utf-8")
    python.chmod(0o755)
    saida = subprocess.run([str(exe), "selftest", "-psn_0_123", "--gui"], capture_output=True, text=True).stdout
    assert saida == "-I|-B|-m|memoria|selftest|--gui|"
