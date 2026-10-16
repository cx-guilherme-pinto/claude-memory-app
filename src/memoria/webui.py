"""API da UI e servidor HTTP local (127.0.0.1, porta aleatória).

A mesma classe `Api` serve as duas pontes:
- janela nativa: `js_api` do pywebview (window.pywebview.api.<método>);
- browser: POST /api/<método> com o cabeçalho X-Memoria-Token.

O servidor só aceita ligações locais, valida o cabeçalho Host (contra DNS
rebinding) e exige um token de sessão aleatório nas chamadas à API.
O token vai no fragmento do URL (#t=...), que o browser nunca envia ao servidor.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

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

    def procurar(self, texto: str, projeto: str | None = None, tipo: str | None = None) -> list[str]:
        return [r["id"] for r in self._mem.procurar(texto, projeto=projeto or None, tipo=tipo or None, limite=200)]

    def adicionar(self, dados: dict) -> dict:
        if not isinstance(dados, dict):
            raise ValueError("Dados inválidos.")
        ligacoes = dados.get("ligacoes") or []
        if isinstance(ligacoes, str):
            ligacoes = [x.strip() for x in ligacoes.split(",") if x.strip()]
        return self._mem.adicionar(
            tipo=str(dados.get("tipo") or ""),
            titulo=str(dados.get("titulo") or ""),
            texto=str(dados.get("texto") or ""),
            projeto=str(dados.get("projeto") or ""),
            tarefa=str(dados.get("tarefa") or "") or None,
            ligacoes=ligacoes,
        )

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
    "inicio", "grafo", "nota", "procurar", "adicionar", "abrir_ficheiro", "abrir_url",
    "verificar_atualizacao", "pronto", "batimento",
}


class ServidorUI:
    def __init__(self, api: Api, raiz: Path | None = None):
        self.api = api
        self.raiz = (raiz or pasta_ui()).resolve()
        self.token = secrets.token_urlsafe(24)
        self.csp = False
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._httpd.daemon_threads = True
        self.porta = self._httpd.server_address[1]
        self._thread: threading.Thread | None = None

    def url(self, com_token: bool) -> str:
        base = f"http://127.0.0.1:{self.porta}/"
        return base + (f"#t={self.token}" if com_token else "#modo=janela")

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
                caminho = self.path.split("?", 1)[0].split("#", 1)[0]
                if caminho in ("", "/"):
                    caminho = "/index.html"
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

            def do_POST(self) -> None:  # noqa: N802
                if not self._host_valido():
                    return self._json(HTTPStatus.FORBIDDEN, {"erro": "host inválido"})
                token = self.headers.get("X-Memoria-Token", "")
                if not hmac.compare_digest(token.encode(), servidor.token.encode()):
                    return self._json(HTTPStatus.FORBIDDEN, {"erro": "token inválido"})
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
