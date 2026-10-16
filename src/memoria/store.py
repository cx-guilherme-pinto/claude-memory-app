"""Ficheiros Markdown das memórias (o contrato partilhado com as skills).

Local:  $MEMORIA_HOME/<projeto>/<AAAA-MM-DD>-<slug>.md
Frontmatter YAML:
    tipo: licao | fazer | nao_fazer | historico
    titulo: texto
    projeto: texto
    tarefa: chave do ticket (opcional, ex.: ABC-123 ou dono/repo#42)
    epico: chave do épico ou do pai (opcional, ex.: ABC-100)        [v0.2]
    url: ligação para o ticket ou PR (opcional, http/https)          [v0.2]
    etiquetas: [palavras para pesquisa] (opcional)                   [v0.2]
    ficheiros: [caminhos de código]
    data: ISO 8601
    custo_usd: número (opcional)
    ligacoes: [nomes de outras memórias]
O corpo pode ter ligações [[nome]].

Os campos novos da v0.2 são opcionais: as notas da v0.1 continuam válidas.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

TIPOS = ("licao", "fazer", "nao_fazer", "historico")
TIPOS_CONTEXTO = ("projeto", "epico", "tarefa", "ficheiro")

_SINONIMOS = {
    "licao": "licao",
    "licoes": "licao",
    "lesson": "licao",
    "fazer": "fazer",
    "do": "fazer",
    "nao_fazer": "nao_fazer",
    "naofazer": "nao_fazer",
    "dont": "nao_fazer",
    "historico": "historico",
    "history": "historico",
}

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
LIGACAO_CORPO = re.compile(r"\[\[([^\[\]\n|]+)(?:\|[^\]\n]*)?\]\]")


# Chaves de tickets: Jira/Linear (ABC-123) e GitHub/Gitea (dono/repo#12).
_JIRA = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-\d+$")
_GITHUB = re.compile(r"^([\w.-]+/[\w.-]+)#(\d+)$")
_URL_JIRA = re.compile(r"(?:/browse/|[?&]selectedIssue=)([A-Za-z][A-Za-z0-9_]*-\d+)\b")
_URL_REPO = re.compile(r"^https?://[^/]+/([\w.-]+)/([\w.-]+)(?:/-)?/(?:issues|pulls?|merge_requests)/(\d+)\b")


def normalizar_chave(valor) -> str:
    """ABC-123 em maiúsculas; dono/repo#12 em minúsculas; o resto como está."""
    chave = " ".join(str(valor or "").split())
    if _JIRA.match(chave):
        return chave.upper()
    m = _GITHUB.match(chave)
    if m:
        return f"{m.group(1).lower()}#{m.group(2)}"
    return chave


def chave_global(chave: str) -> bool:
    """Chaves únicas fora do projeto (Jira, dono/repo#12). "#12" sozinho não é."""
    return bool(_JIRA.match(chave) or _GITHUB.match(chave))


def chave_de_url(url: str) -> str:
    """Chave do ticket a partir do URL (Jira /browse/ABC-1, GitHub/Gitea/GitLab issues e PRs)."""
    url = str(url or "").strip()
    m = _URL_JIRA.search(url)
    if m:
        return m.group(1).upper()
    m = _URL_REPO.match(url)
    if m:
        return f"{m.group(1).lower()}/{m.group(2).lower()}#{m.group(3)}"
    return ""


def validar_url(url: str) -> str:
    url = str(url or "").strip()
    if url and not re.match(r"^https?://\S+$", url):
        raise ValueError("O url tem de começar por http:// ou https://.")
    return url


def sem_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def slug(texto: str, maximo: int = 60) -> str:
    s = sem_acentos(texto).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = s[:maximo].rstrip("-")
    return s or "memoria"


def pasta_projeto(projeto: str) -> str:
    """Nome seguro da pasta do projeto (sem '..', barras ou espaços)."""
    return slug(projeto, maximo=80) if projeto else "geral"


def normalizar_tipo(tipo: str) -> str:
    chave = re.sub(r"[^a-z]", "_", sem_acentos(str(tipo)).strip().lower()).strip("_")
    chave = chave.replace("__", "_")
    if chave in _SINONIMOS:
        return _SINONIMOS[chave]
    if chave.replace("_", "") in _SINONIMOS:
        return _SINONIMOS[chave.replace("_", "")]
    raise ValueError(f"Tipo inválido: {tipo!r}. Usa um destes: {', '.join(TIPOS)}.")


