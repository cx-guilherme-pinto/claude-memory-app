"""Ambientes estragados (teste de caos do workshop): índice corrompido ou preso, notas editadas à mão,
ficheiros estranhos na pasta, entradas MCP estranhas, hindi e japonês. Nada pode prender, partir a UI
ou apagar notas; quando falha, falha com uma linha que diz o que fazer."""

from __future__ import annotations

import asyncio
import io
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

import pytest
from mcp import Client

from memoria import index, service, store
from memoria.cli import main
from memoria.index import Indice
from memoria.mcp_server import criar_servidor, linha_limpa
from memoria.redact import redigir
from memoria.registo import Registo
from memoria.service import Memoria
from memoria.webui import Api

POSIX = os.name != "nt"


def _notas(mem: Memoria, n: int = 3, projeto: str = "arena") -> list[dict]:
    return [
        mem.adicionar(tipo="licao", titulo=f"Cache do build {i}", texto=f"Usar cache no build {i}.", projeto=projeto)
        for i in range(n)
    ]


def _ficheiro_indice(home: Path) -> Path:
    return home / ".index" / index.NOME_FICHEIRO


def _fechar_wal(caminho: Path) -> None:
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()


def _strict(dados) -> str:
    return json.dumps(dados, allow_nan=False)


def _mds(home: Path) -> list[Path]:
    return sorted(home.glob("*/*.md"))


# ------------------------------------------------------------ índice corrompido
@pytest.mark.parametrize("estrago", ["lixo", "cortado"])
def test_indice_corrompido_refaz_se_sozinho(mem: Memoria, home: Path, capsys, estrago):
    _notas(mem)
    f = _ficheiro_indice(home)
    _fechar_wal(f)
    if estrago == "lixo":
        f.write_bytes(b"isto nao e um sqlite" * 200)
    else:
        f.write_bytes(f.read_bytes()[:5000])
    nova = Memoria(home)
    achados = nova.procurar("cache")
    assert len(achados) == 3
    assert "refeito" in capsys.readouterr().err
    assert f.with_name(f.name + ".corrupt").is_file()  # o estragado fica ao lado, para quem quiser ver
    assert len(_mds(home)) == 3  # as notas nunca mudam


def test_indice_com_tabela_estragada_reindex_e_pesquisa(mem: Memoria, home: Path, capsys):
    """Só a página raiz da tabela notas estragada: o ficheiro abre, mas o SELECT e o DROP falham."""
    _notas(mem, 5)
    f = _ficheiro_indice(home)
    _fechar_wal(f)
    con = sqlite3.connect(f)
    raiz = con.execute("SELECT rootpage FROM sqlite_master WHERE name='notas'").fetchone()[0]
    pagina = con.execute("PRAGMA page_size").fetchone()[0]
    con.close()
    with open(f, "r+b") as fh:
        fh.seek((raiz - 1) * pagina)
        fh.write(b"\xff" * pagina)
    assert main(["reindex"]) == 0
    assert len(Memoria(home).procurar("cache")) == 5
    # E sem reindex: a pesquisa refaz o índice sozinha.
    _fechar_wal(f)
    with open(f, "r+b") as fh:
        fh.seek((raiz - 1) * pagina)
        fh.write(b"\xff" * pagina)
    capsys.readouterr()
    assert len(Memoria(home).procurar("cache")) == 5
    assert "refeito" in capsys.readouterr().err


def test_indice_que_nao_se_pode_refazer_da_uma_linha(mem: Memoria, home: Path, capsys, monkeypatch):
    """No Windows, um ficheiro aberto noutro processo não sai: mensagem clara, sem traceback."""
    _notas(mem)
    f = _ficheiro_indice(home)
    _fechar_wal(f)
    f.write_bytes(b"lixo" * 1000)
    monkeypatch.setattr(Indice, "_tirar_ficheiros", lambda self: False)
    capsys.readouterr()
    assert main(["search", "cache"]) == 1
    erro = capsys.readouterr().err
    assert "agent-memory reindex" in erro and "Traceback" not in erro and len(erro.strip().splitlines()) == 1
    # O MCP diz o mesmo ao modelo, e um memory_add continua a gravar (e diz que gravou).
    async def principal():
        async with Client(criar_servidor(Memoria(home))) as c:
            p = await c.call_tool("memory_search", {"text": "cache"})
            a = await c.call_tool("memory_add", {"type": "lesson", "title": "Gravada", "text": "x", "project": "arena"})
            return p, a

    p, a = asyncio.run(principal())
    assert p.is_error and "agent-memory reindex" in p.content[0].text
    assert not a.is_error and Path(a.content[0].text).is_file()
    assert len(_mds(home)) == 4
    # O selftest falha (o setup mostra o E-MEM-05) e diz o que fazer.
    from memoria import selftest

    assert selftest._indice_real(home) is False
    assert "agent-memory reindex" in capsys.readouterr().out


