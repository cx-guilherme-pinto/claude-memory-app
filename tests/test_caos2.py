"""Segunda ronda do teste de caos do workshop: pastas de dados divididas (variáveis, ~, caminhos relativos,
~/.memoria ao lado de uma ~/.agent-memory vazia), segredos de empresa, notas no limite do tamanho,
índice só de leitura ou copiado de outro sítio, `update --check` sem rede e a UI depois de o servidor parar."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest
from mcp import Client

from memoria import config, store, update
from memoria.cli import main
from memoria.index import Indice
from memoria.mcp_server import criar_servidor
from memoria.redact import redigir
from memoria.service import Memoria

POSIX = os.name != "nt"
ROOT = POSIX and os.geteuid() == 0


def _nota(pasta: Path, nome: str, titulo: str) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    f = pasta / f"2026-10-01-{nome}.md"
    f.write_text(f"---\ntype: lesson\ntitle: {titulo}\nproject: {pasta.name}\n---\n\nCorpo de {titulo}.\n", "utf-8")
    return f


@pytest.fixture
def casa(monkeypatch, tmp_path: Path) -> Path:
    """Pasta pessoal sem AGENT_MEMORY_HOME nem MEMORIA_HOME (como a app aberta pelo Dock)."""
    c = tmp_path / "casa"
    c.mkdir()
    monkeypatch.setenv("HOME", str(c))
    monkeypatch.setenv("USERPROFILE", str(c))
    monkeypatch.delenv("AGENT_MEMORY_HOME", raising=False)
    monkeypatch.delenv("MEMORIA_HOME", raising=False)
    return c


# --------------------------------------------------------- pasta dos dados
def test_caminho_relativo_e_til_contam_da_pasta_pessoal(casa: Path, monkeypatch, tmp_path: Path):
    for valor, esperado in (("notas-rel", casa / "notas-rel"), ("~/notas-til", casa / "notas-til"), ("  ~/x  ", casa / "x")):
        monkeypatch.setenv("AGENT_MEMORY_HOME", valor)
        for cwd in (tmp_path, casa):
            monkeypatch.chdir(cwd)
            assert config.memoria_home() == esperado  # nunca uma memória por pasta de trabalho


def test_variaveis_divididas_avisam_das_notas_escondidas(casa: Path, monkeypatch, tmp_path: Path, capsys):
    nova, antiga = tmp_path / "nova", tmp_path / "antiga"
    _nota(nova / "p", "a", "Nova")
    for i in range(3):
        _nota(antiga / "p", f"b{i}", f"Antiga {i}")
    _nota(casa / ".agent-memory" / "p", "c", "Casa")
    monkeypatch.setenv("AGENT_MEMORY_HOME", str(nova))
    monkeypatch.setenv("MEMORIA_HOME", str(antiga))
    assert config.memoria_home() == nova
    ignoradas = {origem: n for origem, _, n in config.pastas_ignoradas()}
    assert ignoradas == {"MEMORIA_HOME": 3, "~/.agent-memory": 1}
    # A pasta em uso nunca aparece; uma variável igual à outra também não.
    monkeypatch.setenv("MEMORIA_HOME", str(nova))
    assert {origem for origem, _, _ in config.pastas_ignoradas()} == {"~/.agent-memory"}
    monkeypatch.setenv("MEMORIA_HOME", str(antiga))

    monkeypatch.setenv("AGENT_MEMORY_LANG", "en")
    from memoria import i18n

    i18n.repor()
    assert main(["search", "nova"]) == 0
    erro = capsys.readouterr().err
    assert "has 3 memories that are not shown" in erro and str(antiga) in erro


def test_selftest_mostra_as_pastas_ignoradas_sem_falhar(casa: Path, monkeypatch, tmp_path: Path, capsys):
    _nota(tmp_path / "antiga" / "p", "a", "Antiga")
    monkeypatch.setenv("AGENT_MEMORY_HOME", str(tmp_path / "nova"))
    monkeypatch.setenv("MEMORIA_HOME", str(tmp_path / "antiga"))
    monkeypatch.setenv("AGENT_MEMORY_LANG", "en")
    from memoria import i18n

    i18n.repor()
    assert main(["selftest"]) == 0
    saida = capsys.readouterr().out
    assert "[WARN]" in saida and "MEMORIA_HOME" in saida and "1 memories that are not shown" in saida


def test_inicio_da_ui_lista_as_pastas_ignoradas(casa: Path, monkeypatch, tmp_path: Path):
    from memoria.webui import Api

    _nota(tmp_path / "antiga" / "p", "a", "Antiga")
    monkeypatch.setenv("AGENT_MEMORY_HOME", str(tmp_path / "nova"))
    monkeypatch.setenv("MEMORIA_HOME", str(tmp_path / "antiga"))
    info = Api(Memoria()).inicio()
    assert info["ignoradas"] == [{"origem": "MEMORIA_HOME", "pasta": str(tmp_path / "antiga"), "n": 1}]


def test_agent_memory_vazia_nao_esconde_a_memoria_antiga(casa: Path):
    _nota(casa / ".memoria" / "arena", "licao", "Lição antiga")
    nova = casa / ".agent-memory"
    nova.mkdir()
    (nova / "config.json").write_text(json.dumps({"MEMORY_APP_REPO_URL": "https://example.test/o/app.git"}), "utf-8")
    (nova / ".index").mkdir()
    assert config.memoria_home() == casa / ".memoria"
    # O config.json que um setup antigo escreveu na pasta nova continua a ser lido.
    assert config.config_utilizador()["MEMORY_APP_REPO_URL"] == "https://example.test/o/app.git"
    assert [r["titulo"] for r in Memoria().procurar("antiga")] == ["Lição antiga"]
    assert config.memoria_home() == casa / ".memoria"  # a pesquisa não mudou nada
    assert config.pastas_ignoradas() == []

    # Com notas nas duas, a nova ganha e avisa das antigas (nada se move).
    _nota(nova / "arena", "nova", "Nova")
    assert config.memoria_home() == nova
    assert [(o, n) for o, _, n in config.pastas_ignoradas()] == [("~/.memoria", 1)]


@pytest.mark.skipif(not POSIX, reason="ligações simbólicas")
def test_link_partido_da_memoria_nao_cria_a_pasta_nova(casa: Path, tmp_path: Path, capsys):
    nuvem = tmp_path / "nuvem"
    _nota(nuvem / "arena", "licao", "Lição na nuvem")
    escondida = tmp_path / "nuvem-por-sincronizar"
    nuvem.rename(escondida)
    (casa / ".memoria").symlink_to(nuvem)
    assert config.memoria_home() == casa / ".memoria"
    assert main(["search", "nuvem"]) == 1
    assert "não está disponível" in capsys.readouterr().err
    assert not (casa / ".agent-memory").exists()  # nada ficou criado: a troca não fica permanente
    escondida.rename(nuvem)
    assert [r["titulo"] for r in Memoria().procurar("nuvem")] == ["Lição na nuvem"]


@pytest.mark.skipif(not POSIX, reason="ligações simbólicas")
def test_selftest_com_link_partido(casa: Path, monkeypatch, tmp_path: Path, capsys):
    (casa / ".memoria").symlink_to(tmp_path / "nao-existe")
    monkeypatch.setenv("AGENT_MEMORY_LANG", "en")
    from memoria import i18n

    i18n.repor()
    assert main(["selftest"]) == 1
    saida = capsys.readouterr().out
    assert "Cannot write to" in saida and "broken link" in saida  # o setup do kit mapeia "Cannot write to" (E-MEM-07)
    assert not (casa / ".agent-memory").exists() and not (tmp_path / "nao-existe").exists()


# ------------------------------------------------------------------ segredos
ATATT = "ATATT3xFfGF0T1aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT=AB12CD34"
SEGREDOS_EMPRESA = [
    (f"curl -u bea@empresa.pt:{ATATT} https://empresa.atlassian.net/rest/api/3/myself", ATATT),
    (f"echo {ATATT}xyz | acli jira auth login --site empresa.atlassian.net --token", ATATT),
    (f"JIRA token is {ATATT}", ATATT),
    ("https://hooks." + "slack.com/services/" + "T0123ABCD/B0123ABCD/abcdefghijklmnopqrstuvwx", "abcdefghijklmnopqrstuvwx"),  # em partes: o valor e falso, mas o push protection do GitHub reconhece o formato
    ("DefaultEndpointsProtocol=https;AccountName=acme;AccountKey=Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MA==;EndpointSuffix=x", "Zm9vYmFy"),
    ("mysql -u root -pMyS3cretRoot42", "MyS3cretRoot42"),
    ("docker login -u bea -p Dock3rS3cret2026 registry.empresa.pt", "Dock3rS3cret2026"),
    ("curl -u admin:Adm1nPassw0rd https://x", "Adm1nPassw0rd"),
    ("machine api.github.com login bea password N3trcPass77", "N3trcPass77"),
]


@pytest.mark.parametrize("texto,segredo", SEGREDOS_EMPRESA)
def test_segredos_de_empresa(texto, segredo):
    redigido, n = redigir(texto)
    assert n >= 1 and segredo not in redigido and "[REDACTED:" in redigido


@pytest.mark.parametrize(
    "texto",
    ["mysql -u root -p mydb", "docker login registry.empresa.pt", "the password reset page", "see -p 8080:80",
     "senha 2024", "password policy v2", "token is ready", "curl -u bea https://x"],
)
def test_sem_falsos_positivos(texto):
    assert redigir(texto) == (texto, 0)


def test_token_atlassian_no_titulo_e_no_projeto_nunca_chega_ao_disco(mem: Memoria, home: Path):
    r = mem.adicionar(tipo="lesson", titulo=f"login {ATATT}", texto="x", projeto=f"proj {ATATT}")
    assert ATATT.lower()[:12] not in r["caminho"].lower()
    assert all(ATATT not in f.read_text("utf-8") for f in home.rglob("*.md"))


# ------------------------------------------------------- tamanhos no limite
def test_a_redacao_nao_deixa_passar_uma_nota_grande_demais(mem: Memoria, home: Path):
    with pytest.raises(ValueError, match="demasiado grande"):
        mem.adicionar(tipo="lesson", titulo="t", texto="pwd=abcd " * 110_000, projeto="p")
    assert list(home.rglob("*.md")) == []


@pytest.mark.parametrize(
    "extra",
    [{"titulo": "x" * 100_000}, {"ficheiros": [f"src/pasta/ficheiro-{i}.ts" for i in range(3000)]},
     {"etiquetas": [f"etiqueta-{i}" for i in range(10_000)]}],
)
def test_cabecalho_grande_demais_e_recusado_sem_ficheiro(mem: Memoria, home: Path, extra):
    dados = {"tipo": "lesson", "titulo": "t", "texto": "x", "projeto": "p", **extra}
    with pytest.raises(ValueError, match="demasiado longos"):
        mem.adicionar(**dados)
    assert list(home.rglob("*.md")) == []


def test_milhares_de_ligacoes_ficam_no_corpo_e_a_nota_aparece(mem: Memoria, home: Path):
    alvo = mem.adicionar(tipo="lesson", titulo="Nota 17", texto="x", projeto="p")
    ligacoes = ["Nota 17", *[f"Uma memória com um nome comprido número {i}" for i in range(3000)]]
    r = mem.adicionar(tipo="lesson", titulo="Hub", texto="Índice.", projeto="p", ligacoes=ligacoes)
    nota = store.ler_nota(Path(r["caminho"]), home)  # o próprio leitor aceita o que a app escreveu
    assert set(nota.todas_ligacoes) == set(ligacoes)
    assert [x["titulo"] for x in mem.procurar("Hub")] == ["Hub"]
    assert any(x["id"] == alvo["id"] for x in mem.relacionadas(r["id"], limite=5))


def test_editor_recusa_um_cabecalho_que_o_indice_nao_leria():
    texto = "---\ntype: lesson\ntitle: x\ntags: [" + ", ".join(f"t{i}" for i in range(20_000)) + "]\n---\n\nx\n"
    with pytest.raises(ValueError, match="64 KB"):
        store.validar_texto(texto)


def test_editor_grava_uma_nota_grande_com_muitos_escapes(mem: Memoria, home: Path):
    import http.client

    from memoria.webui import Api, ServidorUI

    r = mem.adicionar(tipo="lesson", titulo="Log", texto="x", projeto="p")
    caminho = Path(r["caminho"])
    linha = '{"a": "b\\\\c", "d": "e"}\n'
    caminho.write_text(caminho.read_text("utf-8") + linha * (880_000 // len(linha)), "utf-8")
    s = ServidorUI(Api(mem, modo="browser")).iniciar()
    try:
        f = mem.ler_ficheiro(r["id"])
        corpo = json.dumps({"args": [r["id"], f["texto"] + "fim\n", f["versao"]]}).encode()
        assert len(corpo) > 1_000_000  # o limite antigo do pedido recusava-o (413) e a ligação caía
        c = http.client.HTTPConnection("127.0.0.1", s.porta, timeout=30)
        c.request("POST", "/api/guardar_ficheiro", body=corpo,
                  headers={"Host": f"127.0.0.1:{s.porta}", "X-Memoria-Token": s.token, "Content-Type": "application/json"})
        resposta = c.getresponse()
        assert resposta.status == 200, resposta.read()[:200]
    finally:
        s.parar()
    assert caminho.read_text("utf-8").endswith("fim\n")


# ------------------------------------------------- índice só de leitura
@pytest.mark.skipif(not POSIX or ROOT, reason="permissões POSIX (o root escreve sempre)")
def test_indice_so_de_leitura_diz_o_que_fazer_e_nunca_reindex(mem: Memoria, home: Path, capsys, monkeypatch):
    mem.adicionar(tipo="lesson", titulo="Lição", texto="x", projeto="p")
    pasta = home / ".index"
    ficheiros = [f for f in pasta.iterdir() if f.name.startswith("index-v")]
    try:
        for f in ficheiros:
            f.chmod(0o444)
        pasta.chmod(0o555)
        for comando in (["reindex"], ["add", "--type", "lesson", "--title", "Outra", "--project", "p", "--text", "y"]):
            codigo = main(comando)
            erro = capsys.readouterr().err
            if comando[0] == "reindex":
                assert codigo == 1
            assert "agent-memory reindex" not in erro
            assert "chmod -R u+rwX" in erro and ("sem escrita no índice" in erro or "não há escrita no índice" in erro)
        # O selftest diz o mesmo, com o texto que o setup do kit reconhece (E-MEM-07).
        monkeypatch.setenv("AGENT_MEMORY_LANG", "en")
        from memoria import i18n

        i18n.repor()
        assert main(["selftest"]) == 1
        saida = capsys.readouterr().out
        assert "Cannot write to the search index" in saida and "agent-memory reindex" not in saida
    finally:
        pasta.chmod(0o755)
        for f in pasta.iterdir():
            f.chmod(0o644)
    assert {r["titulo"] for r in Memoria(home).procurar("")} == {"Lição", "Outra"}


@pytest.mark.skipif(not POSIX or ROOT, reason="permissões POSIX (o root escreve sempre)")
def test_mcp_com_indice_so_de_leitura(mem: Memoria, home: Path):
    mem.adicionar(tipo="lesson", titulo="Lição", texto="x", projeto="p")
    pasta = home / ".index"
    try:
        for f in pasta.iterdir():
            if f.name.startswith("index-v"):
                f.chmod(0o444)
        pasta.chmod(0o555)

        async def correr():
            async with Client(criar_servidor(Memoria(home))) as c:
                return await c.call_tool("memory_search", {"text": "lição"})

        r = asyncio.run(correr())
        texto = r.content[0].text
        assert r.is_error and "chmod -R u+rwX" in texto and "agent-memory reindex" not in texto
    finally:
        pasta.chmod(0o755)
        for f in pasta.iterdir():
            f.chmod(0o644)


# --------------------------------------------- pasta copiada de outro sítio
def test_pasta_copiada_com_as_datas_refaz_os_caminhos(tmp_path: Path, monkeypatch):
    a, b = tmp_path / "sitio-a", tmp_path / "sitio-b"
    mem_a = Memoria(a)
    nota = mem_a.adicionar(tipo="lesson", titulo="Cache no CI", texto="Usa a cache.", projeto="arena")
    mem_a.adicionar(tipo="do", titulo="Outra", texto="[[Cache no CI]]", projeto="arena")
    assert mem_a.procurar("cache")
    shutil.copytree(a, b, copy_function=shutil.copy2)  # como cp -Rp, rsync -a, o Finder
    shutil.rmtree(a)
    monkeypatch.setenv("AGENT_MEMORY_HOME", str(b))
    mem_b = Memoria(b)
    resultados = mem_b.procurar("cache")
    assert resultados and all(Path(r["caminho"]).is_file() and r["caminho"].startswith(str(b.resolve())) for r in resultados)
    assert mem_b.relacionadas(resultados[0]["caminho"])
    assert mem_b.ler_ficheiro(nota["id"])["texto"].startswith("---")
    indice = Indice(b)
    indice.sincronizar()
    assert indice.sincronizar()["alteradas"] == 0  # depois de refeitos, os caminhos não voltam a mudar


def test_nota_ilegivel_avisa_uma_vez_por_processo(mem: Memoria, home: Path, capsys):
    (home / "p").mkdir(parents=True)
    (home / "p" / "2026-10-01-x.md").write_text("---\ntitle: [aberto\n---\n\nx\n", "utf-8")
    mem.indice.sincronizar()
    mem.indice.sincronizar()
    assert capsys.readouterr().err.count("memória ignorada") == 1
    assert mem.indice.reindexar()["erros"] == 1  # o reindex volta a contar


# ------------------------------------------------------- update --check
@pytest.mark.skipif(not POSIX, reason="git falso em sh")
def test_timeout_do_git_mata_os_ajudantes(tmp_path: Path, monkeypatch):
    pid = tmp_path / "pid"
    git = tmp_path / "git"
    # Como o git: um ajudante (git-remote-https) preso num proxy que não responde.
    git.write_text(f"#!/bin/sh\nsleep 120 &\necho $! > '{pid}'\nwait\n", "utf-8")
    git.chmod(0o755)
    monkeypatch.setattr(update, "_git", lambda: str(git))
    monkeypatch.setenv("https_proxy", "http://bea:Sup3rS3cret@proxy.empresa.pt:8080")
    inicio = time.monotonic()
    with pytest.raises(update.ErroUpdate) as erro:
        update.ultima_tag("https://example.test/o/app.git", timeout=1)
    assert time.monotonic() - inicio < 10
    assert "proxy.empresa.pt:8080" in str(erro.value) and "https_proxy" in str(erro.value)
    assert "Sup3rS3cret" not in str(erro.value) and "bea" not in str(erro.value)
    filho = int(pid.read_text())
    for _ in range(50):
        try:
            os.kill(filho, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(filho, 9)
        pytest.fail("o ajudante do git ficou a correr")


@pytest.mark.parametrize(
    "stderr,proxy,esperado",
    [
        ("fatal: unable to access 'https://h/': Could not resolve host: h", None, "Sem rede ou sem DNS"),
        ("fatal: unable to access 'https://h/': Failed to connect to proxy.x port 8080", "http://proxy.x:8080", "O proxy http://proxy.x:8080"),
        ("fatal: unable to access 'https://h/': CONNECT tunnel failed, response 302", "http://portal:80", "página de login do Wi-Fi"),
        ("xcrun: error: invalid active developer path (/Library/Developer/CommandLineTools)", None, "xcode-select --install"),
        ("fatal: repository not found", None, "git ls-remote falhou: fatal: repository not found"),
    ],
)
def test_erros_do_git_dizem_a_causa(monkeypatch, stderr, proxy, esperado):
    for nome in ("https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY"):
        monkeypatch.delenv(nome, raising=False)
    if proxy:
        monkeypatch.setenv("HTTPS_PROXY", proxy)
    assert esperado in update._explicar(stderr, "https://h/o/app.git")


def test_mcp_sem_hub_perdido(mem: Memoria):
    """memory_add com milhares de ligações: a memória fica pesquisável (antes: OK falso e nunca indexada)."""

    async def correr():
        async with Client(criar_servidor(mem)) as c:
            r = await c.call_tool(
                "memory_add",
                {"type": "lesson", "title": "Big hub via MCP", "text": "x", "project": "p",
                 "links": [f"Nota com um nome bastante comprido {i}" for i in range(3000)]},
            )
            assert not r.is_error
            return await c.call_tool("memory_search", {"text": "Big hub via MCP"})

    r = asyncio.run(correr())
    assert json.loads(r.content[0].text)["total"] >= 1


def test_permissoes_comando_por_sistema(monkeypatch):
    from memoria import index

    monkeypatch.setattr(sys, "platform", "win32")
    assert index.comando_permissoes(Path("C:/Users/x/.agent-memory")).startswith("attrib -R")
    monkeypatch.setattr(sys, "platform", "darwin")
    assert index.comando_permissoes(Path("/Users/x/.agent-memory")) == 'chmod -R u+rwX "/Users/x/.agent-memory"'
