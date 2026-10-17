"""Modo browser a sério: é o recurso do Windows sem WebView2.

Arranca `agent-memory --browser` como um participante (BROWSER=true para não abrir nada),
lê o URL que a app imprime e abre-o num Chromium headless (Playwright).
Confirma que a página usa a ponte HTTP, pede os dados e desenha nós no canvas.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from memoria.exemplo import gerar  # noqa: E402
from memoria.service import Memoria  # noqa: E402
from memoria.webui import Api, ServidorUI  # noqa: E402

# Conta píxeis do canvas diferentes do fundo: prova que os nós foram desenhados.
PIXEIS_DESENHADOS = """() => {
  const c = document.querySelector('canvas');
  if (!c) return 0;
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 0; i < d.length; i += 16) {
    if (d[i] !== d[0] || d[i + 1] !== d[1] || d[i + 2] !== d[2]) n += 1;
  }
  return n;
}"""


@pytest.fixture(scope="module")
def navegador():
    with playwright.sync_playwright() as p:
        browser = None
        erros = []
        for opcoes in ({}, {"channel": "chrome"}):
            try:
                browser = p.chromium.launch(**opcoes)
                break
            except Exception as erro:  # sem Chromium do Playwright nem Google Chrome
                erros.append(str(erro).splitlines()[0])
        if browser is None:
            pytest.skip(f"sem browser para o Playwright: {erros}")
        yield browser
        browser.close()


def _arrancar_browser(home: Path) -> tuple[subprocess.Popen, str]:
    env = {**os.environ, "AGENT_MEMORY_HOME": str(home), "BROWSER": "true", "AGENT_MEMORY_NO_UPDATE": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "memoria", "--browser"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    fim = time.monotonic() + 60
    while time.monotonic() < fim:
        linha = proc.stderr.readline()
        if not linha:
            break
        m = re.search(r"(http://127\.0\.0\.1:\d+/\?t=[\w-]+)", linha)
        if m:
            return proc, m.group(1)
    proc.kill()
    pytest.fail("agent-memory --browser não imprimiu o URL da sessão")


def _esperar_desenho(pagina) -> int:
    """Espera que o grafo desenhe nós e devolve quantos píxeis estavam desenhados nesse momento.

    Devolve o valor visto pela espera, não uma leitura nova: no Chromium headless do Playwright
    os animation frames nem sempre correm, e um canvas redimensionado depois do primeiro desenho
    pode ficar por repintar (num browser visível e na janela nativa repinta no frame seguinte).
    """
    pagina.wait_for_function("document.documentElement.dataset.pronto !== undefined", timeout=30000)
    visto = pagina.wait_for_function(
        f"(() => {{ const n = ({PIXEIS_DESENHADOS})(); return n > 300 ? n : false; }})()", timeout=15000
    )
    return int(visto.json_value())


def test_memoria_browser_desenha_os_nos(home: Path, navegador):
    gerar(home, 41)
    proc, url = _arrancar_browser(home)
    try:
        # bypass_csp só para o Playwright avaliar as suas funções; a página real mantém a CSP.
        contexto = navegador.new_context(viewport={"width": 1280, "height": 800}, bypass_csp=True)
        pagina = contexto.new_page()
        pedidos, erros = [], []
        pagina.on("request", lambda r: pedidos.append(r.url))
        pagina.on("pageerror", lambda e: erros.append(str(e)))
        pagina.goto(url)
        pixeis = _esperar_desenho(pagina)
        estado = pagina.evaluate(
            """() => ({
                pronto: Number(document.documentElement.dataset.pronto),
                ponte: document.documentElement.dataset.ponte,
                modo: document.querySelector('meta[name="memoria-modo"]').content,
                pywebview: typeof window.pywebview,
                caminho: location.pathname + location.search,
            })"""
        )
        assert erros == []
        csp = pagina.evaluate("async () => (await fetch('/')).headers.get('content-security-policy')")
        assert "script-src 'self'" in csp
        assert estado["modo"] == "browser" and estado["pywebview"] == "undefined"
        assert estado["ponte"] == "http"
        assert estado["pronto"] > 41  # memórias + nós de contexto
        assert estado["caminho"] == "/"  # a chave saiu do URL (ficou num cookie)
        assert any(u.endswith("/api/grafo") for u in pedidos)
        assert pixeis > 300

        # Recarregar funciona com o cookie da sessão.
        pagina.reload()
        _esperar_desenho(pagina)

        # Sem a chave (outro browser, sem cookie): explica o que fazer, não mostra um grafo vazio.
        outro = navegador.new_context()
        resposta = outro.new_page().goto(url.split("?", 1)[0])
        assert resposta.status == 403
        assert "Sessão sem chave" in resposta.text()
        outro.close()
        contexto.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_janela_sem_pywebview_usa_http(home: Path, navegador):
    """No modo janela, se a ponte do pywebview não aparecer, a página usa HTTP."""
    gerar(home, 20)
    servidor = ServidorUI(Api(Memoria(home), modo="janela")).iniciar()
    try:
        pagina = navegador.new_page()
        pagina.goto(servidor.url())
        _esperar_desenho(pagina)
        estado = pagina.evaluate(
            "() => [document.querySelector('meta[name=\"memoria-modo\"]').content, document.documentElement.dataset.ponte]"
        )
        assert estado == ["janela", "http"]
        pagina.close()
    finally:
        servidor.parar()


# ---------------------------------------------------------------------- línguas
def _abrir(home: Path, navegador, monkeypatch, lingua: str | None):
    from memoria import i18n

    if lingua:
        monkeypatch.setenv("AGENT_MEMORY_LANG", lingua)
    else:
        monkeypatch.delenv("AGENT_MEMORY_LANG", raising=False)
        monkeypatch.setattr(i18n, "lingua_sistema", lambda: "pt")
    i18n.repor()
    servidor = ServidorUI(Api(Memoria(home), modo="browser"))
    servidor.csp = True
    servidor.iniciar()
    contexto = navegador.new_context(viewport={"width": 1280, "height": 800}, bypass_csp=True)
    pagina = contexto.new_page()
    pagina.goto(servidor.url())
    _esperar_desenho(pagina)
    return servidor, contexto, pagina


RETANGULOS = """() => {
  const r = (s) => {
    const e = document.querySelector(s);
    if (!e) return null;
    const b = e.getBoundingClientRect();
    return { x: b.left, w: b.width };
  };
  return { coluna: r('.coluna'), area: r('.area'), painel: r('.painel') };
}"""


def test_hebraico_em_rtl(home: Path, navegador, monkeypatch):
    gerar(home, 40)
    servidor, contexto, pagina = _abrir(home, navegador, monkeypatch, "he")
    try:
        raiz = pagina.evaluate("() => [document.documentElement.lang, document.documentElement.dir]")
        assert raiz == ["he", "rtl"]
        assert pagina.locator(".recentes h2").inner_text() == "הזיכרונות האחרונים"
        assert pagina.get_by_role("button", name="זיכרון חדש").count() == 1
        caixas = pagina.evaluate(RETANGULOS)
        assert caixas["coluna"]["x"] > caixas["area"]["x"]  # a coluna fica à direita
        # O painel abre do lado de dentro (à esquerda do mapa) e o grafo continua desenhado.
        pagina.locator(".recentes li button").first.click()
        pagina.wait_for_selector(".painel h2")
        pagina.wait_for_timeout(600)  # o painel entra a deslizar (240 ms); mede no fim
        caixas = pagina.evaluate(RETANGULOS)
        assert abs(caixas["painel"]["x"] - caixas["area"]["x"]) < 2
        assert pagina.locator(".painel dt").first.inner_text() == "סוג"
        assert int(pagina.evaluate("() => document.documentElement.dataset.pronto")) > 40
        assert pagina.evaluate(
            "() => [...document.fonts].some((f) => f.family.includes('Noto Sans Hebrew') && f.status === 'loaded')"
        )
    finally:
        contexto.close()
        servidor.parar()


def test_hindi_com_fonte_devanagari(home: Path, navegador, monkeypatch):
    gerar(home, 20)
    servidor, contexto, pagina = _abrir(home, navegador, monkeypatch, "hi")
    try:
        assert pagina.evaluate("() => [document.documentElement.lang, document.documentElement.dir]") == ["hi", "ltr"]
        assert pagina.locator(".recentes h2").inner_text() == "हाल की मेमोरी"
        pagina.wait_for_function(
            "() => [...document.fonts].some((f) => f.family.includes('Noto Sans Devanagari') && f.status === 'loaded')",
            timeout=10000,
        )
    finally:
        contexto.close()
        servidor.parar()


def test_seletor_muda_e_guarda_a_lingua(home: Path, navegador, monkeypatch):
    import json as _json

    gerar(home, 10)
    servidor, contexto, pagina = _abrir(home, navegador, monkeypatch, None)
    try:
        assert pagina.evaluate("() => document.documentElement.lang") == "pt"
        assert pagina.locator(".recentes h2").inner_text() == "Últimas memórias"
        pagina.select_option(".seletor-lingua", "en")
        pagina.wait_for_function("() => document.querySelector('.recentes h2').textContent === 'Latest memories'")
        pagina.wait_for_function("() => document.documentElement.lang === 'en'")
        # Guardado no disco e usado na próxima abertura (o servidor já manda lang="en").
        fim = time.monotonic() + 5
        while time.monotonic() < fim and not (home / "preferences.json").exists():
            time.sleep(0.1)
        assert _json.loads((home / "preferences.json").read_text("utf-8"))["language"] == "en"
        resposta = pagina.reload()
        assert '<html lang="en" dir="ltr">' in resposta.text()
        _esperar_desenho(pagina)
        assert pagina.locator(".recentes h2").inner_text() == "Latest memories"
    finally:
        contexto.close()
        servidor.parar()


def test_atividade_do_claude(home: Path, navegador, monkeypatch):
    """O que o Claude chamou pelo MCP aparece na vista "Atividade" e abre a memória."""
    import asyncio

    from mcp import Client

    from memoria.mcp_server import criar_servidor

    gerar(home, 15)
    mem = Memoria(home)

    async def chamadas():
        async with Client(criar_servidor(mem)) as c:
            await c.call_tool("memory_search", {"text": "cache", "limit": 3})
            await c.call_tool("memory_search", {"text": "coisa que não existe"})

    # O Playwright síncrono já tem um event loop nesta thread: as chamadas MCP vão noutra.
    import threading

    fio = threading.Thread(target=lambda: asyncio.run(chamadas()))
    fio.start()
    fio.join(60)
    servidor, contexto, pagina = _abrir(home, navegador, monkeypatch, "pt")
    try:
        pagina.get_by_role("button", name="Atividade do Claude").click()
        pagina.wait_for_selector(".atividade .registo-linha:not(.registo-cabeca)")
        valores = pagina.locator(".numero-valor").all_inner_texts()
        assert valores[:2] == ["2", "2"]  # hoje e no total
        assert pagina.locator(".numero-rotulo").first.inner_text() == "Chamadas hoje"
        linhas = pagina.locator(".atividade .registo-linha:not(.registo-cabeca)")
        assert linhas.count() == 4  # 3 memórias + 1 pesquisa sem resultados
        assert "Sem resultados" in linhas.first.inner_text()
        titulo = pagina.locator(".atividade .registo-memoria .ligacao-texto").first.inner_text()
        pagina.locator(".atividade .registo-memoria .ligacao-texto").first.click()
        pagina.wait_for_selector(".painel h2")
        assert pagina.locator(".atividade").count() == 0  # voltou ao mapa
        assert pagina.locator(".painel h2").inner_text() == titulo
    finally:
        contexto.close()
        servidor.parar()


# Palavras e pedaços de identificadores portugueses que não podem aparecer na interface em inglês.
PORTUGUES = re.compile(
    r"memória|memoria|lição|licao|fazer|histórico|historico|projeto|tarefa|épico|epico|ficheiro|ligaç|ligac|"
    r"etiqueta|pesquisa|procurar|guardar|cancelar|atividade|sem resultados|redigido|[ãõçáéíóúâêô]",
    re.I,
)


def test_ingles_sem_portugues(home: Path, navegador, monkeypatch):
    """Em inglês, o mapa, o painel de uma nota, o editor e a vista de atividade não mostram português."""
    import asyncio
    import threading

    from mcp import Client

    from memoria.mcp_server import criar_servidor

    mem = Memoria(home)
    a = mem.adicionar(
        tipo="lesson", titulo="Cache the build", texto="Use a shared cache. See [[Retry with backoff]].",
        projeto="security-arena", tarefa="ARENA-7", epico="ARENA-1", etiquetas=["ci"], ficheiros=["build.mjs"],
    )
    mem.adicionar(tipo="dont", titulo="Retry with backoff", texto="Never retry in a loop.", projeto="security-arena", tarefa="ARENA-8")
    mem.adicionar(tipo="history", titulo="Swarm run", texto="Four agents, one wave.", projeto="practice-project", custo_usd=1.25)

    async def chamadas():
        async with Client(criar_servidor(mem)) as c:
            await c.call_tool("memory_search", {"text": "cache", "project": "security-arena"})
            await c.call_tool("memory_related", {"ref": a["caminho"]})
            await c.call_tool("memory_add", {"type": "do", "title": "Plan first", "text": "x", "project": "security-arena"})
            await c.call_tool("memory_search", {"text": "nothing like this"})

    fio = threading.Thread(target=lambda: asyncio.run(chamadas()))
    fio.start()
    fio.join(60)
    servidor, contexto, pagina = _abrir(home, navegador, monkeypatch, "en")
    try:
        textos = [pagina.locator("body").inner_text()]
        pagina.locator(".recentes li button", has_text="Cache the build").click()
        pagina.wait_for_selector(".painel .seccao")
        pagina.wait_for_timeout(300)
        textos.append(pagina.locator(".painel").inner_text())
        pagina.get_by_role("button", name="Edit").click()
        pagina.wait_for_selector(".painel textarea")
        texto_editor = pagina.locator(".painel textarea").input_value()
        assert texto_editor.startswith("---\ntype: lesson\ntitle: Cache the build\nproject: security-arena\n")
        textos += [pagina.locator(".painel").inner_text(), texto_editor]
        pagina.get_by_role("button", name="Cancel").click()
        pagina.get_by_role("button", name="New memory").click()
        pagina.wait_for_selector(".dialogo")
        textos.append(pagina.locator(".dialogo").inner_text())
        pagina.keyboard.press("Escape")
        pagina.get_by_role("button", name="Claude activity").click()
        pagina.wait_for_selector(".atividade .registo-linha:not(.registo-cabeca)")
        textos.append(pagina.locator(".atividade").inner_text())
        titulos = pagina.locator(".atividade [role=cell][title]").evaluate_all("(es) => es.map((e) => e.title)")
        assert set(titulos) == {"memory_search", "memory_related", "memory_add"}
        textos += titulos
        for texto in textos:
            # O seletor de línguas mostra cada língua no seu nome ("Português"): é de propósito.
            texto = texto.replace("Português", "")
            assert not PORTUGUES.search(texto), PORTUGUES.search(texto).group(0) + " em: " + texto[:2000]
    finally:
        contexto.close()
        servidor.parar()


def test_ui_diz_que_a_app_foi_fechada(home: Path, navegador, monkeypatch):
    """O servidor do modo browser termina sem batimento (5 minutos): a página diz isso, nunca fica em branco."""
    gerar(home, 12)
    servidor, contexto, pagina = _abrir(home, navegador, monkeypatch, "en")
    try:
        servidor.parar()
        # O painel carrega-se só quando é preciso: com o servidor parado, esse pedido falha.
        pagina.locator(".recentes li button").first.click()
        pagina.wait_for_selector(".fechada", timeout=15000)
        assert "Agent Memory was closed." in pagina.locator(".fechada").inner_text()
        assert "Failed to fetch" not in pagina.locator("body").inner_text()
    finally:
        contexto.close()
