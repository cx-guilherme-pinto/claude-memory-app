"""Registo das chamadas MCP (vista "Atividade do Claude")."""

import asyncio
import time
from datetime import datetime
from pathlib import Path

from mcp import Client

from memoria import registo as modulo
from memoria.mcp_server import criar_servidor
from memoria.registo import Registo
from memoria.webui import Api


def _nota(i: int, projeto: str = "arena") -> dict:
    return {"id": f"{projeto}/2026-10-16-n{i}", "titulo": f"Nota {i}", "projeto": projeto, "tarefa": f"ABC-{i}", "epico": "ABC-1"}


def test_gravar_e_resumir(home: Path):
    r = Registo(home)
    agora = time.time()
    r.gravar("memory_search", texto="cache", filtros={"projeto": "arena"}, memorias=[_nota(1), _nota(2)], quando=agora - 30)
    r.gravar("memory_search", texto="nada", memorias=[], quando=agora - 20)
    r.gravar("memory_related", texto="arena/2026-10-16-n1", memorias=[_nota(2)], quando=agora - 10)
    resumo = r.resumo(agora=agora)
    assert resumo["total"] == 3 and resumo["hoje"] == 3
    assert resumo["por_minuto"] == 0.3  # 3 chamadas nos últimos 10 minutos
    assert resumo["distintas"] == 2
    assert resumo["ultima"] == agora - 10
    primeiras = resumo["recordadas"]
    assert [x["ferramenta"] for x in primeiras] == ["memory_related", "memory_search", "memory_search", "memory_search"]
    # Sem resultados: uma linha sem memória, com o que se procurou.
    vazia = primeiras[1]
    assert vazia["memoria"] is None and vazia["texto"] == "nada"
    assert {x["titulo"] for x in primeiras[2:]} == {"Nota 1", "Nota 2"}
    assert primeiras[2]["tarefa"].startswith("ABC-")


def test_hoje_por_minuto_e_limite(home: Path):
    r = Registo(home)
    agora = datetime(2026, 10, 16, 12, 0).timestamp()
    ontem = datetime(2026, 10, 15, 23, 59).timestamp()
    r.gravar("memory_search", texto="velha", quando=ontem)
    for i in range(20):
        r.gravar("memory_search", texto=f"q{i}", memorias=[_nota(i)], quando=agora - 60 * 9 + i)
    resumo = r.resumo(limite=5, agora=agora)
    assert resumo["total"] == 21 and resumo["hoje"] == 20
    assert resumo["por_minuto"] == 2.0
    assert len(resumo["recordadas"]) == 5 and resumo["recordadas"][0]["texto"] == "q19"


def test_nunca_guarda_segredos_e_corta_o_texto(home: Path):
    r = Registo(home)
    r.gravar("memory_search", texto="deploy password=NaoGuardar123 sk-ant-api03-ABCDEFGHIJKLMNOP " + "x" * 500)
    linha = r.resumo()["recordadas"][0]
    assert "NaoGuardar123" not in linha["texto"] and "sk-ant-" not in linha["texto"]
    assert "[REDACTED:" in linha["texto"]
    assert len(linha["texto"]) <= modulo.MAX_TEXTO
    conteudo = (home / ".index" / "activity.sqlite").read_bytes()
    assert b"NaoGuardar123" not in conteudo


def test_poda_mantem_o_total(home: Path, monkeypatch):
    monkeypatch.setattr(modulo, "MAX_CHAMADAS", 50)
    monkeypatch.setattr(modulo, "MAX_RECORDADAS", 60)
    r = Registo(home)
    for i in range(400):
        r.gravar("memory_search", texto=f"q{i}", memorias=[_nota(i)])
    resumo = r.resumo(limite=500)
    assert resumo["total"] == 400  # o contador não é podado
    assert len(resumo["recordadas"]) <= 60 + 200
    assert resumo["recordadas"][0]["texto"] == "q399"


def test_erro_ao_gravar_nao_parte_nada(tmp_path: Path, capsys):
    ficheiro = tmp_path / "nao-e-pasta"
    ficheiro.write_text("x")
    r = Registo(tmp_path, caminho=ficheiro / "registo.sqlite")
    r.gravar("memory_search", texto="x")  # não lança
    assert "MCP activity log" in capsys.readouterr().err


