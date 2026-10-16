"""Modo browser a sério: é o recurso do Windows sem WebView2.

Arranca `memoria --browser` como um participante (BROWSER=true para não abrir nada),
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
    env = {**os.environ, "MEMORIA_HOME": str(home), "BROWSER": "true", "MEMORIA_SEM_UPDATE": "1"}
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
    pytest.fail("memoria --browser não imprimiu o URL da sessão")


def _esperar_desenho(pagina) -> int:
    pagina.wait_for_function("document.documentElement.dataset.pronto !== undefined", timeout=30000)
    # A simulação desenha durante alguns frames; dá-lhe tempo.
    pagina.wait_for_function(f"({PIXEIS_DESENHADOS})() > 300", timeout=15000)
    return pagina.evaluate(PIXEIS_DESENHADOS)


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
        monkeypatch.setenv("MEMORIA_LANG", lingua)
    else:
        monkeypatch.delenv("MEMORIA_LANG", raising=False)
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
  const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return { x: b.left, w: b.width }; };
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
        caixas = pagina.evaluate(RETANGULOS)
        assert abs(caixas["painel"]["x"] - caixas["area"]["x"]) < 2
        assert pagina.locator(".painel dt").first.inner_text() == "סוג"
        assert pagina.evaluate(PIXEIS_DESENHADOS) > 300
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
        while time.monotonic() < fim and not (home / "preferencias.json").exists():
            time.sleep(0.1)
        assert _json.loads((home / "preferencias.json").read_text("utf-8"))["lingua"] == "en"
        resposta = pagina.reload()
        assert '<html lang="en" dir="ltr">' in resposta.text()
        _esperar_desenho(pagina)
        assert pagina.locator(".recentes h2").inner_text() == "Latest memories"
    finally:
        contexto.close()
        servidor.parar()
