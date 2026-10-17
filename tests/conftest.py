"""Isolamento: nenhum teste toca em ~/.agent-memory, ~/.memoria nem em ~/.claude do utilizador."""

from __future__ import annotations

from pathlib import Path

import pytest

CHAVES_CONFIG = (
    "MEMORY_APP_REPO_URL",
    "RELEASE_DOWNLOAD_URL",
    "PYTHON_VERSION",
    "UV",
    "AGENT_MEMORY_DOWNLOAD_TOKEN",
    "MEMORIA_DOWNLOAD_TOKEN",
)
# Nomes antigos (até à v0.4): nunca herdados do ambiente de quem corre os testes.
CHAVES_ANTIGAS = ("MEMORIA_HOME", "MEMORIA_LANG", "MEMORIA_SEM_UPDATE")


@pytest.fixture(autouse=True)
def isolar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "user-home"
    casa.mkdir()
    home = tmp_path / "agent-memory-home"
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("USERPROFILE", str(casa))
    for chave in CHAVES_ANTIGAS:
        monkeypatch.delenv(chave, raising=False)
    monkeypatch.setenv("AGENT_MEMORY_HOME", str(home))
    monkeypatch.setenv("AGENT_MEMORY_NO_UPDATE", "1")
    # Os testes antigos verificam mensagens em português; os de i18n mudam a língua.
    monkeypatch.setenv("AGENT_MEMORY_LANG", "pt")
    from memoria import i18n

    i18n.repor()
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
