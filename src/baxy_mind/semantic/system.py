"""System: power, lock, battery, processes, hardware, weather, time and countdowns. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _fold, _has, _strip_request_envelope, _process_list_domain, _PERCENTAGE_WORD_VALUES, _request_clauses
from .intent import EffectIntent
from .web import _WEATHER_WORDS, _weather_lookup_query


_WEATHER_MEDIUM = (
    r"\b(?:google|bing|internet|la\s+web|the\s+web|online|en\s+linea)\b"
)


def _weather_location(text: str) -> str | None:
    """REOPEN1993 (grupo W): the place the person named for the weather («en
    Buenos Aires», «in Madrid»), with their own spelling; None when no place is
    named (the read then uses this PC's own location) or the words after the
    preposition are a medium («en google», «en internet»)."""

    query = _weather_lookup_query(text)
    if query is None:
        return None
    match = re.search(
        r"\b(?:en|in|de|para|for|at)\s+(?P<place>[^,;:.!?]+?)\s*"
        r"(?:\b(?:hoy|manana|mañana|ahora|today|tomorrow|now|right\s+now|por\s+favor|please)\b.*)?$",
        query,
        re.IGNORECASE,
    )
    if match is None:
        return None
    place = match.group("place").strip(" \t\r\n.,;:")
    place = re.sub(r"^(?:la\s+ciudad\s+de|the\s+city\s+of)\s+", "", place, flags=re.IGNORECASE)
    folded_place = _fold(place)
    if (
        not folded_place
        or _has(folded_place, _WEATHER_MEDIUM)
        or _has(folded_place, _WEATHER_WORDS)
        or len(place.encode("utf-8")) > 128
    ):
        return None
    return place


def _weather_read_intent(
    text: str,
    available_operations: Iterable[str],
) -> EffectIntent | None:
    """REOPEN1993 (grupo W): a live weather question is a typed weather read,
    never a web search (twelve rows were credited with pages about the
    weather or an honest failure instead of the weather itself)."""

    if "weather.current" not in frozenset(available_operations):
        return None
    if _weather_lookup_query(text) is None or len(_request_clauses(_fold(text))) != 1:
        return None
    return EffectIntent(("weather.current",), (text.strip(),))


def process_inventory_arguments(text: str) -> dict[str, object] | None:
    """Keep rank, metric and spoken page size bound to the process request."""
    text = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.")
    if not _process_list_domain(text):
        return None
    sorts = {
        sort for sort, pattern in (
            ("cpu", r"\b(?:cpu|procesador|processor)\b"),
            ("memory", r"\b(?:ram|memoria|memory|working set)\b"),
            ("name", r"\b(?:por nombre|by name)\b"),
        ) if _has(text, pattern)
    }
    if len(sorts) > 1:
        return None
    result: dict[str, object] = {"sort": next(iter(sorts))} if sorts else {}
    number = r"(?:\d+|" + "|".join(
        re.escape(word) for word in sorted(_PERCENTAGE_WORD_VALUES, key=len, reverse=True)
    ) + r")"
    sizes = list(re.finditer(
        rf"\b(?:top|primeros|first|hasta|up\s+to)\s+(?P<rank>{number})\b|"
        rf"\b(?P<count>{number})\s+(?:(?:running|active|activos)\s+)?"
        r"(?:procesos?|process(?:es)?)\b", text,
    ))
    values = set()
    for match in sizes:
        raw = match.group("rank") or match.group("count")
        values.add(int(raw) if raw.isdecimal() else _PERCENTAGE_WORD_VALUES[raw])
    # A number outside a rank frame may be a PID, threshold or another action.
    remainder = text
    for match in reversed(sizes):
        remainder = remainder[:match.start()] + remainder[match.end():]
    if len(values) > 1 or _has(remainder, r"\d"):
        return None
    if values:
        value = next(iter(values))
        if not 1 <= value <= 50:
            return None
        result["limit"] = value
    elif _has(text, r"\b(?:que proceso|which process|what process)\b"):
        result["limit"] = 1
    return result
