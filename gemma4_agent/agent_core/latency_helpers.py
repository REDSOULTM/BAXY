"""Helpers de LATENCIA del hot-path del turno: gates de modo rápido (fast_info
sin tools, research con búsqueda breve), señal de idioma barata, y la decisión de
research profunda vs snippets. Extraído de agent.py (2026-06-09, ratchet
archivo-dios: la tanda de latencia de Codex creció agent.py sobre su techo).

Funciones PURAS (sin estado del agente). `_detect_lang_strong_signal` necesita la
tabla `_IMPERATIVE_VERBS` de agent.py; se importa a nivel de función para no crear
un ciclo de import en tiempo de carga.
"""
from __future__ import annotations

import os
from typing import Any


# Interrogativos ACENTUADOS exclusivos del español: el pt usa que/como/onde/
# quando/quem/qual/quanto (sin tilde; "quê" solo final con circunflejo) y fr/it/
# de no tienen estas formas. Ortografía del idioma (misma clase que ¿¡ñ), no
# keywords de contenido. MEDIDO 2026-06-11: sin esto, py3langid manda "qué hora
# es"→pt y "dime la hora"→fr, y el repair de idioma REESCRIBE replies correctos
# es→pt/fr (visto en vivo: "La hora actual es 00:04..." → "O horário atual...").
_ES_INTERROGATIVES = frozenset({
    "qué", "cómo", "dónde", "adónde", "cuándo", "quién", "quiénes",
    "cuál", "cuáles", "cuánto", "cuánta", "cuántos", "cuántas",
})


def detect_lang_strong_signal(text: str) -> str | None:
    """Señal de idioma rápida y de alta precisión para el hot-path.

    Cubre SOLO señales estructurales baratas y fiables: puntuación/letra
    exclusiva del español o portugués, interrogativos acentuados del español y
    verbos imperativos distintivos. La clasificación estadística (py3langid)
    queda para `_detect_lang()` (uso frío/fallback)."""
    from .agent import _IMPERATIVE_VERBS
    tl = (text or "").lower()
    if not tl:
        return None
    if any(ch in tl for ch in ("¿", "¡", "ñ")):
        return "es"
    # ã/õ no existen en es/en/fr/de/it (de los 6 soportados, solo pt): "não",
    # "ações", "amanhã" → pt inequívoco.
    if any(ch in tl for ch in ("ã", "õ")):
        return "pt"
    words = {w.strip(".,;:!?\"'()") for w in tl.split()}
    if words & _ES_INTERROGATIVES:
        return "es"
    s = f" {tl} "
    for lang, verbs in _IMPERATIVE_VERBS:
        if any(v in s for v in verbs):
            return lang
    return None


def fast_info_no_tools_enabled() -> bool:
    """No mandar schemas de tools en turnos fast_info (default ON).

    fast_info es para respuestas paramétricas y concisas. Si el user pide info
    actual/con fuentes, choose_mode rutea a research ANTES de este punto. Dejar
    schemas web/browser especulativos en fast_info causaba loops de acción y
    outliers de varios segundos ('hablame de Mortal Kombat')."""
    return (os.environ.get("GEMMA4_FAST_INFO_NO_TOOLS", "1") or "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def research_fast_search_enabled() -> bool:
    """Preferir búsqueda por snippets sobre lecturas de página completa (latencia)."""
    return (os.environ.get("GEMMA4_RESEARCH_FAST_SEARCH", "1") or "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def experience_cold_load_enabled() -> bool:
    """Permitir que la memoria de experiencias cargue el embedder en frío (sync)."""
    return (os.environ.get("GEMMA4_EXPERIENCE_COLD_LOAD", "0") or "0").strip().lower() \
        in {"1", "true", "yes", "on"}


_DEEP_RESEARCH_MARKERS = (
    # Pedidos multilingües de profundidad/fuentes; preservan la research completa.
    "source", "sources", "citation", "citations", "reference", "references",
    "cite", "cited", "deep", "detailed", "thorough", "in depth",
    "fuente", "fuentes", "cita", "citas", "referencia", "referencias",
    "citar", "profundo", "detallado", "exhaustivo", "a fondo",
    "fonte", "fontes", "citacao", "citacoes",
    "aprofundado", "detalhado",
    "approfondi", "detaille", "detaillee",
    "quellen", "zitat", "zitate", "referenz", "referenzen",
    "ausfuhrlich", "tiefgehend",
    "fonti", "citazione", "citazioni", "riferimento", "riferimenti",
    "approfondito", "dettagliato",
)


def should_keep_full_web_research(user_text: str, args: dict[str, Any]) -> bool:
    """True cuando un web.research debe leer páginas completas.

    web.research genérico es caro: abre páginas e inyecta extractos grandes en el
    2do pase del LLM. Para lookups de voz/breves, los snippets son el tradeoff
    calidad-latencia correcto. Mantenemos el camino completo cuando la llamada
    trae params de profundidad explícitos o el user pide fuentes/profundidad."""
    for key in ("read_limit", "per_page_chars", "max_chars"):
        val = args.get(key)
        if val not in (None, "", 0, "0"):
            return True
    low = (user_text or "").casefold()
    return any(marker in low for marker in _DEEP_RESEARCH_MARKERS)


__all__ = [
    "detect_lang_strong_signal",
    "fast_info_no_tools_enabled",
    "research_fast_search_enabled",
    "experience_cold_load_enabled",
    "should_keep_full_web_research",
]
