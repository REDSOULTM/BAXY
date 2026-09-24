"""Network: Wi-Fi and Bluetooth state and control. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _CLOCK_READ_HEAD, _fold, _match, _has, _REQUEST_PREFIX, _strip_request_envelope, _request_head, _head_is, _negative_action_forms, _machine_status_scopes_are_one_reading, _machine_status_is_the_whole_clause, _system_status_domain, _process_list_domain, _network_status_domain, _LIST, _COVERAGE_ACTION_HEAD, _MACHINE_STATUS_OBSERVATION_HEAD, _MACHINE_STATUS_HEAD, _MACHINE_STATUS_OBSERVATION
from .audio import _volume_domain
from .intent import EffectIntent, _is_negated_match, _append
from .normalize import alternation
from .temporal import MONTH_NUMBERS, _WEEKDAYS, countdown_target


def _direct_current_time_request(folded: str) -> bool:
    """Recognize a whole request for the local clock, shared by all three gates.

    Only present/local modifiers belong to this reading. Event dates, elapsed
    CPU time, other places and literal content must not match a trailing noun.
    """

    if countdown_target(folded) is not None:
        return True
    # Fase 3.5: trailing courtesy («decime la hora porfa») is not part of the reading.
    folded = re.sub(r"[\s,]*(?:por\s+favor|porfa|porfis|please|pls|plz)[\s.!?]*$", "", folded)
    # CLOCK1327 H0054/H0312 «Tiempo»/«tiempo»: the bare word asks for the
    # time; the weather is not something this PC reads.
    if re.fullmatch(r"(?:el\s+)?tiempo(?:\s*,?\s*(?:por\s+favor|porfa|please))?",
                    _strip_request_envelope(folded).strip(" ¿?¡!.,")):
        return True
    # Fase 3.5 (layer C «Dime la hora exacta»): «exacta/precisa» also ask for the present clock.
    current = r"(?:actual|local|exacta|exactamente|precisa|exact|(?:de\s+)?hoy|ahora(?:\s+mismo)?|(?:right\s+)?now)"
    nominal = (
        r"(?:(?:la|el|the)\s+)?"
        r"(?:(?:current|local)\s+){0,2}(?:hora|fecha|time|date)"
        rf"(?:\s+{current}){{0,2}}|today(?:['’]s)?\s+date"
    )
    observation = (
        rf"(?:{_CLOCK_READ_HEAD}|"
        r"(?:necesito|quiero|quisiera)\s+saber|"
        r"(?:i\s+)?(?:need|want)\s+to\s+know)"
    )
    request = _strip_request_envelope(folded).strip(" ¿?¡!.")
    if _PRESENT_CALENDAR_QUESTION.fullmatch(request) is not None:
        return True
    return re.fullmatch(
        rf"(?:{observation}\s+(?:{nominal})|"
        rf"(?:what(?:\s+is|'s|’s|s)\s+(?=(?:the|current|local|today)\b)|"
        rf"(?:que|cual)\s+es\s+)(?:{nominal})|"
        rf"(?:{observation}\s+)?(?:"
        r"(?:que|qe)\s+(?:hora|ora|fecha|dia)\s+es(?:\s+(?:ahora|hoy|ya|exactamente))?|"
        # Uso real 2026-09-23 «¿en qué día de la semana estamos?»: the day and
        # the weekday of this PC's own calendar are the same clock read.
        r"(?:en\s+)?(?:que|qe)\s+(?:fecha|dia(?:\s+de\s+la\s+semana)?)\s+"
        r"(?:es|estamos)(?:\s+(?:ahora|hoy))?|"
        r"what\s+day\s+of\s+the\s+week\s+is\s+(?:it|today)(?:\s+today)?|"
        r"what\s+(?:time|date|day)\s+is\s+it(?:\s+(?:(?:right\s+)?now|today))?)|"
        # «la fecha hoy», «la hora actual»: the noun with its article and a present modifier.
        rf"(?:(?:la|el|the)\s+)?(?:hora|fecha)\s+{current}|(?:current|local)\s+(?:local\s+)?(?:time|date)|"
        rf"today(?:['’]s)?\s+date|(?:{observation}\s+)?"
        r"(?:the\s+)?time\s+(?:right\s+now|now)"
        r"(?:\s*[,;:]?\s*what\s+is\s+it)?|"
        r"que\s+hora\s+(?:marca|muestra|tiene)\s+(?:este|el|mi)\s+"
        r"(?:computador|equipo|pc)|"
        r"what\s+time\s+does\s+(?:this|the|my)\s+(?:computer|pc)\s+(?:show|display)|"
        r"(?:search|look|busca)\s+(?:to\s+)?(?:find|encontrar)\s+"
        r"(?:(?:the|la)\s+)?(?:current|actual)\s+(?:local\s+)?"
        r"(?:time|hora)(?:\s+(?:and|y)\s+(?:time\s+zone|zona\s+horaria))?)",
        request,
        re.IGNORECASE,
    ) is not None


# Tanda 3 2026-09-24 «what day are we in» (asked back «Want me to tell you the current date?») and «¿estamos a enero o
# febrero?» (searched on the web): which day, date, weekday, month or year it is now is this PC's calendar, asked
# however it is asked — «en qué mes estamos», «a cuántos estamos», «¿hoy es lunes?», «what year is it», «is today
# friday», «do you know what day it is». The whole message must be the question: «qué día es el partido», «en qué año
# nació Messi», «what date is easter» ask for the date of something else.
_CALENDAR_UNIT = r"(?:dia(?:\s+de\s+la\s+semana)?|fecha|mes|ano|day(?:\s+of\s+the\s+week)?|date|month|year|weekday)"
_CALENDAR_NAME = alternation(tuple(MONTH_NUMBERS) + tuple(name for names in _WEEKDAYS for name in names))
_CALENDAR_NAMES = rf"{_CALENDAR_NAME}(?:\s+(?:o|u|or)\s+(?:(?:a|en)\s+)?{_CALENDAR_NAME})*"
_CALENDAR_NOW = r"(?:\s+(?:hoy|ahora(?:\s+mismo)?|ya|today|now|right\s+now))?"
_CALENDAR_ASK = (
    r"(?:(?:sabes|sabe|sabrias|me\s+(?:dices|decis|puedes\s+decir)|dime|decime|do\s+you\s+know|"
    r"(?:can|could)\s+you\s+tell\s+me|tell\s+me)\s+)?"
)
# Tanda 4 «¿qué mes sale ahora mismo en el calendario de mi casa?» read the Outlook agenda: what a calendar or a
# clock shows now is today's date, whoever's wall it hangs on.
_CALENDAR_DISPLAY = (
    r"(?:el|la|mi|the|my)\s+(?:calendario|calendar|reloj|clock)(?:\s+(?:de|of)\s+(?:mi|la|el|my|the)\s+\w+)?"
)
_CALENDAR_SHOWN = (
    r"(?:(?:sale|marca|muestra|dice|aparece|pone|indica|shows?|says?|displays?)"
    r"(?:\s+(?:hoy|ahora(?:\s+mismo)?|today|now|right\s+now))?"
    rf"(?:\s+(?:(?:en|on|in)\s+)?{_CALENDAR_DISPLAY})?|"
    rf"(?:does|is)\s+{_CALENDAR_DISPLAY}\s+(?:show|say|display)(?:ing)?)"
    r"(?:\s+(?:hoy|ahora(?:\s+mismo)?|today|now|right\s+now))?"
)
_PRESENT_CALENDAR_QUESTION = re.compile(
    rf"{_CALENDAR_ASK}(?:"
    rf"(?:en|a)\s+(?:que|cual)\s+{_CALENDAR_UNIT}\s+(?:estamos|nos\s+encontramos){_CALENDAR_NOW}|"
    rf"(?:hoy\s+)?(?:que|cual)\s+{_CALENDAR_UNIT}\s+(?:es|tenemos|estamos|cae){_CALENDAR_NOW}|"
    rf"(?:que|cual|what|which)\s+{_CALENDAR_UNIT}\s+{_CALENDAR_SHOWN}|"
    rf"a\s+(?:cuantos|que(?:\s+dia)?)\s+estamos{_CALENDAR_NOW}|"
    rf"(?:ya\s+)?(?:hoy\s+)?(?:es|estamos\s+(?:a|en))\s+{_CALENDAR_NAMES}{_CALENDAR_NOW}|"
    rf"(?:what|which)\s+{_CALENDAR_UNIT}\s+(?:is\s+it|it\s+is|is\s+today|today\s+is|is\s+this|"
    rf"are\s+we\s+(?:in|on|at)|we\s+are\s+(?:in|on|at)){_CALENDAR_NOW}|"
    r"what(?:\s+is|'s|’s|s)\s+(?:today|the\s+(?:day|date|month|year)(?:\s+(?:today|now))?|today['’]?s\s+(?:date|day))|"
    r"today\s+is\s+what\s+(?:day|date)|"
    rf"is\s+(?:it|today)\s+{_CALENDAR_NAMES}(?:\s+today)?"
    r")"
)


# The month and weekday names, but the English «may» («may I know the time») asks for nothing.
_CALENDAR_PART_NAME = alternation(
    tuple(name for name in MONTH_NUMBERS if name != "may") + tuple(name for names in _WEEKDAYS for name in names)
)


def asks_calendar_part(text: str) -> bool:
    """Whether a clock question asks for part of the date (day, date, weekday, month or year) rather than the time.

    Tanda 3 «¿estamos a enero o febrero?» read the clock and was answered «Son 02:54.»: the month asked, said by
    its name, is the date too. A calendar unit, a month or weekday name, or «a cuántos estamos» asks for it. The
    App's visible policy (UserMessagePolicy.AsksCalendarPart) reads the same words; the two must not diverge."""

    return _has(_fold(text), rf"\b(?:{_CALENDAR_UNIT}|{_CALENDAR_PART_NAME}|a\s+cuantos\s+estamos)\b")


