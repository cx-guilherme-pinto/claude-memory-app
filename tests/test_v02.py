"""v0.2: épico, url e etiquetas; pesquisa por nome, projeto e chave de ticket."""

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from memoria import store
from memoria.index import NOME_FICHEIRO, id_chave, id_epico, id_projeto, id_tarefa
from memoria.service import Memoria

# Nota tal como a v0.1.0 a escreve (sem os campos novos).
NOTA_V01 = """---
tipo: licao
titulo: Usar cache no build
projeto: arena-de-segurança
tarefa: ABC-1
ficheiros:
- src/build.py
data: '2026-10-16T13:25:33+01:00'
ligacoes: []
---

O build fica 3x mais rápido com cache.
"""


def _meta(caminho: str) -> dict:
    return yaml.safe_load(Path(caminho).read_text("utf-8").split("---\n")[1])


# ------------------------------------------------------------ contrato
def test_campos_novos_no_frontmatter(mem):
    r = mem.adicionar(
        tipo="licao",
        titulo="Com ticket",
        texto="x",
        projeto="p",
        tarefa="abc-123",
        epico=" abc-100 ",
        url="https://empresa.atlassian.net/browse/ABC-123",
        etiquetas=["#ci", "Cache", "cache", ""],
    )
    meta = _meta(r["caminho"])
    assert meta["task"] == "ABC-123" and meta["epic"] == "ABC-100"
    assert meta["url"] == "https://empresa.atlassian.net/browse/ABC-123"
    assert meta["tags"] == ["ci", "Cache"]
    assert list(meta)[:7] == ["type", "title", "project", "task", "epic", "url", "tags"]


def test_campos_vazios_nao_sao_escritos(mem):
    meta = _meta(mem.adicionar(tipo="fazer", titulo="Simples", texto="x", projeto="p")["caminho"])
    assert not {"task", "epic", "url", "tags", "cost_usd"} & set(meta)
    assert meta["files"] == [] and meta["links"] == []


@pytest.mark.parametrize(
    "url,tarefa",
    [
        ("https://x.atlassian.net/browse/ARENA-7", "ARENA-7"),
        ("https://x.atlassian.net/jira/software/projects/A/boards/1?selectedIssue=a-9", "A-9"),
        ("https://github.com/Org/Repo/pull/12", "org/repo#12"),
        ("https://gitea.exemplo.pt/dono/app/issues/3", "dono/app#3"),
        ("https://gitlab.com/g/p/-/merge_requests/5", "g/p#5"),
        ("https://exemplo.pt/outra/coisa", ""),
    ],
)
def test_tarefa_inferida_do_url(mem, url, tarefa):
    meta = _meta(mem.adicionar(tipo="fazer", titulo="U", texto="x", projeto="p", url=url)["caminho"])
    assert meta.get("task", "") == tarefa


def test_url_invalido(mem):
    with pytest.raises(ValueError, match="http"):
        mem.adicionar(tipo="fazer", titulo="U", texto="x", projeto="p", url="javascript:alert(1)")


def test_url_com_credenciais_e_redigido(mem):
    meta = _meta(mem.adicionar(tipo="fazer", titulo="U", texto="x", projeto="p", url="https://eu:Segredo123@git.pt/o/r/pull/1")["caminho"])
    assert "Segredo123" not in meta["url"]


def test_epico_igual_a_tarefa_nao_duplica(mem):
    meta = _meta(mem.adicionar(tipo="fazer", titulo="E", texto="x", projeto="p", tarefa="ABC-100", epico="abc-100")["caminho"])
    assert meta["task"] == "ABC-100" and "epic" not in meta


@pytest.mark.parametrize(
    "entrada,saida,global_",
    [("abc-12", "ABC-12", True), ("Org/Repo#3", "org/repo#3", True), ("#12", "#12", False), ("tarefa livre", "tarefa livre", False)],
)
def test_normalizar_chave(entrada, saida, global_):
    assert store.normalizar_chave(entrada) == saida
    assert store.chave_global(saida) is global_


# ------------------------------------------------- compatibilidade com a v0.1
def test_notas_e_indice_da_v01(home: Path):
    pasta = home / "arena-de-seguranca"
    pasta.mkdir(parents=True)
    (pasta / "2026-10-16-usar-cache-no-build.md").write_text(NOTA_V01, "utf-8")
    antigo = home / ".indice" / "memoria.sqlite"
    antigo.parent.mkdir()
    antigo.write_bytes(b"indice da v0.1")
    antigo_v2 = home / ".indice" / "memoria-v2.sqlite"
    antigo_v2.write_bytes(b"indice da v0.4")
    registo_antigo = home / ".indice" / "registo.sqlite"
    registo_antigo.write_bytes(b"registo da v0.4")
    mem = Memoria(home)
    achado = mem.procurar("cache")[0]
    assert achado["tarefa"] == "ABC-1" and achado["epico"] == "" and achado["etiquetas"] == [] and achado["url"] == ""
    assert (home / ".index" / NOME_FICHEIRO).is_file()
    assert NOME_FICHEIRO == "index-v3.sqlite"
    mem.reindexar()
    assert not antigo.exists() and not antigo_v2.exists()
    assert registo_antigo.exists()  # o registo MCP nunca é apagado
    assert (pasta / "2026-10-16-usar-cache-no-build.md").read_text("utf-8") == NOTA_V01  # nem as notas
    assert mem.procurar("ABC-1")[0]["id"] == achado["id"]


