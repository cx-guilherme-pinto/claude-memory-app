"""Caminhos e configuração.

Pasta dos dados (notas, índice, config.json), a primeira que se aplicar:
1. variável de ambiente AGENT_MEMORY_HOME;
2. variável antiga MEMORIA_HOME (instalações até à v0.4);
3. ~/.memoria, se existir e ~/.agent-memory não tiver notas (nunca se move nada);
4. ~/.agent-memory.
Um valor com ~ ou relativo conta a partir da pasta pessoal (nunca da pasta onde o processo corre).

Ordem de leitura de cada chave de configuração (a primeira que existir ganha):
1. variável de ambiente com o mesmo nome;
2. <pasta dos dados>/config.json (escrito pelo setup do workshop);
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

ENV_HOME = "AGENT_MEMORY_HOME"
ENV_HOME_ANTIGA = "MEMORIA_HOME"
PASTA_DADOS = ".agent-memory"
PASTA_DADOS_ANTIGA = ".memoria"
# Pasta escondida dentro da pasta dos dados: índice, registo MCP e log da janela.
PASTA_INTERNA = ".index"
PASTA_INTERNA_ANTIGA = ".indice"

# Variáveis de ambiente: o nome novo e o antigo (ainda aceite).
ENV_LINGUA = ("AGENT_MEMORY_LANG", "MEMORIA_LANG")
ENV_SEM_UPDATE = ("AGENT_MEMORY_NO_UPDATE", "MEMORIA_SEM_UPDATE")
ENV_TOKEN = ("AGENT_MEMORY_DOWNLOAD_TOKEN", "MEMORIA_DOWNLOAD_TOKEN")

# Chaves que `agent-memory update` lê. Os nomes são os mesmos do repos.conf do workshop.
CHAVES_UPDATE = (
    "MEMORY_APP_REPO_URL",  # obrigatório: URL git do repositório (com ou sem .git)
    "RELEASE_DOWNLOAD_URL",  # padrão: {repo}/releases/download/{version}/{file}
    "PYTHON_VERSION",  # opcional: versão do Python gerido pelo uv (por defeito 3.12)
    "UV",  # opcional: caminho absoluto do executável uv
)


def ambiente(nomes: tuple[str, ...]) -> str:
    """Valor da primeira variável de ambiente definida (nome novo primeiro, depois o antigo)."""
    for nome in nomes:
        valor = os.environ.get(nome)
        if valor:
            return valor
    return ""


def sem_update() -> bool:
    return bool(ambiente(ENV_SEM_UPDATE))


def ambiente_sem_update() -> dict[str, str]:
    """Para um processo filho (o selftest de uma versão nova): os dois nomes, a nova e a antiga entendem."""
    return {nome: "1" for nome in ENV_SEM_UPDATE}


def _pasta_do_ambiente(valor: str) -> Path:
    """O valor de AGENT_MEMORY_HOME/MEMORIA_HOME como caminho absoluto.

    Um "~/..." entre aspas no .zshrc chega com o ~ literal, e um caminho relativo dependia da pasta onde
    cada processo arrancava (uma memória por pasta de trabalho). Os dois contam a partir da pasta pessoal.
    """
    caminho = Path(valor.strip()).expanduser()
    return caminho if caminho.is_absolute() else Path.home() / caminho


def contar_notas(pasta: Path) -> int:
    """Notas em <pasta>/<projeto>/*.md (as que a app mostra). 0 se a pasta não existir ou não der para ler."""
    try:
        return sum(1 for _ in pasta.glob("[!.]*/*.md"))
    except OSError:
        return 0


def _tem_notas(pasta: Path) -> bool:
    try:
        return next(iter(pasta.glob("[!.]*/*.md")), None) is not None
    except OSError:
        return False


def memoria_home() -> Path:
    valor = ambiente((ENV_HOME, ENV_HOME_ANTIGA))
    if valor.strip():
        return _pasta_do_ambiente(valor)
    casa = Path.home()
    nova, antiga = casa / PASTA_DADOS, casa / PASTA_DADOS_ANTIGA
    # Quem já tinha notas em ~/.memoria continua lá: nunca se move nem apaga nada. Decide pelo conteúdo:
    # uma ~/.agent-memory sem notas (só config.json ou .index, de um setup ou de uma pesquisa) não esconde
    # as notas antigas, e um link ~/.memoria partido (pasta na nuvem por sincronizar) continua a ser a pasta.
    if antiga.is_dir() or antiga.is_symlink():
        if not nova.exists() or (not _tem_notas(nova) and (not antiga.is_dir() or _tem_notas(antiga))):
            return antiga
    return nova


