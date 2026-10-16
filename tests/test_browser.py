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
