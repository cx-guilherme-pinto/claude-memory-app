"""`memoria selftest --gui` a sério: abre a janela nativa e fecha-a sozinha.

Só corre num Mac com sessão gráfica (fora do CI). Usa um MEMORIA_HOME temporário
com 500 memórias e confirma o orçamento de 2 s da interface.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from memoria.exemplo import gerar

pytestmark = [
    pytest.mark.gui,
    pytest.mark.skipif(sys.platform != "darwin", reason="janela nativa testada só no macOS"),
    pytest.mark.skipif(bool(os.environ.get("CI")), reason="sem ecrã no CI"),
]


def _selftest(home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "MEMORIA_HOME": str(home)}
    return subprocess.run(
        [sys.executable, "-m", "memoria", "selftest", "--gui", "--timeout", "60"],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )


def test_selftest_gui_vazio(home: Path):
    r = _selftest(home)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "selftest --gui: OK" in r.stderr
    assert "ponte pywebview" in r.stderr  # a janela usa o js_api, não o recurso HTTP


def test_selftest_gui_500_memorias_abaixo_de_2s(home: Path):
    gerar(home, 500)
    r = _selftest(home)
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.search(r"(\d+) nós; interface pronta em (\d+) ms", r.stderr)
    assert m, r.stderr
    nos, ms = int(m.group(1)), int(m.group(2))
    print(f"\n{r.stderr.strip()}")
    assert nos > 500
    assert ms < 2000
