"""Editar o ficheiro de uma memória dentro da app (sem editor externo)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria.service import Memoria
from memoria.webui import METODOS, Api


@pytest.fixture
def api(mem: Memoria) -> Api:
    return Api(mem)


def _nova(mem: Memoria) -> dict:
    return mem.adicionar(tipo="licao", titulo="Usar cache", texto="O build fica mais rápido.", projeto="loja")


def test_metodos_expostos():
    assert {"ficheiro", "guardar_ficheiro"} <= METODOS


def test_ler_devolve_o_markdown_do_disco(mem: Memoria, api: Api):
    r = _nova(mem)
    f = api.ficheiro(r["id"])
    assert f["id"] == r["id"]
    assert f["nome"] == Path(r["caminho"]).name
    assert f["texto"] == Path(r["caminho"]).read_text("utf-8")
    assert f["texto"].startswith("---\ntipo: licao\n")
    assert f["versao"]


def test_guardar_grava_e_reindexa(mem: Memoria, api: Api):
    r = _nova(mem)
    f = api.ficheiro(r["id"])
    texto = f["texto"].replace("titulo: Usar cache", "titulo: Usar cache no CI").replace(
        "O build fica mais rápido.", "O build fica mais rápido com cache partilhada."
    )
    g = api.guardar_ficheiro(r["id"], texto, f["versao"])
    assert g == {"id": r["id"], "redigidos": 0, "versao": g["versao"]}
    assert Path(r["caminho"]).read_text("utf-8") == texto
    assert mem.nota(r["id"])["titulo"] == "Usar cache no CI"
    assert [m["id"] for m in mem.procurar("partilhada")] == [r["id"]]
    # Sem ficheiros temporários esquecidos na pasta.
    assert sorted(p.name for p in Path(r["caminho"]).parent.iterdir()) == [Path(r["caminho"]).name]


def test_guardar_redige_segredos(mem: Memoria, api: Api):
    r = _nova(mem)
    f = api.ficheiro(r["id"])
    g = api.guardar_ficheiro(r["id"], f["texto"] + "\nChave sk-ant-api03-ABCDEFGHIJKLMNOPQRST\n", f["versao"])
    assert g["redigidos"] == 1
    gravado = Path(r["caminho"]).read_text("utf-8")
    assert "sk-ant-" not in gravado and "[REDIGIDO:" in gravado


@pytest.mark.parametrize(
    "estragar,mensagem",
    [
        (lambda t: t.replace("---\n", "", 1), "cabeçalho"),
        (lambda t: t.replace("tipo: licao", "tipo: [aberto"), "YAML"),
        (lambda t: t.replace("tipo: licao", "tipo: ideia"), "Tipo inválido"),
        (lambda t: t.replace("titulo: Usar cache", "titulo: ''"), "titulo"),
    ],
)
def test_guardar_recusa_cabecalho_invalido_e_nao_mexe(mem: Memoria, api: Api, estragar, mensagem):
    r = _nova(mem)
    f = api.ficheiro(r["id"])
    with pytest.raises(ValueError, match=mensagem):
        api.guardar_ficheiro(r["id"], estragar(f["texto"]), f["versao"])
    assert Path(r["caminho"]).read_text("utf-8") == f["texto"]


def test_guardar_nao_escreve_por_cima_de_outra_edicao(mem: Memoria, api: Api):
    r = _nova(mem)
    f = api.ficheiro(r["id"])
    caminho = Path(r["caminho"])
    caminho.write_text(f["texto"] + "\nEscrito pelo Claude Code.\n", "utf-8")
    os.utime(caminho, ns=(caminho.stat().st_atime_ns, caminho.stat().st_mtime_ns + 5_000_000))
    with pytest.raises(ValueError, match="mudou no disco"):
        api.guardar_ficheiro(r["id"], f["texto"] + "\nA minha versão.\n", f["versao"])
    assert "Escrito pelo Claude Code." in caminho.read_text("utf-8")


def test_guardar_so_dentro_da_pasta(mem: Memoria, api: Api):
    with pytest.raises(LookupError):
        api.ficheiro("/etc/passwd")
    with pytest.raises(LookupError):
        api.guardar_ficheiro("../../etc/passwd", "---\ntipo: licao\ntitulo: x\n---\n", None)


def test_guardar_normaliza_fins_de_linha(mem: Memoria, api: Api):
    r = _nova(mem)
    f = api.ficheiro(r["id"])
    api.guardar_ficheiro(r["id"], f["texto"].rstrip("\n").replace("\n", "\r\n"), f["versao"])
    gravado = Path(r["caminho"]).read_bytes()
    assert b"\r\n" not in gravado and gravado.endswith(b"\n")
