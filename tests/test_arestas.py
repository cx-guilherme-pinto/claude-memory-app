"""Ordem de força: ligação explícita > mesma tarefa > mesmo projeto > ficheiros partilhados."""

from memoria.index import id_ficheiro, id_projeto, id_tarefa


def _cenario(mem):
    a = mem.adicionar(
        tipo="licao", titulo="Alvo", texto="Ver [[Explícita]].", projeto="p1", tarefa="T-1", ficheiros=["src/x.py", "src/y.py"]
    )
    b = mem.adicionar(tipo="fazer", titulo="Explícita", texto="sem nada em comum", projeto="outro")
    c = mem.adicionar(tipo="fazer", titulo="Mesma tarefa", texto="t", projeto="p1", tarefa="T-1")
    d = mem.adicionar(tipo="fazer", titulo="Mesmo projeto e dois ficheiros", texto="p", projeto="p1", ficheiros=["src/x.py", "src/y.py"])
    e = mem.adicionar(tipo="fazer", titulo="Mesmo projeto", texto="p", projeto="p1")
    f = mem.adicionar(tipo="fazer", titulo="Só ficheiro", texto="f", projeto="p1-b", ficheiros=["src/x.py"])
    g = mem.adicionar(tipo="fazer", titulo="Nada", texto="n", projeto="longe")
    return a, b, c, d, e, f, g


def test_ordem_de_forca(mem):
    a, b, c, d, e, f, g = _cenario(mem)
    rel = mem.relacionadas(a["id"])
    ordem = [r["titulo"] for r in rel]
    assert ordem[:4] == ["Explícita", "Mesma tarefa", "Mesmo projeto e dois ficheiros", "Mesmo projeto"]
    assert "Nada" not in ordem
    # Ficheiros são relativos ao projeto: "src/x.py" de outro projeto não liga.
    assert "Só ficheiro" not in ordem
    forca = {r["titulo"]: r["forca"] for r in rel}
    # Cada nível vale mais do que todos os de baixo somados.
    assert forca["Explícita"] > forca["Mesma tarefa"] + 0  # explícita sem mais nada
    assert forca["Mesma tarefa"] > forca["Mesmo projeto e dois ficheiros"] > forca["Mesmo projeto"]
    assert rel[0]["motivos"] == {"ligacao": 1}
    assert rel[1]["motivos"] == {"tarefa": 1, "projeto": 1}


def test_ligacao_e_simetrica(mem):
    a, b, *_ = _cenario(mem)
    assert mem.relacionadas(b["id"])[0]["id"] == a["id"]


def test_resolver_ligacoes_por_id_nome_e_titulo(mem):
    alvo = mem.adicionar(tipo="licao", titulo="Título Com Acentos", texto="x", projeto="p")
    nome = alvo["id"].split("/")[-1]
    origem = mem.adicionar(
        tipo="fazer",
        titulo="Origem",
        texto=f"[[{alvo['id']}]] [[{nome}]] [[título com acentos|alias]]",
        projeto="q",
        ligacoes=["titulo-com-acentos"],
    )
    rel = mem.relacionadas(origem["id"])
    assert [r["id"] for r in rel] == [alvo["id"]]
    assert mem.relacionadas(alvo["caminho"])[0]["id"] == origem["id"]


def test_grafo_tem_nos_de_contexto(mem):
    a, *_ = _cenario(mem)
    g = mem.grafo()
    ids = {n["id"]: n for n in g["nos"]}
    assert ids[id_projeto("p1")]["tipo"] == "projeto"
    assert ids[id_tarefa("p1", "T-1")]["tipo"] == "tarefa"
    assert ids[id_ficheiro("p1", "src/x.py")]["tipo"] == "ficheiro"
    assert ids[id_ficheiro("p1", "src/x.py")]["rotulo"] == "src/x.py"
    # Grau = número de ligações do nó.
    assert ids[a["id"]]["grau"] == sum(1 for lig in g["ligacoes"] if a["id"] in (lig["source"], lig["target"]))
    assert g["total"] == 7
    assert {"source", "target", "tipo"} <= set(g["ligacoes"][0])
    assert "corpo" not in g["nos"][0]  # o grafo é leve: o corpo vem a pedido
