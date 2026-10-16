"""Isolamento: nenhum teste toca em ~/.memoria nem em ~/.claude do utilizador."""

from __future__ import annotations

from pathlib import Path

import pytest

CHAVES_CONFIG = ("MEMORY_APP_REPO_URL", "RELEASE_DOWNLOAD_URL", "PYTHON_VERSION", "UV", "MEMORIA_DOWNLOAD_TOKEN")


@pytest.fixture(autouse=True)
def isolar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    casa.mkdir()
    home = tmp_path / "memoria-home"
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("USERPROFILE", str(casa))
    monkeypatch.setenv("MEMORIA_HOME", str(home))
    monkeypatch.setenv("MEMORIA_SEM_UPDATE", "1")
    for chave in CHAVES_CONFIG:
        monkeypatch.delenv(chave, raising=False)
    return home


@pytest.fixture
def home(isolar: Path) -> Path:
    return isolar


@pytest.fixture
def mem(home: Path):
    from memoria.service import Memoria

    return Memoria(home)