def test_resumo_sem_registo(home: Path):
    assert Registo(home).resumo() == {"hoje": 0, "total": 0, "por_minuto": 0.0, "distintas": 0, "ultima": None, "recordadas": []}


def test_ferramentas_mcp_gravam(mem, home: Path):
    a = mem.adicionar(tipo="licao", titulo="Cache no CI", texto="usar cache", projeto="arena", tarefa="ABC-7", epico="ABC-1")

    async def principal():
        async with Client(criar_servidor(mem)) as c:
            await c.call_tool("memory_search", {"text": "cache token ghp_0123456789abcdefghijABCDEFGHIJ0123", "project": "arena"})
            await c.call_tool("memory_search", {"text": "inexistente"})
            await c.call_tool("memory_related", {"ref": a["caminho"]})
            nova = {"type": "do", "title": "Nova regra", "text": "x", "project": "arena", "task": "abc-8"}
            await c.call_tool("memory_add", nova)
            erro = await c.call_tool("memory_add", {"type": "xpto", "title": "x", "text": "y", "project": "p"})
            return erro

    erro = asyncio.run(principal())
    assert erro.is_error
    resumo = Registo(home).resumo()
    assert resumo["total"] == 5
    linhas = resumo["recordadas"]
    por_ferramenta = {}
    for linha in linhas:
        por_ferramenta.setdefault(linha["ferramenta"], []).append(linha)
    assert set(por_ferramenta) == {"memory_search", "memory_related", "memory_add"}
    procura = [x for x in por_ferramenta["memory_search"] if x["memoria"]][0]
    assert procura["titulo"] == "Cache no CI" and procura["tarefa"] == "ABC-7" and procura["epico"] == "ABC-1"
    assert "ghp_" not in procura["texto"]
    assert any(x["memoria"] is None and x["texto"] == "inexistente" for x in por_ferramenta["memory_search"])
    # relacionadas guarda o id da memória de partida, não o caminho no disco
    assert all(x["texto"] == a["id"] for x in por_ferramenta["memory_related"])
    nova = [x for x in por_ferramenta["memory_add"] if x["memoria"]][0]
    assert nova["titulo"] == "Nova regra" and nova["tarefa"] == "ABC-8"
    assert (home / ".index" / "activity.sqlite").is_file() and not (home / ".indice").exists()


def test_registo_antigo_copiado_com_nomes_novos(home: Path):
    """O registo da v0.4 (.indice/registo.sqlite, nomes memoria_*) passa para a v0.5 sem se perder nem mexer."""
    antigo = home / ".indice" / "registo.sqlite"
    Registo(home, caminho=antigo).gravar("memory_search", texto="velha", memorias=[_nota(1)], quando=time.time() - 5)
    Registo(home, caminho=antigo).gravar("memory_related", texto="x", memorias=[_nota(2)], quando=time.time() - 4)
    antes = antigo.read_bytes()
    r = Registo(home)
    resumo = r.resumo()
    assert resumo["total"] == 2
    assert [x["ferramenta"] for x in resumo["recordadas"]] == ["memory_related", "memory_search"]
    r.gravar("memory_add", texto="nova", memorias=[_nota(3)])
    assert r.resumo()["total"] == 3
    assert antigo.read_bytes() == antes  # o antigo fica como estava
    assert sorted(p.name for p in antigo.parent.iterdir()) == ["registo.sqlite"]
    assert Registo(home, caminho=antigo).resumo()["total"] == 2


def test_api_atividade_e_reindex_nao_apaga(mem, home: Path):
    Registo(home).gravar("memory_search", texto="x", memorias=[_nota(1)])
    mem.reindexar()
    resumo = Api(mem).atividade(10)
    assert resumo["total"] == 1 and resumo["recordadas"][0]["titulo"] == "Nota 1"


def test_registo_antigo_estragado_nao_parte_nada(home: Path):
    antigo = home / ".indice" / "registo.sqlite"
    antigo.parent.mkdir(parents=True)
    antigo.write_bytes(b"isto nao e sqlite" * 100)
    r = Registo(home)
    assert r.resumo()["total"] == 0  # começa vazio
    r.gravar("memory_search", texto="x", memorias=[_nota(1)])
    assert r.resumo()["total"] == 1
    assert antigo.read_bytes() == b"isto nao e sqlite" * 100
    assert [p.name for p in (home / ".index").iterdir() if p.name.endswith(".copy")] == []
