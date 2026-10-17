"""Operações de alto nível, usadas pelo servidor MCP, pela CLI e pela UI."""

from __future__ import annotations

import functools
import sqlite3
import sys
import threading
import time
from pathlib import Path

from memoria import config, store
from memoria.i18n import t
from memoria.index import ESPERA_CURTA, Indice, indice_estragado, indice_ocupado
from memoria.redact import redigir, redigir_valor

# Intervalo mínimo entre verificações do disco (edições feitas à mão).
_INTERVALO_SYNC = 3.0


def _repara_indice(metodo):
    """Índice estragado (ficheiro corrompido): refaz-se a partir dos Markdown e tenta-se outra vez.

    O índice é descartável; as notas nunca mudam. Se não der para o refazer (no Windows, outro
    processo tem-no aberto), o erro sobe, e a CLI e o MCP explicam o que fazer (erro.indice).
    """

    @functools.wraps(metodo)
    def envolto(self, *args, **kwargs):
        try:
            return metodo(self, *args, **kwargs)
        except sqlite3.DatabaseError as erro:
            if not indice_estragado(erro) or getattr(erro, "memoria_tentou_refazer", False):
                raise
            try:
                with self._trinco:
                    self.indice.reindexar(estragado=True)
                    self._ultimo_sync = time.monotonic()
            except sqlite3.DatabaseError as falha:
                falha.memoria_tentou_refazer = True
                raise
            print(t("aviso.indice_refeito", erro=erro), file=sys.stderr)
            try:
                return metodo(self, *args, **kwargs)
            except sqlite3.DatabaseError as outro:
                outro.memoria_tentou_refazer = True
                raise

    return envolto


class Memoria:
    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home else config.memoria_home()
        self.indice = Indice(self.home)
        self._trinco = threading.Lock()
        self._ultimo_sync = 0.0

    @_repara_indice
    def sincronizar(self, forcar: bool = False, espera: float | None = None) -> dict | None:
        """Lê o que mudou no disco. Devolve None se não foi preciso, ou se outro processo tem o índice preso
        (a sincronização seguinte apanha o que faltou)."""
        with self._trinco:
            if not forcar and time.monotonic() - self._ultimo_sync < _INTERVALO_SYNC:
                return None
            if espera is None and not forcar:
                espera = ESPERA_CURTA  # de rotina: espera pouco por um lock (forçada: a espera normal do índice)
            try:
                estado = self.indice.sincronizar(espera=espera)
            except sqlite3.OperationalError as erro:
                if not indice_ocupado(erro):
                    raise
                estado = None  # o .md já está no disco: entra na próxima sincronização
            self._ultimo_sync = time.monotonic()
            return estado

    def reindexar(self) -> dict:
        with self._trinco:
            estado = self.indice.reindexar()
            self._ultimo_sync = time.monotonic()
            return estado

    def _sincronizar_depois_de_gravar(self) -> None:
        """A nota já está gravada: um índice preso ou estragado não pode fazer parecer que falhou.

        Espera pouco por um lock (ex.: um reindex noutro processo): a nota entra na sincronização seguinte.
        """
        try:
            self.sincronizar(forcar=True, espera=ESPERA_CURTA)
        except sqlite3.Error as erro:
            print(t("aviso.indice_falhou", erro=erro), file=sys.stderr)

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
        if len(str(texto or "").encode("utf-8", "replace")) > store.TAMANHO_MAXIMO:
            raise ValueError(t("erro.nota_grande"))  # um log colado: a CLI e o MCP mostram a mensagem
        texto, n_texto = redigir(store.sem_surrogates(texto or ""))
        titulo, n_titulo = redigir(store.sem_surrogates(titulo or ""))
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
        self._sincronizar_depois_de_gravar()
        try:
            nid = store.id_de(caminho, self.home)
        except ValueError:  # pasta do projeto é uma ligação para fora (o sincronizar avisa)
            nid = f"{caminho.parent.name}/{caminho.stem}"
        return {
            "caminho": str(caminho),
            "id": nid,
            "redigidos": n_texto + n_titulo,
        }

    @_repara_indice
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

    @_repara_indice
    def procurar_agrupado(self, texto: str, limite: int = 8) -> dict:
        self.sincronizar()
        return self.indice.procurar_agrupado(texto, limite=limite)

    @_repara_indice
    def relacionadas(self, ref: str, limite: int = 10) -> list[dict]:
        self.sincronizar()
        return self.indice.relacionadas(ref, limite=limite)

    @_repara_indice
    def nota(self, ref: str) -> dict | None:
        self.sincronizar()
        return self.indice.nota(ref)

    @_repara_indice
    def resolver(self, ref: str) -> str | None:
        return self.indice.resolver(ref)

    @_repara_indice
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
        if caminho.stat().st_size > store.TAMANHO_MAXIMO:
            raise ValueError(t("erro.nota_grande"))  # o editor não grava mais do que isto (e 30 MB prendiam a UI)
        return {
            "id": store.id_de(caminho, self.home),
            "nome": caminho.name,
            "texto": store.ler_texto(caminho),
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
        self._sincronizar_depois_de_gravar()
        return {"id": store.id_de(caminho, self.home), "redigidos": redigidos, "versao": store.versao_ficheiro(caminho)}
