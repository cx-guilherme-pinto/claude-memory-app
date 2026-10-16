import http.client
import json
from pathlib import Path

import pytest

from memoria import webui
from memoria.service import Memoria
from memoria.webui import Api, ServidorUI


@pytest.fixture
def raiz_ui(tmp_path: Path) -> Path:
    raiz = tmp_path / "ui"
    (raiz / "assets").mkdir(parents=True)
    (raiz / "index.html").write_text("<!doctype html><title>Memória</title>", "utf-8")
    (raiz / "assets" / "a.js").write_text("console.log(1)", "utf-8")
    return raiz


@pytest.fixture
def servidor(mem: Memoria, raiz_ui: Path):
    s = ServidorUI(Api(mem, modo="browser"), raiz=raiz_ui)
    s.csp = True
    s.iniciar()
    yield s
    s.parar()


def _pedido(s: ServidorUI, metodo: str, caminho: str, corpo=None, token: str | None = None, host: str | None = None):
    c = http.client.HTTPConnection("127.0.0.1", s.porta, timeout=10)
    cab = {"Host": host or f"127.0.0.1:{s.porta}"}
    if token is not None:
        cab["X-Memoria-Token"] = token
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    c.request(metodo, caminho, body=dados, headers=cab)
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read()


def test_estaticos_e_cabecalhos(servidor):
    estado, cab, corpo = _pedido(servidor, "GET", "/")
    assert estado == 200 and b"Mem" in corpo
    assert "default-src 'self'" in cab["Content-Security-Policy"]
    assert cab["X-Content-Type-Options"] == "nosniff"
    estado, cab, _ = _pedido(servidor, "GET", "/assets/a.js")
    assert estado == 200 and cab["Content-Type"].startswith("text/javascript")


def test_sem_fuga_de_pasta(servidor):
    for caminho in ("/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd", "/assets/../../x"):
        estado, _, _ = _pedido(servidor, "GET", caminho)
        assert estado == 404


def test_api_exige_token_e_host(servidor):
    assert _pedido(servidor, "POST", "/api/inicio", {"args": []})[0] == 403
    assert _pedido(servidor, "POST", "/api/inicio", {"args": []}, token="errado")[0] == 403
    assert _pedido(servidor, "POST", "/api/inicio", {"args": []}, token=servidor.token, host="malicioso.pt")[0] == 403
    estado, _, corpo = _pedido(servidor, "POST", "/api/inicio", {"args": []}, token=servidor.token)
    assert estado == 200 and json.loads(corpo)["resultado"]["modo"] == "browser"
    assert _pedido(servidor, "POST", "/api/_mem", {"args": []}, token=servidor.token)[0] == 404


def test_api_fluxo_completo(servidor):
    t = servidor.token
    estado, _, corpo = _pedido(
        servidor,
        "POST",
        "/api/adicionar",
        {"args": [{"tipo": "licao", "titulo": "", "texto": "Primeira linha\nresto", "projeto": "p", "ligacoes": "a, b"}]},
        token=t,
    )
    assert estado == 200
    novo = json.loads(corpo)["resultado"]
    assert novo["id"].startswith("p/") and novo["id"].endswith("primeira-linha")
    grafo = json.loads(_pedido(servidor, "POST", "/api/grafo", {"args": []}, token=t)[2])["resultado"]
    assert grafo["total"] == 1
    achados = json.loads(_pedido(servidor, "POST", "/api/procurar", {"args": ["primeira"]}, token=t)[2])["resultado"]
    assert achados["ids"] == [novo["id"]] and achados["memorias"][0]["id"] == novo["id"]
    nota = json.loads(_pedido(servidor, "POST", "/api/nota", {"args": [novo["id"]]}, token=t)[2])["resultado"]
    assert nota["corpo"].startswith("Primeira linha") and nota["relacionadas"] == []
    estado, _, corpo = _pedido(servidor, "POST", "/api/nota", {"args": ["nada"]}, token=t)
    assert estado == 400 and "não encontrada" in json.loads(corpo)["erro"]


def test_abrir_ficheiro_so_dentro_da_pasta(mem: Memoria, monkeypatch):
    abertos = []
    monkeypatch.setattr(webui, "abrir_com_sistema", lambda caminho: abertos.append(caminho))
    api = Api(mem)
    r = mem.adicionar(tipo="licao", titulo="Abrir", texto="x", projeto="p")
    assert api.abrir_ficheiro(r["id"]) is True
    assert abertos == [Path(r["caminho"]).resolve()]
    with pytest.raises(LookupError):
        api.abrir_ficheiro("/etc/passwd")


def test_abrir_url_so_http(mem: Memoria, monkeypatch):
    abertos = []
    monkeypatch.setattr("webbrowser.open", lambda url: abertos.append(url) or True)
    api = Api(mem)
    assert api.abrir_url("https://exemplo.pt") is True
    for mau in ("javascript:alert(1)", "file:///etc/passwd", "memoria://x"):
        with pytest.raises(ValueError):
            api.abrir_url(mau)
    assert abertos == ["https://exemplo.pt"]


def test_atributos_privados_nao_expostos(mem: Memoria):
    publicos = {n for n in dir(Api(mem)) if not n.startswith("_")}
    assert publicos == webui.METODOS


def test_ui_incluida_no_pacote():
    assert (webui.pasta_ui() / "index.html").is_file(), "corre scripts/build.sh (ou vite build) antes dos testes"