def pastas_ignoradas(home: Path | None = None) -> list[tuple[str, Path, int]]:
    """Outras pastas de dados com notas que a app não mostra: (de onde vem, pasta, número de notas).

    Ex.: MEMORIA_HOME quando AGENT_MEMORY_HOME também está definida, ou ~/.memoria ao lado de uma
    ~/.agent-memory com notas. A pasta em uso fica como está: só se avisa (nunca se move nada).
    """
    try:
        em_uso = Path(home or memoria_home()).resolve()
    except OSError:
        return []
    candidatas = [(nome, _pasta_do_ambiente(os.environ[nome])) for nome in (ENV_HOME, ENV_HOME_ANTIGA) if os.environ.get(nome, "").strip()]
    casa = Path.home()
    candidatas += [(f"~/{nome}", casa / nome) for nome in (PASTA_DADOS, PASTA_DADOS_ANTIGA)]
    vistas = {em_uso}
    saida = []
    for origem, pasta in candidatas:
        try:
            real = pasta.resolve()
        except OSError:
            continue
        if real in vistas or not real.is_dir():
            continue
        vistas.add(real)
        n = contar_notas(real)
        if n:
            saida.append((origem, pasta, n))
    return saida


def verificar_pasta(home: Path) -> None:
    """Falha com uma frase clara se a pasta dos dados é uma ligação partida (pasta na nuvem por sincronizar)
    ou um ficheiro. Nunca se cria nada no lugar dela (a app passava a usar outra pasta para sempre)."""
    home = Path(home)
    if not home.is_dir() and (home.is_symlink() or home.exists()):
        from memoria.i18n import t

        raise OSError(t("erro.pasta_indisponivel", pasta=home))


def pasta_interna(home: Path | None = None) -> Path:
    return Path(home or memoria_home()) / PASTA_INTERNA


def config_path() -> Path:
    return memoria_home() / "config.json"


def indice_path() -> Path:
    from memoria.index import NOME_FICHEIRO

    return pasta_interna() / NOME_FICHEIRO


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
    from memoria.i18n import t

    caminho = config_path()
    if not caminho.is_file() and caminho.parent == Path.home() / PASTA_DADOS_ANTIGA:
        # Um setup antigo escreveu o config.json numa ~/.agent-memory ainda sem notas, ao lado de ~/.memoria.
        caminho = Path.home() / PASTA_DADOS / "config.json"
    try:
        dados = json.loads(caminho.read_text("utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as erro:
        print(t("aviso.config_invalido", caminho=caminho, erro=erro), file=sys.stderr)
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
    from memoria.i18n import t

    valores = partes_repo(repo_url)
    valores.update(extra)
    resultado = padrao
    for chave, valor in valores.items():
        resultado = resultado.replace("{" + chave + "}", valor)
    if "{" in resultado:
        raise ValueError(t("erro.marcador", padrao=padrao))
    return resultado


def url_asset(cfg: dict[str, str], versao: str, ficheiro: str) -> str:
    from memoria.i18n import t

    repo = cfg.get("MEMORY_APP_REPO_URL", "")
    padrao = cfg.get("RELEASE_DOWNLOAD_URL", "")
    if not repo or not padrao:
        raise ValueError(t("erro.falta_urls", caminho=config_path()))
    url = expandir(padrao, repo, version=versao, file=ficheiro)
    validar_url(url)
    return url


def validar_url(url: str) -> None:
    from memoria.i18n import t

    """Só HTTPS. HTTP apenas para 127.0.0.1/localhost (testes)."""
    partes = urlsplit(url)
    if partes.scheme == "https" and partes.hostname:
        return
    if partes.scheme == "http" and partes.hostname in ("127.0.0.1", "localhost"):
        return
    raise ValueError(t("erro.url_recusado", url=url))
