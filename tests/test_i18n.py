"""Línguas: deteção, preferência guardada, catálogos completos e mensagens traduzidas."""

import asyncio
import json
import locale
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from memoria import i18n
from memoria.cli import main
from memoria.mensagens import MENSAGENS

RAIZ = Path(__file__).resolve().parents[1]
LOCALES = RAIZ / "web" / "src" / "locales"
MARCADOR = re.compile(r"\{(\w+)\}")


@pytest.fixture
def sem_env(monkeypatch):
    monkeypatch.delenv("AGENT_MEMORY_LANG", raising=False)
    monkeypatch.delenv("MEMORIA_LANG", raising=False)
    i18n.repor()
    yield
    i18n.repor()


@pytest.mark.parametrize(
    "codigo,esperado",
    [
        ("pt-PT", "pt"),
        ("pt_BR.UTF-8", "pt"),
        ("en-US", "en"),
        ("he-IL", "he"),
        ("iw", "he"),
        ("hi_IN", "hi"),
        ("HI", "hi"),
        ("fr-FR", None),
        ("", None),
        (None, None),
    ],
)
def test_normalizar(codigo, esperado):
    assert i18n.normalizar(codigo) == esperado


def test_macos_applelanguages(monkeypatch, sem_env):
    saida = '(\n    "fr-FR",\n    "he-IL",\n    "en-US"\n)\n'
    monkeypatch.setattr(i18n.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=saida, returncode=0))
    monkeypatch.setattr(i18n, "sys", SimpleNamespace(platform="darwin"))
    # A primeira suportada na ordem do sistema: o francês salta, o hebraico ganha.
    assert i18n._preferidas_macos() == ["fr-FR", "he-IL", "en-US"]
    assert i18n.lingua_sistema() == "he"


def test_windows_codigos_da_interface():
    # GetUserDefaultUILanguage devolve um LANGID; o locale do Python traduz para o nome.
    assert i18n.normalizar(locale.windows_locale[0x040D]) == "he"  # he_IL
    assert i18n.normalizar(locale.windows_locale[0x0439]) == "hi"  # hi_IN
    assert i18n.normalizar(locale.windows_locale[0x0816]) == "pt"  # pt_PT
    assert i18n.normalizar(locale.windows_locale[0x0416]) == "pt"  # pt_BR
    assert i18n.normalizar(locale.windows_locale[0x0409]) == "en"  # en_US


