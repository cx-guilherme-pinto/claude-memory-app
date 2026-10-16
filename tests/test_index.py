import sqlite3
from pathlib import Path

import pytest

from memoria import index
from memoria.index import FTS5Indisponivel, Indice


def test_fts5_existe():
    index._FTS5_OK = False
    index.verificar_fts5()


def test_fts5_em_falta_da_erro_claro(monkeypatch):
    class LigacaoSemFts:
        def execute(self, sql):
            raise sqlite3.OperationalError("no such module: fts5")

        def close(self):
            pass

    monkeypatch.setattr(index, "_FTS5_OK", False)
    monkeypatch.setattr(index.sqlite3, "connect", lambda *_a, **_k: LigacaoSemFts())
    with pytest.raises(FTS5Indisponivel, match="não tem FTS5"):
        index.verificar_fts5()


def test_procurar_com_acentos_e_filtros(mem):
    mem.adicionar(tipo="licao", titulo="Lição sobre migrações", texto="Fazer migrações reversíveis.", projeto="a")
    mem.adicionar(tipo="fazer", titulo="Outra", texto="Migracoes com backup.", projeto="b")
    mem.adicionar(tipo="historico", titulo="Sem relação", texto="Nada a ver.", projeto="a")

    todos = mem.procurar("migracoes")
    assert {r["projeto"] for r in todos} == {"a", "b"}
    assert [r["projeto"] for r in mem.procurar("migrações", projeto="b")] == ["b"]
    assert [r["tipo"] for r in mem.procurar("migracoes", tipo="lição")] == ["licao"]
    assert mem.procurar("inexistente") == []
    # Prefixo: "migra" encontra "migrações".
    assert len(mem.procurar("migra")) == 2
    # O título pesa mais do que o corpo.
    assert mem.procurar("lição")[0]["titulo"] == "Lição sobre migrações"


def test_procurar_vazio_devolve_recentes(mem):
    for i in range(3):
        mem.adicionar(tipo="fazer", titulo=f"N{i}", texto="x", projeto="p")
    assert len(mem.procurar("", limite=2)) == 2


def test_procurar_caracteres_especiais(mem):
    mem.adicionar(tipo="fazer", titulo="Aspas", texto='texto com "aspas" e OR AND NOT *', projeto="p")
    assert mem.procurar('"aspas" OR (') and mem.procurar("*") == mem.procurar("")


def test_reindex_reconstroi_do_markdown(mem, home: Path):
    mem.adicionar(tipo="licao", titulo="Um", texto="alfa", projeto="p")
    mem.adicionar(tipo="licao", titulo="Dois", texto="beta [[Um]]", projeto="p")
    base = home / ".indice" / "memoria.sqlite"
    for sufixo in ("", "-wal", "-shm"):
        Path(str(base) + sufixo).unlink(missing_ok=True)
    estado = mem.reindexar()
    assert estado["total"] == 2
    assert mem.procurar("beta")[0]["titulo"] == "Dois"
    assert mem.relacionadas(mem.procurar("beta")[0]["id"])[0]["titulo"] == "Um"


def test_sincronizar_deteta_edicoes_e_remocoes(mem, home: Path):
    r = mem.adicionar(tipo="licao", titulo="Editável", texto="original", projeto="p")
    caminho = Path(r["caminho"])
    texto = caminho.read_text("utf-8").replace("original", "alterado")
    caminho.write_text(texto, "utf-8")
    mem.sincronizar(forcar=True)
    assert mem.procurar("alterado") and not mem.procurar("original")
    caminho.unlink()
    mem.sincronizar(forcar=True)
    assert mem.procurar("alterado") == []


def test_ficheiro_invalido_e_ignorado(mem, home: Path, capsys):
    mem.adicionar(tipo="licao", titulo="Boa", texto="ok", projeto="p")
    (home / "p" / "2026-01-01-ma.md").write_text("---\ntipo: [\n---\nx", "utf-8")
    estado = mem.reindexar()
    assert estado["total"] == 1 and estado["erros"] == 1
    assert "ignorada" in capsys.readouterr().err


def test_indice_nao_toca_nos_markdown(mem, home: Path):
    r = mem.adicionar(tipo="licao", titulo="Fixa", texto="conteúdo", projeto="p")
    antes = Path(r["caminho"]).read_bytes()
    mem.reindexar()
    mem.grafo()
    assert Path(r["caminho"]).read_bytes() == antes


def test_extensao_embeddings_desligada(home: Path):
    assert Indice(home).embeddings is None
