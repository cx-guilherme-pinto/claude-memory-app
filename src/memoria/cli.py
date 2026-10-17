"""Linha de comandos `agent-memory` (e `memoria`, o nome antigo, que continua a funcionar).

Desde a v0.5, os comandos e as opções são em inglês. Os nomes antigos em português
(`procurar`, `lingua`, `--tipo`, `--projeto`, `--verificar`, ...) continuam aceites,
mas não aparecem na ajuda: ver COMANDOS_ANTIGOS e OPCOES_ANTIGAS.
"""

from __future__ import annotations

import time

T0 = time.perf_counter()

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402

from memoria import __version__  # noqa: E402
from memoria.i18n import t  # noqa: E402

PROGRAMA = "agent-memory"

COMANDOS_ANTIGOS = {"procurar": "search", "lingua": "language"}
OPCOES_ANTIGAS = {
    "--tipo": "--type",
    "--titulo": "--title",
    "--projeto": "--project",
    "--texto": "--text",
    "--tarefa": "--task",
    "--epico": "--epic",
    "--etiqueta": "--tag",
    "--ficheiro": "--file",
    "--ligacao": "--link",
    "--custo": "--cost",
    "--limite": "--limit",
    "--verificar": "--check",
    "--forcar": "--force",
    "--versao": "--version",
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROGRAMA,
        description=t("cli.descricao"),
    )
    p.add_argument("--version", action="version", version=f"{PROGRAMA} {__version__}")
    p.add_argument("--browser", action="store_true", help=t("cli.browser"))
    sub = p.add_subparsers(dest="command", metavar="command")

    sub.add_parser("mcp", help=t("cli.mcp"))

    a = sub.add_parser("add", help=t("cli.add"))
    a.add_argument("--type", required=True, help=t("cli.add.tipo"))
    a.add_argument("--title", default="", help=t("cli.add.titulo"))
    a.add_argument("--project", required=True, help=t("cli.add.projeto"))
    a.add_argument("--text", help=t("cli.add.texto"))
    a.add_argument("--task", help=t("cli.add.tarefa"))
    a.add_argument("--epic", help=t("cli.add.epico"))
    a.add_argument("--url", help=t("cli.add.url"))
    a.add_argument("--tag", action="append", default=[], help=t("cli.add.etiqueta"))
    a.add_argument("--file", action="append", default=[], help=t("cli.add.ficheiro"))
    a.add_argument("--link", action="append", default=[], help=t("cli.add.ligacao"))
    a.add_argument("--cost", type=float, metavar="USD", help=t("cli.add.custo"))

    q = sub.add_parser("search", help=t("cli.procurar"))
    q.add_argument("text", nargs="?", default="")
    q.add_argument("--project")
    q.add_argument("--type")
    q.add_argument("--task")
    q.add_argument("--epic")
    q.add_argument("--limit", type=int, default=10)
    q.add_argument("--json", action="store_true")

    sub.add_parser("reindex", help=t("cli.reindex"))

    u = sub.add_parser("update", help=t("cli.update"))
    u.add_argument("--check", action="store_true", help=t("cli.update.verificar"))
    u.add_argument("--force", action="store_true", help=t("cli.update.forcar"))
    u.add_argument("--version", dest="release", metavar="TAG", help=t("cli.update.versao"))

    s = sub.add_parser("selftest", help=t("cli.selftest"))
    s.add_argument("--gui", action="store_true", help=t("cli.selftest.gui"))
    s.add_argument("--timeout", type=float, default=60.0)

    lg = sub.add_parser("language", help=t("cli.lingua"))
    lg.add_argument("code", nargs="?", choices=["pt", "en", "hi", "he"])
    return p


def traduzir_argumentos(argv: list[str]) -> list[str]:
    """Nomes antigos -> novos: o comando (`procurar` -> `search`) e as opções depois dele."""
    saida = list(argv)
    indice = next((i for i, a in enumerate(saida) if not a.startswith("-")), None)
    if indice is None:
        return saida
    saida[indice] = COMANDOS_ANTIGOS.get(saida[indice], saida[indice])
    for i in range(indice + 1, len(saida)):
        arg = saida[i]
        if arg == "--":
            break
        nome, igual, valor = arg.partition("=")
        if nome in OPCOES_ANTIGAS:
            saida[i] = OPCOES_ANTIGAS[nome] + igual + valor
    return saida


def _saida_segura() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(traduzir_argumentos(sys.argv[1:] if argv is None else argv))

    if args.command == "mcp":
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
            print(f"{PROGRAMA}: {erro}", file=sys.stderr)
            return 1
        raise


def _executar(args: argparse.Namespace) -> int:
    if args.command is None:
        from memoria import window

        return window.correr(browser=args.browser, t0=T0)

    if args.command == "add":
        from memoria.service import Memoria

        texto = args.text if args.text is not None else ("" if sys.stdin.isatty() else sys.stdin.read())
        r = Memoria().adicionar(
            tipo=args.type,
            titulo=args.title,
            texto=texto,
            projeto=args.project,
            tarefa=args.task,
            epico=args.epic,
            url=args.url,
            etiquetas=args.tag,
            ficheiros=args.file,
            ligacoes=args.link,
            custo_usd=args.cost,
        )
        if r["redigidos"]:
            print(t("cli.redigidos", n=r["redigidos"]), file=sys.stderr)
        print(r["caminho"])
        return 0

    if args.command == "search":
        from memoria import store
        from memoria.mcp_server import externo
        from memoria.service import Memoria

        resultados = Memoria().procurar(
            args.text, projeto=args.project, tipo=args.type, limite=args.limit, tarefa=args.task, epico=args.epic
        )
        if args.json:
            print(json.dumps([externo(r) for r in resultados], ensure_ascii=False, indent=2))
        else:
            for r in resultados:
                chave = " ".join(x for x in (r["tarefa"], f"[{r['epico']}]" if r["epico"] else "") if x)
                print(f"{r['data'][:10]}  {store.tipo_externo(r['tipo']):<9}  {r['titulo']}  {chave}  ({r['id']})")
            if not resultados:
                print(t("cli.sem_resultados"))
        return 0

    if args.command == "reindex":
        from memoria.service import Memoria

        estado = Memoria().reindexar()
        print(t("cli.reindex_feito", total=estado["total"], segundos=estado["segundos"]))
        if estado["erros"]:
            print(t("cli.ignorados", n=estado["erros"]), file=sys.stderr)
        return 0

    if args.command == "language":
        from memoria import i18n

        if args.code:
            i18n.definir_lingua(args.code)
        atual = i18n.lingua()
        print(t("cli.lingua_atual", nome=i18n.NOMES[atual], codigo=atual, sistema=i18n.lingua_sistema()))
        return 0

    if args.command == "update":
        from memoria import update

        return update.atualizar(forcar=args.force, versao=args.release, so_verificar=args.check)

    if args.command == "selftest":
        from memoria import selftest

        return selftest.correr(gui=args.gui, timeout=args.timeout, t0=T0)

    return 2


def main_gui() -> int:
    """Entrada sem consola (Windows: agent-memory-gui.exe). Erros vão para um log local."""
    if sys.stdout is None or sys.stderr is None:
        from memoria import config

        pasta = config.pasta_interna()
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            log = open(pasta / "gui.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
            sys.stdout = sys.stdout or log
            sys.stderr = sys.stderr or log
        except OSError:
            pass
    from memoria import window

    return window.correr(t0=T0)


if __name__ == "__main__":
    raise SystemExit(main())