# ----------------------------------------------------------------- grafo
def _jira(mem):
    a = mem.adicionar(
        tipo="licao", titulo="Login com SSO", texto="Usar o IdP da empresa.", projeto="portal", tarefa="ABC-123", epico="ABC-100"
    )
    b = mem.adicionar(tipo="fazer", titulo="Testar sessão", texto="Testes de sessão.", projeto="portal", tarefa="ABC-123")
    c = mem.adicionar(
        tipo="nao_fazer", titulo="Guardar senhas", texto="Nunca no cliente.", projeto="api", tarefa="ABC-124", epico="ABC-100"
    )
    d = mem.adicionar(tipo="historico", titulo="Épico fechado", texto="Resumo do épico.", projeto="portal", tarefa="ABC-100")
    e = mem.adicionar(tipo="fazer", titulo="Outro ticket", texto="Referência a ABC-123 no texto.", projeto="portal", tarefa="XYZ-9")
    f = mem.adicionar(tipo="fazer", titulo="Número solto", texto="Tem 123 e ABC sozinhos.", projeto="portal")
    return a, b, c, d, e, f


def test_grafo_epico_e_tarefas(mem):
    a, b, c, d, e, f = _jira(mem)
    g = mem.grafo()
    nos = {n["id"]: n for n in g["nos"]}
    epico = id_epico("portal", "ABC-100")
    assert epico == "epico:ABC-100" and nos[epico]["tipo"] == "epico"
    assert nos[id_tarefa("portal", "ABC-123")]["tipo"] == "tarefa"
    ligacoes = {(lig["source"], lig["target"], lig["tipo"]) for lig in g["ligacoes"]}
    assert (id_tarefa("x", "ABC-123"), epico, "subtarefa") in ligacoes
    assert (a["id"], epico, "epico") in ligacoes
    # b não indica o épico mas herda-o da tarefa ABC-123.
    assert (b["id"], epico, "epico") in ligacoes and nos[b["id"]]["epico"] == "ABC-100"
    # d tem como tarefa a chave do épico: liga ao nó do épico.
    assert (d["id"], epico, "tarefa") in ligacoes
    # Chaves globais juntam projetos diferentes.
    assert (c["id"], epico, "epico") in ligacoes
    assert g["epicos"] == ["ABC-100"]
    assert {"chave": "ABC-123", "epico": "ABC-100"} in g["tarefas"]


def test_chave_local_fica_no_projeto(mem):
    mem.adicionar(tipo="fazer", titulo="A", texto="x", projeto="p1", tarefa="#12")
    mem.adicionar(tipo="fazer", titulo="B", texto="x", projeto="p2", tarefa="#12")
    ids = {n["id"] for n in mem.grafo()["nos"]}
    assert {id_chave("tarefa", "p1", "#12"), id_chave("tarefa", "p2", "#12")} <= ids
    assert "tarefa:p1:#12" in ids


def test_ordem_explicita_tarefa_epico_projeto_ficheiros(mem):
    alvo = mem.adicionar(
        tipo="licao", titulo="Alvo", texto="Ver [[Explícita]].", projeto="p", tarefa="ABC-1", epico="ABC-0", ficheiros=["a.py", "b.py"]
    )
    mem.adicionar(tipo="fazer", titulo="Explícita", texto="x", projeto="longe")
    mem.adicionar(tipo="fazer", titulo="Mesma tarefa", texto="x", projeto="longe", tarefa="ABC-1")
    mem.adicionar(tipo="fazer", titulo="Mesmo épico", texto="x", projeto="longe", tarefa="ABC-2", epico="ABC-0")
    mem.adicionar(tipo="fazer", titulo="Projeto e ficheiros", texto="x", projeto="p", ficheiros=["a.py", "b.py"])
    mem.adicionar(tipo="fazer", titulo="Só projeto", texto="x", projeto="p")
    rel = mem.relacionadas(alvo["id"])
    assert [r["titulo"] for r in rel] == ["Explícita", "Mesma tarefa", "Mesmo épico", "Projeto e ficheiros", "Só projeto"]
    motivos = {r["titulo"]: r["motivos"] for r in rel}
    # "Mesma tarefa" também partilha o épico (herdado), mas a relação conta uma vez por motivo.
    assert motivos["Mesma tarefa"] == {"tarefa": 1, "epico": 1}
    assert motivos["Mesmo épico"] == {"epico": 1}


