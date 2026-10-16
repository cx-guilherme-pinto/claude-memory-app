"""Linha de comandos `memoria`."""

from __future__ import annotations

import time

T0 = time.perf_counter()

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402

from memoria import __version__  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="memoria",
        description="Memória: notas locais do Claude Code, com grafo e servidor MCP. Sem argumentos, abre a janela.",
    )
    p.add_argument("--version", action="version", version=f"memoria {__version__}")
    p.add_argument("--browser", action="store_true", help="abrir a interface no browser em vez da janela")
    sub = p.add_subparsers(dest="comando", metavar="comando")

    sub.add_parser("mcp", help="servidor MCP em stdio (para o Claude Code)")

    a = sub.add_parser("add", help="adicionar uma memória")
    a.add_argument("--tipo", required=True, help="licao, fazer, nao_fazer ou historico")
    a.add_argument("--titulo", default="", help="título curto (por omissão, a primeira linha do texto)")
    a.add_argument("--projeto", required=True)
    a.add_argument("--texto", help="corpo em Markdown (por omissão lê do stdin)")
    a.add_argument("--tarefa", help="chave do ticket, ex.: ABC-123 ou dono/repo#12")
    a.add_argument("--epico", help="chave do épico ou do pai, ex.: ABC-100")
    a.add_argument("--url", help="ligação para o ticket ou PR")
    a.add_argument("--etiqueta", action="append", default=[], help="palavra para pesquisa (pode repetir)")
    a.add_argument("--ficheiro", action="append", default=[], help="caminho de código (pode repetir)")
    a.add_argument("--ligacao", action="append", default=[], help="outra memória (pode repetir)")
    a.add_argument("--custo", type=float, help="custo em dólares")

    q = sub.add_parser("procurar", help="procurar memórias")
    q.add_argument("texto", nargs="?", default="")
    q.add_argument("--projeto")
    q.add_argument("--tipo")
    q.add_argument("--tarefa")
    q.add_argument("--epico")
    q.add_argument("--limite", type=int, default=10)
    q.add_argument("--json", action="store_true")

    sub.add_parser("reindex", help="reconstruir o índice a partir dos Markdown")

    u = sub.add_parser("update", help="instalar a versão mais recente")
    u.add_argument("--verificar", action="store_true", help="só mostrar se há versão nova")
    u.add_argument("--forcar", action="store_true", help="reinstalar mesmo que seja a mesma versão")
    u.add_argument("--versao", help="instalar esta tag (ex.: v0.1.0)")

    s = sub.add_parser("selftest", help="verificar a instalação")
    s.add_argument("--gui", action="store_true", help="abrir a janela e fechá-la sozinha")
    s.add_argument("--timeout", type=float, default=60.0)
    return p


def _saida_segura() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.comando == "mcp":
        from memoria.mcp_server import correr_stdio

        return correr_stdio()

    _saida_segura()
    try:
        return _executar(args)
    except KeyboardInterrupt:
        return 130
    except Exception as erro:  # mensagens curtas para humanos
        from memoria.index import FTS5Indisponivel
        from memoria.update import ErroUpdate

        if isinstance(erro, (ErroUpdate, FTS5Indisponivel, ValueError, LookupError)):
            print(f"memoria: {erro}", file=sys.stderr)
            return 1
        raise


def _executar(args: argparse.Namespace) -> int:
    if args.comando is None:
        from memoria import window

        return window.correr(browser=args.browser, t0=T0)

    if args.comando == "add":
        from memoria.service import Memoria

        texto = args.texto if args.texto is not None else ("" if sys.stdin.isatty() else sys.stdin.read())
        r = Memoria().adicionar(
            tipo=args.tipo,
            titulo=args.titulo,
            texto=texto,
            projeto=args.projeto,
            tarefa=args.tarefa,
            epico=args.epico,
            url=args.url,
            etiquetas=args.etiqueta,
            ficheiros=args.ficheiro,
            ligacoes=args.ligacao,
            custo_usd=args.custo,
        )
        if r["redigidos"]:
            print(f"Aviso: {r['redigidos']} segredo(s) redigido(s).", file=sys.stderr)
        print(r["caminho"])
        return 0

    if args.comando == "procurar":
        from memoria.service import Memoria

        resultados = Memoria().procurar(
            args.texto, projeto=args.projeto, tipo=args.tipo, limite=args.limite, tarefa=args.tarefa, epico=args.epico
        )
        if args.json:
            print(json.dumps(resultados, ensure_ascii=False, indent=2))
        else:
            for r in resultados:
                chave = " ".join(x for x in (r["tarefa"], f"[{r['epico']}]" if r["epico"] else "") if x)
                print(f"{r['data'][:10]}  {r['tipo']:<9}  {r['titulo']}  {chave}  ({r['id']})")
            if not resultados:
                print("Sem resultados.")
        return 0

    if args.comando == "reindex":
        from memoria.service import Memoria

        estado = Memoria().reindexar()
        print(f"Índice reconstruído: {estado['total']} memórias em {estado['segundos']} s.")
        if estado["erros"]:
            print(f"Aviso: {estado['erros']} ficheiro(s) ignorado(s) (ver acima).", file=sys.stderr)
        return 0

    if args.comando == "update":
        from memoria import update

        return update.atualizar(forcar=args.forcar, versao=args.versao, so_verificar=args.verificar)

    if args.comando == "selftest":
        from memoria import selftest

        return selftest.correr(gui=args.gui, timeout=args.timeout, t0=T0)

    return 2


def main_gui() -> int:
    """Entrada sem consola (Windows: memoria-gui.exe). Erros vão para um log local."""
    if sys.stdout is None or sys.stderr is None:
        from memoria import config

        pasta = config.memoria_home() / ".indice"
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            log = open(pasta / "memoria-gui.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
            sys.stdout = sys.stdout or log
            sys.stderr = sys.stderr or log
        except OSError:
            pass
    from memoria import window

    return window.correr(t0=T0)


if __name__ == "__main__":
    raise SystemExit(main())
