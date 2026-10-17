"""Janela nativa (pywebview) com recurso ao browser.

No Windows, o pywebview cai em silêncio no IE11 quando falta o WebView2.
Por isso detetamos o WebView2 pelo registo (valor `pv`) antes de abrir a janela.
Se faltar, ou se a janela falhar, a mesma UI abre no browser em 127.0.0.1.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
import webbrowser

from memoria.i18n import t
from memoria.service import Memoria
from memoria.webui import Api, ServidorUI, pasta_ui

WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_CHAVES = (
    ("HKEY_LOCAL_MACHINE", rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_GUID}"),
    ("HKEY_CURRENT_USER", rf"Software\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_GUID}"),
    # Windows de 32 bits (raro) não tem WOW6432Node.
    ("HKEY_LOCAL_MACHINE", rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_GUID}"),
)

# Sem batimentos da página durante este tempo, o modo browser termina.
LIMITE_SEM_BATIMENTO = 300.0
LIMITE_PRIMEIRO_BATIMENTO = 600.0


def _info(msg: str) -> None:
    if sys.stderr:
        try:
            print(msg, file=sys.stderr)
        except Exception:
            pass


def versao_webview2(winreg=None) -> str | None:
    """Versão do WebView2 Runtime instalada (valor `pv`), ou None.

    `winreg` só é passado nos testes (módulo falso); no Windows usa o verdadeiro.
    """
    if winreg is None:
        if os.name != "nt":
            return None
        import winreg

    for raiz, caminho in WEBVIEW2_CHAVES:
        try:
            with winreg.OpenKey(getattr(winreg, raiz), caminho) as chave:
                valor, _ = winreg.QueryValueEx(chave, "pv")
        except OSError:
            continue
        valor = str(valor or "").strip()
        if valor and valor != "0.0.0.0":
            return valor
    return None


def janela_disponivel() -> tuple[bool, str]:
    if os.name == "nt":
        versao = versao_webview2()
        if not versao:
            return False, t("jan.sem_webview2")
        return True, f"WebView2 {versao}"
    if sys.platform == "darwin":
        return True, "WKWebView"
    try:  # Linux: precisa de GTK (PyGObject) ou Qt
        import gi  # noqa: F401

        return True, "GTK"
    except ImportError:
        return False, t("jan.sem_gtk")


def tema_escuro() -> bool:
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=2)
            return "Dark" in r.stdout
        if os.name == "nt":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            ) as chave:
                valor, _ = winreg.QueryValueEx(chave, "AppsUseLightTheme")
                return valor == 0
    except Exception:
        pass
    return False


def correr(browser: bool = False, selftest: bool = False, timeout: float = 60.0, t0: float | None = None) -> int:
    t0 = t0 or time.perf_counter()
    if not (pasta_ui() / "index.html").is_file():
        _info(t("jan.sem_ui", pasta=pasta_ui()))
        return 2
    mem = Memoria()
    try:
        mem.sincronizar(forcar=True)
    except (sqlite3.Error, OSError) as erro:  # a janela abre na mesma (as notas estão no disco); o erro diz o que fazer
        from memoria.index import indice_ocupado

        if indice_ocupado(erro):
            _info(t("erro.indice_ocupado"))
        else:
            _info(t("erro.indice", erro=erro) if isinstance(erro, sqlite3.Error) else t("aviso.indexar", erro=erro))

    if not browser:
        ok, motivo = janela_disponivel()
        if ok:
            api = Api(mem, modo="janela", selftest=selftest)
            servidor = ServidorUI(api).iniciar()
            try:
                return _correr_janela(api, servidor, selftest, timeout, t0)
            except _JanelaFalhou as erro:
                motivo = str(erro)
            finally:
                servidor.parar()
        if selftest:
            _info(t("jan.selftest_sem_janela", motivo=motivo))
            _info(t("jan.sem_janela_browser"))
            return 3
        _info(t("jan.indisponivel", motivo=motivo))
    return _correr_browser(mem, selftest, timeout, t0)


class _JanelaFalhou(RuntimeError):
    pass


def _correr_janela(api: Api, servidor: ServidorUI, selftest: bool, timeout: float, t0: float) -> int:
    try:
        import webview
    except Exception as erro:
        raise _JanelaFalhou(t("jan.pywebview", erro=erro)) from erro

    gui = None
    if os.name == "nt":
        gui = "edgechromium"
        try:
            from webview.platforms import winforms

            if getattr(winforms, "renderer", "") != "edgechromium":
                raise _JanelaFalhou(t("jan.renderer", renderer=winforms.renderer))
        except _JanelaFalhou:
            raise
        except Exception as erro:
            raise _JanelaFalhou(t("jan.winforms", erro=erro)) from erro

    escuro = tema_escuro()
    janela = webview.create_window(
        "Agent Memory",
        url=servidor.url(),
        js_api=api,
        width=1280,
        height=820,
        min_size=(820, 560),
        background_color="#16191c" if escuro else "#f3f4f2",
        text_select=True,
    )
    resultado = {"codigo": 0}

    def vigiar() -> None:
        if not api._pronto.wait(timeout):
            _info(t("jan.sem_resposta", s=f"{timeout:.0f}"))
            resultado["codigo"] = 1
        else:
            info = api._info_pronto
            total_ms = (time.perf_counter() - t0) * 1000
            if info.get("erro"):
                _info(t("jan.erro_ui", erro=info["erro"]))
                resultado["codigo"] = 1
            else:
                _info(
                    t(
                        "jan.ok",
                        nos=info.get("nos", "?"),
                        ms=info.get("ms", "?"),
                        via=info.get("via", "?"),
                        ponte=info.get("ponte", "?"),
                        grafo=info.get("grafo", "?"),
                        total=f"{total_ms:.0f}",
                    )
                )
        time.sleep(0.2)
        janela.destroy()

    try:
        if selftest:
            webview.start(vigiar, gui=gui, private_mode=True)
        else:
            webview.start(gui=gui, private_mode=True)
    except Exception as erro:
        if api._pronto.is_set():
            return resultado["codigo"]
        raise _JanelaFalhou(t("jan.nao_arrancou", erro=erro)) from erro
    return resultado["codigo"]


def _correr_browser(mem: Memoria, selftest: bool, timeout: float, t0: float) -> int:
    api = Api(mem, modo="browser", selftest=selftest)
    servidor = ServidorUI(api)
    servidor.csp = True
    servidor.iniciar()
    url = servidor.url()
    try:
        # O URL leva a chave desta sessão (como o Jupyter): é local e só vale enquanto
        # este processo corre. Mostramo-lo sempre, para se poder abrir noutro browser.
        aberto = webbrowser.open(url)
        _info(t("jan.browser_url", url=url))
        _info(t("jan.browser_aberto") if aberto else t("jan.browser_abre"))
        if selftest:
            if api._pronto.wait(timeout) and not api._info_pronto.get("erro"):
                _info(t("jan.browser_ok", ms=api._info_pronto.get("ms", "?")))
                return 0
            _info(t("jan.browser_falhou"))
            return 1
        inicio = time.monotonic()
        while True:
            time.sleep(2)
            agora = time.monotonic()
            ultimo = api._ultimo_batimento
            if ultimo and agora - ultimo > LIMITE_SEM_BATIMENTO:
                break
            if not ultimo and agora - inicio > LIMITE_PRIMEIRO_BATIMENTO:
                break
    except KeyboardInterrupt:
        pass
    finally:
        servidor.parar()
    return 0


__all__ = ["correr", "versao_webview2", "janela_disponivel"]
