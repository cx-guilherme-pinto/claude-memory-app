import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from memoria.mcp_server import criar_servidor


def _correr(coro):
    return asyncio.run(coro)


def _json(resultado) -> dict:
    return json.loads(resultado.content[0].text)


def test_ferramentas_e_esquemas(mem):
    async def principal():
        async with Client(criar_servidor(mem)) as c:
            return (await c.list_tools()).tools

    ferramentas = {t.name: t for t in _correr(principal())}
    assert set(ferramentas) == {"memoria_procurar", "memoria_adicionar", "memoria_relacionadas"}
    props = ferramentas["memoria_adicionar"].input_schema["properties"]
    assert set(props) == {
        "tipo", "titulo", "texto", "projeto", "tarefa", "epico", "url", "ficheiros", "ligacoes", "etiquetas", "custo_usd",
    }
    assert set(ferramentas["memoria_adicionar"].input_schema["required"]) == {"tipo", "titulo", "texto", "projeto"}
    assert set(ferramentas["memoria_procurar"].input_schema["properties"]) == {"texto", "projeto", "tipo", "tarefa", "epico", "limite"}
    assert ferramentas["memoria_procurar"].input_schema["properties"]["limite"]["default"] == 10
    assert set(ferramentas["memoria_relacionadas"].input_schema["properties"]) == {"id_ou_caminho", "limite"}
    assert ferramentas["memoria_procurar"].annotations.read_only_hint is True


def test_adicionar_procurar_relacionadas(mem, home: Path):
    async def principal():
        async with Client(criar_servidor(mem)) as c:
            r1 = await c.call_tool(
                "memoria_adicionar",
                {
                    "tipo": "licao",
                    "titulo": "Enxame com limite de custo",
                    "texto": "Dar a cada agente um teto. Chave sk-ant-api03-NAOPODEFICAR1234567.",
                    "projeto": "arena-de-seguranca",
                    "tarefa": "ARENA-7",
                    "ficheiros": ["orquestrador/plan.mjs"],
                    "custo_usd": 2.5,
                },
            )
            r2 = await c.call_tool(
                "memoria_adicionar",
                {
                    "tipo": "nao_fazer",
                    "titulo": "Planear sem memória",
                    "texto": "Ver [[Enxame com limite de custo]].",
                    "projeto": "arena-de-seguranca",
                },
            )
            procura = await c.call_tool("memoria_procurar", {"texto": "arena enxame", "projeto": "arena-de-seguranca"})
            rel = await c.call_tool("memoria_relacionadas", {"id_ou_caminho": r1.structured_content["result"]})
            erro = await c.call_tool("memoria_adicionar", {"tipo": "xpto", "titulo": "x", "texto": "y", "projeto": "p"})
            vazio = await c.call_tool("memoria_relacionadas", {"id_ou_caminho": "nao-existe"})
            return r1, r2, procura, rel, erro, vazio

    r1, r2, procura, rel, erro, vazio = _correr(principal())
    caminho = Path(r1.content[0].text)
    assert caminho.is_file() and caminho.is_relative_to(home.resolve())
    assert caminho.parent.name == "arena-de-seguranca"
    assert "sk-ant-" not in caminho.read_text("utf-8")

    dados = _json(procura)
    assert dados["total"] >= 1
    primeiro = dados["resultados"][0]
    assert primeiro["titulo"] == "Enxame com limite de custo"
    assert primeiro["tarefa"] == "ARENA-7" and primeiro["custo_usd"] == 2.5
    assert "ligacoes" not in primeiro  # campos vazios não gastam tokens

    relacionadas = _json(rel)["resultados"]
    assert relacionadas[0]["titulo"] == "Planear sem memória"
    assert relacionadas[0]["motivos"]["ligacao"] == 1

    assert erro.is_error and "Tipo inválido" in erro.content[0].text
    assert vazio.is_error and "não encontrada" in vazio.content[0].text


def test_stdio_so_protocolo_no_stdout(home: Path):
    """Arranca `python -m memoria mcp` como o Claude Code e fala o protocolo."""
    env = {**os.environ, "MEMORIA_HOME": str(home), "PYTHONUNBUFFERED": "1"}

    async def principal():
        params = StdioServerParameters(command=sys.executable, args=["-m", "memoria", "mcp"], env=env)
        async with Client(params) as c:
            nomes = {t.name for t in (await c.list_tools()).tools}
            r = await c.call_tool("memoria_adicionar", {"tipo": "fazer", "titulo": "Via stdio", "texto": "ok", "projeto": "p"})
            p = await c.call_tool("memoria_procurar", {"texto": "stdio"})
            return nomes, r, p

    nomes, r, p = _correr(principal())
    assert len(nomes) == 3
    assert Path(r.content[0].text).is_file()
    assert _json(p)["resultados"][0]["titulo"] == "Via stdio"


def test_stdio_stdout_limpo_linha_a_linha(home: Path):
    """Cada linha do stdout tem de ser JSON-RPC: nada de prints nem avisos."""
    env = {**os.environ, "MEMORIA_HOME": str(home)}
    pedidos = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "teste", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "memoria_procurar", "arguments": {"texto": "nada"}}},
    ]
    proc = subprocess.Popen(
        [sys.executable, "-m", "memoria", "mcp"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    try:
        linhas = []
        for pedido in pedidos:
            proc.stdin.write(json.dumps(pedido) + "\n")
            proc.stdin.flush()
            if "id" in pedido:
                linha = proc.stdout.readline()
                assert linha, proc.stderr.read()
                linhas.append(linha)
        proc.stdin.close()
        resto = proc.stdout.read()
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    linhas += [linha for linha in resto.splitlines() if linha.strip()]
    for linha in linhas:
        assert json.loads(linha)["jsonrpc"] == "2.0", linha
    assert [json.loads(linha).get("id") for linha in linhas[:3]] == [1, 2, 3]
