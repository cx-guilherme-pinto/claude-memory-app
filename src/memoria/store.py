"""Ficheiros Markdown das memórias (o contrato partilhado com as skills).

Local:  <pasta dos dados>/<projeto>/<AAAA-MM-DD>-<slug>.md
Frontmatter YAML, escrito em inglês desde a v0.5:
    type: lesson | do | dont | history
    title: texto
    project: texto
    task: chave do ticket (opcional, ex.: ABC-123 ou dono/repo#42)
    epic: chave do épico ou do pai (opcional, ex.: ABC-100)         [v0.2]
    url: ligação para o ticket ou PR (opcional, http/https)          [v0.2]
    tags: [palavras para pesquisa] (opcional)                        [v0.2]
    files: [caminhos de código]
    date: ISO 8601
    cost_usd: número (opcional)
    links: [nomes de outras memórias]
O corpo pode ter ligações [[nome]].

As notas antigas, com as chaves em português (tipo: licao | fazer | nao_fazer | historico,
titulo, projeto, tarefa, epico, etiquetas, ficheiros, data, custo_usd, ligacoes),
continuam a ser lidas tal como estão: nunca se reescreve uma nota.

Por dentro (índice e interface), o tipo usa os nomes antigos (licao, fazer, nao_fazer,
historico). Para fora (ficheiros novos, MCP, CLI), usa os ingleses: ver TIPO_EXTERNO.
"""

from __future__ import annotations

import codecs
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from memoria import config
from memoria.i18n import t

TIPOS = ("licao", "fazer", "nao_fazer", "historico")
TIPOS_CONTEXTO = ("projeto", "epico", "tarefa", "ficheiro")

# Nome de cada tipo fora da app: no frontmatter das notas novas, no MCP e na CLI.
TIPO_EXTERNO = {"licao": "lesson", "fazer": "do", "nao_fazer": "dont", "historico": "history"}
TIPOS_EXTERNOS = tuple(TIPO_EXTERNO.values())

_SINONIMOS = {
    "licao": "licao",
    "licoes": "licao",
    "lesson": "licao",
    "lessons": "licao",
    "fazer": "fazer",
    "do": "fazer",
    "nao_fazer": "nao_fazer",
    "naofazer": "nao_fazer",
    "dont": "nao_fazer",
    "don_t": "nao_fazer",
    "do_not": "nao_fazer",
    "historico": "historico",
    "history": "historico",
}

# Chave do frontmatter em inglês (as notas novas) -> a antiga em português (ainda lida).
CHAVES_FRONTMATTER = {
    "type": "tipo",
    "title": "titulo",
    "project": "projeto",
    "task": "tarefa",
    "epic": "epico",
    "url": "url",
    "tags": "etiquetas",
    "files": "ficheiros",
    "date": "data",
    "cost_usd": "custo_usd",
    "links": "ligacoes",
}


def campo(meta: dict, chave: str, omissao=None):
    """Valor de um campo do frontmatter: a chave inglesa primeiro, depois a portuguesa."""
    valor = meta.get(chave)
    if valor is None:
        valor = meta.get(CHAVES_FRONTMATTER.get(chave, chave))
    return omissao if valor is None else valor


def tipo_externo(tipo: str) -> str:
    """licao -> lesson (os outros valores ficam como estão)."""
    return TIPO_EXTERNO.get(tipo, tipo)

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
        raise ValueError(t("erro.url"))
    return url


def sem_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def slug(texto: str, maximo: int = 60) -> str:
    s = sem_acentos(texto).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = s[:maximo].rstrip("-")
    return s or "note"


def pasta_projeto(projeto: str) -> str:
    """Nome seguro da pasta do projeto (sem '..', barras ou espaços)."""
    return slug(projeto, maximo=80) if projeto else "general"


def normalizar_tipo(tipo: str) -> str:
    chave = re.sub(r"[^a-z]", "_", sem_acentos(str(tipo)).strip().lower()).strip("_")
    chave = chave.replace("__", "_")
    if chave in _SINONIMOS:
        return _SINONIMOS[chave]
    if chave.replace("_", "") in _SINONIMOS:
        return _SINONIMOS[chave.replace("_", "")]
    raise ValueError(t("erro.tipo_invalido", tipo=repr(tipo), tipos=", ".join(TIPOS_EXTERNOS)))


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


def id_de(caminho: Path, home: Path) -> str:
    rel = caminho.resolve().relative_to(home.resolve())
    # NFC: o macOS pode devolver nomes decompostos (NFD); uma [[ligação]] escrita à mão vem em NFC.
    return unicodedata.normalize("NFC", rel.with_suffix("").as_posix())


# Um cabeçalho com mais do que isto não é de uma nota (o YAML em Python puro levava minutos).
MAX_CABECALHO = 64_000


