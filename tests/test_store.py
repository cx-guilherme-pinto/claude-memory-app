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
    # Desde a v0.5, chaves e valores em inglês.
    assert list(meta) == ["type", "title", "project", "task", "files", "date", "cost_usd", "links"]
    assert meta["type"] == "lesson"
    assert meta["title"] == "Usar cache no build"
    assert meta["project"] == "Arena de Segurança"
    assert meta["task"] == "ABC-12"
    assert meta["files"] == ["src/a.py", "src/b.py"]
    assert meta["links"] == ["x", "y"]
    assert isinstance(meta["date"], str) and meta["date"].startswith("2026-10-01T12:30:00")
    assert meta["cost_usd"] == 1.234567

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
    [
        ("lição", "licao"),
        ("Não fazer", "nao_fazer"),
        ("nao-fazer", "nao_fazer"),
        ("Histórico", "historico"),
        ("FAZER", "fazer"),
        ("lesson", "licao"),
        ("Do", "fazer"),
        ("dont", "nao_fazer"),
        ("don't", "nao_fazer"),
        ("do not", "nao_fazer"),
        ("History", "historico"),
    ],
)
def test_normalizar_tipo(entrada, esperado):
    assert store.normalizar_tipo(entrada) == esperado


@pytest.mark.parametrize("tipo,externo", [("licao", "lesson"), ("fazer", "do"), ("nao_fazer", "dont"), ("historico", "history")])
def test_tipo_escrito_em_ingles(home: Path, tipo, externo):
    caminho = store.escrever_nota(home, tipo=tipo, titulo="t", texto="", projeto="p")
    assert yaml.safe_load(caminho.read_text("utf-8").split("---\n")[1])["type"] == externo
    assert store.ler_nota(caminho, home).tipo == tipo


def test_titulo_sem_letras_latinas(home: Path):
    caminho = store.escrever_nota(home, tipo="fazer", titulo="שלום", texto="", projeto="p")
    assert caminho.name.endswith("-note.md")


def test_tipo_invalido(home: Path):
    with pytest.raises(ValueError, match="Tipo inválido.*lesson, do, dont, history"):
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


def test_ler_frontmatter_ingles_escrito_a_mao(home: Path):
    pasta = home / "manual"
    pasta.mkdir(parents=True)
    f = pasta / "2026-02-03-note.md"
    f.write_text(
        "---\ntype: dont\ntitle: Hand written\nproject: manual\ntask: abc-1\nepic: ABC-0\ntags: [x]\n"
        "date: 2026-02-03\nfiles: a.py, b.py\ncost_usd: 0.5\nlinks: ['[[other]]']\n---\nText\n",
        "utf-8",
    )
    nota = store.ler_nota(f, home)
    assert (nota.tipo, nota.titulo, nota.projeto, nota.tarefa, nota.epico) == ("nao_fazer", "Hand written", "manual", "ABC-1", "ABC-0")
    assert nota.etiquetas == ["x"] and nota.ficheiros == ["a.py", "b.py"] and nota.custo_usd == 0.5
    assert nota.data == "2026-02-03" and nota.ligacoes == ["other"]


def test_chave_inglesa_ganha_a_portuguesa(home: Path):
    pasta = home / "misto"
    pasta.mkdir(parents=True)
    f = pasta / "2026-02-03-misto.md"
    f.write_text("---\ntype: lesson\ntipo: historico\ntitle: Novo\ntitulo: Antigo\nproject: misto\n---\nx\n", "utf-8")
    nota = store.ler_nota(f, home)
    assert (nota.tipo, nota.titulo) == ("licao", "Novo")


@pytest.mark.parametrize(
    "cabecalho",
    ["type: lesson\ntitle: Novo\nproject: p", "tipo: licao\ntitulo: Antigo\nprojeto: p"],
)
def test_validar_aceita_os_dois_cabecalhos(cabecalho):
    store.validar_texto(f"---\n{cabecalho}\n---\n\ntexto\n")
