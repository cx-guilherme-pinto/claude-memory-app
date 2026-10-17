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
    # Só os nomes ingleses (sem duplicados com os antigos memoria_*).
    assert set(ferramentas) == {"memory_search", "memory_add", "memory_related"}
    props = ferramentas["memory_add"].input_schema["properties"]
    assert set(props) == {
        "type", "title", "text", "project", "task", "epic", "url", "files", "links", "tags", "cost_usd",
    }
    assert set(ferramentas["memory_add"].input_schema["required"]) == {"type", "title", "text", "project"}
    assert set(ferramentas["memory_search"].input_schema["properties"]) == {"text", "project", "type", "task", "epic", "limit"}
    assert not ferramentas["memory_search"].input_schema.get("required")
    assert ferramentas["memory_search"].input_schema["properties"]["limit"]["default"] == 10
    assert set(ferramentas["memory_related"].input_schema["properties"]) == {"ref", "limit"}
    assert ferramentas["memory_related"].input_schema["required"] == ["ref"]
    assert ferramentas["memory_search"].annotations.read_only_hint is True
    # Nem nas descrições nem nas instruções aparecem os nomes antigos.
    texto = json.dumps([t.model_dump() for t in ferramentas.values()])
    for antigo in ("memoria_", "licao", "nao_fazer", "historico", "tarefa", "projeto", "texto"):
        assert antigo not in texto, antigo


def test_instrucoes_e_nome_do_servidor(mem):
    async def principal():
        async with Client(criar_servidor(mem)) as c:
            return c.server_info, c.instructions

    info, instrucoes = _correr(principal())
    assert info.name == "agent-memory"
    for nome in ("memory_search", "memory_add", "lesson", "dont", "history"):
        assert nome in instrucoes
    assert "memoria" not in instrucoes and "licao" not in instrucoes


def test_adicionar_procurar_relacionadas(mem, home: Path):
    async def principal():
        async with Client(criar_servidor(mem)) as c:
            r1 = await c.call_tool(
                "memory_add",
                {
                    "type": "lesson",
                    "title": "Swarm with a cost cap",
                    "text": "Give each agent a ceiling. Key sk-ant-api03-NAOPODEFICAR1234567.",
                    "project": "security-arena",
                    "task": "ARENA-7",
                    "files": ["orchestrator/plan.mjs"],
                    "tags": ["swarm"],
                    "cost_usd": 2.5,
                },
            )
            r2 = await c.call_tool(
                "memory_add",
                {
                    "type": "dont",
                    "title": "Plan without memory",
                    "text": "See [[Swarm with a cost cap]].",
                    "project": "security-arena",
                },
            )
            procura = await c.call_tool("memory_search", {"text": "arena swarm", "project": "security-arena"})
            por_tipo = await c.call_tool("memory_search", {"type": "dont"})
            sem_texto = await c.call_tool("memory_search", {})
            rel = await c.call_tool("memory_related", {"ref": r1.structured_content["result"]})
            erro = await c.call_tool("memory_add", {"type": "xpto", "title": "x", "text": "y", "project": "p"})
            vazio = await c.call_tool("memory_related", {"ref": "does-not-exist"})
            return r1, r2, procura, por_tipo, sem_texto, rel, erro, vazio

    r1, r2, procura, por_tipo, sem_texto, rel, erro, vazio = _correr(principal())
    caminho = Path(r1.content[0].text)
    assert caminho.is_file() and caminho.is_relative_to(home.resolve())
    assert caminho.parent.name == "security-arena"
    conteudo = caminho.read_text("utf-8")
    assert "sk-ant-" not in conteudo and "[REDACTED:anthropic]" in conteudo
    # Frontmatter em inglês: chaves e valores.
    assert "type: lesson\n" in conteudo and "task: ARENA-7\n" in conteudo and "cost_usd: 2.5\n" in conteudo
    for antigo in ("tipo:", "titulo:", "projeto:", "tarefa:", "ficheiros:", "ligacoes:", "etiquetas:", "data:", "licao"):
        assert antigo not in conteudo, antigo

    dados = _json(procura)
    assert dados["total"] >= 1 and "resultados" not in dados
    primeiro = dados["results"][0]
    assert primeiro["title"] == "Swarm with a cost cap"
    assert primeiro["type"] == "lesson" and primeiro["project"] == "security-arena"
    assert primeiro["task"] == "ARENA-7" and primeiro["cost_usd"] == 2.5
    assert primeiro["files"] == ["orchestrator/plan.mjs"] and primeiro["tags"] == ["swarm"]
    assert primeiro["path"] == str(caminho) and "excerpt" in primeiro and "score" in primeiro
    assert "links" not in primeiro  # campos vazios não gastam tokens
    assert not {"titulo", "tipo", "projeto", "tarefa", "caminho", "excerto", "pontuacao"} & set(primeiro)

    assert [r["title"] for r in _json(por_tipo)["results"]] == ["Plan without memory"]
    assert _json(por_tipo)["results"][0]["type"] == "dont"
    assert _json(sem_texto)["total"] == 2

    relacionadas = _json(rel)["results"]
    assert relacionadas[0]["title"] == "Plan without memory"
    assert relacionadas[0]["reasons"] == {"link": 1, "project": 1}
    assert relacionadas[0]["strength"] > 0

    assert erro.is_error and "Tipo inválido" in erro.content[0].text and "lesson, do, dont, history" in erro.content[0].text
    assert vazio.is_error and "não encontrada" in vazio.content[0].text


