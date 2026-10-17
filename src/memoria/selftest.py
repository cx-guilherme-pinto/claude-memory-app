"""`agent-memory selftest`: verifica a instalação sem tocar nas memórias do utilizador."""

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


def _aviso(texto: str) -> bool:
    """Uma linha [WARN]: não faz falhar o selftest."""
    print(f"  [{t('st.aviso')}] {texto}")
    return True


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

    with tempfile.TemporaryDirectory(prefix="agent-memory-selftest-") as tmp:
        try:
            mem = Memoria(Path(tmp))
            a = mem.adicionar(
                tipo="lesson",
                titulo="Startup check",
                texto="The key sk-ant-api03-ABCDEFGHIJKLMNOPQRST must not stay. See [[second note]].",
                projeto="selftest",
                tarefa="TEST-2",
                epico="TEST-1",
            )
            mem.adicionar(tipo="do", titulo="Second note", texto="Another note.", projeto="selftest", tarefa="TEST-3", epico="TEST-1")
            conteudo = Path(a["caminho"]).read_text("utf-8")
            resultados.append(_linha("sk-ant-" not in conteudo and "[REDACTED:" in conteudo, t("st.redacao")))
            achados = mem.procurar("startup")
            resultados.append(_linha(bool(achados) and achados[0]["id"] == a["id"], t("st.fts")))
            rel = mem.relacionadas(a["id"])
            resultados.append(_linha(bool(rel) and rel[0]["motivos"].get("ligacao") == 1, t("st.arestas")))
            por_chave = {r["titulo"] for r in mem.procurar("TEST-2")}
            resultados.append(_linha(por_chave == {"Startup check", "Second note"}, t("st.chave")))
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
        config.verificar_pasta(home)  # ligação partida (nuvem por sincronizar) ou um ficheiro
        home.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=home, prefix=".selftest-"):
            pass
        resultados.append(_linha(True, t("st.pasta", pasta=home)))
    except OSError as erro:
        resultados.append(_linha(False, t("st.sem_escrita", pasta=home, erro=erro)))
    else:
        resultados.append(_indice_real(home))
    for origem, pasta, n in config.pastas_ignoradas(home):
        resultados.append(_aviso(t("st.pasta_ignorada", pasta=pasta, origem=origem, n=n)))

    from memoria import portatil

    dados = portatil.info()
    if dados and portatil.translocada():
        resultados.append(_linha(False, t("st.copia_temporaria")))
    elif dados:
        resultados.append(_linha(True, t("st.portatil", plataforma=dados["plataforma"], raiz=portatil.raiz())))

    return all(resultados)


def _indice_real(home: Path) -> bool:
    """O índice das memórias desta pessoa abre (e, se estava estragado, refaz-se). As notas não mudam."""
    from memoria.index import comando_permissoes, indice_ocupado, indice_sem_escrita
    from memoria.service import Memoria

    try:
        estado = Memoria(home).sincronizar(forcar=True, espera=5)
    except Exception as erro:
        if indice_ocupado(erro):  # outro processo está a escrever: o índice existe e está a ser usado
            return _linha(True, t("st.indice_ocupado"))
        if indice_sem_escrita(erro):  # permissões (ex.: depois de um sudo): o reindex não resolve
            return _linha(False, t("st.indice_sem_escrita", pasta=home, erro=erro, comando=comando_permissoes(home)))
        return _linha(False, t("st.indice_erro", erro=f"{type(erro).__name__}: {erro}"))
    if estado is None:
        return _linha(True, t("st.indice_ocupado"))
    return _linha(True, t("st.indice", total=estado["total"]))


def _mcp_ok(mem) -> bool:
    from mcp import Client

    from memoria.mcp_server import FERRAMENTAS, criar_servidor

    async def correr() -> bool:
        async with Client(criar_servidor(mem)) as cliente:
            nomes = {t.name for t in (await cliente.list_tools()).tools}
            r = await cliente.call_tool("memory_search", {"text": "startup"})
            return nomes == set(FERRAMENTAS) and not r.is_error

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
    for nome, valor in config.ambiente_sem_update().items():
        os.environ.setdefault(nome, valor)
    return window.correr(selftest=True, timeout=timeout, t0=t0)