def _direct_process_inventory_request(text: str) -> bool:
    return _process_list_domain(text) and _has(
        text, rf"^[¿?¡!\s]*{_REQUEST_PREFIX}(?:{_LIST}|mostrame|dime|dame|tell|"
        r"cuenta|count|ordena|sort|quiero|which|what|que|cual|cuales|cuantos|how)\b",
    )


def _local_internet_connection_query(text: str) -> bool:
    """A current local connection check is not a request for internet content."""
    machine_en = r"(?:this|the|my)\s+(?:computer|pc|machine)"
    machine_es = r"(?:este|el|mi)\s+(?:equipo|pc|computador(?:a)?|ordenador)"
    state_en = r"(?:connected\s+to\s+(?:the\s+)?internet|online)"
    state_es = r"conectad[oa]\s+a\s+internet"
    return re.fullmatch(
        rf"[¿?\s]*(?:"
        rf"(?:is\s+{machine_en}|am\s+i)\s+{state_en}|"
        rf"(?:check|verify)\s+(?:whether|if)\s+{machine_en}\s+is\s+{state_en}|"
        rf"esta\s+{machine_es}\s+{state_es}|"
        rf"(?:comprueba|revisa|verifica)\s+si\s+{machine_es}\s+esta\s+{state_es}"
        r")(?:\s+(?:right\s+now|now|ahora|actualmente))?[.!?\s]*",
        text,
        re.IGNORECASE,
    ) is not None


