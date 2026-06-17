"""Perfil de idioma del usuario para la voz.

REESCRITURA Parakeet-only (2026-06-17): antes este módulo configuraba a Whisper
(`whisper_language` fijo + `initial_prompt` por idioma con framing bilingüe
anti-fonetización). Whisper se eliminó y Parakeet auto-detecta el idioma sin
admitir forzarlo ni prompt, así que toda esa maquinaria desapareció.

Lo que queda es la IDENTIDAD de idioma del usuario: un código ISO resuelto desde
`GEMMA4_VOICE_LANG` (selector de settings) o el default. La voz lo usa como HINT
para el agente — para que el reply salga en el idioma del usuario aunque la
transcripción de un comando corto haya leakeado a inglés (limitación conocida
del LID de Parakeet en frases cortas; ver _BASELINE_VOZ). El agente ya consume
este código vía `_reply_lang` (agent_core/agent.py) + el hint per-turno.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LangProfile:
    code: str       # código ISO de 2 letras ("es", "en", ...)
    label: str      # etiqueta humana para logs/UI


# Idiomas con perfil explícito. Cualquier código ISO-2 válido funciona como hint;
# estos son los que el producto rotula y prueba. Ampliar es trivial.
PROFILES: dict[str, LangProfile] = {
    "es": LangProfile("es", "Español"),
    "en": LangProfile("en", "English"),
    "pt": LangProfile("pt", "Português"),
    "fr": LangProfile("fr", "Français"),
    "de": LangProfile("de", "Deutsch"),
    "it": LangProfile("it", "Italiano"),
}

DEFAULT_LANG = "es"


def resolve_lang(lang: str | None = None) -> str:
    """Resuelve el código de idioma a usar:
      1. `lang` explícito si es válido.
      2. env GEMMA4_VOICE_LANG (selector de settings).
      3. DEFAULT_LANG.
    Acepta variantes ("es-419", "en_US") tomando el prefijo de 2 letras.
    """
    for candidate in (lang, os.environ.get("GEMMA4_VOICE_LANG")):
        if not candidate:
            continue
        code = str(candidate).strip().lower().replace("_", "-").split("-")[0]
        if code in PROFILES:
            return code
    return DEFAULT_LANG


def get_profile(lang: str | None = None) -> LangProfile:
    return PROFILES[resolve_lang(lang)]
