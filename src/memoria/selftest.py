"""`memoria selftest`: verifica a instalação sem tocar nas memórias do utilizador."""

from __future__ import annotations

import asyncio
import os
import platform
import sqlite3
import sys
import tempfile
from pathlib import Path

from memoria import __version__, config, i18n
from memoria.i18n import t


def _linha(ok: bool, texto: str) -> bool:
    print(f"  [{t('st.ok') if ok else t('st.falhou')}] {texto}")
    return ok


def verificar_base() -> bool:
    from memoria.index import FTS5Indisponivel, verificar_fts5
    from memoria.service import Memoria
    from memoria.webui import pasta_ui

    print(f"Agent Memory {__version__} · Python {platform.python_version()} · {platform.system()} {platform.machine()}")
    atual = i18n.lingua()
    print(f"  {t('st.lingua', nome=i18n.NOMES[atual], codigo=atual)}")
    resultados = []

    try:
        verificar_fts5()
        resultados.append(_linha(True, t("st.sqlite", versao=sqlite3.sqlite_version)))
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
            resultados.append(_linha("sk-ant-" not in conteudo and "[REDIGIDO:" in conteudo, t("st.redacao")))
            achados = mem.procurar("arranque")
            resultados.append(_linha(bool(achados) and achados[0]["id"] == a["id"], t("st.fts")))
            rel = mem.relacionadas(a["id"])
            resultados.append(_linha(bool(rel) and rel[0]["motivos"].get("ligacao") == 1, t("st.arestas")))
            por_chave = {r["titulo"] for r in mem.procurar("TESTE-2")}
            resultados.append(_linha(por_chave == {"Teste de arranque", "Segunda nota"}, t("st.chave")))
            estado = mem.reindexar()
            resultados.append(_linha(estado["total"] == 2, t("st.reindex")))
            resultados.append(_linha(_mcp_ok(mem), t("st.mcp")))
        except Exception as erro:
            resultados.append(_linha(False, t("st.basicas", erro=f"{type(erro).__name__}: {erro}")))

    resultados.append(_linha((pasta_ui() / "index.html").is_file(), t("st.ui")))

    cfg = config.definicoes()
    try:
        url = config.url_asset(cfg, "v0.0.0", "SHA256SUMS")
        resultados.append(_linha(True, t("st.urls_ok", host=config.partes_repo(cfg["MEMORY_APP_REPO_URL"])["host"])))
    except (ValueError, KeyError) as erro:
        url = None
        resultados.append(_linha(False, t("st.urls_erro", erro=erro)))
    del url

    home = config.memoria_home()
    try:
        home.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=home, prefix=".selftest-"):
            pass
        resultados.append(_linha(True, t("st.pasta", pasta=home)))
    except OSError as erro:
        resultados.append(_linha(False, t("st.sem_escrita", pasta=home, erro=erro)))

    from memoria import portatil

    dados = portatil.info()
    if dados and portatil.translocada():
        resultados.append(_linha(False, t("st.copia_temporaria")))
    elif dados:
        resultados.append(_linha(True, t("st.portatil", plataforma=dados["plataforma"], raiz=portatil.raiz())))

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
        print(t("st.resultado", estado=t("st.ok") if ok else t("st.falhou")))
        from memoria import portatil

        if ok and portatil.info():
            print(f"{t('st.ligar')}\n  {portatil.comando_claude()}")
        return 0 if ok else 1
    if not ok:
        print(t("st.antes_janela", estado=t("st.falhou")))
        return 1
    from memoria import window

    sys.stdout.flush()
    os.environ.setdefault("MEMORIA_SEM_UPDATE", "1")
    return window.correr(selftest=True, timeout=timeout, t0=t0)