def test_selftest_abre_o_indice_real(mem: Memoria, home: Path, capsys):
    _notas(mem, 2)
    from memoria import selftest

    f = _ficheiro_indice(home)
    _fechar_wal(f)
    f.write_bytes(b"lixo" * 1000)
    assert selftest._indice_real(home) is True  # refeito
    assert "(2 " in capsys.readouterr().out


def test_registo_corrompido_volta_a_funcionar(home: Path):
    r = Registo(home)
    r.gravar("memory_search", texto="a")
    r.caminho.write_bytes(b"lixo" * 1000)
    for sufixo in ("-wal", "-shm"):
        r.caminho.with_name(r.caminho.name + sufixo).unlink(missing_ok=True)
    assert r.resumo()["total"] == 0
    r.gravar("memory_search", texto="b")
    assert r.resumo()["total"] == 1


# ------------------------------------------------------------- índice preso
def test_lock_de_outro_processo_nao_parte_pesquisa_nem_add(mem: Memoria, home: Path, monkeypatch):
    monkeypatch.setattr(index, "ESPERA", 1.0)
    monkeypatch.setattr(service, "ESPERA_CURTA", 0.5)
    _notas(mem, 2)
    outro = sqlite3.connect(_ficheiro_indice(home), isolation_level=None)
    outro.execute("BEGIN IMMEDIATE")  # outro processo a meio de uma escrita
    try:
        nova = Memoria(home)
        inicio = time.perf_counter()
        assert len(nova.procurar("cache")) == 2  # lê o índice atual, sem esperar pelo lock
        assert time.perf_counter() - inicio < 1.5
        r = nova.adicionar(tipo="fazer", titulo="Durante o lock", texto="ok", projeto="arena")
        assert Path(r["caminho"]).is_file()
    finally:
        outro.execute("ROLLBACK")
        outro.close()
    assert len(_mds(home)) == 3  # sem duplicados
    time.sleep(0.01)
    assert [x["titulo"] for x in Memoria(home).procurar("lock")] == ["Durante o lock"]


def test_lock_exclusivo_da_uma_linha_na_cli(mem: Memoria, home: Path, capsys, monkeypatch):
    monkeypatch.setattr(index, "ESPERA", 0.3)
    monkeypatch.setattr(service, "ESPERA_CURTA", 0.3)
    _notas(mem, 1)
    outro = sqlite3.connect(_ficheiro_indice(home), isolation_level=None)
    outro.execute("PRAGMA locking_mode=EXCLUSIVE")
    outro.execute("BEGIN EXCLUSIVE")
    outro.execute("DELETE FROM contexto")
    try:
        capsys.readouterr()
        assert main(["search", "cache"]) == 1
    finally:
        outro.execute("ROLLBACK")
        outro.close()
    erro = capsys.readouterr().err
    assert "ocupado" in erro and "Traceback" not in erro


def test_reindex_numa_so_transacao(mem: Memoria, home: Path, monkeypatch):
    """Durante um reindex (lento, ou parado com Ctrl+Z), os outros continuam a ver o índice."""
    _notas(mem, 4)
    dentro = threading.Event()
    continuar = threading.Event()
    original = store.listar_ficheiros

    def devagar(home_, problemas=None):
        dentro.set()
        continuar.wait(10)
        yield from original(home_, problemas)

    monkeypatch.setattr(store, "listar_ficheiros", devagar)
    t = threading.Thread(target=Memoria(home).reindexar)
    t.start()
    try:
        assert dentro.wait(10)
        leitor = sqlite3.connect(_ficheiro_indice(home))
        assert leitor.execute("SELECT count(*) FROM notas").fetchone()[0] == 4
        leitor.close()
    finally:
        continuar.set()
        t.join(10)
    monkeypatch.setattr(store, "listar_ficheiros", original)
    assert len(Memoria(home).procurar("cache")) == 4


