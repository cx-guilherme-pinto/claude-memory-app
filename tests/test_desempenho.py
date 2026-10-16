"""Orçamento de arranque: a UI tem de carregar em menos de 2 s com 500 memórias.

Aqui medimos a parte do Python: reindexar 500 notas e servir o payload do grafo
pela API HTTP. A parte do browser mede-se em test_gui.py (selftest --gui).
"""

import http.client
import json
import time
from pathlib import Path

from memoria.exemplo import gerar
from memoria.service import Memoria
from memoria.webui import Api, ServidorUI

ORCAMENTO_S = 2.0


def test_500_memorias_indice_e_payload(home: Path, tmp_path: Path):
    gerar(home, 500)
    raiz = tmp_path / "ui"
    raiz.mkdir()
    (raiz / "index.html").write_text("<!doctype html>", "utf-8")

    inicio = time.perf_counter()
    mem = Memoria(home)
    estado = mem.reindexar()
    t_indice = time.perf_counter() - inicio

    servidor = ServidorUI(Api(mem, modo="browser"), raiz=raiz).iniciar()
    try:
        t0 = time.perf_counter()
        c = http.client.HTTPConnection("127.0.0.1", servidor.porta, timeout=10)
        c.request(
            "POST",
            "/api/grafo",
            body=b'{"args": []}',
            headers={"X-Memoria-Token": servidor.token, "Host": f"127.0.0.1:{servidor.porta}"},
        )
        corpo = c.getresponse().read()
        t_payload = time.perf_counter() - t0
    finally:
        servidor.parar()

    grafo = json.loads(corpo)["resultado"]
    total = time.perf_counter() - inicio
    print(
        f"\n500 memórias: índice {t_indice * 1000:.0f} ms, payload {t_payload * 1000:.0f} ms "
        f"({len(corpo) / 1024:.0f} KB, {len(grafo['nos'])} nós, {len(grafo['ligacoes'])} arestas), total {total * 1000:.0f} ms"
    )
    assert estado["total"] == 500 and grafo["total"] == 500
    assert total < ORCAMENTO_S
    # Margem para o browser: o lado do Python fica bem abaixo do orçamento.
    assert total < ORCAMENTO_S * 0.75


def test_sincronizar_sem_alteracoes_e_rapido(home: Path):
    gerar(home, 500)
    mem = Memoria(home)
    mem.reindexar()
    t0 = time.perf_counter()
    estado = mem.sincronizar(forcar=True)
    assert estado["alteradas"] == 0
    assert time.perf_counter() - t0 < 0.5
