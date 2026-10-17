"""Línguas da app: português, inglês, hindi e hebraico.

Ordem de escolha (a primeira que existir ganha):
1. variável de ambiente AGENT_MEMORY_LANG (pt, en, hi, he), ou a antiga MEMORIA_LANG;
2. a escolha guardada no seletor da interface (<pasta dos dados>/preferences.json;
   lê também o preferencias.json das versões até à v0.4);
3. a língua do sistema (macOS: AppleLanguages; Windows: língua da interface;
   outros: LANGUAGE/LC_ALL/LC_MESSAGES/LANG);
4. inglês.

As mensagens estão em `memoria.mensagens`. A interface web tem os seus próprios
catálogos (web/src/locales/*.json); os testes confirmam que os dois estão completos.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from functools import lru_cache
from pathlib import Path

LINGUAS = ("pt", "en", "hi", "he")
RESERVA = "en"
NOMES = {"pt": "Português", "en": "English", "hi": "हिन्दी", "he": "עברית"}
RTL = {"he"}
_SINONIMOS = {"iw": "he"}  # código antigo do hebraico (Java, Android antigo)

_trinco = threading.Lock()
_atual: str | None = None


def normalizar(codigo: str | None) -> str | None:
    """'pt-PT', 'pt_BR.UTF-8', 'he-IL', 'iw', 'hi_IN' → 'pt', 'pt', 'he', 'he', 'hi'. Outras → None."""
    if not codigo:
        return None
    base = re.split(r"[-_.@]", str(codigo).strip().strip('"').lower(), maxsplit=1)[0]
    base = _SINONIMOS.get(base, base)
    return base if base in LINGUAS else None


def _preferidas_macos() -> list[str]:
    try:
        r = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    # Formato: ( "pt-PT", "en-US" )
    return re.findall(r'"?([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)*)"?\s*[,)]', r.stdout)


def _preferidas_windows() -> list[str]:
    try:
        import ctypes
        import locale

        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
        nome = locale.windows_locale.get(langid)
        return [nome] if nome else []
    except Exception:
        return []


def _preferidas_env() -> list[str]:
    valores = []
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        valor = os.environ.get(var, "")
        if valor and valor not in ("C", "POSIX", "C.UTF-8"):
            valores += valor.split(":")
    return valores


@lru_cache(maxsize=1)
def lingua_sistema() -> str:
    """A primeira língua suportada nas preferências do sistema; senão, inglês."""
    if sys.platform == "darwin":
        preferidas = _preferidas_macos() or _preferidas_env()
    elif os.name == "nt":
        preferidas = _preferidas_windows() or _preferidas_env()
    else:
        preferidas = _preferidas_env()
    for codigo in preferidas:
        lingua = normalizar(codigo)
        if lingua:
            return lingua
    return RESERVA


FICHEIRO_PREFERENCIAS = "preferences.json"
FICHEIRO_PREFERENCIAS_ANTIGO = "preferencias.json"  # até à v0.4, chave "lingua"


def _ficheiro_preferencias(antigo: bool = False) -> Path:
    from memoria import config

    return config.memoria_home() / (FICHEIRO_PREFERENCIAS_ANTIGO if antigo else FICHEIRO_PREFERENCIAS)


def _ler_preferencias(antigo: bool = False) -> dict | None:
    try:
        dados = json.loads(_ficheiro_preferencias(antigo).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def lingua_guardada() -> str | None:
    dados = _ler_preferencias()
    if dados is not None:
        return normalizar(dados.get("language") or dados.get("lingua"))
    antigas = _ler_preferencias(antigo=True)
    return normalizar(antigas.get("lingua")) if antigas else None


def lingua_ambiente() -> str | None:
    from memoria import config

    return normalizar(config.ambiente(config.ENV_LINGUA))


def lingua() -> str:
    global _atual
    with _trinco:
        if _atual is None:
            _atual = lingua_ambiente() or lingua_guardada() or lingua_sistema()
        return _atual


def definir_lingua(codigo: str, guardar: bool = True) -> str:
    """Muda a língua desta sessão e, por omissão, guarda a escolha para as próximas."""
    global _atual
    lingua_nova = normalizar(codigo)
    if not lingua_nova:
        raise ValueError(t("erro.lingua", codigo=codigo, linguas=", ".join(LINGUAS)))
    if guardar:
        caminho = _ficheiro_preferencias()
        # Primeira escolha na v0.5: leva as outras preferências do ficheiro antigo (que fica como está).
        dados = _ler_preferencias()
        if dados is None:
            dados = _ler_preferencias(antigo=True) or {}
        dados.pop("lingua", None)
        dados["language"] = lingua_nova
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_name(f".{caminho.name}.tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", "utf-8")
        os.replace(temporario, caminho)
    with _trinco:
        _atual = lingua_nova
    return lingua_nova


def repor() -> None:
    """Esquece a língua em memória (testes; ou depois de mudar a pasta dos dados)."""
    global _atual
    with _trinco:
        _atual = None
    limpar = getattr(lingua_sistema, "cache_clear", None)
    if limpar:
        limpar()


def direcao(codigo: str | None = None) -> str:
    return "rtl" if (codigo or lingua()) in RTL else "ltr"


def t(chave: str, lingua_pedida: str | None = None, **valores) -> str:
    """Mensagem traduzida. Falta numa língua → inglês → português → a própria chave."""
    from memoria.mensagens import MENSAGENS

    entrada = MENSAGENS.get(chave)
    if entrada is None:
        return chave
    lng = lingua_pedida or lingua()
    texto = entrada.get(lng) or entrada.get(RESERVA) or entrada.get("pt") or chave
    return texto.format(**valores) if valores else texto


def info() -> dict:
    """Para a interface: língua atual, a do sistema e as disponíveis."""
    atual = lingua()
    return {
        "lingua": atual,
        "direcao": direcao(atual),
        "sistema": lingua_sistema(),
        "guardada": lingua_guardada(),
        "linguas": [{"codigo": c, "nome": NOMES[c], "direcao": direcao(c)} for c in LINGUAS],
    }