def test_esquema_so_e_criado_uma_vez(mem: Memoria, home: Path, monkeypatch):
    """Ligar a um índice que já existe não escreve nada (não precisa do lock de escrita)."""
    _notas(mem, 1)
    instrucoes: list[str] = []
    ligar = sqlite3.connect

    def com_registo(*args, **kwargs):
        con = ligar(*args, **kwargs)
        con.set_trace_callback(instrucoes.append)
        return con

    monkeypatch.setattr(index.sqlite3, "connect", com_registo)
    with Indice(home).ligar() as con:
        con.execute("SELECT count(*) FROM notas").fetchone()
    assert instrucoes and not [s for s in instrucoes if s.lstrip().upper().startswith(("INSERT", "CREATE", "DROP", "BEGIN"))]


# ------------------------------------------------------------ notas à mão
def _nota_manual(home: Path, nome: str, cabecalho: str, corpo: str = "Corpo.", projeto: str = "arena") -> Path:
    pasta = home / projeto
    pasta.mkdir(parents=True, exist_ok=True)
    f = pasta / nome
    f.write_text(f"---\n{cabecalho}\n---\n\n{corpo}\n", "utf-8")
    return f


def test_custo_infinito_nao_parte_o_json(mem: Memoria, home: Path):
    limpa = mem.adicionar(tipo="licao", titulo="Nota valida", texto="ok", projeto="arena")
    _nota_manual(home, "2026-10-01-inf.md", "type: lesson\ntitle: Infinita\nproject: arena\ncost_usd: .inf")
    _nota_manual(home, "2026-10-01-inf2.md", "type: lesson\ntitle: Infinita 2\nproject: arena\ncost_usd: Infinity")
    _nota_manual(home, "2026-10-01-nan.md", "type: lesson\ntitle: Nan\nproject: arena\ncost_usd: .nan")
    mem.sincronizar(forcar=True)
    api = Api(mem, modo="browser")
    assert len(mem.procurar("")) == 4
    _strict(mem.procurar(""))
    _strict(mem.procurar("infinita"))
    for r in mem.procurar(""):
        _strict(api.nota(r["id"]))  # inclui as relacionadas (a nota limpa ficava estragada por elas)
    _strict(api.nota(limpa["id"]))
    assert {r["custo_usd"] for r in mem.procurar("infinita")} == {None}


def test_add_com_custo_infinito_nao_escreve_inf(home: Path, capsys):
    assert main(["add", "--type", "lesson", "--title", "Caro", "--project", "p", "--text", "x", "--cost", "1e999"]) == 0
    caminho = Path(capsys.readouterr().out.strip())
    assert "inf" not in caminho.read_text("utf-8").lower()
    assert main(["search", "caro", "--json"]) == 0
    json.loads(capsys.readouterr().out, parse_constant=lambda c: pytest.fail(f"JSON com {c}"))


def test_tipo_de_contexto_escrito_a_mao_continua_memoria(mem: Memoria, home: Path):
    _nota_manual(home, "2026-10-01-tipo-tarefa.md", "type: tarefa\ntitle: Tipo tarefa\nproject: arena")
    _nota_manual(home, "2026-10-01-tipo-bug.md", "type: bug\ntitle: Tipo bug\nproject: arena")
    nos = {n["id"]: n for n in mem.grafo()["nos"]}
    assert nos["arena/2026-10-01-tipo-tarefa"]["tipo"] == "historico"
    assert nos["arena/2026-10-01-tipo-bug"]["tipo"] == "bug"  # tipos desconhecidos continuam memórias na UI


