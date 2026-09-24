"""System: power, lock, battery, processes, hardware, weather, time and countdowns. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _fold, _has, _strip_request_envelope, _process_list_domain, _PERCENTAGE_WORD_VALUES, _request_clauses, _ENGLISH_SMALL_NUMBERS, _SPANISH_SMALL_NUMBERS, SPOKEN_NUMBER
from .intent import EffectIntent
from .temporal import is_window_phrase
from .web import _WEATHER_WORDS, _names_weather, _weather_lookup_query


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
    # names its time first and its place after. Uso real tanda 2 «tengo un
    # festival de música dentro de dos días. ¿Me llevo el chubasquero?»: when the
    # weather is asked only through the gear, an amount or a sun time, «de» and
    # «para» belong to other things («un festival de música», «para mañana»);
    # only «en», «in» and «at» name the place.
    prepositions = r"en|in|de|para|for|at" if _names_weather(_fold(query)) else r"en|in|at"
    for match in re.finditer(rf"\b(?:{prepositions})\s+(?=(?P<place>[^,;:.!?]+))", query, re.IGNORECASE):
        candidate = match.group("place").strip(" \t\r\n.,;:")
        if _names_a_time(_fold(candidate)):
            continue
        place = _without_trailing_time(candidate)
        place = re.sub(r"^(?:la\s+ciudad\s+de|the\s+city\s+of)\s+", "", place, flags=re.IGNORECASE)
        folded_place = _fold(place)
        if (
            not folded_place
            or _has(folded_place, _WEATHER_MEDIUM)
            or _has(folded_place, _WEATHER_WORDS)
            # Uso real 2026-09-23 «va a llover el fin de semana?» read the weather of
            # «Sémana» (Mali), tanda 3 «para la semana del 5 al 12 de julio» the weather
            # of «Júlio» (Mozambique): a time is not a place.
            or _names_a_time(folded_place)
            # MASSIVE «la temperatura será más alta de cuarenta grados mañana»: a measure is not a place.
            or _has(folded_place, rf"^{SPOKEN_NUMBER}\s*(?:grados|degrees|°|milimetros|mm|centimetros|cm|pulgadas|inches)\b")
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
        if _names_a_time(tail) or _names_a_time(re.sub(r"^(?:para|for|de|del|en|in|on|a|al)\s+", "", tail)) or _has(
            tail, r"^(?:ahora|now|right\s+now|por\s+favor|please)\b"
        ):
            return " ".join(words[:index])
    return place


def _names_a_time(folded: str) -> bool:
    """«la semana del 5 al 12 de julio», «julio», «el 4 de julio», «next monday», «navidad»: the words say a time
    (semantic.temporal reads dates, months, weekdays and spans; the list below adds holidays and counted spans)."""

    return _has(folded, _WEATHER_TIME_WORDS) or is_window_phrase(folded) or is_window_phrase("en " + folded)


# Uso real 2026-09-23 «pronóstico de diez días» asked the weather service for a
# place called «diez días», and «el weather para San Valentín» for a place
# called like the holiday: a span («los próximos 5 días», «the next 7 days») or
# a named day of the year is a time, not a place. Portuguese month spellings
# («julho») are months too; «janeiro» and «março» are left to Rio de Janeiro and
# to the Spanish word «marco».
_WEATHER_SPAN_COUNT = r"(?:\d{1,3}|" + "|".join(
    sorted({*_SPANISH_SMALL_NUMBERS, *_ENGLISH_SMALL_NUMBERS}, key=len, reverse=True)
) + r")"
_WEATHER_TIME_WORDS = (
    r"^(?:(?:el|la|los|las|este|esta|estos|estas|the|this|these|next|coming|"
    r"proximo|proxima|proximos|proximas|siguiente|siguientes|dentro\s+de)\s+){0,2}"
    rf"(?:{_WEATHER_SPAN_COUNT}\s+)?(?:semanas?|finde|fin\s+de\s+semana|"
    r"weeks?|weekend|manana|tarde|noche|morning|afternoon|evening|night|hoy|today|tomorrow|"
    r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday|dia|dias|days?|mes|meses|months?|ano|anos|years?|"
    r"navidad|nochebuena|nochevieja|ano\s+nuevo|san\s+valentin|halloween|pascua|semana\s+santa|"
    r"dia\s+de\s+(?:los\s+)?(?:enamorados|muertos|la\s+madre|el\s+padre)|"
    r"christmas|new\s+year|valentine|easter|thanksgiving|"
    r"fevereiro|maio|junho|julho|setembro|outubro|novembro|dezembro)\b"
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


# Uso real 2026-09-23 «prepárame una taza de café» → «¿Te refieres a que el café esté más suave o con menos
# ruido?»: food and drink are made or brought in the physical world, where BAXY has no hands; the honest turn is
# a plain limit, never a question about the PC. «pon en marcha una taza de café» (MASSIVE iot_coffee) starts it.
_ERRAND = (
    r"\b(?:prepara|preparame|preparar|prepararme|haz|hazme|hace|haceme|hacer|hacerme|"
    r"sirve|sirveme|servime|servirme|trae|traeme|traer|traerme|cocina|cociname|cocinar|"
    r"cocinarme|calienta|calientame|calentarme|pon(?:er|me)?\s+en\s+marcha|"
    r"make|brew|bring|cook|serve|fetch|pour|heat\s+up|start)\b"
    r"(?:\s+(?:me|us))?\s+(?:(?:un|una|unos|unas|el|la|los|las|mi|a|an|some|the|my)\s+)?"
    r"(?:(?:taza|tacita|vaso|copa|plato|jarra|cup|mug|glass|plate|bowl|pot)\s+(?:de|of)\s+)?"
    r"(?:cafe|cafecito|coffee|espresso|capuchino|cappuccino|latte|te|tecito|tea|mate|chocolate|"
    r"leche|milk|agua|water|jugo|zumo|juice|cerveza|beer|vino|wine|trago|drink|"
    r"comida|food|desayuno|breakfast|almuerzo|lunch|cena|dinner|sandwich|sandwiches|"
    r"sopa|soup|huevos?|eggs?|tostadas?|toast|pancakes|panqueques|snack|merienda)\b"
)
# MASSIVE iot_* (dev corpus 2026-09-23): the devices of the house are not this PC. An appliance is one by its
# name; a light or its colour is one only in a room of the house («las luces de la cocina», «colores oscuros en
# la casa»), since «baja las luces» alone is the screen's brightness here.
_HOME_APPLIANCE = (
    r"\b(?:cafetera|coffee\s+maker|aspiradora|robot\s+aspirador|roomba|vacuum(?:\s+cleaner)?|lavadora|"
    r"washing\s+machine|washer|secadora|dryer|lavavajillas|lavaplatos|dishwasher|horno|oven|microondas|"
    r"microwave|aire\s+acondicionado|air\s+condition(?:ing|er)|calefaccion|calefactor|heater|heating|"
    r"termostato|thermostat|persianas?|blinds|enchufes?\s+inteligentes?|smart\s+plugs?|bombillas?|bulbs?)\b"
)
_HOME_LIGHT = r"\b(?:luz|luces|lampara|lamparas|colores|light|lights|lamp|lamps|colou?rs)\b"
_HOME_ROOM = (
    r"\b(?:(?:en|de|del)\s+(?:la\s+|el\s+|mi\s+)?(?:casa|cocina|sala|salon|living|cuarto|habitacion|dormitorio|"
    r"bano|comedor|jardin|garaje|pasillo|patio)|"
    r"(?:in|of)\s+(?:the\s+|my\s+)?(?:house|home|kitchen|bedroom|living\s+room|bathroom|hallway|garden|garage))\b"
)
_HOME_CONTROL = (
    r"\b(?:enciende|encender|enciendeme|prende|prender|prendeme|apaga|apagar|apagame|pon|poner|ponme|"
    r"pon(?:er)?\s+en\s+marcha|arranca|arrancar|activa|activar|desactiva|desactivar|sube|subir|baja|bajar|"
    r"ajusta|ajustar|cambia|cambiar|regula|regular|atenua|atenuar|abre|abrir|cierra|cerrar|"
    r"turn\s+(?:on|off|up|down)|switch\s+(?:on|off)|start|stop|dim|brighten|set|open|close|run)\b"
)


def physical_world_request(folded: str) -> bool:
    """An errand with food or drink, or a device of the house to control (see above)."""

    return _has(folded, _ERRAND) or (
        _has(folded, _HOME_CONTROL)
        and (_has(folded, _HOME_APPLIANCE) or (_has(folded, _HOME_LIGHT) and _has(folded, _HOME_ROOM)))
    )
