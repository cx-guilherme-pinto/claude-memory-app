"""API da UI e servidor HTTP local (127.0.0.1, porta aleatória).

A mesma classe `Api` serve as duas pontes:
- janela nativa: `js_api` do pywebview (window.pywebview.api.<método>);
- browser: POST /api/<método> com o cabeçalho X-Memoria-Token.

O servidor só aceita ligações locais e valida o cabeçalho Host (contra DNS
rebinding) e a Origin. Cada sessão tem uma chave aleatória:
- o URL de entrada é http://127.0.0.1:<porta>/?t=<chave>;
- o servidor troca a chave por um cookie HttpOnly e SameSite=Strict e redireciona para "/";
- a API aceita o cookie ou o cabeçalho X-Memoria-Token.
No modo browser, sem a chave, a página explica o que abrir (não mostra um grafo vazio).
O servidor diz à página em que modo está (<meta name="memoria-modo">).
"""

from __future__ import annotations

import hmac
import html
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from memoria import __version__, store
from memoria.service import Memoria

TIPOS_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)


def pasta_ui() -> Path:
    return Path(str(resources.files("memoria").joinpath("web_dist")))


def abrir_com_sistema(caminho: Path) -> None:
    """Abre um ficheiro com a app por omissão do sistema."""
    if sys.platform == "darwin":
        r = subprocess.run(["open", str(caminho)], capture_output=True)
        if r.returncode != 0:  # nenhuma app associada a .md
            subprocess.run(["open", "-t", str(caminho)], check=True, capture_output=True)
    elif os.name == "nt":
        try:
            os.startfile(str(caminho))  # type: ignore[attr-defined]
        except OSError:
            subprocess.Popen(["notepad.exe", str(caminho)])
    else:
        subprocess.Popen(["xdg-open", str(caminho)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Api:
    """Métodos chamados pela UI. Atributos privados (com _) não são expostos."""

    def __init__(self, memoria: Memoria, modo: str = "janela", selftest: bool = False):
        self._mem = memoria
        self._modo = modo
        self._selftest = selftest
        self._pronto = threading.Event()
        self._info_pronto: dict = {}
        self._ultimo_batimento = 0.0
        self._update: dict | None = None
        self._trinco_update = threading.Lock()

    # ---------------------------------------------------------------- dados
    def inicio(self) -> dict:
        return {
            "versao": __version__,
            "home": str(self._mem.home),
            "modo": self._modo,
            "tipos": list(store.TIPOS),
            "selftest": self._selftest,
        }

    def grafo(self) -> dict:
        return self._mem.grafo()

    def nota(self, ref: str) -> dict:
        nota = self._mem.nota(ref)
        if not nota:
            raise LookupError(f"Memória não encontrada: {ref}")
        nota["relacionadas"] = self._mem.relacionadas(nota["id"], limite=12)
        return nota

    def procurar(self, texto: str) -> dict:
        """Resultados agrupados (memórias, projetos, tarefas e épicos) e os nós a destacar."""
        return self._mem.procurar_agrupado(str(texto or ""))

    def adicionar(self, dados: dict) -> dict:
        if not isinstance(dados, dict):
            raise ValueError("Dados inválidos.")
        def lista(chave: str) -> list[str]:
            valor = dados.get(chave) or []
            if isinstance(valor, str):
                valor = valor.split(",")
            return [str(x).strip() for x in valor if str(x).strip()]

        return self._mem.adicionar(
            tipo=str(dados.get("tipo") or ""),
            titulo=str(dados.get("titulo") or ""),
            texto=str(dados.get("texto") or ""),
            projeto=str(dados.get("projeto") or ""),
            tarefa=str(dados.get("tarefa") or "") or None,
            epico=str(dados.get("epico") or "") or None,
            url=str(dados.get("url") or "") or None,
            etiquetas=lista("etiquetas"),
            ligacoes=lista("ligacoes"),
        )

    def ficheiro(self, ref: str) -> dict:
        """Markdown da memória para o editor da app."""
        return self._mem.ler_ficheiro(str(ref))

    def guardar_ficheiro(self, ref: str, texto: str, versao: str | None = None) -> dict:
        return self._mem.guardar_ficheiro(str(ref), str(texto or ""), str(versao) if versao else None)

    def abrir_ficheiro(self, ref: str) -> bool:
        abrir_com_sistema(self._mem.caminho_seguro(ref))
        return True

    def abrir_url(self, url: str) -> bool:
        """Ligações externas do Markdown abrem no browser do sistema (só http/https)."""
        import webbrowser
        from urllib.parse import urlsplit

        if urlsplit(str(url)).scheme not in ("http", "https"):
            raise ValueError("Só ligações http/https.")
        return bool(webbrowser.open(str(url)))

    def verificar_atualizacao(self) -> dict:
        """Corre em segundo plano; nunca bloqueia a UI."""
        if self._selftest or os.environ.get("MEMORIA_SEM_UPDATE"):
            return {"atual": __version__, "disponivel": False}
        with self._trinco_update:
            if self._update is None:
                from memoria import update

                try:
                    self._update = update.verificar(timeout=10)
                except Exception as erro:
                    self._update = {"atual": __version__, "disponivel": False, "erro": str(erro)}
            return self._update

    # ------------------------------------------------------- ciclo de vida
    def pronto(self, info: dict | None = None) -> bool:
        self._info_pronto = dict(info or {})
        self._pronto.set()
        return True

    def batimento(self) -> bool:
        self._ultimo_batimento = time.monotonic()
        return True


METODOS = {
    "inicio", "grafo", "nota", "procurar", "adicionar", "ficheiro", "guardar_ficheiro", "abrir_ficheiro", "abrir_url",
    "verificar_atualizacao", "pronto", "batimento",
}


PAGINA_SEM_SESSAO = """<!doctype html>
<html lang="pt-PT"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Memória</title>
<style>
body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: system-ui, sans-serif;
  background: #f2f2ef; color: #121614; }}
main {{ max-width: 34rem; padding: 1.5rem; }}
p {{ line-height: 1.5; }}
@media (prefers-color-scheme: dark) {{ body {{ background: #0f1311; color: #e8ede9; }} }}
</style></head>
<body><main>
<h1>Sessão sem chave</h1>
<p>Abre o endereço completo que a Memória mostrou no terminal. Começa por {base}?t=</p>
<p>Ou fecha esta página e corre de novo: memoria --browser</p>
</main></body></html>
"""


class ServidorUI:
    def __init__(self, api: Api, raiz: Path | None = None):
        self.api = api
        self.modo = api._modo
        self.raiz = (raiz or pasta_ui()).resolve()
        self.token = secrets.token_urlsafe(24)
        self.csp = False
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._httpd.daemon_threads = True
        self.porta = self._httpd.server_address[1]
        self.cookie = f"memoria_{self.porta}"
        self._thread: threading.Thread | None = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.porta}/"

    def url(self) -> str:
        """URL de entrada desta sessão. A chave só vale enquanto o processo corre."""
        return f"{self.base}?t={self.token}"

    def chave_valida(self, valor: str | None) -> bool:
        return bool(valor) and hmac.compare_digest(str(valor).encode(), self.token.encode())

    def iniciar(self) -> "ServidorUI":
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="memoria-http", daemon=True)
        self._thread.start()
        return self

    def parar(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def _handler(self):
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "memoria"
            sys_version = ""

            def log_message(self, *args) -> None:  # silencioso: nada no stdout/stderr
                return

            def _host_valido(self) -> bool:
                host = self.headers.get("Host", "")
                return host in (f"127.0.0.1:{servidor.porta}", f"localhost:{servidor.porta}")

            def _cabecalhos_comuns(self) -> None:
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                if servidor.csp:
                    self.send_header("Content-Security-Policy", CSP)

            def _cookie(self) -> str | None:
                for parte in self.headers.get("Cookie", "").split(";"):
                    nome, _, valor = parte.strip().partition("=")
                    if nome == servidor.cookie:
                        return valor
                return None

            def _origem_valida(self) -> bool:
                origem = self.headers.get("Origin")
                return origem is None or origem in (f"http://127.0.0.1:{servidor.porta}", f"http://localhost:{servidor.porta}")

            def _autenticado(self) -> bool:
                return servidor.chave_valida(self.headers.get("X-Memoria-Token")) or servidor.chave_valida(self._cookie())

            def _enviar(self, estado: int, tipo: str, corpo: bytes, extra: dict | None = None) -> None:
                self.send_response(estado)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                for chave, valor in (extra or {}).items():
                    self.send_header(chave, valor)
                self._cabecalhos_comuns()
                self.end_headers()
                self.wfile.write(corpo)

            def _json(self, estado: int, dados) -> None:
                corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
                self.send_response(estado)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                self._cabecalhos_comuns()
                self.end_headers()
                self.wfile.write(corpo)

            def do_GET(self) -> None:  # noqa: N802
                if not self._host_valido():
                    return self._json(HTTPStatus.FORBIDDEN, {"erro": "host inválido"})
                partes = urlsplit(self.path)
                caminho = partes.path
                if caminho in ("", "/", "/index.html"):
                    return self._pagina(parse_qs(partes.query).get("t", [None])[0])
                alvo = (servidor.raiz / caminho.lstrip("/")).resolve()
                try:
                    alvo.relative_to(servidor.raiz)
                except ValueError:
                    return self._json(HTTPStatus.NOT_FOUND, {"erro": "não encontrado"})
                if not alvo.is_file():
                    return self._json(HTTPStatus.NOT_FOUND, {"erro": "não encontrado"})
                corpo = alvo.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", TIPOS_MIME.get(alvo.suffix, "application/octet-stream"))
                self.send_header("Content-Length", str(len(corpo)))
                imutavel = "/assets/" in caminho
                self.send_header("Cache-Control", "public, max-age=31536000, immutable" if imutavel else "no-store")
                self._cabecalhos_comuns()
                self.end_headers()
                self.wfile.write(corpo)

            def _pagina(self, chave: str | None) -> None:
                """index.html com o modo injetado; troca ?t=<chave> por um cookie de sessão."""
                if chave is not None:
                    if not servidor.chave_valida(chave):
                        return self._sem_sessao()
                    cookie = f"{servidor.cookie}={servidor.token}; Path=/; HttpOnly; SameSite=Strict"
                    return self._enviar(
                        HTTPStatus.SEE_OTHER,
                        "text/plain; charset=utf-8",
                        b"",
                        {"Location": "/", "Set-Cookie": cookie, "Cache-Control": "no-store"},
                    )
                # Na janela, a página abre sem cookie (a API passa pelo js_api).
                if servidor.modo != "janela" and not self._autenticado():
                    return self._sem_sessao()
                texto = (servidor.raiz / "index.html").read_text("utf-8")
                meta = f'<meta name="memoria-modo" content="{html.escape(servidor.modo)}">'
                cabeca = re.search(r"<head[^>]*>", texto, re.I) or re.search(r"<!doctype[^>]*>", texto, re.I)
                posicao = cabeca.end() if cabeca else 0
                texto = f"{texto[:posicao]}\n    {meta}{texto[posicao:]}"
                self._enviar(HTTPStatus.OK, "text/html; charset=utf-8", texto.encode("utf-8"), {"Cache-Control": "no-store"})

            def _sem_sessao(self) -> None:
                corpo = PAGINA_SEM_SESSAO.format(base=html.escape(servidor.base)).encode("utf-8")
                self._enviar(HTTPStatus.FORBIDDEN, "text/html; charset=utf-8", corpo, {"Cache-Control": "no-store"})

            def do_POST(self) -> None:  # noqa: N802
                if not self._host_valido() or not self._origem_valida():
                    return self._json(HTTPStatus.FORBIDDEN, {"erro": "origem inválida"})
                if not self._autenticado():
                    return self._json(HTTPStatus.FORBIDDEN, {"erro": "sessão inválida"})
                if not self.path.startswith("/api/"):
                    return self._json(HTTPStatus.NOT_FOUND, {"erro": "não encontrado"})
                metodo = self.path[len("/api/"):].split("?", 1)[0]
                if metodo not in METODOS:
                    return self._json(HTTPStatus.NOT_FOUND, {"erro": "método desconhecido"})
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > 1_000_000:
                    return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"erro": "pedido grande demais"})
                try:
                    corpo = json.loads(self.rfile.read(tamanho) or b"{}")
                    args = corpo.get("args", []) if isinstance(corpo, dict) else []
                    resultado = getattr(servidor.api, metodo)(*args)
                except (ValueError, LookupError, TypeError) as erro:
                    return self._json(HTTPStatus.BAD_REQUEST, {"erro": str(erro)})
                except Exception as erro:
                    return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"erro": f"{type(erro).__name__}: {erro}"})
                return self._json(HTTPStatus.OK, {"resultado": resultado})

        return Handler