def limpar_ligacao(nome: str) -> str:
    nome = str(nome).strip()
    m = LIGACAO_CORPO.fullmatch(nome)
    if m:
        nome = m.group(1)
    return nome.strip()


def _lista(valor) -> list[str]:
    if valor is None or valor == "":
        return []
    if isinstance(valor, (list, tuple)):
        return [str(v).strip() for v in valor if str(v).strip()]
    return [s.strip() for s in str(valor).split(",") if s.strip()]


def _etiquetas(valor) -> list[str]:
    vistas: dict[str, str] = {}
    for e in _lista(valor):
        e = e.lstrip("#").strip()
        if e:
            vistas.setdefault(e.lower(), e)
    return list(vistas.values())


def _data_iso(valor) -> str:
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds")
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor or "").strip()


@dataclass
class Nota:
    id: str
    caminho: Path
    tipo: str
    titulo: str
    projeto: str
    tarefa: str = ""
    ficheiros: list[str] = field(default_factory=list)
    data: str = ""
    custo_usd: float | None = None
    ligacoes: list[str] = field(default_factory=list)
    corpo: str = ""
    epico: str = ""
    url: str = ""
    etiquetas: list[str] = field(default_factory=list)

    @property
    def ligacoes_corpo(self) -> list[str]:
        return [m.group(1).strip() for m in LIGACAO_CORPO.finditer(self.corpo)]

    @property
    def todas_ligacoes(self) -> list[str]:
        vistas: dict[str, None] = {}
        for nome in [*self.ligacoes, *self.ligacoes_corpo]:
            nome = limpar_ligacao(nome)
            if nome:
                vistas.setdefault(nome, None)
        return list(vistas)

    def resumo(self) -> dict:
        return {
            "id": self.id,
            "caminho": str(self.caminho),
            "tipo": self.tipo,
            "titulo": self.titulo,
            "projeto": self.projeto,
            "tarefa": self.tarefa,
            "epico": self.epico,
            "url": self.url,
            "etiquetas": self.etiquetas,
            "ficheiros": self.ficheiros,
            "data": self.data,
            "custo_usd": self.custo_usd,
            "ligacoes": self.todas_ligacoes,
        }


def id_de(caminho: Path, home: Path) -> str:
    rel = caminho.resolve().relative_to(home.resolve())
    return rel.with_suffix("").as_posix()


def ler_nota(caminho: Path, home: Path) -> Nota:
    texto = caminho.read_text("utf-8-sig")
    meta: dict = {}
    corpo = texto
    m = _FRONTMATTER.match(texto)
    if m:
        dados = yaml.safe_load(m.group(1)) or {}
        if not isinstance(dados, dict):
            raise ValueError("frontmatter não é um mapa YAML")
        meta = dados
        corpo = texto[m.end():]
    try:
        tipo = normalizar_tipo(meta.get("tipo", "historico"))
    except ValueError:
        tipo = str(meta.get("tipo"))
    custo = meta.get("custo_usd")
    try:
        custo = float(custo) if custo not in (None, "") else None
    except (TypeError, ValueError):
        custo = None
    data_txt = _data_iso(meta.get("data"))
    if not data_txt:
        data_txt = _data_do_nome(caminho) or datetime.fromtimestamp(
            caminho.stat().st_mtime
        ).astimezone().isoformat(timespec="seconds")
    return Nota(
        id=id_de(caminho, home),
        caminho=caminho.resolve(),
        tipo=tipo,
        titulo=str(meta.get("titulo") or caminho.stem),
        projeto=str(meta.get("projeto") or caminho.parent.name),
        tarefa=normalizar_chave(meta.get("tarefa")),
        epico=normalizar_chave(meta.get("epico")),
        url=str(meta.get("url") or "").strip(),
        etiquetas=_etiquetas(meta.get("etiquetas")),
        ficheiros=_lista(meta.get("ficheiros")),
        data=data_txt,
        custo_usd=custo,
        ligacoes=[limpar_ligacao(x) for x in _lista(meta.get("ligacoes"))],
        corpo=corpo.lstrip("\n"),
    )


def _data_do_nome(caminho: Path) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})-", caminho.name)
    return m.group(1) if m else ""