def test_notas_com_codificacoes_e_cabecalhos_estranhos(mem: Memoria, home: Path, capsys):
    pasta = home / "arena"
    pasta.mkdir(parents=True)
    texto = "---\ntype: lesson\ntitle: Lição em UTF-16\nproject: arena\n---\n\nCorpo com ação.\n"
    (pasta / "2026-10-01-utf16.md").write_bytes(texto.encode("utf-16"))  # com BOM, como o Bloco de Notas
    (pasta / "2026-10-01-cp1252.md").write_bytes("---\ntype: lesson\ntitle: Ação\nproject: arena\n---\n\nx\n".encode("cp1252"))
    (pasta / "2026-10-01-binario.md").write_bytes(bytes(range(256)) * 20)
    (pasta / "2026-10-01-yaml.md").write_text("---\ntitle: [aberto\n---\n\nx\n", "utf-8")
    (pasta / "2026-10-01-cabecalho.md").write_text("---\ntitle: x\n" + "a: b\n" * 20000 + "---\n\nx\n", "utf-8")
    estado = mem.reindexar()
    erro = capsys.readouterr().err
    assert [r["titulo"] for r in mem.procurar("utf")] == ["Lição em UTF-16"]
    assert mem.ler_ficheiro("arena/2026-10-01-utf16")["texto"].startswith("---\ntype: lesson")
    assert estado["erros"] == 4
    assert "UTF-8" in erro and "cp1252" in erro and "binario" in erro and "demasiado grande" in erro
    assert "O cabeçalho YAML tem um erro (linha 2)" in erro and "while parsing" not in erro  # uma linha, como no editor
    _strict(mem.grafo())


# --------------------------------------------------------- ficheiros estranhos
def test_nota_enorme_nao_prende_a_pesquisa(mem: Memoria, home: Path):
    pasta = home / "logs"
    pasta.mkdir(parents=True)
    linha = "servidor de build falhou no passo de build do servidor\n"
    (pasta / "2026-10-01-log.md").write_text("---\ntype: history\ntitle: Log\nproject: logs\n---\n\n" + linha * 40_000, "utf-8")
    _notas(mem, 2)
    inicio = time.perf_counter()
    achados = mem.procurar("servidor de build servidor build servidor")
    assert time.perf_counter() - inicio < 2.0  # antes: minutos (snippet() quadrático)
    assert achados and achados[0]["id"] == "logs/2026-10-01-log"
    inicio = time.perf_counter()
    mem.procurar_agrupado("servidor build")
    assert time.perf_counter() - inicio < 2.0
    # A UI recebe um corpo limitado, e o editor recusa o ficheiro (não grava mais de 1 MB).
    assert len(mem.nota("logs/2026-10-01-log")["corpo"]) <= index.LIMITE_CORPO + 3
    with pytest.raises(ValueError, match="grande"):
        mem.ler_ficheiro("logs/2026-10-01-log")
    # Um log colado no add é recusado com uma mensagem, sem deixar ficheiro.
    with pytest.raises(ValueError, match="grande"):
        mem.adicionar(tipo="historico", titulo="Log colado", texto=linha * 40_000, projeto="logs")
    assert len(list(pasta.glob("*.md"))) == 1


@pytest.mark.skipif(not POSIX, reason="ligações simbólicas, FIFOs e chmod do POSIX")
def test_ligacoes_fifos_e_pastas_sem_permissao(mem: Memoria, home: Path, tmp_path: Path, capsys):
    _notas(mem, 1, projeto="arena")
    mem.adicionar(tipo="licao", titulo="Secreta", texto="dentro", projeto="secreto")
    fora = tmp_path / "dropbox" / "equipa"
    fora.mkdir(parents=True)
    _nota_manual(fora.parent, "2026-10-01-equipa.md", "type: lesson\ntitle: Equipa\nproject: equipa", projeto="equipa")
    (home / "equipa").symlink_to(fora, target_is_directory=True)
    (home / "arena" / "2026-10-01-ciclo.md").symlink_to(home / "arena" / "2026-10-01-ciclo.md")
    os.mkfifo(home / "arena" / "2026-10-01-fifo.md")
    (home / "solta.md").write_text("---\ntitle: Solta\n---\n", "utf-8")
    secreto = home / "secreto"
    secreto.chmod(0)
    try:
        capsys.readouterr()
        resultado = {}
        t = threading.Thread(target=lambda: resultado.update(estado=Memoria(home).sincronizar(forcar=True)))
        t.start()
        t.join(20)
        assert not t.is_alive(), "a sincronização prendeu (FIFO?)"
        erro = capsys.readouterr().err
        assert "equipa" in erro and "fora da pasta" in erro  # não desaparece em silêncio
        assert "secreto" in erro and "permiss" in erro
        assert "solta.md" in erro
        assert [r["titulo"] for r in Memoria(home).procurar("secreta")] == ["Secreta"]  # ficou no índice
        Memoria(home).reindexar()  # e um reindex também não a apaga
        assert [r["titulo"] for r in Memoria(home).procurar("secreta")] == ["Secreta"]
    finally:
        secreto.chmod(0o755)
    assert [r["titulo"] for r in Memoria(home).procurar("secreta")] == ["Secreta"]


