"""`memoria selftest`: verifica a instalação sem tocar nas memórias do utilizador."""

from __future__ import annotations

import asyncio
import os
import platform
import sqlite3
import sys
import tempfile
from pathlib import Path

from memoria import __version__, config


def _linha(ok: bool, texto: str) -> bool:
    print(f"  [{'OK' if ok else 'FALHOU'}] {texto}")
    return ok


def verificar_base() -> bool:
    from memoria.index import FTS5Indisponivel, verificar_fts5
    from memoria.service import Memoria
    from memoria.webui import pasta_ui

    print(f"Memória {__version__} · Python {platform.python_version()} · {platform.system()} {platform.machine()}")
    resultados = []

    try:
        verificar_fts5()
        resultados.append(_linha(True, f"SQLite {sqlite3.sqlite_version} com FTS5"))
    except FTS5Indisponivel as erro:
        resultados.append(_linha(False, str(erro)))
        return False

    with tempfile.TemporaryDirectory(prefix="memoria-selftest-") as tmp:
        try:
            mem = Memoria(Path(tmp))
            a = mem.adicionar(
                tipo="licao",
                titulo="Teste de arranque",
                texto="Chave sk-ant-api03-ABCDEFGHIJKLMNOPQRST não pode ficar. Ver [[segunda nota]].",
                projeto="selftest",
                tarefa="TESTE-2",
                epico="TESTE-1",
            )
            mem.adicionar(tipo="fazer", titulo="Segunda nota", texto="Outra nota.", projeto="selftest", tarefa="TESTE-3", epico="TESTE-1")
            conteudo = Path(a["caminho"]).read_text("utf-8")
            resultados.append(_linha("sk-ant-" not in conteudo and "[REDIGIDO:" in conteudo, "Redação de segredos"))
            achados = mem.procurar("arranque")
            resultados.append(_linha(bool(achados) and achados[0]["id"] == a["id"], "Pesquisa FTS5"))
            rel = mem.relacionadas(a["id"])
            resultados.append(_linha(bool(rel) and rel[0]["motivos"].get("ligacao") == 1, "Arestas e relacionadas"))
            por_chave = {r["titulo"] for r in mem.procurar("TESTE-2")}
            resultados.append(_linha(por_chave == {"Teste de arranque", "Segunda nota"}, "Pesquisa por tarefa e épico"))
            estado = mem.reindexar()
            resultados.append(_linha(estado["total"] == 2, "Reindex a partir do Markdown"))
            resultados.append(_linha(_mcp_ok(mem), "Servidor MCP (3 ferramentas)"))
        except Exception as erro:
            resultados.append(_linha(False, f"Operações básicas: {type(erro).__name__}: {erro}"))

    resultados.append(_linha((pasta_ui() / "index.html").is_file(), "Interface incluída no pacote"))

    cfg = config.definicoes()
    try:
        url = config.url_asset(cfg, "v0.0.0", "SHA256SUMS")
        resultados.append(_linha(True, f"URLs de atualização ({config.partes_repo(cfg['MEMORY_APP_REPO_URL'])['host']})"))
    except (ValueError, KeyError) as erro:
        url = None
        resultados.append(_linha(False, f"URLs de atualização: {erro}"))
    del url

    home = config.memoria_home()
    try:
        home.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=home, prefix=".selftest-"):
            pass
        resultados.append(_linha(True, f"Pasta das memórias: {home}"))
    except OSError as erro:
        resultados.append(_linha(False, f"Sem escrita em {home}: {erro}"))

    from memoria import portatil

    dados = portatil.info()
    if dados and portatil.translocada():
        resultados.append(_linha(False, "A app corre de uma cópia temporária do macOS. Move-a para Aplicações."))
    elif dados:
        resultados.append(_linha(True, f"Versão portátil {dados['plataforma']}: {portatil.raiz()}"))

    return all(resultados)


def _mcp_ok(mem) -> bool:
    from mcp import Client

    from memoria.mcp_server import criar_servidor

    async def correr() -> bool:
        async with Client(criar_servidor(mem)) as cliente:
            nomes = {t.name for t in (await cliente.list_tools()).tools}
            r = await cliente.call_tool("memoria_procurar", {"texto": "arranque"})
            return nomes == {"memoria_procurar", "memoria_adicionar", "memoria_relacionadas"} and not r.is_error

    return asyncio.run(correr())


def correr(gui: bool = False, timeout: float = 60.0, t0: float | None = None) -> int:
    ok = verificar_base()
    if not gui:
        print("selftest: OK" if ok else "selftest: FALHOU")
        from memoria import portatil

        if ok and portatil.info():
            print(f"Para ligar ao Claude Code:\n  {portatil.comando_claude()}")
        return 0 if ok else 1
    if not ok:
        print("selftest: FALHOU (antes da janela)")
        return 1
    from memoria import window

    sys.stdout.flush()
    os.environ.setdefault("MEMORIA_SEM_UPDATE", "1")
    return window.correr(selftest=True, timeout=timeout, t0=t0)