def test_le_notas_antigas_em_portugues(mem, home: Path):
    """Notas da v0.4 (frontmatter em português) aparecem com os nomes ingleses."""
    pasta = home / "arena-de-seguranca"
    pasta.mkdir(parents=True)
    (pasta / "2026-10-01-antiga.md").write_text(
        "---\ntipo: nao_fazer\ntitulo: Nota antiga\nprojeto: arena-de-seguranca\ntarefa: ARENA-1\nepico: ARENA-0\n"
        "etiquetas: [legado]\nficheiros: [a.py]\ndata: '2026-10-01T10:00:00+01:00'\ncusto_usd: 1.5\nligacoes: []\n---\n\nCorpo antigo.\n",
        "utf-8",
    )

    async def principal():
        async with Client(criar_servidor(mem)) as c:
            return await c.call_tool("memory_search", {"text": "antiga", "type": "dont", "epic": "ARENA-0"})

    nota = _json(_correr(principal()))["results"][0]
    assert nota["title"] == "Nota antiga" and nota["type"] == "dont"
    assert nota["task"] == "ARENA-1" and nota["epic"] == "ARENA-0"
    assert nota["tags"] == ["legado"] and nota["files"] == ["a.py"] and nota["cost_usd"] == 1.5
    assert nota["date"].startswith("2026-10-01")
    # Ler não reescreve a nota.
    assert "tipo: nao_fazer" in (pasta / "2026-10-01-antiga.md").read_text("utf-8")


def test_stdio_so_protocolo_no_stdout(home: Path):
    """Arranca `python -m memoria mcp` como o Claude Code e fala o protocolo."""
    env = {**os.environ, "AGENT_MEMORY_HOME": str(home), "PYTHONUNBUFFERED": "1"}

    async def principal():
        params = StdioServerParameters(command=sys.executable, args=["-m", "memoria", "mcp"], env=env)
        async with Client(params) as c:
            nomes = {t.name for t in (await c.list_tools()).tools}
            r = await c.call_tool("memory_add", {"type": "do", "title": "Via stdio", "text": "ok", "project": "p"})
            p = await c.call_tool("memory_search", {"text": "stdio"})
            return nomes, r, p

    nomes, r, p = _correr(principal())
    assert nomes == {"memory_search", "memory_add", "memory_related"}
    assert Path(r.content[0].text).is_file()
    assert _json(p)["results"][0]["title"] == "Via stdio"


def test_stdio_com_a_variavel_antiga(home: Path, tmp_path: Path):
    """O kit antigo regista o MCP com MEMORIA_HOME: continua a funcionar."""
    antiga = tmp_path / "pasta-antiga"
    env = {k: v for k, v in os.environ.items() if k != "AGENT_MEMORY_HOME"}
    env["MEMORIA_HOME"] = str(antiga)

    async def principal():
        params = StdioServerParameters(command=sys.executable, args=["-m", "memoria", "mcp"], env=env)
        async with Client(params) as c:
            return await c.call_tool("memory_add", {"type": "history", "title": "Old variable", "text": "ok", "project": "p"})

    r = _correr(principal())
    assert Path(r.content[0].text).is_relative_to(antiga.resolve())


def test_stdio_stdout_limpo_linha_a_linha(home: Path):
    """Cada linha do stdout tem de ser JSON-RPC: nada de prints nem avisos."""
    env = {**os.environ, "AGENT_MEMORY_HOME": str(home)}
    pedidos = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "teste", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "memory_search", "arguments": {"text": "nada"}}},
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
    assert not json.loads(linhas[2])["result"].get("isError")