# «me queda…», «me alcanza…»: el clítico dativo abre una pregunta de estado
# solo con uno de estos verbos. «Me interesa…» o «me gustaría…» no lo son, así
# que el clítico nunca entra suelto en la lista de cabezas.
_DATIVE_STATE_OPENING = (
    r"me\s+(?:queda|quedan|quedaba|alcanza|alcanzan|sobra|sobran|falta|faltan|"
    r"dices|dice|decis|puedes decir|podrias decir)"
)


# «modelo» abre una pregunta de estado solo cuando el objeto es una pieza de
# este equipo. Suelto encabeza notas de configuración («Modelo FT Q4_K_M…»).
_HARDWARE_MODEL_OPENING = (
    r"(?:modelo|model)\s+(?:de\s+)?"
    r"(?:(?:mi|la|el|este|esta|my|the|this)\s+)?"
    r"(?:gpu|vram|tarjeta|placa|procesador|processor|cpu|video|"
    r"graphics|equipo|pc|computador|computadora|computer)"
)


_WIFI_STATE_QUESTION = re.compile(
    r"\bwi[\s-]?fi\s+(?:esta|is|anda)\s+(?:prendid[oa]|encendid[oa]|apagad[oa]|"
    r"activ[oa]|activad[oa]|desactivad[oa]|conectad[oa]|funcionando|on|off|"
    r"enabled|disabled|connected|working)\b|"
    r"\b(?:esta|is)\s+(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|on|off|enabled)\s+"
    r"(?:el\s+|the\s+)?wi[\s-]?fi\b",
    re.IGNORECASE,
)


