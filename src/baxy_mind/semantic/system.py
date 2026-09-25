"""System: power, lock, battery, processes, hardware, weather, time and countdowns. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _fold, _has, _strip_request_envelope, _process_list_domain, _PERCENTAGE_WORD_VALUES, _request_clauses, _ENGLISH_SMALL_NUMBERS, _SPANISH_SMALL_NUMBERS, SPOKEN_NUMBER, _COVERAGE_ACTION_HEAD
from .intent import EffectIntent
from .temporal import is_window_phrase
from .web import AIR_QUALITY_WORDS, _SKY_MEASURE_WORDS, _WEATHER_SUN_TIME, _WEATHER_WORDS, _names_weather, _weather_lookup_query, asks_own_place, weather_asks_sun_time


_WEATHER_MEDIUM = (
    r"\b(?:google|bing|internet|la\s+web|the\s+web|online|en\s+linea)\b"
)
_GENERIC_PLACE = (
    r"^(?:(?:the|my|a|la|el|mi|una?)\s+)?(?:beach|playa|park|parque|lake|lago|mountains?|montana|office|oficina|pool|"
    r"piscina|stadium|estadio|school|colegio|escuela|work|trabajo|home|casa|river|rio|field|campo|golf\s+course|"
    r"cancha|centro|downtown|calle|street)$"
)
_PART_OF_TOWN = (
    r"^(?:(?:la\s+ciudad|el\s+centro|centro|las\s+afueras|the\s+city|the\s+cent(?:er|re)|the\s+outskirts)\s+(?:de|del|of)\s+|"
    r"(?:down\s*town|mid\s*town|up\s*town)\s+)"
)


def _weather_location(text: str) -> str | None:
    """REOPEN1993 (grupo W): the place the person named for the weather («en
    Buenos Aires», «in Madrid»), with their own spelling; None when no place is
    named (the read then uses this PC's own location) or the words after the
    preposition are a medium («en google», «en internet»)."""

    query = _weather_lookup_query(text)
    if query is None or asks_own_place(text):
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
        if _has(_fold(match.group(0)), r"^(?:para|for)\b") and _has(
            _fold(candidate), r"^(?:\w+(?:ar|er|ir)(?:me|te|se|nos|lo|la|los|las)?|\w+ing|to\s+\w+)\b"
        ):
            # MASSIVE weather_query «es necesario llevar paraguas para salir»: «para» before a verb says what for.
            continue
        place = _without_trailing_time(candidate)
        # Uso real tanda 5 «wat level of air pollution hay en downtown Houston»: the weather service
        # knows no «downtown Houston»; the part of the town is not its name.
        place = re.sub(_PART_OF_TOWN, "", place, flags=re.IGNORECASE)
        folded_place = _fold(place)
        if (
            # Tanda 5 «en tus aplicaciones del tiempo», tanda 4f «en una terraza en Sevilla»: a thing said with «tu»,
            # «mi» or «una» is not the name of a town, and the next preposition may still name one. «a» is an
            # article only before another place («at a cafe in Paris»); «A Coruña» is a town.
            re.match(r"(?:mis?|tus?|sus?|nuestr[oa]s?|my|your|our|un|una|unos|unas|an|some)\s", folded_place)
            or re.match(r"a\s+\w+(?:\s+\w+)?\s+(?:in|en|at)\s", folded_place)
            or not folded_place
            or _has(folded_place, _WEATHER_MEDIUM)
            or _has(folded_place, _WEATHER_WORDS)
            or _has(folded_place, AIR_QUALITY_WORDS)
            # Uso real tanda 6 «i'm meeting a friend at sunrise tomorrow»: «at sunrise» is a time of the day.
            or _has(folded_place, _WEATHER_SUN_TIME)
            # Uso real tanda 6: «punto de rocío» and «índice de radiación UV» are one measure, not «de» a place.
            or _has(" ".join([*_fold(query[:match.start()]).split()[-1:], _fold(match.group(0)), folded_place]),
                    _SKY_MEASURE_WORDS)
            # Uso real 2026-09-23 «va a llover el fin de semana?» read the weather of
            # «Sémana» (Mali), tanda 3 «para la semana del 5 al 12 de julio» the weather
            # of «Júlio» (Mozambique): a time is not a place.
            or _names_a_time(folded_place)
            # «clima para el día de la madre» read the weather of «la madre»: «de» after «día» names the day.
            or _fold(query[:match.start()]).split()[-1:] in (["dia"], ["dias"])
            # MASSIVE «la temperatura será más alta de cuarenta grados mañana»: a measure is not a place.
            or _has(folded_place, rf"^{SPOKEN_NUMBER}\s*(?:grados|degrees|°|milimetros|mm|centimetros|cm|pulgadas|inches)\b")
            # MASSIVE «will it be nice at the beach on friday»: a kind of place is where the person goes, not a town.
            or _has(folded_place, _GENERIC_PLACE)
            # Tanda 7: «casa de mi hermana» is no town; a town may still be named after it («… en Lima»).
            or _has(folded_place, rf"^(?:{_SOMEONES_PLACE})")
            or len(place.encode("utf-8")) > 128
        ):
            continue
        return place
    return None


# Tanda 7 «¿Va a llover tomorrow at my sister's?» was answered for this PC's town as «en casa de tu hermana»: a
# place said only through a person («casa de mi hermana», «lo de mi vieja», «where my dad lives», «at my mom's»)
# is somewhere BAXY does not know. It is asked, never taken for here.
_SOMEONES_PLACE = (
    r"\b(?:(?:la\s+)?casa\s+de\s+(?:mi|mis|tu|tus|su|sus|nuestr[oa]s?)\s+\w+|lo\s+de\s+(?:mi|mis|tu|tus|su|sus)\s+\w+|"
    r"donde\s+(?:vive|viven|trabaja|trabajan|esta|estan)\s+(?:mi|mis|tu|tus|su|sus)\s+\w+|"
    r"(?:at|to|in|near|by)\s+(?:my|your|his|her|our|their)\s+\w+['’]s\b|"
    r"(?:my|your|his|her|our|their)\s+\w+['’]s\s+(?:house|place|home)|"
    r"where\s+(?:my|your|his|her|our|their)\s+\w+\s+(?:lives|live|works|work|is|are|stays))"
)


def weather_place_known_only_through_someone(text: str) -> bool:
    """The weather is asked for a place said only through a person, with no town named."""

    return _has(_fold(text), _SOMEONES_PLACE) and _weather_location(text) is None


def _without_trailing_time(place: str) -> str:
    """«Buenos Aires para mañana» → «Buenos Aires»: a time or courtesy after the
    place (with or without its own preposition) is not part of the name."""

    words = place.split()
    for index in range(1, len(words)):
        tail = _fold(" ".join(words[index:]))
        if _names_a_time(tail) or _names_a_time(re.sub(r"^(?:para|for|de|del|en|in|on|a|al)\s+", "", tail)) or _has(
            # Tanda 4c «puesta de sol en Mendoza a qué hora»: the question asked after the place.
            # Tanda 9: «el tiempo de Sevilla porfa» — the courtesy said short is not part of the town either.
            tail, r"^(?:ahora|now|right\s+now|por\s+favor|porfa|porfis|please|pls|plz|"
            r"(?:a\s+)?(?:que|what)\s+(?:hora|time)|cuando|when)\b"
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
    # Tanda 8 «¿Cómo estará the weather en el fin the semana de Memorial Day?» read the weather of «El Final»
    # (Chiapas): the weekend with the English article the ear put for «de», and a holiday named «X Day» (as
    # «día de X» already is by «dia»), are times too.
    rf"(?:{_WEATHER_SPAN_COUNT}\s+)?(?:semanas?|finde|fin\s+(?:de|the|d)\s+semana|long\s+weekend|"
    r"weeks?|weekend|manana|tarde|noche|morning|afternoon|evening|night|hoy|today|tomorrow|ahora|now|"
    r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday|dia|dias|days?|mes|meses|months?|ano|anos|years?|"
    r"navidad|nochebuena|nochevieja|ano\s+nuevo|san\s+valentin|halloween|pascua|semana\s+santa|"
    r"feriado|festivo|fiestas\s+patrias|(?:[a-z]+(?:'s|s)?\s+){1,2}day|"
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
    if _weather_lookup_query(text) is None:
        return None
    clauses = _request_clauses(_fold(text))
    if len(clauses) != 1 and not _sun_time_asked_after_it(clauses):
        return None
    return EffectIntent(("weather.current",), (text.strip(),))


# Uso real tanda 6 «he quedado con un amigo a la salida del sol mañana para correr, ¿qué hora será?» searched the
# whole sentence and ended in ⚠: the sun time is named in what the person tells, and the question after it only
# asks when that is. Two clauses, the first no order, the second a bare question of the time. «¿qué hora es?» and
# «what time is it» ask this PC's clock, not when the sun rises.
_BARE_TIME_QUESTION = (
    r"^[¿¡\s]*(?:a\s+que\s+hora(?:\s+(?:sera|es|seria))?|que\s+hora\s+(?:sera|seria)|"
    r"(?:at\s+)?what\s+time(?:\s+(?:is\s+that|will\s+(?:that|it)\s+be|would\s+that\s+be))?|"
    r"cuando\s+(?:sera|es)|when\s+(?:is\s+that|will\s+(?:that|it)\s+be))[\s?!.]*$"
)


def _sun_time_asked_after_it(clauses: tuple[str, ...]) -> bool:
    return (
        len(clauses) == 2
        and weather_asks_sun_time(clauses[0])
        and re.match(rf"^[¿¡\s]*(?:{_COVERAGE_ACTION_HEAD})\b", clauses[0]) is None
        and _has(clauses[1], _BARE_TIME_QUESTION)
    )


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