def test_tarefa_que_e_epico_conta_como_mesmo_epico(mem):
    a, b, c, d, e, f = _jira(mem)
    rel_d = {r["id"]: r["motivos"] for r in mem.relacionadas(d["id"])}
    assert "epico" in rel_d[a["id"]] and "tarefa" not in rel_d[a["id"]]
    rel_a = {r["id"]: r["motivos"] for r in mem.relacionadas(a["id"])}
    assert "epico" in rel_a[d["id"]] and "tarefa" not in rel_a[d["id"]]


# --------------------------------------------------------------- pesquisa
def test_chave_jira_encontra_tarefa_e_epico(mem):
    a, b, c, d, e, f = _jira(mem)
    titulos = [r["titulo"] for r in mem.procurar("ABC-123", limite=20)]
    # Primeiro a tarefa, depois o resto do épico, depois a menção no texto.
    assert set(titulos[:2]) == {"Login com SSO", "Testar sessão"}
    assert set(titulos[2:4]) == {"Guardar senhas", "Épico fechado"}
    assert "Outro ticket" in titulos
    assert "Número solto" not in titulos  # "123" e "ABC" soltos não contam
    # Minúsculas também.
    assert [r["titulo"] for r in mem.procurar("abc-123", limite=2)] == titulos[:2]


def test_chave_do_epico_encontra_as_tarefas(mem):
    _jira(mem)
    titulos = {r["titulo"] for r in mem.procurar("ABC-100", limite=20)}
    assert {"Login com SSO", "Testar sessão", "Guardar senhas", "Épico fechado"} <= titulos


def test_filtros_tarefa_epico_projeto(mem):
    _jira(mem)
    assert {r["titulo"] for r in mem.procurar("", tarefa="abc-123")} == {"Login com SSO", "Testar sessão"}
    assert {r["titulo"] for r in mem.procurar("", epico="ABC-100")} == {"Login com SSO", "Testar sessão", "Guardar senhas", "Épico fechado"}
    assert {r["titulo"] for r in mem.procurar("senhas", epico="ABC-100", projeto="API")} == {"Guardar senhas"}


def test_procurar_por_nome_e_projeto(mem):
    mem.adicionar(tipo="licao", titulo="Deploy azul-verde", texto="x", projeto="Loja Online")
    mem.adicionar(tipo="fazer", titulo="Outra", texto="sem relação", projeto="Loja Online")
    mem.adicionar(tipo="fazer", titulo="Nada", texto="x", projeto="portal")
    assert mem.procurar("azul")[0]["titulo"] == "Deploy azul-verde"
    assert {r["titulo"] for r in mem.procurar("loja")} == {"Deploy azul-verde", "Outra"}
    assert {r["titulo"] for r in mem.procurar("", projeto="loja-online")} == {"Deploy azul-verde", "Outra"}


def test_etiquetas_sao_pesquisaveis(mem):
    mem.adicionar(tipo="licao", titulo="Pipeline", texto="x", projeto="p", etiquetas=["observabilidade"])
    assert mem.procurar("observab")[0]["titulo"] == "Pipeline"


def test_procurar_agrupado(mem):
    a, b, c, d, e, f = _jira(mem)
    g = mem.procurar_agrupado("portal")
    assert [p["nome"] for p in g["projetos"]] == ["portal"]
    assert id_projeto("portal") in g["nos"]
    assert {a["id"], b["id"], d["id"], e["id"], f["id"]} <= set(g["ids"])  # as memórias do projeto

    g = mem.procurar_agrupado("ABC-123")
    chaves = {(k["tipo"], k["chave"]) for k in g["chaves"]}
    assert ("tarefa", "ABC-123") in chaves and ("epico", "ABC-100") in chaves
    assert {a["id"], b["id"], c["id"], d["id"]} <= set(g["ids"])

    g = mem.procurar_agrupado("sessão")
    assert g["memorias"][0]["titulo"] == "Testar sessão" and g["projetos"] == []

    assert mem.procurar_agrupado("  ") == {"memorias": [], "projetos": [], "chaves": [], "ids": [], "nos": []}


def test_mcp_novos_parametros(mem):
    from mcp import Client

    from memoria.mcp_server import criar_servidor

    async def principal():
        async with Client(criar_servidor(mem)) as cliente:
            r = await cliente.call_tool(
                "memory_add",
                {
                    "type": "lesson",
                    "title": "Via MCP",
                    "text": "x",
                    "project": "p",
                    "task": "ABC-7",
                    "epic": "ABC-1",
                    "url": "https://empresa.atlassian.net/browse/ABC-7",
                    "tags": ["mcp"],
                },
            )
            p = await cliente.call_tool("memory_search", {"text": "", "epic": "abc-1"})
            return r, p

    r, p = asyncio.run(principal())
    meta = _meta(r.content[0].text)
    assert meta["epic"] == "ABC-1" and meta["tags"] == ["mcp"]
    achado = json.loads(p.content[0].text)["results"][0]
    assert achado["task"] == "ABC-7" and achado["epic"] == "ABC-1" and achado["url"].endswith("ABC-7")