_BLUETOOTH_STATE_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «tengo el bluetooth encendido», «¿tengo el bluetooth prendido?»
    r"(?:tengo|tenes|tienes|dejaste|deje|do\s+i\s+have)\s+(?:el\s+|the\s+)?bluetooth\s+"
    r"(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|activad[oa]|desactivad[oa]|on|off|enabled|disabled)|"
    # «el bluetooth está prendido?», «bluetooth is on?»
    r"(?:el\s+|the\s+)?bluetooth\s+(?:esta|is|anda|queda|quedo)\s+"
    r"(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|activad[oa]|desactivad[oa]|on|off|enabled|disabled)|"
    # «está encendido el bluetooth?», «is the bluetooth on?»
    r"(?:esta|is)\s+(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|activad[oa]|on|off|enabled)\s+(?:el\s+|the\s+)?bluetooth|"
    # «y el bluetooth?», «and bluetooth?»: the state question with no antecedent.
    r"(?:y|and)\s+(?:el\s+|the\s+)?bluetooth"
    r")\b[\s?!.,]*$",
    re.IGNORECASE,
)


def _bluetooth_state_question(text: str) -> bool:
    """NETWORK1457 «tengo el bluetooth encendido», «y el bluetooth?»: a
    bluetooth.radio.status read — the radio's state, never a device list."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _BLUETOOTH_STATE_QUESTION.match(folded) is not None
        and not _has(folded, r"\b(?:dispositivo|device|auriculares?|headphones?|parlante|speaker)\b")
    )


_WIFI_SCAN_QUESTION = re.compile(
    r"(?:^|\b)(?:que|cuales|cuantas|what|which|how many)\s+(?:(?:wifi|wi[\s-]*fi|wireless)\s+)?(?:redes|networks)(?:\s+(?:wifi|wi[\s-]*fi|inalambricas|wireless))?\s+(?:are\s+)?(?:hay|existen|veo|ves|detectas|encontras|encuentras|alcanzas|disponibles|cerca|cercanas|around|nearby|available|there|can you see|do you see)\b"
    r"|\b(?:escanea|escaneame|escanear|scan|busca|buscame|buscar|search for|list|lista|listame|listar|mostrame|muestrame|show)\b.{0,24}\b(?:redes|networks)(?:\s+(?:wifi|wi[\s-]*fi|inalambricas|wireless))?\b"
    r"|\b(?:redes|networks)\s+(?:wifi|wi[\s-]*fi|inalambricas|wireless)\s+(?:disponibles|cercanas|visibles|available|nearby|visible|around)\b"
)


_WIFI_RADIO_SET_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?P<verb>prende|prendeme|prender|encende|encendeme|encender|enciende|activa|activame|activar|turn\s+on|switch\s+on|enable|"
    r"apaga|apagame|apagar|desactiva|desactivame|desactivar|turn\s+off|switch\s+off|disable)\s+"
    r"(?:me\s+)?(?:el\s+|la\s+|the\s+)?(?:radio\s+)?(?:wifi|wi[\s-]*fi|wireless|red\s+inalambrica)"
    r"(?:\s+(?:del\s+|de\s+la\s+|of\s+the\s+)?(?:pc|computadora|compu|equipo|laptop|notebook|computer))?[\s.!?]*$"
)


_WIFI_OFF_OFFER = re.compile(
    r"(?:wifi|wi[\s-]*fi|radio|antena).{0,80}(?:apagad|off).{0,160}\?|(?:apagad|off).{0,80}(?:wifi|wi[\s-]*fi).{0,160}\?"
)


_ASSENT_TO_OFFER = re.compile(
    r"^[¿?¡!\s]*(?:si|sí|dale|ok|okey|okay|bueno|claro|obvio|por\s+favor|yes|yeah|yep|sure|please|go\s+ahead|do\s+it|hacelo|hazlo|prendelo|encendelo|enciendelo|prende|encende|turn\s+it\s+on)"
    r"(?:[,\s]+(?:si|sí|dale|por\s+favor|please|hacelo|hazlo|prendelo|encendelo|enciendelo|y\s+busca|y\s+escanea|and\s+scan|prende\s+el\s+wifi|encende\s+el\s+wifi|turn\s+it\s+on|turn\s+on\s+the\s+wifi))*[\s.!?]*$"
)


_ACCEPTED_WIFI_OFFER_EVIDENCE = "encender el wifi y buscar redes (oferta aceptada)"


def _accepted_wifi_offer_evidence(evidence: str) -> bool:
    return evidence == _ACCEPTED_WIFI_OFFER_EVIDENCE


# REOPEN1957 H0170/H0376 «conectate al wifi de casa» (D24): «casa» names a
# place, not a saved network. The words the person may use for each place; the
# canonical key is what the provider remembers the association under.
_WIFI_PLACE_ALIASES = {
    "casa": "casa", "mi casa": "casa", "la casa": "casa", "home": "casa", "my home": "casa",
    "my house": "casa", "the house": "casa", "house": "casa",
    "trabajo": "trabajo", "mi trabajo": "trabajo", "el trabajo": "trabajo", "work": "trabajo",
    "my work": "trabajo", "the job": "trabajo",
    "oficina": "oficina", "la oficina": "oficina", "mi oficina": "oficina", "office": "oficina",
    "my office": "oficina", "the office": "oficina",
}


_WIFI_PLACE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:por\s+favor[,\s]+)?(?:baxy[,\s]+)?(?:podes|podrias|puedes|can\s+you|could\s+you)?\s*"
    r"(?:"
    r"(?:conecta|conectar|conectarme|conectarte|conectame|conectate|connect(?:\s+me)?)\s+"
    r"(?:(?:al|a\s+la|a|to|to\s+the|to\s+my)\s+)?(?:(?:red|network)\s+)?wi[\s-]?fi(?:\s+(?:network|red))?\s+"
    r"(?:de|del|de\s+la|of|of\s+the|of\s+my)\s+(?P<place_a>[a-z ]+?)"
    r"|(?:conecta|conectar|conectarme|conectarte|conectame|conectate|connect(?:\s+me)?)\s+"
    r"(?:(?:al|a\s+la|a|to|to\s+the|to\s+my)\s+)?(?:the\s+|my\s+)?(?P<place_b>home|work|office|house)\s+"
    r"(?:wi[\s-]?fi|network|red)(?:\s+(?:network|red))?"
    r"|(?:cambia|cambiar|cambiate|change|switch)\s+(?:(?:el|the)\s+)?wi[\s-]?fi\s+(?:al|a|to)\s+"
    r"(?:(?:el|la|the)\s+)?(?:(?:de|of)\s+)?(?P<place_c>[a-z ]+?)"
    r")[\s.!?]*$"
)


def wifi_place_request(text: str) -> str | None:
    """«conectate al wifi de casa», «connect to my home wifi», «cambia el wifi
    al de casa» → the canonical place («casa»); a name that is not a place
    («wifi de la luna», «wifi de Galaxy») abstains and stays a profile name."""

    folded = _strip_request_envelope(_fold(text)).strip()
    if not folded or _negative_action_forms(folded):
        return None
    match = _WIFI_PLACE_REQUEST.match(folded)
    if match is None:
        return None
    raw = next(
        group for group in (match.group("place_a"), match.group("place_b"), match.group("place_c")) if group
    )
    return _WIFI_PLACE_ALIASES.get(" ".join(raw.split()))


_WIFI_PLACE_QUESTION = re.compile(
    r"\b(?:cual|cuales|which|what)\b.{0,80}\b(?:red(?:es)?|wi[\s-]?fi|network|networks)\b|"
    r"\b(?:red(?:es)?|wi[\s-]?fi|network|networks)\b.{0,80}\b(?:cual|cuales|which|what)\b|"
    r"\b(?:como\s+se\s+llama|what(?:'s| is)\s+(?:it|the\s+name))\b"
)


def wifi_place_answer(text: str, history: object) -> tuple[str, str] | None:
    """REOPEN1957 H0170/H0376: after «conectate al wifi de casa» BAXY listed the
    saved networks and asked which one is the home one; the person's short
    answer names it («Fibertel-2G», «es la Fibertel», «se llama Vecino 5G»).
    The explicit forms stand on the previous request alone; a bare name needs
    the assistant's question in the history, so a greeting after the request
    is never read as a network name."""

    if not isinstance(history, list):
        return None
    items = [item for item in history if isinstance(item, dict)]
    if items and items[-1].get("role") == "user" and items[-1].get("content") == text:
        items = items[:-1]
    previous = next((str(item.get("content") or "") for item in reversed(items) if item.get("role") == "user"), "")
    assistant = next((str(item.get("content") or "") for item in reversed(items) if item.get("role") == "assistant"), "")
    place = wifi_place_request(previous) if previous else None
    if place is None:
        return None
    answer = text.strip().strip("\"'“”«»").strip()
    folded = _strip_request_envelope(_fold(answer))
    if not folded or "?" in answer or len(folded.split()) > 6:
        return None
    if _head_is(_request_head(folded), _COVERAGE_ACTION_HEAD) or _negative_action_forms(folded):
        return None
    if re.fullmatch(
        r"(?:no|nada|ninguna?|none|nothing|cancela|cancelar|cancel|olvidalo|dejalo|si|dale|ok|okey|bueno|gracias|hola|thanks)\b.*",
        folded,
    ):
        return None
    explicit = re.match(
        r"^(?:es|se\s+llama|it'?s|it\s+is|its\s+name\s+is|the\s+(?:network|wifi)\s+is|"
        r"(?:la|el)\s+(?:red|wifi)(?:\s+de\s+\w+)?\s+(?:es|se\s+llama)|(?:la|el)\s+de\s+\w+\s+(?:es|se\s+llama))\s+(?P<name>.+)$",
        answer,
        re.IGNORECASE,
    )
    if explicit is not None:
        name = explicit.group("name")
    elif assistant and _WIFI_PLACE_QUESTION.search(_fold(assistant)) is not None:
        name = answer
    else:
        return None
    name = re.sub(r"^(?:la|el|the)\s+(?=\S)", "", name.strip(), flags=re.IGNORECASE).strip(" .!\"'“”«»")
    if not name or len(name.encode("utf-8")) > 256 or re.search(r"\b(?:y|and|or|o)\b|[&,/\\]", _fold(name)):
        return None
    return name, place


def wifi_place_answer_intent(text: str, history: object, available_operations: Iterable[str]) -> EffectIntent | None:
    """The answer alone is the evidence of one wifi.connect.named; the arguments
    are grounded from the same surface (name + place) with the history."""

    if "wifi.connect.named" not in frozenset(available_operations):
        return None
    return EffectIntent(("wifi.connect.named",), (text,)) if wifi_place_answer(text, history) is not None else None


def accepted_wifi_offer(
    text: str,
    history: object,
    available_operations: Iterable[str],
) -> EffectIntent | None:
    """NETWORK1737: the person asked which networks there are, the assistant said the
    Wi-Fi radio is off and offered to turn it on, and the person now assents
    → turn the radio on (confirmed) and scan. Nothing else reads an assent."""

    available = frozenset(available_operations)
    if not {"wifi.radio.set", "wifi.scan"} <= available or not isinstance(history, list):
        return None
    if _ASSENT_TO_OFFER.match(_strip_request_envelope(_fold(text)).strip()) is None:
        return None
    items = [item for item in history if isinstance(item, dict)]
    if items and items[-1].get("role") == "user" and items[-1].get("content") == text:
        items = items[:-1]
    assistant = next((str(item.get("content") or "") for item in reversed(items) if item.get("role") == "assistant"), "")
    previous = next((str(item.get("content") or "") for item in reversed(items) if item.get("role") == "user"), "")
    if not assistant or not previous:
        return None
    if _WIFI_OFF_OFFER.search(_fold(assistant)) is None or not _wifi_scan_question(previous):
        return None
    return EffectIntent(("wifi.radio.set", "wifi.scan"), (_ACCEPTED_WIFI_OFFER_EVIDENCE, _ACCEPTED_WIFI_OFFER_EVIDENCE))


def wifi_radio_set_request(text: str) -> bool | None:
    """NETWORK1737 «prendé el wifi», «apagá el wifi», «turn on the wifi»: the desired
    radio state, or None when the text is not that order."""

    folded = _strip_request_envelope(_fold(text)).strip()
    found = _WIFI_RADIO_SET_REQUEST.match(folded)
    if found is None:
        return None
    return not _has(found.group("verb"), r"^(?:apaga|apagame|apagar|desactiva|desactivame|desactivar|turn\s+off|switch\s+off|disable)$")


def _wifi_scan_question(text: str) -> bool:
    """NETWORK1729 «qué redes wifi hay», «escaneá las redes wifi», «what wifi networks
    are there»: a wifi.scan read of the networks the adapter sees — never a
    connection, a change of the radio, nor the saved-profile listing."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _WIFI_SCAN_QUESTION.search(folded) is not None
        and _has(folded, r"\b(?:wifi|wi[\s-]*fi|inalambric\w*|wireless|redes|networks)\b")
        and not _has(folded, r"\b(?:conecta\w*|desconecta\w*|connect|apaga\w*|prende\w*|enciende\w*|turn|guardad\w*|saved|perfiles?|profiles?|olvida\w*|forget|borra\w*|delete)\b")
    )


