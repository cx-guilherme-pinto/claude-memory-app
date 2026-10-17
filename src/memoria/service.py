"""Operações de alto nível, usadas pelo servidor MCP, pela CLI e pela UI."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from memoria import config, store
from memoria.i18n import t
from memoria.index import Indice
from memoria.redact import redigir, redigir_valor

# Intervalo mínimo entre verificações do disco (edições feitas à mão).
_INTERVALO_SYNC = 3.0


class Memoria:
    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home else config.memoria_home()
        self.indice = Indice(self.home)
        self._trinco = threading.Lock()
        self._ultimo_sync = 0.0

    def sincronizar(self, forcar: bool = False) -> dict | None:
        with self._trinco:
            if not forcar and time.monotonic() - self._ultimo_sync < _INTERVALO_SYNC:
                return None
            estado = self.indice.sincronizar()
            self._ultimo_sync = time.monotonic()
            return estado

    def reindexar(self) -> dict:
        with self._trinco:
            estado = self.indice.reindexar()
            self._ultimo_sync = time.monotonic()
            return estado

    def adicionar(
        self,
        *,
        tipo: str,
        titulo: str,
        texto: str,
        projeto: str,
        tarefa: str | None = None,
        ficheiros: list[str] | None = None,
        ligacoes: list[str] | None = None,
        custo_usd: float | None = None,
        epico: str | None = None,
        url: str | None = None,
        etiquetas: list[str] | None = None,
    ) -> dict:
        """Redige segredos, escreve o Markdown e atualiza o índice."""
        texto, n_texto = redigir(texto or "")
        titulo, n_titulo = redigir(titulo or "")
        if not titulo.strip():
            # Sem título: usa a primeira linha do texto.
            primeira = next((linha.strip("# ").strip() for linha in texto.splitlines() if linha.strip()), "")
            titulo = primeira[:90]
        caminho = store.escrever_nota(
            self.home,
            tipo=tipo,
            titulo=titulo,
            texto=texto,
            projeto=redigir(projeto or "")[0],
            tarefa=redigir(tarefa or "")[0] or None,
            ficheiros=redigir_valor(list(ficheiros or [])),
            ligacoes=redigir_valor(list(ligacoes or [])),
            custo_usd=custo_usd,
            epico=redigir(epico or "")[0] or None,
            url=redigir(url or "")[0] or None,
            etiquetas=redigir_valor(list(etiquetas or [])),
        )
        self.sincronizar(forcar=True)
        return {
            "caminho": str(caminho),
            "id": store.id_de(caminho, self.home),
            "redigidos": n_texto + n_titulo,
        }

    def procurar(
        self,
        texto: str,
        projeto: str | None = None,
        tipo: str | None = None,
        limite: int = 10,
        tarefa: str | None = None,
        epico: str | None = None,
    ) -> list[dict]:
        self.sincronizar()
        return self.indice.procurar(texto, projeto=projeto, tipo=tipo, limite=limite, tarefa=tarefa, epico=epico)

    def procurar_agrupado(self, texto: str, limite: int = 8) -> dict:
        self.sincronizar()
        return self.indice.procurar_agrupado(texto, limite=limite)

    def relacionadas(self, ref: str, limite: int = 10) -> list[dict]:
        self.sincronizar()
        return self.indice.relacionadas(ref, limite=limite)

    def nota(self, ref: str) -> dict | None:
        self.sincronizar()
        return self.indice.nota(ref)

    def grafo(self) -> dict:
        self.sincronizar()
        return self.indice.grafo()

    def caminho_seguro(self, ref: str) -> Path:
        """Caminho de uma memória, garantindo que fica dentro da pasta dos dados."""
        nota = self.nota(ref)
        if not nota:
            raise LookupError(t("erro.memoria_nao_encontrada", ref=ref))
        caminho = Path(nota["caminho"]).resolve()
        caminho.relative_to(self.home.resolve())  # ValueError se estiver fora
        return caminho

    def ler_ficheiro(self, ref: str) -> dict:
        """O Markdown de uma memória, tal como está no disco (para editar na app)."""
        caminho = self.caminho_seguro(ref)
        return {
            "id": store.id_de(caminho, self.home),
            "nome": caminho.name,
            "texto": caminho.read_text("utf-8-sig"),
            "versao": store.versao_ficheiro(caminho),
        }

    def guardar_ficheiro(self, ref: str, texto: str, versao: str | None = None) -> dict:
        """Grava o Markdown editado na app: confirma o cabeçalho, redige segredos e reindexa.

        `versao` é a que `ler_ficheiro` devolveu. Se o ficheiro mudou entretanto
        (por exemplo, o Claude Code escreveu nele), não grava por cima.
        """
        caminho = self.caminho_seguro(ref)
        if versao and versao != store.versao_ficheiro(caminho):
            raise ValueError(t("erro.ficheiro_mudou"))
        texto = str(texto or "").replace("\r\n", "\n")
        if not texto.endswith("\n"):
            texto += "\n"
        texto, redigidos = redigir(texto)
        store.validar_texto(texto)
        with self._trinco:
            store.gravar_atomico(caminho, texto)
        self.sincronizar(forcar=True)
        return {"id": store.id_de(caminho, self.home), "redigidos": redigidos, "versao": store.versao_ficheiro(caminho)}
