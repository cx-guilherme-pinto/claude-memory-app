"""Redação de segredos antes de escrever uma memória.

Substitui tokens, chaves de API, JWTs, blocos de chave privada e padrões
do tipo password=... por [REDACTED:<tipo>]. Mais vale redigir a mais.
Até à v0.4 a marca era [REDIGIDO:<tipo>]: continua a ser reconhecida (não se redige duas vezes).
"""

from __future__ import annotations

import re

MARCA = "[REDACTED:{}]"
MARCAS = ("[REDACTED:", "[REDIGIDO:")

# (tipo, regex). A ordem importa: os padrões específicos vêm primeiro.
_PADROES: list[tuple[str, re.Pattern[str]]] = [
    (
        "private-key",
        re.compile(
            r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"
            r"[\s\S]*?(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----|\Z)"
        ),
    ),
    ("anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{8,}")),
    ("openai", re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}")),
    ("github", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("gitlab", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("aws", re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b")),
    ("slack", re.compile(r"\bxox[abposre]-[A-Za-z0-9-]{10,}")),
    ("slack", re.compile(r"\bxapp-\d-[A-Za-z0-9-]{10,}")),
    ("google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe", re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("npm", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("huggingface", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    ),
    # Atlassian (Jira/Confluence, o token do acli): ATATT3xFfGF0... e ATCTT... (Connect).
    ("atlassian", re.compile(r"\bAT[AC]TT[A-Za-z0-9_=-]{20,}")),
    # Webhooks do Slack: o URL inteiro é o segredo.
    ("slack", re.compile(r"\bhttps://hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9/_-]{20,}")),
    # Palavras-passe em linhas de comando: o valor sai, a opção fica.
    #   curl -u utilizador:segredo / --user utilizador:segredo
    ("cli-password", re.compile(r"(?<!\S)((?:-u|--user)(?:\s+|=)[^\s:'\"]+:)([^\s'\"]{4,})")),
    #   mysql -pSEGREDO (colado: com espaço, o mysql pede-a)
    ("cli-password", re.compile(r"(\b(?:mysql|mysqldump|mysqladmin|mariadb)\b[^\n]{0,200}?\s-p)([^\s'\"]{4,})")),
    #   docker/podman/helm login ... -p SEGREDO / --password SEGREDO
    (
        "cli-password",
        re.compile(
            r"(\b(?:docker|podman|helm|nerdctl|buildah|skopeo|oras)\b[^\n]{0,80}?\blogin\b[^\n]{0,200}?\s(?:-p|--password)(?:=|\s+))"
            r"([^\s'\"]{4,})"
        ),
    ),
    (
        "bearer",
        re.compile(r"(?i)\b(Bearer|Basic|token)(\s+)((?=[A-Za-z0-9._~+/=-]*\d)[A-Za-z0-9._~+/=-]{16,})"),
    ),
    # Credenciais dentro de URLs: https://utilizador:segredo@servidor
    # Uma só tentativa por sequência de [a-z0-9+.-], e só se ela acabar em "://": recomeçar em cada \b
    # dentro de uma sequência longa sem espaços era quadrático (dezenas de segundos para 40 KB).
    # O grupo atómico escolhe o mesmo início do esquema que o \b escolhia; o texto antes fica no grupo 1.
    (
        "url",
        re.compile(
            r"(?i)(?<![a-z0-9+.-])(?=[a-z0-9+.-]*+://)"
            r"((?>[a-z0-9+.-]*?\b[a-z])[a-z0-9+.-]*+://[^\s:/@]+:)([^\s@/]{3,})(@)"
        ),
    ),
]

# chave = valor / chave: valor, em texto, YAML, JSON, .env e linhas de comando.
_CHAVES = (
    r"password|passwd|pwd|pass|senha|palavra[-_ ]?passe|passphrase|secret|"
    r"client[-_]?secret|api[-_]?key|apikey|access[-_]?key|secret[-_]?key|"
    r"private[-_]?key|auth[-_]?token|access[-_]?token|refresh[-_]?token|token|"
    r"aws_secret_access_key|credential|credentials|account[-_]?key|shared[-_]?access[-_]?key"
)
# A chave começa no início de uma sequência de [A-Za-z0-9_.-] (igual ao padrão "url" acima): apanha
# tudo o que o \b apanhava, mas sem recomeçar dentro da sequência, o que era quadrático.
_ATRIBUICAO = re.compile(
    r"(?i)(?P<chave>[\"']?(?<![A-Za-z0-9_.-])[A-Za-z0-9_.-]*(?:" + _CHAVES + r")\b[\"']?)"
    r"(?P<sep>\s*[:=]\s*|\s+)"
    r"(?P<valor>\"[^\"\n]{4,}\"|'[^'\n]{4,}'|[^\s\"',;)}\]]{4,})"
)
# Sem separador ':'/'=' só redigimos se o valor parecer mesmo um segredo.
_PARECE_SEGREDO = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9._~+/=-]{12,}$")
# Depois de "password"/"senha" (ex.: .netrc "password Abc12345"): basta ter 6+ caracteres e um dígito.
_CHAVE_SENHA = re.compile(r"(?i)(?:password|passwd|pwd|pass|senha)[\"']?$")
_PARECE_SENHA = re.compile(r"^(?=.*\d)\S{6,}$")


def redigir(texto: str) -> tuple[str, int]:
    """Devolve (texto redigido, número de substituições)."""
    if not texto:
        return texto, 0
    total = 0
    for tipo, padrao in _PADROES:
        marca = MARCA.format(tipo)
        if tipo == "bearer":
            texto, n = padrao.subn(lambda m, marca=marca: f"{m.group(1)}{m.group(2)}{marca}", texto)
        elif tipo == "cli-password":
            texto, n = padrao.subn(
                lambda m, marca=marca: m.group(0) if any(x in m.group(2) for x in MARCAS) else f"{m.group(1)}{marca}", texto
            )
        elif tipo == "url":
            texto, n = padrao.subn(lambda m, marca=marca: f"{m.group(1)}{marca}{m.group(3)}", texto)
        else:
            texto, n = padrao.subn(marca, texto)
        total += n

    contagem = 0

    def atribuicao(m: re.Match[str]) -> str:
        nonlocal contagem
        valor = m.group("valor")
        if any(marca in valor for marca in MARCAS):
            return m.group(0)
        if not re.search(r"[:=]", m.group("sep")) and not _PARECE_SEGREDO.match(valor):
            if not (_CHAVE_SENHA.search(m.group("chave")) and _PARECE_SENHA.match(valor)):
                return m.group(0)
        contagem += 1
        aspas = valor[0] if valor[0] in "\"'" else ""
        return f"{m.group('chave')}{m.group('sep')}{aspas}{MARCA.format('secret')}{aspas}"

    texto = _ATRIBUICAO.sub(atribuicao, texto)
    return texto, total + contagem


def redigir_valor(valor):
    """Redige strings, listas e dicionários (recursivo)."""
    if isinstance(valor, str):
        return redigir(valor)[0]
    if isinstance(valor, list):
        return [redigir_valor(v) for v in valor]
    if isinstance(valor, dict):
        return {k: redigir_valor(v) for k, v in valor.items()}
    return valor