def _wifi_state_question(text: str) -> bool:
    """«decime si el wifi está prendido», «¿el wifi está encendido?»: a wifi.status read."""

    return (
        _WIFI_STATE_QUESTION.search(text) is not None
        and not _has(
            text,
            r"\b(?:apaga\w*|prende\w*|enciende\w*|encende\w*|activa\w*|desactiva\w*|"
            r"conecta\w*|desconecta\w*|turn|enable|disable)\b",
        )
        # «… y apagalo»: a second action makes it a compound, not a bare read.
        and not _has(text, r"\b(?:y|and)\s+\w")
    )


def _review_system_and_network_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
) -> None:
    """Append read-only system, network, and nearby-device effects."""

    if _direct_current_time_request(folded):
        _append(matches, folded, "system.time", r"\b(?:hora|time|fecha|date)\b")
    process_domain = _process_list_domain(folded)
    if _direct_process_inventory_request(folded):
        _append(
            matches,
            folded,
            "system.process.list",
            r"^",
        )
    if (
        not any(entry[2] == "system.process.list" for entry in matches)
        and process_domain
        and _has(folded, r"\b(?:programas?|programs?|apps?|aplicaciones?)\b")
        and _has(
            folded,
            r"\b(?:memoria|memory|cpu|ram|comiendo|eating)\b",
        )
        and not _has(folded, r"\b(?:instalad[oa]s?|installed)\b")
    ):
        _append(
            matches,
            folded,
            "system.process.list",
            r"^",
        )
    if (
        not any(entry[2] == "system.process.list" for entry in matches)
        and (
            _head_is(head, rf"(?:{_MACHINE_STATUS_HEAD}|tell)")
            or _has(
                folded,
                rf"^[¿?¡!\s]*(?:{_DATIVE_STATE_OPENING}|"
                rf"{_HARDWARE_MODEL_OPENING})\b",
            )
        )
        and _system_status_domain(folded)
        and _machine_status_scopes_are_one_reading(folded)
        and _machine_status_is_the_whole_clause(folded)
        # «el volumen del sistema» nombra el equipo solo como poseedor del
        # audio: esa lectura pertenece a audio.status, no a system.status.
        and not _volume_domain(folded)
        and (
            _has(folded, r"\b(?:como|health)\b")
            or _has(folded, _MACHINE_STATUS_OBSERVATION)
            or _head_is(head, _MACHINE_STATUS_OBSERVATION_HEAD)
        )
    ):
        _append(
            matches,
            folded,
            "system.status",
            # Identity/usage can precede the hardware noun. Retain the whole
            # request for the existing scope extractor, not just its noun.
            r"^",
        )

    if _head_is(head, r"(?:haz|hacer|ejecuta|run|ping)") and _has(
        folded,
        r"\b(?:haz|hacer|ejecuta|run)\s+(?:un\s+)?ping\b|\bping\s+(?:a|to)\b",
    ):
        _append(
            matches,
            folded,
            "network.ping",
            r"\b(?:haz|hacer|ejecuta|run|ping)\b",
        )
    elif (
        _head_is(head, r"(?:see|check|ping|haz|hacer|ejecuta|run)")
        and _has(folded, r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        and _has(
            folded,
            r"\b(?:answers?|responde|contest|ping|alcanza|reach)\b",
        )
        and not _has(
            folded,
            r"\b(?:en|on)\s+(?:la\s+|the\s+)?(?:web|internet)\b",
        )
    ):
        _append(
            matches,
            folded,
            "network.ping",
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        )
    elif (
        _head_is(head, r"(?:como|how|muestra|show|dime|que|what)")
        and _network_status_domain(folded)
        and _has(folded, r"\b(?:como|estado|status|health)\b")
    ):
        _append(matches, folded, "network.status", r"\bred\b|\bnetwork\b")
    if (
        _head_is(head, r"(?:lista|listar|muestra|muestrame|show|list)")
        and _has(folded, r"\bbluetooth\b")
        and _has(folded, rf"\b{_LIST}\b")
    ):
        _append(
            matches,
            folded,
            "bluetooth.device.list",
            r"\bbluetooth\b",
        )
    bluetooth_radio_verb = (
        r"(?:activa(?:me|lo)?|activar|desactiva(?:me|lo)?|desactivar|enciende(?:me|lo)?|"
        # NETWORK1293: voseo «encendé el bluetooth» folds to «encende».
        r"encende(?:me|lo)?|encender|prende(?:me|lo)?|"
        r"prender|apaga(?:me|lo)?|apagar|enable|disable|turn)"
    )
    if (
        _head_is(head, bluetooth_radio_verb)
        and _has(folded, r"\bbluetooth\b")
        and _has(folded, rf"\b{bluetooth_radio_verb}\b")
        and not _has(folded, r"\b(?:dispositivo|device|auriculares?|headphones?)\b")
        and not _has(
            folded,
            r"\b(?:del|de mi|on my|of my)\s+"
            r"(?:auto|car|telefono|celular|movil|phone|smartphone|tablet)\b",
        )
    ):
        _append(
            matches,
            folded,
            "bluetooth.radio.set",
            rf"\b{bluetooth_radio_verb}\b",
        )
    if (
        _head_is(head, r"(?:lista|listar|muestra|muestrame|show|list)")
        and _has(folded, r"\b(?:perifericos?|peripherals?)\b")
        and _has(folded, rf"\b{_LIST}\b|\bconectad")
    ):
        _append(
            matches,
            folded,
            "peripheral.list",
            r"\b(?:perifericos?|peripherals?)\b",
        )
    if _has(folded, r"\bwi[\s-]?fi\b") and not _has(
        folded,
        r"\b(?:del|de mi|on my|of my)\s+"
        r"(?:router|telefono|celular|movil|phone|smartphone|tablet|auto|car)\b",
    ):
        if (
            _has(folded, r"\b(?:perfiles?|profiles?)\b")
            and _has(folded, rf"\b{_LIST}\b|\bguardad")
            and _head_is(
                head,
                r"(?:lista|listar|muestra|muestrame|show|list)",
            )
        ):
            _append(matches, folded, "wifi.profile.list", r"\bwi[\s-]?fi\b")
        elif _head_is(
            head,
            r"(?:a|como|how|muestra|show|dime|que|what)",
        ) and _has(
            folded,
            r"\b(?:como|estado|status|health|conectad[oa]|connected)\b",
        ):
            _append(matches, folded, "wifi.status", r"\bwi[\s-]?fi\b")
        elif _wifi_state_question(folded):
            # NETWORK1293 H0230 «decime si el wifi está prendido», «¿el wifi
            # está encendido?»: a state question is the read, not an effect.
            _append(matches, folded, "wifi.status", r"\bwi[\s-]?fi\b")
        elif _head_is(head, r"(?:apaga|apagar|desconecta|disconnect)") and _has(
            folded, r"\b(?:apaga|apagar|desconecta|disconnect)\b"
        ):
            _append(
                matches,
                folded,
                "wifi.disconnect",
                r"\b(?:apaga|apagar|desconecta|disconnect)\b",
            )
        elif _head_is(
            head,
            # NETWORK1721 «conectate al wifi de casa»: the voseo reflexive is
            # the same order, and «al» is «a» + «el».
            r"(?:conecta|conectar|conectame|conectate|cambia|change|connect)",
        ) and _has(
            folded,
            r"\b(?:conecta|conectar|conectame|conectate|cambia|change|connect)\b",
        ):
            named_profile = _has(
                folded,
                r"\b(?:cambia|change)\s+(?:el\s+|la\s+)?wi[\s-]?fi\s+"
                r"(?:a|to)\s+\S|"
                r"\b(?:conecta|conectame|conectate|connect)\s+(?:a|al|to)\s+"
                r"(?:la\s+|the\s+)?(?:red\s+|network\s+)?wi[\s-]?fi\s+"
                r"(?:de|llamad[oa]|named|called)\s+\S|"
                r"\bconnect\s+to\s+(?:the\s+)?wi[\s-]?fi\s+network\s+"
                r"(?:named|called)\s+\S",
            )
            _append(
                matches,
                folded,
                "wifi.connect.named" if named_profile else "wifi.ensure.connected",
                r"\b(?:conecta|conectar|conectame|conectate|cambia|change|connect)\b",
            )


def _wifi_email_intent(
    text: str,
    available_operations: frozenset[str],
) -> EffectIntent | None:
    """Resolve Wi-Fi availability followed by reading the latest email."""

    required = {"wifi.ensure.connected", "email.latest.read"}
    if not required <= available_operations:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:conecta|conectar|connect)\s+"
            r"(?:(?:el|the)\s+)?wi[\s-]?fi\b[^.;!?]{0,80}"
            r"\b(?:abre|open)\s+(?:(?:el|the)\s+)?(?:correo|email|mail)\b"
            r"[^.;!?]{0,80}\b(?:lee|leeme|read)\b[^.;!?]{0,80}"
            r"\b(?:ultimo|ultima|latest|most recent)\b"
            r"(?:\s+(?:mensaje|message|correo|email|mail))?"
            r"(?:\s+(?:por favor|please))?[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("wifi.ensure.connected", "email.latest.read"),
        (evidence, evidence),
    )
