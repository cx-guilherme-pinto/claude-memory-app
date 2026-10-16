"""scripts/mudar-alojamento.sh: muda o alojamento e a versão de uma vez, sem commit."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
FICHEIROS = [
    "release.conf",
    "pyproject.toml",
    "CHANGELOG.md",
    "CHANGELOG.pt.md",
    "README.md",
    "README.pt.md",
    "README.hi.md",
    "README.he.md",
    "install/install.sh",
    "install/install.ps1",
    "web/package.json",
    "web/package-lock.json",
    "scripts/render_installers.py",
    "scripts/mudar_alojamento.py",
    "scripts/mudar-alojamento.sh",
]
NOVO = "https://github.empresa.com/org-ia/claude-memory-app.git"


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    for f in FICHEIROS:
        destino = tmp_path / f
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / f, destino)
    return tmp_path


def _correr(raiz: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(raiz / "scripts" / "mudar_alojamento.py"), "--sem-lock", *args],
        capture_output=True,
        text=True,
    )


def test_muda_tudo_de_uma_vez(copia: Path):
    lock_antes = json.loads((copia / "web/package-lock.json").read_text("utf-8"))
    r = _correr(copia, "--repo-url", NOVO, "--provider", "github", "--versao", "v9.8.7", "--data", "2026-11-02")
    assert r.returncode == 0, r.stderr
    conf = (copia / "release.conf").read_text("utf-8")
    assert f"MEMORY_APP_REPO_URL={NOVO}\n" in conf
    assert "MEMORY_APP_VERSION=v9.8.7\n" in conf and "RELEASE_PROVIDER=github\n" in conf
    assert 'version = "9.8.7"' in (copia / "pyproject.toml").read_text("utf-8")
    assert json.loads((copia / "web/package.json").read_text("utf-8"))["version"] == "9.8.7"
    lock = json.loads((copia / "web/package-lock.json").read_text("utf-8"))
    assert lock["version"] == "9.8.7" and lock["packages"][""]["version"] == "9.8.7"
    # As dependências não mudam.
    for chave, pacote in lock["packages"].items():
        if chave:
            assert pacote == lock_antes["packages"][chave]
    for instalador in ("install/install.sh", "install/install.ps1"):
        texto = (copia / instalador).read_text("utf-8")
        assert NOVO in texto and "v9.8.7" in texto and "gitea.guilhermepinto.pt" not in texto
    for readme in ("README.md", "README.pt.md", "README.hi.md", "README.he.md"):
        texto = (copia / readme).read_text("utf-8")
        assert "https://github.empresa.com/org-ia/claude-memory-app/releases/download/v9.8.7/install.sh" in texto, readme
        assert "gitea.guilhermepinto.pt" not in texto, readme
    for nome, linha in (("CHANGELOG.md", "- Published on github.empresa.com."), ("CHANGELOG.pt.md", "- Publicação em github.empresa.com.")):
        changelog = (copia / nome).read_text("utf-8")
        assert changelog.index("## [9.8.7] - 2026-11-02") < changelog.index("## [0."), nome
        assert linha in changelog, nome
    # Os instaladores ficam em sincronia com o release.conf (o build.sh verifica isto).
    v = subprocess.run([sys.executable, str(copia / "scripts/render_installers.py"), "--verificar"], capture_output=True, text=True)
    assert v.returncode == 0, v.stderr
    assert "Mudou:" in r.stdout and "release.conf" in r.stdout


def test_segunda_vez_nao_muda_nada(copia: Path):
    args = ("--repo-url", NOVO, "--provider", "github", "--versao", "v9.8.7", "--data", "2026-11-02")
    assert _correr(copia, *args).returncode == 0
    antes = {f: (copia / f).read_bytes() for f in FICHEIROS}
    r = _correr(copia, *args)
    assert r.returncode == 0 and "Nada mudou" in r.stdout
    assert {f: (copia / f).read_bytes() for f in FICHEIROS} == antes


@pytest.mark.parametrize(
    "args,erro",
    [
        (("--repo-url", "http://servidor/o/n.git", "--provider", "github", "--versao", "v1.0.0"), "https"),
        (("--repo-url", "https://servidor/n", "--provider", "github", "--versao", "v1.0.0"), "https"),
        (("--repo-url", NOVO, "--provider", "github", "--versao", "1.0.0"), "vX.Y.Z"),
        (("--repo-url", NOVO, "--provider", "github", "--versao", "v1.0.0-rc.1"), "vX.Y.Z"),
        (("--repo-url", NOVO, "--provider", "github", "--versao", "v1.0.0", "--data", "02/11/2026"), "AAAA-MM-DD"),
    ],
)
def test_recusa_argumentos_invalidos(copia: Path, args, erro):
    antes = (copia / "release.conf").read_bytes()
    r = _correr(copia, *args)
    assert r.returncode == 2 and erro in r.stderr
    assert (copia / "release.conf").read_bytes() == antes


def test_fornecedor_invalido(copia: Path):
    r = _correr(copia, "--repo-url", NOVO, "--provider", "gitlab", "--versao", "v1.0.0")
    assert r.returncode == 2 and "invalid choice" in r.stderr


def test_sh_chama_o_python():
    assert subprocess.run(["bash", "-n", str(RAIZ / "scripts" / "mudar-alojamento.sh")]).returncode == 0
    assert "mudar_alojamento.py" in (RAIZ / "scripts" / "mudar-alojamento.sh").read_text("utf-8")
