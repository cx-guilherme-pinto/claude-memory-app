import json
from pathlib import Path

import pytest
import yaml

from memoria.cli import main, traduzir_argumentos


def test_add_search_reindex(home: Path, capsys, monkeypatch):
    codigo = main(
        [
            "add",
            "--type", "lesson",
            "--title", "Pela linha de comandos",
            "--project", "cli",
            "--text", "corpo com password=naoGuardar123",
            "--task", "c-1",
            "--epic", "c-0",
            "--url", "https://empresa.atlassian.net/browse/C-1",
            "--tag", "cli",
            "--file", "a.py",
            "--file", "b.py",
            "--link", "outra",
            "--cost", "0.42",
        ]
    )
    saida = capsys.readouterr()
    assert codigo == 0
    caminho = Path(saida.out.strip())
    assert caminho.is_file() and "naoGuardar123" not in caminho.read_text("utf-8")
    assert "redigido" in saida.err
    meta = yaml.safe_load(caminho.read_text("utf-8").split("---\n")[1])
    assert meta["type"] == "lesson" and meta["task"] == "C-1" and meta["epic"] == "C-0"
    assert meta["tags"] == ["cli"] and meta["files"] == ["a.py", "b.py"] and meta["links"] == ["outra"]
    assert meta["cost_usd"] == 0.42

    assert main(["search", "linha"]) == 0
    saida = capsys.readouterr().out
    assert "Pela linha de comandos" in saida and " lesson " in saida and "licao" not in saida
    assert main(["search", "", "--epic", "C-0"]) == 0
    saida = capsys.readouterr().out
    assert "Pela linha de comandos" in saida and "C-1 [C-0]" in saida
    assert main(["search", "linha", "--json", "--limit", "1"]) == 0
    dados = json.loads(capsys.readouterr().out)
    assert dados[0]["title"] == "Pela linha de comandos" and dados[0]["type"] == "lesson" and dados[0]["task"] == "C-1"
    assert not {"titulo", "tipo", "tarefa", "caminho"} & set(dados[0])
    assert main(["reindex"]) == 0
    assert "1 memórias" in capsys.readouterr().out


def test_nomes_antigos_continuam_a_funcionar(home: Path, capsys):
    """`memoria procurar --tipo ...` e as opções em português (até à v0.4) são aceites."""
    codigo = main(
        [
            "add",
            "--tipo", "licao",
            "--titulo", "Opções antigas",
            "--projeto", "cli",
            "--texto", "corpo",
            "--tarefa", "c-2",
            "--epico=c-0",
            "--etiqueta", "x",
            "--ficheiro", "a.py",
            "--ligacao", "outra",
            "--custo", "1",
        ]
    )
    caminho = Path(capsys.readouterr().out.strip())
    assert codigo == 0
    meta = yaml.safe_load(caminho.read_text("utf-8").split("---\n")[1])
    assert meta["type"] == "lesson" and meta["task"] == "C-2" and meta["epic"] == "C-0" and meta["cost_usd"] == 1
    assert main(["procurar", "antigas", "--tipo", "licao", "--projeto", "cli", "--limite", "5"]) == 0
    assert "Opções antigas" in capsys.readouterr().out
    assert main(["lingua"]) == 0
    assert "Língua" in capsys.readouterr().out


def test_traduzir_argumentos():
    assert traduzir_argumentos(["procurar", "--tipo=fazer", "--limite", "3"]) == ["search", "--type=fazer", "--limit", "3"]
    assert traduzir_argumentos(["update", "--verificar", "--forcar", "--versao", "v0.4.0"]) == [
        "update", "--check", "--force", "--version", "v0.4.0",
    ]
    # Antes do comando e depois de "--", nada muda.
    assert traduzir_argumentos(["--browser"]) == ["--browser"]
    assert traduzir_argumentos(["add", "--", "--tipo"]) == ["add", "--", "--tipo"]


def test_ajuda_em_ingles_sem_nomes_antigos(capsys, monkeypatch):
    from memoria import i18n

    monkeypatch.setenv("AGENT_MEMORY_LANG", "en")
    i18n.repor()
    for argv in (["--help"], ["add", "--help"], ["search", "--help"], ["update", "--help"], ["language", "--help"]):
        with pytest.raises(SystemExit):
            main(argv)
        ajuda = capsys.readouterr().out
        assert ajuda.startswith("usage: agent-memory")
        for antigo in ("procurar", "lingua", "--tipo", "--projeto", "--verificar", "licao", "fazer", "historico", "memoria"):
            assert antigo not in ajuda, (argv, antigo)


def test_versao(capsys):
    from memoria import __version__

    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.strip() == f"agent-memory {__version__}"


def test_add_le_do_stdin(home: Path, capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("Título do stdin\nresto"))
    assert main(["add", "--type", "do", "--project", "p"]) == 0
    assert Path(capsys.readouterr().out.strip()).name.endswith("titulo-do-stdin.md")


def test_erros_curtos(home: Path, capsys):
    assert main(["add", "--type", "ideia", "--project", "p", "--text", "x"]) == 1
    erro = capsys.readouterr().err
    assert erro.startswith("agent-memory: ") and "Tipo inválido" in erro


def test_selftest_sem_janela(home: Path, capsys):
    assert main(["selftest"]) == 0
    saida = capsys.readouterr().out
    assert "FALHOU" not in saida and "selftest: OK" in saida
    # O selftest não deixa memórias na pasta do utilizador.
    assert not any(p.suffix == ".md" for p in home.rglob("*.md"))