def ler_texto(caminho: Path) -> str:
    """O texto de uma nota: UTF-8 (com ou sem BOM) ou UTF-16 com BOM (o "Unicode" do Bloco de Notas)."""
    dados = caminho.read_bytes()
    if dados.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return dados.decode("utf-16")
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(t("erro.codificacao")) from None


def ler_nota(caminho: Path, home: Path) -> Nota:
    texto = ler_texto(caminho)
    meta: dict = {}
    corpo = texto
    m = _FRONTMATTER.match(texto)
    if m:
        if len(m.group(1)) > MAX_CABECALHO:
            raise ValueError(t("erro.cabecalho_grande"))
        try:
            dados = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as erro:
            raise ValueError(_erro_yaml(erro)) from None  # uma linha, como no editor
        if not isinstance(dados, dict):
            raise ValueError(t("erro.frontmatter_mapa"))
        meta = dados
        corpo = texto[m.end():]
    tipo_lido = campo(meta, "type", "historico")
    try:
        tipo = normalizar_tipo(tipo_lido)
    except ValueError:
        tipo = str(tipo_lido).strip()
        # Um tipo escrito à mão que é o nome de um nó de contexto (tarefa, projeto...) fazia a UI
        # desenhar a memória como esse nó, e o corpo nunca abria.
        if not tipo or tipo in TIPOS_CONTEXTO:
            tipo = "historico"
    custo = campo(meta, "cost_usd")
    try:
        custo = float(custo) if custo not in (None, "") else None
    except (TypeError, ValueError):
        custo = None
    if custo is not None and not math.isfinite(custo):
        custo = None  # Infinity/NaN não são JSON válido (a UI deixava de mostrar a nota e as relacionadas)
    data_txt = _data_iso(campo(meta, "date"))
    if not data_txt:
        data_txt = _data_do_nome(caminho) or datetime.fromtimestamp(
            caminho.stat().st_mtime
        ).astimezone().isoformat(timespec="seconds")
    return Nota(
        id=id_de(caminho, home),
        caminho=caminho.resolve(),
        tipo=tipo,
        titulo=str(campo(meta, "title") or caminho.stem),
        projeto=str(campo(meta, "project") or caminho.parent.name),
        tarefa=normalizar_chave(campo(meta, "task")),
        epico=normalizar_chave(campo(meta, "epic")),
        url=str(campo(meta, "url") or "").strip(),
        etiquetas=_etiquetas(campo(meta, "tags")),
        ficheiros=_lista(campo(meta, "files")),
        data=data_txt,
        custo_usd=custo,
        ligacoes=[limpar_ligacao(x) for x in _lista(campo(meta, "links"))],
        corpo=corpo.lstrip("\n"),
    )


def _data_do_nome(caminho: Path) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})-", caminho.name)
    return m.group(1) if m else ""


