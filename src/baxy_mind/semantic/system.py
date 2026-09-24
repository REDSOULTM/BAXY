"""System: power, lock, battery, processes, hardware, weather, time and countdowns. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _fold, _has, _strip_request_envelope, _process_list_domain, _PERCENTAGE_WORD_VALUES, _request_clauses, _ENGLISH_SMALL_NUMBERS, _SPANISH_SMALL_NUMBERS
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
    # Each preposition opens a candidate: «clima de la semana en Buenos Aires»
    # names its time first and its place after.
    for match in re.finditer(r"\b(?:en|in|de|para|for|at)\s+(?=(?P<place>[^,;:.!?]+))", query, re.IGNORECASE):
        candidate = match.group("place").strip(" \t\r\n.,;:")
        if _has(_fold(candidate), _WEATHER_TIME_WORDS):
            continue
        place = _without_trailing_time(candidate)
        place = re.sub(r"^(?:la\s+ciudad\s+de|the\s+city\s+of)\s+", "", place, flags=re.IGNORECASE)
        folded_place = _fold(place)
        if (
            not folded_place
            or _has(folded_place, _WEATHER_MEDIUM)
            or _has(folded_place, _WEATHER_WORDS)
            # Uso real 2026-09-23 «va a llover el fin de semana?» read the weather of
            # «Sémana» (Mali): a time is not a place.
            or _has(folded_place, _WEATHER_TIME_WORDS)
            or len(place.encode("utf-8")) > 128
        ):
            continue
        return place
    return None


def _without_trailing_time(place: str) -> str:
    """«Buenos Aires para mañana» → «Buenos Aires»: a time or courtesy after the
    place (with or without its own preposition) is not part of the name."""

    words = place.split()
    for index in range(1, len(words)):
        tail = _fold(" ".join(words[index:]))
        tail = re.sub(r"^(?:para|for|de|del|en|in|on|a|al|this|este|esta)\s+", "", tail)
        if _has(tail, _WEATHER_TIME_WORDS) or _has(
            tail, r"^(?:ahora|now|right\s+now|por\s+favor|please)\b"
        ):
            return " ".join(words[:index])
    return place


# Uso real 2026-09-23 «pronóstico de diez días» asked the weather service for a
# place called «diez días», and «el weather para San Valentín» for a place
# called like the holiday: a span («los próximos 5 días», «the next 7 days») or
# a named day of the year is a time, not a place.
_WEATHER_SPAN_COUNT = r"(?:\d{1,3}|" + "|".join(
    sorted({*_SPANISH_SMALL_NUMBERS, *_ENGLISH_SMALL_NUMBERS}, key=len, reverse=True)
) + r")"
_WEATHER_TIME_WORDS = (
    r"^(?:(?:el|la|los|las|este|esta|estos|estas|the|this|these|next|coming|"
    r"proximo|proxima|proximos|proximas|siguiente|siguientes)\s+){0,2}"
    rf"(?:{_WEATHER_SPAN_COUNT}\s+)?(?:semanas?|finde|fin\s+de\s+semana|"
    r"weeks?|weekend|manana|tarde|noche|morning|afternoon|evening|night|hoy|today|tomorrow|"
    r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday|dia|dias|days?|mes|meses|months?|ano|anos|years?|"
    r"navidad|nochebuena|nochevieja|ano\s+nuevo|san\s+valentin|halloween|pascua|semana\s+santa|"
    r"dia\s+de\s+(?:los\s+)?(?:enamorados|muertos|la\s+madre|el\s+padre)|"
    r"christmas|new\s+year|valentine|easter|thanksgiving)\b"
)


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
