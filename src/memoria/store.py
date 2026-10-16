"""Ficheiros Markdown das memórias (o contrato partilhado com as skills).

Local:  $MEMORIA_HOME/<projeto>/<AAAA-MM-DD>-<slug>.md
Frontmatter YAML:
    tipo: licao | fazer | nao_fazer | historico
    titulo: texto
    projeto: texto
    tarefa: texto (opcional, ex.: ABC-123 ou #42)
    ficheiros: [caminhos de código]
    data: ISO 8601
    custo_usd: número (opcional)
    ligacoes: [nomes de outras memórias]
O corpo pode ter ligações [[nome]].
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
TIPOS_CONTEXTO = ("projeto", "tarefa", "ficheiro")

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
        tarefa=str(meta.get("tarefa") or "").strip(),
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
    if tarefa and str(tarefa).strip():
        meta["tarefa"] = str(tarefa).strip()
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