def listar_ficheiros(home: Path):
    """Todos os .md em $MEMORIA_HOME/<projeto>/ (ignora pastas escondidas)."""
    if not home.is_dir():
        return
    for pasta in sorted(home.iterdir()):
        if not pasta.is_dir() or pasta.name.startswith("."):
            continue
        for ficheiro in sorted(pasta.glob("*.md")):
            if ficheiro.is_file() and not ficheiro.name.startswith("."):
                yield ficheiro


def escrever_nota(
    home: Path,
    *,
    tipo: str,
    titulo: str,
    texto: str,
    projeto: str,
    tarefa: str | None = None,
    ficheiros: list[str] | None = None,
    ligacoes: list[str] | None = None,
    custo_usd: float | None = None,
    agora: datetime | None = None,
    epico: str | None = None,
    url: str | None = None,
    etiquetas: list[str] | None = None,
) -> Path:
    """Escreve a nota de forma atómica e devolve o caminho. Não redige: ver service."""
    tipo = normalizar_tipo(tipo)
    titulo = " ".join(str(titulo or "").split())
    projeto = str(projeto or "").strip()
    if not titulo:
        raise ValueError("Falta o título.")
    if not projeto:
        raise ValueError("Falta o projeto.")
    agora = (agora or datetime.now()).astimezone()
    meta = {
        "tipo": tipo,
        "titulo": titulo,
        "projeto": projeto,
    }
    url = validar_url(url)
    tarefa = normalizar_chave(tarefa) or chave_de_url(url)
    epico = normalizar_chave(epico)
    if tarefa:
        meta["tarefa"] = tarefa
    if epico and epico != tarefa:
        meta["epico"] = epico
    if url:
        meta["url"] = url
    if _etiquetas(etiquetas):
        meta["etiquetas"] = _etiquetas(etiquetas)
    meta["ficheiros"] = _lista(ficheiros)
    meta["data"] = agora.isoformat(timespec="seconds")
    if custo_usd is not None and custo_usd != "":
        meta["custo_usd"] = round(float(custo_usd), 6)
    meta["ligacoes"] = [x for x in (limpar_ligacao(v) for v in _lista(ligacoes)) if x]

    cabecalho = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
    conteudo = f"---\n{cabecalho}---\n\n{str(texto or '').strip()}\n"

    pasta = home / pasta_projeto(projeto)
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"{agora.date().isoformat()}-{slug(titulo)}"
    for n in range(1, 1000):
        nome = f"{base}.md" if n == 1 else f"{base}-{n}.md"
        destino = pasta / nome
        try:
            # 'x' falha se já existir: nunca reescreve uma memória.
            with open(destino, "x", encoding="utf-8", newline="\n") as f:
                f.write(conteudo)
                f.flush()
                os.fsync(f.fileno())
            return destino.resolve()
        except FileExistsError:
            continue
    raise RuntimeError(f"Demasiadas memórias com o nome {base}.")


# --- edição na app -------------------------------------------------------------

TAMANHO_MAXIMO = 1_000_000  # bytes; uma nota é texto curto


def versao_ficheiro(caminho: Path) -> str:
    """Identifica o estado do ficheiro no disco (para não gravar por cima de outra edição)."""
    st = caminho.stat()
    return f"{st.st_mtime_ns}-{st.st_size}"


def validar_texto(texto: str) -> None:
    """Confirma que o texto é uma nota: cabeçalho YAML (um mapa) com um tipo conhecido."""
    if len(texto.encode("utf-8")) > TAMANHO_MAXIMO:
        raise ValueError("A nota é demasiado grande.")
    m = _FRONTMATTER.match(texto)
    if not m:
        raise ValueError("Falta o cabeçalho no início: linhas '---' com tipo, titulo e projeto.")
    try:
        dados = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as erro:
        linha = getattr(getattr(erro, "problem_mark", None), "line", None)
        onde = f" (linha {linha + 2})" if linha is not None else ""
        raise ValueError(f"O cabeçalho YAML tem um erro{onde}.") from None
    if not isinstance(dados, dict):
        raise ValueError("O cabeçalho tem de ser uma lista de 'chave: valor'.")
    normalizar_tipo(dados.get("tipo", ""))
    if not str(dados.get("titulo") or "").strip():
        raise ValueError("Falta o titulo no cabeçalho.")


def gravar_atomico(caminho: Path, texto: str) -> None:
    """Substitui o ficheiro de uma vez: nunca fica meio escrito."""
    temporario = caminho.with_name(f".{caminho.name}.a-gravar")
    with open(temporario, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporario, caminho)
