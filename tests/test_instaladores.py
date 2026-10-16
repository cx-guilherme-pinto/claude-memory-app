"""Verificações estáticas dos instaladores e dos scripts (o Windows não corre aqui)."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PS1 = RAIZ / "install" / "install.ps1"
SH = RAIZ / "install" / "install.sh"


def test_ps1_so_ascii():
    dados = PS1.read_bytes()
    assert dados.isascii(), [i for i, b in enumerate(dados) if b > 127][:5]


def test_ps1_requisitos_powershell_51():
    texto = PS1.read_text("ascii")
    assert "[Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12" in texto
    assert "$ProgressPreference = 'SilentlyContinue'" in texto
    assert "https://go.microsoft.com/fwlink/p/?LinkId=2124703" in texto
    assert "'/silent', '/install'" in texto
    assert "-UseBasicParsing" in texto
    # WebView2 só é instalado se faltar, pelas duas chaves do registo.
    assert "if (Test-WebView2)" in texto
    assert r"HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\'" in texto
    assert r"HKCU:\Software\Microsoft\EdgeUpdate\Clients\'" in texto
    # Sem sintaxe de PowerShell 7.
    for proibido in ("??", "?.", "-Parallel", "&&", "||", "ForEach-Object -Parallel"):
        assert proibido not in re.sub(r"#.*", "", texto), proibido
    # 'exit' fecharia a janela de quem corre "irm | iex".
    assert not re.search(r"^\s*exit\b", texto, re.M)
    assert "Agent Memory.lnk" in texto
    assert "[char]0x00F3" in texto  # remove o atalho antigo "Memória.lnk" sem caracteres não ASCII no ficheiro


def test_instaladores_em_sincronia_com_release_conf():
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "render_installers.py"), "--verificar"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_bloco_de_config_vem_do_release_conf():
    conf = dict(
        linha.split("=", 1)
        for linha in (RAIZ / "release.conf").read_text("utf-8").splitlines()
        if linha and not linha.startswith("#") and "=" in linha
    )
    sh = SH.read_text("utf-8")
    ps = PS1.read_text("ascii")
    for chave in ("MEMORY_APP_REPO_URL", "MEMORY_APP_VERSION", "RELEASE_DOWNLOAD_URL", "UV_VERSION", "PYTHON_VERSION"):
        assert f"{chave}='{conf[chave]}'" in sh
        assert f"'{conf[chave]}'" in ps
    # Fora do bloco gerado, nenhum URL do repositório.
    for texto in (sh, ps):
        fora = texto[: texto.index("# >>> config")] + texto[texto.index("# <<< config") :]
        assert conf["MEMORY_APP_REPO_URL"] not in fora


def test_sh_sintaxe():
    assert subprocess.run(["sh", "-n", str(SH)]).returncode == 0
    for script in ("build.sh", "publish-release.sh", "lock.sh"):
        assert subprocess.run(["bash", "-n", str(RAIZ / "scripts" / script)]).returncode == 0


def test_sh_padrao_de_url():
    """O install.sh expande o padrão de URL igual à app."""
    script = SH.read_text("utf-8")
    inicio = script.index('repo="${MEMORY_APP_REPO_URL%/}"')
    fim = script.index("baixar() {")
    trecho = script[inicio:fim]
    prog = (
        "MEMORY_APP_REPO_URL='https://gitea.exemplo.pt/dono/nome.git'\n"
        "MEMORY_APP_VERSION='v1.2.3'\nRELEASE_DOWNLOAD_URL='{repo}/releases/download/{version}/{file}'\n"
        f"{trecho}\nurl_asset SHA256SUMS\n"
    )
    r = subprocess.run(["sh", "-c", prog], capture_output=True, text=True)
    assert r.stdout == "https://gitea.exemplo.pt/dono/nome/releases/download/v1.2.3/SHA256SUMS"


def test_publish_release_api_so_em_create_release():
    texto = (RAIZ / "scripts" / "publish-release.sh").read_text("utf-8")
    inicio = texto.index("create_release() {")
    fim = texto.index("\n}\n", inicio)
    fora = texto[:inicio] + texto[fim:]
    for especifico in ("/api/v1", "gh release", "api.github.com"):
        assert especifico not in re.sub(r"^#.*$", "", fora, flags=re.M), especifico
    assert "GET /api/v1/user" in texto and '"$api/user"' in texto
    assert "git credential fill" in texto
    # Nunca imprime o token.
    assert "set -x" not in texto
    assert not re.search(r"echo[^\n]*\$TOKEN", texto)


def test_constraints_in_e_pyproject_alinhados():
    import tomllib

    pinos = [linha.strip() for linha in (RAIZ / "constraints.in").read_text().splitlines() if linha.strip() and not linha.startswith("#")]
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text())
    assert pinos == pyproject["tool"]["uv"]["constraint-dependencies"]
    constraints = (RAIZ / "constraints.txt").read_text()
    for pino in pinos:
        assert pino in constraints


@pytest.mark.skipif(not shutil.which("pwsh"), reason="pwsh não instalado: análise do .ps1 só estática")
def test_ps1_sintaxe_com_pwsh():
    cmd = (
        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{PS1}', [ref]$null, [ref]$e) | Out-Null; if ($e.Count) {{ $e; exit 1 }}"
    )
    assert subprocess.run(["pwsh", "-NoProfile", "-Command", cmd]).returncode == 0