def test_nome_nfd_e_ligacao_nfc(mem: Memoria, home: Path):
    pasta = home / "arena"
    pasta.mkdir(parents=True)
    nome_nfd = unicodedata.normalize("NFD", "2026-10-01-lição.md")
    (pasta / nome_nfd).write_text("---\ntype: lesson\ntitle: Lição\nproject: arena\n---\n\nx\n", "utf-8")
    liga = mem.adicionar(tipo="licao", titulo="Liga", texto="Ver [[2026-10-01-lição]].", projeto="arena")
    rel = mem.relacionadas(liga["id"])
    assert rel and rel[0]["motivos"].get("ligacao") == 1
    nfc = unicodedata.normalize("NFC", "arena/2026-10-01-lição")
    assert rel[0]["id"] == nfc
    assert mem.ler_ficheiro(nfc)["nome"]


# --------------------------------------------------------------- entradas MCP
def test_redacao_linear_e_igual(mem: Memoria):
    for texto in ("ab-" * 13_334, "token-" * 6_667, "a." * 20_000, "x" * 100_000):
        inicio = time.perf_counter()
        redigir(texto)
        assert time.perf_counter() - inicio < 0.5, texto[:10]
    # Continua a apanhar o que apanhava: chaves compridas e credenciais depois de um '-'.
    assert "segredo" not in redigir("SPRING_DATASOURCE_HIKARI_DATA_SOURCE_PROPERTIES_PASSWORD=segredo123")[0]
    assert "segredo" not in redigir("ver -https://eu:segredo123@exemplo.pt/x")[0]
    assert "segredo" not in redigir("git+ssh://eu:segredo123@exemplo.pt/x")[0]
    inicio = time.perf_counter()
    mem.procurar("ab-" * 13_334)
    assert time.perf_counter() - inicio < 2.0


def test_ligacao_vazia_ou_nao_latina_nao_resolve_para_outra(mem: Memoria):
    mem.adicionar(tipo="licao", titulo="कैश साफ़ करें", texto="x", projeto="arena")
    mem.adicionar(tipo="licao", titulo="ניקוי מטמון", texto="x", projeto="arena")
    for ref in ("[[]]", "कुछ और", "משהו אחר"):
        with pytest.raises(LookupError):
            mem.relacionadas(ref)


def test_escrita_falhada_nao_deixa_nota(home: Path, monkeypatch):
    def cheio(_fd):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(store.os, "fsync", cheio)
    with pytest.raises(OSError):
        store.escrever_nota(home, tipo="licao", titulo="Cheio", texto="x" * 1000, projeto="p")
    assert _mds(home) == []
    monkeypatch.undo()
    caminho = store.escrever_nota(home, tipo="licao", titulo="Surrogate \udce9", texto="caf\udce9", projeto="p")
    assert "�" in caminho.read_text("utf-8")


def test_erro_do_disco_na_cli_e_uma_linha(home: Path, capsys):
    home.parent.mkdir(parents=True, exist_ok=True)
    home.write_text("não é uma pasta", "utf-8")
    assert main(["add", "--type", "lesson", "--title", "x", "--project", "p", "--text", "x"]) == 1
    erro = capsys.readouterr().err
    assert "Traceback" not in erro and len(erro.strip().splitlines()) == 1


def test_linha_com_surrogate_solto():
    linha = '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"x","arguments":{"text":"a\\ud83d b"}}}\n'
    limpa = json.loads(linha_limpa(linha))
    assert limpa["id"] == 7 and limpa["params"]["arguments"]["text"] == "a� b"
    normal = '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
    assert linha_limpa(normal) is normal