def listar_ficheiros(home: Path, problemas: list | None = None):
    """Todos os .md em <pasta dos dados>/<projeto>/ (ignora pastas escondidas).

    `problemas` recebe (caminho, motivo) do que não se pôde ver: "pasta_ilegivel" (sem permissão)
    e "fora_de_projeto" (um .md solto na pasta dos dados). Ver as mensagens aviso.<motivo>.
    """
    if problemas is None:
        problemas = []
    if not home.is_dir():
        return
    try:
        pastas = sorted(home.iterdir())
    except OSError:
        problemas.append((home, "pasta_ilegivel"))
        return
    for pasta in pastas:
        if pasta.name.startswith("."):
            continue
        if not pasta.is_dir():
            if pasta.suffix.lower() == ".md":
                problemas.append((pasta, "fora_de_projeto"))
            continue
        try:
            os.listdir(pasta)  # o glob() devolve [] numa pasta sem permissão, sem erro nenhum
        except OSError:
            problemas.append((pasta, "pasta_ilegivel"))
            continue
        for ficheiro in sorted(pasta.glob("*.md")):
            # is_file(): nem FIFOs, nem ligações em ciclo, nem pastas com nome .md.
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
        raise ValueError(t("erro.falta_titulo"))
    if not projeto:
        raise ValueError(t("erro.falta_projeto"))
    agora = (agora or datetime.now()).astimezone()
    # Chaves e valores em inglês (ver o topo do ficheiro).
    meta = {
        "type": tipo_externo(tipo),
        "title": titulo,
        "project": projeto,
    }
    url = validar_url(url)
    tarefa = normalizar_chave(tarefa) or chave_de_url(url)
    epico = normalizar_chave(epico)
    if tarefa:
        meta["task"] = tarefa
    if epico and epico != tarefa:
        meta["epic"] = epico
    if url:
        meta["url"] = url
    if _etiquetas(etiquetas):
        meta["tags"] = _etiquetas(etiquetas)
    meta["files"] = _lista(ficheiros)
    meta["date"] = agora.isoformat(timespec="seconds")
    if custo_usd is not None and custo_usd != "" and math.isfinite(float(custo_usd)):
        meta["cost_usd"] = round(float(custo_usd), 6)
    meta["links"] = [x for x in (limpar_ligacao(v) for v in _lista(ligacoes)) if x]

    cabecalho = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
    extra = ""
    # ler_nota recusa um cabeçalho maior do que MAX_CABECALHO: nunca escrever uma nota que depois não se lê.
    if len(cabecalho) > MAX_CABECALHO:
        # Demasiadas ligações para o cabeçalho: as que dão [[nome]] passam para o fim do corpo (contam igual).
        no_corpo = [x for x in meta["links"] if LIGACAO_CORPO.fullmatch(f"[[{x}]]")]
        meta["links"] = [x for x in meta["links"] if not LIGACAO_CORPO.fullmatch(f"[[{x}]]")]
        cabecalho = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
        if len(cabecalho) > MAX_CABECALHO:  # o título, as etiquetas ou os ficheiros
            raise ValueError(t("erro.cabecalho_nota_grande"))
        extra = "\n\n" + " ".join(f"[[{x}]]" for x in no_corpo)
    conteudo = f"---\n{cabecalho}---\n\n{str(texto or '').strip()}{extra}\n"
    # Antes de criar o ficheiro: um texto que não dá UTF-8 (surrogates de um terminal Latin-1)
    # deixava um .md vazio, que depois aparecia como memória.
    dados = sem_surrogates(conteudo).encode("utf-8")
    if len(dados) > TAMANHO_MAXIMO:  # a redação pode fazer o texto crescer (pwd=x -> pwd=[REDACTED:secret])
        raise ValueError(t("erro.nota_grande"))  # o editor da app não abriria a nota

    config.verificar_pasta(home)
    pasta = home / pasta_projeto(projeto)
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"{agora.date().isoformat()}-{slug(titulo)}"
    for n in range(1, 1000):
        nome = f"{base}.md" if n == 1 else f"{base}-{n}.md"
        destino = pasta / nome
        try:
            # 'x' falha se já existir: nunca reescreve uma memória.
            f = open(destino, "xb")  # noqa: SIM115
        except FileExistsError:
            continue
        try:
            with f:
                f.write(dados)
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            # Disco cheio, limite de tamanho...: nunca fica uma nota vazia ou cortada.
            try:
                destino.unlink()
            except OSError:
                pass
            raise
        return destino.resolve()
    raise RuntimeError(t("erro.demasiadas", base=base))


_SURROGATE = re.compile("[\ud800-\udfff]")


def sem_surrogates(texto: str) -> str:
    """Troca os surrogates soltos (não são UTF-8) por U+FFFD."""
    return _SURROGATE.sub("\ufffd", texto)


# --- edição na app -------------------------------------------------------------

TAMANHO_MAXIMO = 1_000_000  # bytes; uma nota é texto curto


def versao_ficheiro(caminho: Path) -> str:
    """Identifica o estado do ficheiro no disco (para não gravar por cima de outra edição)."""
    st = caminho.stat()
    return f"{st.st_mtime_ns}-{st.st_size}"


def validar_texto(texto: str) -> None:
    """Confirma que o texto é uma nota: cabeçalho YAML (um mapa) com um tipo conhecido."""
    if len(texto.encode("utf-8")) > TAMANHO_MAXIMO:
        raise ValueError(t("erro.nota_grande"))
    m = _FRONTMATTER.match(texto)
    if not m:
        raise ValueError(t("erro.falta_cabecalho"))
    if len(m.group(1)) > MAX_CABECALHO:  # o índice não leria a nota (ler_nota)
        raise ValueError(t("erro.cabecalho_grande"))
    try:
        dados = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as erro:
        raise ValueError(_erro_yaml(erro)) from None
    if not isinstance(dados, dict):
        raise ValueError(t("erro.cabecalho_mapa"))
    normalizar_tipo(campo(dados, "type", ""))
    if not str(campo(dados, "title") or "").strip():
        raise ValueError(t("erro.falta_titulo_cabecalho"))


def _erro_yaml(erro: yaml.YAMLError) -> str:
    """A mensagem de um erro no cabeçalho, com a linha do ficheiro (o cabeçalho começa na linha 2)."""
    linha = getattr(getattr(erro, "problem_mark", None), "line", None)
    return t("erro.yaml") if linha is None else t("erro.yaml_linha", linha=linha + 2)


def gravar_atomico(caminho: Path, texto: str) -> None:
    """Substitui o ficheiro de uma vez: nunca fica meio escrito."""
    temporario = caminho.with_name(f".{caminho.name}.saving")
    with open(temporario, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporario, caminho)