def test_windows_usa_a_lingua_da_interface(monkeypatch, sem_env):
    monkeypatch.setattr(i18n, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(i18n, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(i18n, "_preferidas_windows", lambda: ["hi_IN"])
    assert i18n.lingua_sistema() == "hi"


def test_linux_e_reserva_ingles(monkeypatch, sem_env):
    monkeypatch.setattr(i18n, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(i18n, "os", SimpleNamespace(name="posix", environ={"LANG": "de_DE.UTF-8"}))
    assert i18n.lingua_sistema() == "en"  # alemão não é suportado → inglês
    i18n.lingua_sistema.cache_clear()
    monkeypatch.setattr(i18n, "os", SimpleNamespace(name="posix", environ={"LANGUAGE": "de:pt_PT", "LANG": "C"}))
    assert i18n.lingua_sistema() == "pt"


def test_precedencia_env_guardada_sistema(monkeypatch, home, sem_env):
    monkeypatch.setattr(i18n, "lingua_sistema", lambda: "hi")
    assert i18n.lingua() == "hi"
    i18n.definir_lingua("he")
    i18n.repor()
    monkeypatch.setattr(i18n, "lingua_sistema", lambda: "hi")
    assert i18n.lingua() == "he"  # a escolha guardada ganha ao sistema
    dados = json.loads((home / "preferences.json").read_text("utf-8"))
    assert dados == {"language": "he"}
    assert not (home / "preferencias.json").exists()
    monkeypatch.setenv("MEMORIA_LANG", "en")
    i18n.repor()
    assert i18n.lingua() == "en"  # a variável de ambiente (mesmo a antiga) ganha a tudo
    monkeypatch.setenv("AGENT_MEMORY_LANG", "hi")
    i18n.repor()
    assert i18n.lingua() == "hi"  # o nome novo ganha ao antigo


def test_le_a_escolha_guardada_pela_v04(home, sem_env, monkeypatch):
    monkeypatch.setattr(i18n, "lingua_sistema", lambda: "en")
    home.mkdir(parents=True, exist_ok=True)
    (home / "preferencias.json").write_text('{"lingua": "he"}', "utf-8")
    assert i18n.lingua() == "he"
    # O ficheiro novo, quando existe, ganha ao antigo.
    (home / "preferences.json").write_text('{"language": "pt"}', "utf-8")
    i18n.repor()
    monkeypatch.setattr(i18n, "lingua_sistema", lambda: "en")
    assert i18n.lingua() == "pt"


def test_definir_lingua_invalida(sem_env, home):
    with pytest.raises(ValueError):
        i18n.definir_lingua("fr")
    assert not (home / "preferences.json").exists()


def test_preferencias_mantem_outras_chaves(home, sem_env):
    home.mkdir(parents=True, exist_ok=True)
    (home / "preferencias.json").write_text('{"outra": 1, "lingua": "he"}', "utf-8")
    i18n.definir_lingua("pt")
    assert json.loads((home / "preferences.json").read_text("utf-8")) == {"outra": 1, "language": "pt"}
    assert json.loads((home / "preferencias.json").read_text("utf-8")) == {"outra": 1, "lingua": "he"}  # intacto
    i18n.definir_lingua("en")
    assert json.loads((home / "preferences.json").read_text("utf-8")) == {"outra": 1, "language": "en"}


# ------------------------------------------------------------------ catálogos
def test_mensagens_python_completas():
    for chave, entrada in MENSAGENS.items():
        assert set(entrada) == set(i18n.LINGUAS), chave
        base = set(MARCADOR.findall(entrada["pt"]))
        for lingua, texto in entrada.items():
            assert texto.strip(), (chave, lingua)
            assert set(MARCADOR.findall(texto)) == base, (chave, lingua)


def test_mensagens_usadas_existem():
    """Cada t("chave") no código tem entrada no catálogo."""
    usadas = set()
    for f in (RAIZ / "src" / "memoria").glob("*.py"):
        usadas |= set(re.findall(r"""\bt\(\s*["']([\w.]+)["']""", f.read_text("utf-8")))
    assert usadas, "nenhuma chave encontrada"
    assert usadas - set(MENSAGENS) == set()


def _marcadores(valor) -> set[str]:
    if isinstance(valor, dict):
        # Nas formas do plural, o {n} pode faltar (ex.: "זיכרון אחד" = "uma memória").
        return set().union(*(MARCADOR.findall(v) for v in valor.values())) - {"n"}
    return set(MARCADOR.findall(valor))


def test_catalogos_web_completos():
    catalogos = {lingua: json.loads((LOCALES / f"{lingua}.json").read_text("utf-8")) for lingua in i18n.LINGUAS}
    base = catalogos["pt"]
    for lingua, catalogo in catalogos.items():
        assert set(catalogo) == set(base), (lingua, set(catalogo) ^ set(base))
        for chave, valor in catalogo.items():
            assert type(valor) is type(base[chave]), (lingua, chave)
            if isinstance(valor, dict):
                assert {"one", "other"} <= set(valor), (lingua, chave)
            assert _marcadores(valor) == _marcadores(base[chave]), (lingua, chave)


def test_chaves_web_usadas_existem():
    base = json.loads((LOCALES / "pt.json").read_text("utf-8"))
    usadas = set()
    for f in (RAIZ / "web" / "src").glob("*.js*"):
        if f.name == "i18n.jsx":  # o próprio módulo só tem exemplos nos comentários
            continue
        usadas |= set(re.findall(r"""\btx?\(\s*'([\w.]+)'""", f.read_text("utf-8")))
    dinamicas = {f"tipo.{t}" for t in ("licao", "fazer", "nao_fazer", "historico", "projeto", "epico", "tarefa", "ficheiro")}
    dinamicas |= {f"motivo.{m}" for m in ("ligacao", "tarefa", "epico", "projeto", "ficheiro")}
    dinamicas |= {"vista.mapa", "vista.atividade"}
    dinamicas |= {f"ferramenta.memory_{f}" for f in ("search", "related", "add")}
    periodos = ("tudo", "7", "30", "90", "365")
    dinamicas |= {f"periodo.{p}" for p in periodos} | {f"periodo.{p}.curto" for p in periodos}
    assert usadas, "nenhuma chave encontrada"
    assert (usadas | dinamicas) - set(base) == set()
    assert set(base) - usadas - dinamicas == set(), "chaves que ninguém usa"


# ---------------------------------------------------------- mensagens na CLI
@pytest.mark.parametrize(
    "lingua,trecho",
    [("pt", "Tipo inválido"), ("en", "Invalid type"), ("hi", "इनवैलिड टाइप"), ("he", "סוג לא תקין")],
)
def test_erros_na_lingua(monkeypatch, capsys, lingua, trecho):
    monkeypatch.setenv("AGENT_MEMORY_LANG", lingua)
    i18n.repor()
    assert main(["add", "--type", "ideia", "--project", "p", "--text", "x"]) == 1
    assert trecho in capsys.readouterr().err


def test_comando_lingua(monkeypatch, capsys, home, sem_env):
    monkeypatch.setattr(i18n, "lingua_sistema", lambda: "pt")
    assert main(["language", "he"]) == 0
    assert "עברית (he)" in capsys.readouterr().out
    i18n.repor()
    monkeypatch.setattr(i18n, "lingua_sistema", lambda: "pt")
    assert main(["language"]) == 0
    assert "שפה: עברית (he)" in capsys.readouterr().out


def test_selftest_mostra_a_lingua(monkeypatch, capsys):
    # O setup do kit pede o selftest em inglês com a variável antiga (MEMORIA_LANG=en).
    monkeypatch.delenv("AGENT_MEMORY_LANG")
    monkeypatch.setenv("MEMORIA_LANG", "en")
    i18n.repor()
    assert main(["selftest"]) == 0
    saida = capsys.readouterr().out
    assert "Language: English (en)" in saida and "selftest: OK" in saida and "Secret redaction" in saida
    assert saida.startswith("Agent Memory ")
    # Em inglês, nem uma palavra portuguesa.
    assert not re.search(r"memória|memoria|falhou|pasta|língua|[ãõçáéíóú]", saida, re.I), saida


def test_mcp_em_ingles_em_qualquer_lingua(monkeypatch, mem):
    """As descrições das ferramentas são para o modelo: sempre em inglês."""
    from mcp import Client

    from memoria.mcp_server import INSTRUCOES, criar_servidor

    monkeypatch.setenv("AGENT_MEMORY_LANG", "he")
    i18n.repor()

    async def ferramentas():
        async with Client(criar_servidor(mem)) as c:
            return (await c.list_tools()).tools

    textos = [INSTRUCOES]
    for f in asyncio.run(ferramentas()):
        textos.append(f.description)
        textos += [p.get("description", "") for p in f.input_schema["properties"].values()]
    for texto in textos:
        assert texto.isascii(), texto
        # Desde a v0.5, também os nomes (parâmetros, tipos) são ingleses.
        assert not re.search(r"\b(memórias|ligação|Procura|Guarda|projeto atual|Só deste)\b", texto), texto
        assert not re.search(r"memoria_|licao|fazer|historico|tarefa|epico|projeto|texto|titulo", texto), texto


def test_pagina_traz_lingua_e_direcao(monkeypatch, mem, tmp_path):
    import http.client

    from memoria.webui import Api, ServidorUI

    raiz = tmp_path / "ui"
    raiz.mkdir()
    (raiz / "index.html").write_text('<!doctype html><html lang="pt-PT"><head><title>M</title></head></html>', "utf-8")
    monkeypatch.setenv("AGENT_MEMORY_LANG", "he")
    i18n.repor()
    s = ServidorUI(Api(mem, modo="janela"), raiz=raiz).iniciar()
    try:
        c = http.client.HTTPConnection("127.0.0.1", s.porta, timeout=10)
        c.request("GET", "/", headers={"Host": f"127.0.0.1:{s.porta}"})
        corpo = c.getresponse().read().decode("utf-8")
        assert '<html lang="he" dir="rtl">' in corpo
        assert '<meta name="memoria-lingua" content="he">' in corpo
        # Sem sessão, a página explicativa também vem em hebraico e RTL.
        s.modo = "browser"
        c = http.client.HTTPConnection("127.0.0.1", s.porta, timeout=10)
        c.request("GET", "/", headers={"Host": f"127.0.0.1:{s.porta}"})
        corpo = c.getresponse().read().decode("utf-8")
        assert 'dir="rtl"' in corpo and "הפעלה ללא מפתח" in corpo
    finally:
        s.parar()


def test_api_definir_lingua(mem, home, sem_env):
    from memoria.webui import Api

    api = Api(mem)
    info = api.definir_lingua("hi")
    assert info["lingua"] == "hi" and info["direcao"] == "ltr"
    assert api.inicio()["lingua"] == "hi"
    assert {lng["codigo"] for lng in info["linguas"]} == {"pt", "en", "hi", "he"}
    assert json.loads((home / "preferences.json").read_text("utf-8"))["language"] == "hi"
    with pytest.raises(ValueError):
        api.definir_lingua("xx")


def test_preferencias_estragadas_sao_ignoradas(home, sem_env, monkeypatch):
    monkeypatch.setattr(i18n, "lingua_sistema", lambda: "en")
    home.mkdir(parents=True, exist_ok=True)
    (home / "preferences.json").write_text("{nao e json", "utf-8")
    (home / "preferencias.json").write_text('["lista"]', "utf-8")
    assert i18n.lingua() == "en"
    i18n.definir_lingua("he")
    assert json.loads((home / "preferences.json").read_text("utf-8")) == {"language": "he"}
