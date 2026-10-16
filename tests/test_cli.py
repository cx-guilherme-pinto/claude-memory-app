from pathlib import Path

from memoria.cli import main


def test_add_procurar_reindex(home: Path, capsys, monkeypatch):
    codigo = main(
        [
            "add",
            "--tipo", "licao",
            "--titulo", "Pela linha de comandos",
            "--projeto", "cli",
            "--texto", "corpo com password=naoGuardar123",
            "--tarefa", "c-1",
            "--epico", "c-0",
            "--url", "https://empresa.atlassian.net/browse/C-1",
            "--etiqueta", "cli",
            "--ficheiro", "a.py",
            "--ficheiro", "b.py",
            "--ligacao", "outra",
            "--custo", "0.42",
        ]
    )
    saida = capsys.readouterr()
    assert codigo == 0
    caminho = Path(saida.out.strip())
    assert caminho.is_file() and "naoGuardar123" not in caminho.read_text("utf-8")
    assert "redigido" in saida.err

    assert main(["procurar", "linha"]) == 0
    assert "Pela linha de comandos" in capsys.readouterr().out
    assert main(["procurar", "", "--epico", "C-0"]) == 0
    saida = capsys.readouterr().out
    assert "Pela linha de comandos" in saida and "C-1 [C-0]" in saida
    assert main(["reindex"]) == 0
    assert "1 memórias" in capsys.readouterr().out


def test_add_le_do_stdin(home: Path, capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("Título do stdin\nresto"))
    assert main(["add", "--tipo", "fazer", "--projeto", "p"]) == 0
    assert Path(capsys.readouterr().out.strip()).name.endswith("titulo-do-stdin.md")


def test_erros_curtos(home: Path, capsys):
    assert main(["add", "--tipo", "ideia", "--projeto", "p", "--texto", "x"]) == 1
    assert "Tipo inválido" in capsys.readouterr().err


def test_selftest_sem_janela(home: Path, capsys):
    assert main(["selftest"]) == 0
    saida = capsys.readouterr().out
    assert "FALHOU" not in saida and "selftest: OK" in saida
    # O selftest não deixa memórias na pasta do utilizador.
    assert not any(p.suffix == ".md" for p in home.rglob("*.md"))