def test_stdio_responde_a_surrogates_soltos(home: Path):
    """O SDK deitava fora o pedido sem responder: o Claude Code ficava à espera."""
    env = {**os.environ, "AGENT_MEMORY_HOME": str(home)}
    pedidos = [
        '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", '
        '"capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}',
        '{"jsonrpc": "2.0", "method": "notifications/initialized"}',
        '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "memory_add", "arguments": '
        '{"type": "lesson", "title": "Surrogate \\ud83d", "text": "lone \\udc00 x", "project": "p"}}}',
        '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "memory_search", "arguments": {"text": "\\ud83d"}}}',
    ]
    proc = subprocess.Popen(
        [sys.executable, "-m", "memoria", "mcp"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    respostas = {}
    try:
        for pedido in pedidos:
            proc.stdin.write((pedido + "\n").encode("utf-8"))
            proc.stdin.flush()
            if '"id"' in pedido:
                resposta = {}
                t = threading.Thread(target=lambda r=resposta: r.update(linha=proc.stdout.readline()))
                t.start()
                t.join(30)
                assert resposta.get("linha"), f"sem resposta a {pedido[:60]}"
                dados = json.loads(resposta["linha"])
                respostas[dados["id"]] = dados
        proc.stdin.close()
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert set(respostas) == {1, 2, 3}
    assert not respostas[2]["result"].get("isError")
    assert Path(respostas[2]["result"]["content"][0]["text"]).read_text("utf-8").count("�") == 2


# ------------------------------------------------------------------ línguas
@pytest.fixture
def poliglota(mem: Memoria) -> Memoria:
    mem.adicionar(tipo="licao", titulo="डेटाबेस कैश", texto="बिल्ड से पहले कैश साफ़ करें।", projeto="arena")
    mem.adicionar(tipo="licao", titulo="データベース", texto="データベースのキャッシュをクリアしてからビルドする。", projeto="arena")
    mem.adicionar(tipo="licao", titulo="缓存", texto="构建前先清除缓存。猫。", projeto="arena")
    mem.adicionar(tipo="licao", titulo="ניקוי מטמון", texto="לנקות את המטמון לפני הבנייה.", projeto="arena")
    mem.adicionar(tipo="licao", titulo="Ação", texto=unicodedata.normalize("NFD", "Limpar a cache em decomposição."), projeto="arena")
    for i in range(12):  # mais recentes: a pesquisa errada devolvia estas
        mem.adicionar(tipo="historico", titulo=f"Filler {i}", texto="nada", projeto="arena")
    return mem


@pytest.mark.parametrize(
    "consulta, titulo",
    [
        ("कैश", "डेटाबेस कैश"),
        ("बिल्ड", "डेटाबेस कैश"),
        ("साफ़", "डेटाबेस कैश"),
        ("डेटाबेस कैश", "डेटाबेस कैश"),
        ("キャッシュ", "データベース"),
        ("クリア", "データベース"),
        ("データベース", "データベース"),
        ("清除", "缓存"),
        ("猫", "缓存"),
        ("מטמון", "ניקוי מטמון"),
        ("acao", "Ação"),
        ("decomposicao", "Ação"),
    ],
)
def test_pesquisa_em_varias_linguas(poliglota: Memoria, consulta: str, titulo: str):
    achados = poliglota.procurar(consulta)
    assert achados and achados[0]["titulo"] == titulo, [a["titulo"] for a in achados]
    assert achados[0]["pontuacao"] > 0


def test_stdin_utf8_num_locale_latin1(home: Path, capsys, monkeypatch):
    texto = "Ação שלום कैश"
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(texto.encode("utf-8")), encoding="latin-1"))
    assert main(["add", "--type", "lesson", "--title", "Stdin", "--project", "p"]) == 0
    caminho = Path(capsys.readouterr().out.strip())
    assert texto in caminho.read_text("utf-8")
    assert main(["search", "שלום", "--json"]) == 0
    saida = capsys.readouterr().out
    assert saida.isascii() and json.loads(saida)[0]["title"] == "Stdin"


@pytest.mark.skipif(not POSIX, reason="locale do POSIX")
def test_cli_com_locale_latin1_escreve_utf8(home: Path, tmp_path: Path):
    env = {**os.environ, "AGENT_MEMORY_HOME": str(tmp_path / "dados Ção"), "LC_ALL": "pt_PT.ISO8859-1", "LANG": "pt_PT.ISO8859-1"}
    env.pop("PYTHONIOENCODING", None)
    env.pop("PYTHONUTF8", None)
    texto = "Ação שלום"
    r = subprocess.run(
        [sys.executable, "-m", "memoria", "add", "--type", "lesson", "--title", "Latin1", "--project", "p"],
        input=texto.encode("utf-8"), capture_output=True, env=env, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    caminho = Path(r.stdout.decode("utf-8").strip())
    assert caminho.is_file() and texto in caminho.read_text("utf-8")  # o caminho impresso é o do disco
