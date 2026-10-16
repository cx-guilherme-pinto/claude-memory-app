from datetime import datetime
from pathlib import Path

import pytest
import yaml

from memoria import store


def test_escrever_e_ler(home: Path):
    caminho = store.escrever_nota(
        home,
        tipo="lição",
        titulo="Usar cache no build",
        texto="Corpo com [[outra nota]].",
        projeto="Arena de Segurança",
        tarefa="ABC-12",
        ficheiros=["src/a.py", "src/b.py"],
        ligacoes=["[[x]]", "y"],
        custo_usd=1.234567,
        agora=datetime(2026, 10, 1, 12, 30).astimezone(),
    )
    assert caminho.parent == (home / "arena-de-seguranca").resolve()
    assert caminho.name == "2026-10-01-usar-cache-no-build.md"
    texto = caminho.read_text("utf-8")
    assert texto.startswith("---\n")
    meta = yaml.safe_load(texto.split("---\n")[1])
    assert meta["tipo"] == "licao"
    assert meta["projeto"] == "Arena de Segurança"
    assert meta["ficheiros"] == ["src/a.py", "src/b.py"]
    assert meta["ligacoes"] == ["x", "y"]
    assert isinstance(meta["data"], str) and meta["data"].startswith("2026-10-01T12:30:00")
    assert meta["custo_usd"] == 1.234567

    nota = store.ler_nota(caminho, home)
    assert nota.id == "arena-de-seguranca/2026-10-01-usar-cache-no-build"
    assert nota.tarefa == "ABC-12"
    assert nota.todas_ligacoes == ["x", "y", "outra nota"]


def test_nunca_reescreve(home: Path):
    agora = datetime(2026, 1, 1).astimezone()
    a = store.escrever_nota(home, tipo="fazer", titulo="T", texto="1", projeto="p", agora=agora)
    b = store.escrever_nota(home, tipo="fazer", titulo="T", texto="2", projeto="p", agora=agora)
    assert a != b and b.name.endswith("-t-2.md")
    assert "1" in a.read_text() and "2" in b.read_text()


@pytest.mark.parametrize(
    "entrada,esperado",
    [("lição", "licao"), ("Não fazer", "nao_fazer"), ("nao-fazer", "nao_fazer"), ("Histórico", "historico"), ("FAZER", "fazer")],
)
def test_normalizar_tipo(entrada, esperado):
    assert store.normalizar_tipo(entrada) == esperado


def test_tipo_invalido(home: Path):
    with pytest.raises(ValueError, match="Tipo inválido"):
        store.escrever_nota(home, tipo="ideia", titulo="x", texto="", projeto="p")


def test_projeto_sem_fuga_de_pasta(home: Path):
    caminho = store.escrever_nota(home, tipo="fazer", titulo="x", texto="", projeto="../../etc")
    assert caminho.resolve().is_relative_to(home.resolve())


def test_ler_frontmatter_escrito_a_mao(home: Path):
    pasta = home / "manual"
    pasta.mkdir(parents=True)
    f = pasta / "2026-02-03-nota.md"
    f.write_text(
        "---\ntipo: nao fazer\ntitulo: Escrita à mão\nprojeto: manual\ndata: 2026-02-03\nficheiros: a.py, b.py\n---\nTexto\n",
        "utf-8",
    )
    nota = store.ler_nota(f, home)
    assert nota.tipo == "nao_fazer"
    assert nota.data == "2026-02-03"
    assert nota.ficheiros == ["a.py", "b.py"]
    assert nota.corpo == "Texto\n"


def test_ler_sem_frontmatter(home: Path):
    pasta = home / "solto"
    pasta.mkdir(parents=True)
    f = pasta / "2026-03-04-livre.md"
    f.write_text("Só texto, sem cabeçalho.\n", "utf-8")
    nota = store.ler_nota(f, home)
    assert nota.titulo == "2026-03-04-livre"
    assert nota.projeto == "solto"
    assert nota.data == "2026-03-04"
