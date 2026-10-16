"""Deteção do WebView2 (só estática fora do Windows) e recurso ao browser."""

from memoria import window


class Chave:
    def __init__(self, valor):
        self.valor = valor

    def __enter__(self):
        return self.valor

    def __exit__(self, *a):
        return False


class Registo:
    """Imita o módulo winreg com um dicionário {(raiz, caminho): pv}."""

    HKEY_LOCAL_MACHINE = "HKEY_LOCAL_MACHINE"
    HKEY_CURRENT_USER = "HKEY_CURRENT_USER"

    def __init__(self, valores):
        self.valores = valores
        self.lidos = []

    def OpenKey(self, raiz, caminho):  # noqa: N802
        self.lidos.append((raiz, caminho))
        if (raiz, caminho) not in self.valores:
            raise OSError("não existe")
        return Chave(self.valores[(raiz, caminho)])

    def QueryValueEx(self, valor, nome):  # noqa: N802
        assert nome == "pv"
        return valor, 1


HKLM = ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
HKCU = ("HKEY_CURRENT_USER", r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")


def test_webview2_por_maquina():
    assert window.versao_webview2(Registo({HKLM: "130.0.2849.80"})) == "130.0.2849.80"


def test_webview2_por_utilizador():
    reg = Registo({HKCU: "131.0.1.0"})
    assert window.versao_webview2(reg) == "131.0.1.0"
    assert reg.lidos[:2] == [HKLM, HKCU]


def test_webview2_em_falta_ou_zerado():
    assert window.versao_webview2(Registo({})) is None
    assert window.versao_webview2(Registo({HKLM: "0.0.0.0", HKCU: ""})) is None


def test_sem_janela_usa_browser(monkeypatch, home):
    chamadas = []
    monkeypatch.setattr(window, "janela_disponivel", lambda: (False, "O WebView2 Runtime não está instalado."))
    monkeypatch.setattr(window, "_correr_browser", lambda mem, selftest, timeout, t0: chamadas.append(selftest) or 0)
    monkeypatch.setattr(window, "pasta_ui", lambda: _ui_falsa(home))
    assert window.correr() == 0
    assert chamadas == [False]
    # No selftest --gui, a falta da janela é uma falha (código 3), não um recurso silencioso.
    assert window.correr(selftest=True) == 3


def test_janela_que_falha_cai_no_browser(monkeypatch, home):
    chamadas = []

    def falha(*a, **k):
        raise window._JanelaFalhou("a janela não arrancou")

    monkeypatch.setattr(window, "janela_disponivel", lambda: (True, "teste"))
    monkeypatch.setattr(window, "_correr_janela", falha)
    monkeypatch.setattr(window, "_correr_browser", lambda mem, selftest, timeout, t0: chamadas.append(True) or 0)
    monkeypatch.setattr(window, "pasta_ui", lambda: _ui_falsa(home))
    assert window.correr() == 0 and chamadas == [True]


def _ui_falsa(home):
    pasta = home.parent / "ui-falsa"
    pasta.mkdir(exist_ok=True)
    (pasta / "index.html").write_text("<!doctype html>")
    return pasta
