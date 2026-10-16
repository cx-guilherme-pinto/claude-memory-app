"""Caminhos e configuração.

Ordem de leitura de cada chave (a primeira que existir ganha):
1. variável de ambiente com o mesmo nome;
2. $MEMORIA_HOME/config.json (escrito pelo setup do workshop);
3. release.conf embutido no pacote no momento do build.

Nenhum URL está escrito no código Python.
"""

from __future__ import annotations

import json
import os
import sys
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

ENV_HOME = "MEMORIA_HOME"

# Chaves que `memoria update` lê. Os nomes são os mesmos do repos.conf do workshop.
CHAVES_UPDATE = (
    "MEMORY_APP_REPO_URL",  # obrigatório: URL git do repositório (com ou sem .git)
    "RELEASE_DOWNLOAD_URL",  # padrão: {repo}/releases/download/{version}/{file}
    "PYTHON_VERSION",  # opcional: versão do Python gerido pelo uv (por defeito 3.12)
    "UV",  # opcional: caminho absoluto do executável uv
)


def memoria_home() -> Path:
    valor = os.environ.get(ENV_HOME)
    return Path(valor).expanduser() if valor else Path.home() / ".memoria"


def config_path() -> Path:
    return memoria_home() / "config.json"


def indice_path() -> Path:
    return memoria_home() / ".indice" / "memoria.sqlite"


def ler_conf(texto: str) -> dict[str, str]:
    """Lê o formato CHAVE=valor do release.conf / repos.conf."""
    valores: dict[str, str] = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip()
    return valores


def release_conf() -> dict[str, str]:
    """release.conf embutido no pacote (ou o da raiz, a correr do código fonte)."""
    try:
        texto = resources.files("memoria").joinpath("release.conf").read_text("utf-8")
    except (FileNotFoundError, OSError):
        raiz = Path(__file__).resolve().parents[2] / "release.conf"
        try:
            texto = raiz.read_text("utf-8")
        except OSError:
            return {}
    return ler_conf(texto)


def config_utilizador() -> dict[str, str]:
    caminho = config_path()
    try:
        dados = json.loads(caminho.read_text("utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as erro:
        print(f"Aviso: {caminho} inválido ({erro}). A ignorar.", file=sys.stderr)
        return {}
    if not isinstance(dados, dict):
        return {}
    return {str(k): str(v) for k, v in dados.items() if isinstance(v, (str, int, float))}


def definicoes() -> dict[str, str]:
    valores = dict(release_conf())
    valores.update(config_utilizador())
    for chave in set(valores) | set(CHAVES_UPDATE):
        if os.environ.get(chave):
            valores[chave] = os.environ[chave]
    return valores


def partes_repo(repo_url: str) -> dict[str, str]:
    """Divide o URL do repositório nos marcadores {repo} {host} {owner} {name}."""
    repo = repo_url.strip().rstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    partes = urlsplit(repo)
    caminho = [p for p in partes.path.split("/") if p]
    return {
        "repo": repo,
        "host": partes.hostname or "",
        "owner": caminho[-2] if len(caminho) >= 2 else "",
        "name": caminho[-1] if caminho else "",
    }


def expandir(padrao: str, repo_url: str, **extra: str) -> str:
    valores = partes_repo(repo_url)
    valores.update(extra)
    resultado = padrao
    for chave, valor in valores.items():
        resultado = resultado.replace("{" + chave + "}", valor)
    if "{" in resultado:
        raise ValueError(f"Marcador desconhecido no padrão: {padrao}")
    return resultado


def url_asset(cfg: dict[str, str], versao: str, ficheiro: str) -> str:
    repo = cfg.get("MEMORY_APP_REPO_URL", "")
    padrao = cfg.get("RELEASE_DOWNLOAD_URL", "")
    if not repo or not padrao:
        raise ValueError(
            "Falta MEMORY_APP_REPO_URL ou RELEASE_DOWNLOAD_URL "
            f"em {config_path()} e no release.conf do pacote."
        )
    url = expandir(padrao, repo, version=versao, file=ficheiro)
    validar_url(url)
    return url


def validar_url(url: str) -> None:
    """Só HTTPS. HTTP apenas para 127.0.0.1/localhost (testes)."""
    partes = urlsplit(url)
    if partes.scheme == "https" and partes.hostname:
        return
    if partes.scheme == "http" and partes.hostname in ("127.0.0.1", "localhost"):
        return
    raise ValueError(f"URL recusado (só https): {url}")
