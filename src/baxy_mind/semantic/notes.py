"""Notes and tasks: notes, reminders, timers, alarms, agenda and calendar. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence
from .grammar import TASK_REMINDER_HEAD, _RELATIVE_DURATION_PATTERN, _fold, _match, _has, _strip_request_envelope, _request_body_surface, _request_head, _head_is, _LIST, _READ, _CREATE, _request_clauses
from .intent import EffectIntent, _append
from .temporal import _absolute_calendar_range_parts, _DEICTIC_DAY, _CLOCK_TIME_SELECTOR, _BOUNDED_TEMPORAL_SELECTOR, spoken_clock


def _relative_calendar_read_request(folded: str) -> bool:
    """Recognize a read-only calendar query with a relative bounded range."""

    return (
        re.fullmatch(
            r"(?:is|are)\s+there\s+(?:any\s+)?(?:events?|meetings?|appointments?)\s+"
            r"(?:planned|scheduled|booked)\s+(?:for|in|over)\s+the\s+next\s+"
            r"(?:\d+|one|two|three|four|five|six|several|few)\s+"
            r"(?:days?|weeks?|months?)[\s.!?]*|"
            # Uso real 2026-09-23 «do i have appointments today» was asked
            # «What time are you looking for appointments today?»: the day
            # window is the whole range; the calendar grounding reads it.
            r"[¿?\s]*(?:do|will)\s+i\s+have\s+(?:any\s+)?(?:events?|meetings?|appointments?|plans)\s+"
            r"(?:today|tomorrow|tonight|this\s+week(?:end)?|next\s+week(?:end)?)[\s.!?]*|"
            r"[¿?\s]*tengo\s+(?:alguna?s?|algo\s+de)\s+(?:citas?|reuniones|reunion|eventos?)\s+"
            r"(?:para\s+)?(?:hoy|manana|esta\s+noche|esta\s+semana|la\s+proxima\s+semana|"
            r"este\s+fin\s+de\s+semana)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def _time_only_reminder_request(folded: str) -> bool:
    direct_clock = _has(
        folded,
        r"\b(?:recordatorio|reminder)\s+(?:para|for)\s+"
        r"(?:(?:las?|at)\s+)?(?:[0-9]|one|two|three|four|five|six|"
        r"seven|eight|nine|ten|eleven|twelve|una?|dos|tres|cuatro|"
        r"cinco|seis|siete|ocho|nueve|diez|once|doce)\b",
    )
    dated_clock = _has(
        folded,
        (
            r"\b(?:recordatorio|reminder)\s+(?:para|for)\s+"
            r"(?:hoy|today|manana|tomorrow|esta noche|tonight)"
            r"(?:\s+(?:a las?|at)\s+(?:las\s+)?"
            r"(?:[0-2]?\d|one|two|three|four|five|six|seven|eight|nine|"
            r"ten|eleven|twelve|una?|dos|tres|cuatro|cinco|seis|siete|"
            r"ocho|nueve|diez|once|doce)(?::[0-5]\d)?"
            r"\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)?)?"
            r"[\s.!?]*$"
        ),
    )
    return direct_clock or dated_clock


# «contá 10 minutos», «count down 4 minutes»: the count head names a timer only
# when a duration follows it at once, so «cuenta» (account) never qualifies.
_COUNT_DOWN_REQUEST = re.compile(
    rf"^[¿?¡!\s]*(?:conta|cuenta|contame|cuentame|count(?:\s+down)?)\s+{_RELATIVE_DURATION_PATTERN}\b"
)


def _count_down_request(folded: str) -> bool:
    """Recognize a bare countdown request that names its duration first."""

    return _COUNT_DOWN_REQUEST.match(_strip_request_envelope(folded)) is not None


def _reminder_has_actionable_due(folded: str) -> bool:
    """Require a literal instant or duration, not merely a calendar day."""

    return bool(
        _has(folded, _CLOCK_TIME_SELECTOR)
        or _has(
            folded,
            r"\b(?:(?:en|in|dentro de|within)\s+)?"
            rf"{_RELATIVE_DURATION_PATTERN}"
            r"(?:\s+(?:from now|desde ahora))?\b",
        )
        or _has(folded, r"\b\d{4}-\d{2}-\d{2}t\d{2}:\d{2}(?::\d{2})?\S*\b")
    )


def _multiple_alarm_schedule_intent(
    folded: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Expand one explicit plural alarm request into its literal clock effects."""

    if "notification.schedule" not in available or _has(
        folded,
        r"\b(?:recurrente|recurrentes|repeating|recurring|cada|every)\b",
    ):
        return None
    clock_token = (
        r"(?:[0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|"
        r"ten|eleven|twelve|una?|dos|tres|cuatro|cinco|seis|siete|"
        r"ocho|nueve|diez|once|doce)(?::[0-5][0-9])?"
    )
    request = re.match(
        (
            r"^[^\w]*(?:record|create|set|schedule|crea|crear|programa|"
            r"programar|pon|ponme)\s+(?:(?:the|las?)\s+)?"
            r"(?:alarms|alarmas)\s+(?:(?:for|at|a|para)\s+(?:las?\s+)?)?"
            rf"(?P<clocks>{clock_token}(?:\s*(?:,|and|y)\s*{clock_token})+)\s*"
            r"(?P<period>a\.?\s*m\.?|p\.?\s*m\.?|de la manana|"
            r"de la tarde|de la noche|in the morning|in the afternoon|"
            r"in the evening)[\s.!?]*$"
        ),
        folded,
        re.IGNORECASE,
    )
    if request is None:
        return None
    clocks = tuple(
        token.strip()
        for token in re.split(r"\s*(?:,|and|y)\s*", request.group("clocks"))
        if token.strip()
    )
    if not 2 <= len(clocks) <= 8 or len(set(clocks)) != len(clocks):
        return None
    for clock in clocks:
        hour_text = clock.split(":", 1)[0]
        if hour_text.isdigit() and not 1 <= int(hour_text) <= 12:
            return None
    period = request.group("period")
    noun = "alarma a las" if _has(folded, r"\balarmas\b") else "alarm at"
    evidence = tuple(f"{noun} {clock} {period}" for clock in clocks)
    return EffectIntent(
        tuple("notification.schedule" for _ in clocks),
        evidence,
    )


_TASK_DATE_ONLY = re.compile(
    r"^(?:crea|creame|crear|agrega|agregame|anade|anadime|add|create|make|haz|hazme|pon|ponme|poneme|nueva|new)\s+"
    r"(?:(?:una|la|a|the)\s+)?(?:tarea|task|to-do|todo|pendiente)(?:\s+(?:nueva|new))?"
    r"(?:\s+(?:para|for|el|la|on|por|by|due|hasta|until)\s+(?:(?:el|la|este|esta|next|this|el\s+proximo|la\s+proxima)\s+)?"
    r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"manana|tomorrow|hoy|today|pasado\s+manana|semana|week|mes|month|fin\s+de\s+semana|weekend)"
    r"(?:\s+(?:que\s+viene|proxim[oa]))?"
    r"(?:\s+(?:a\s+las?|at)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|h|hs)?)?)?"
    r"[\s.!?]*$"
)


def _task_without_title(folded: str) -> bool:
    """«crea una tarea para el viernes»: a creation with at most a date, no content."""

    return _TASK_DATE_ONLY.match(_strip_request_envelope(folded).strip(" ¿?¡!.,")) is not None


# Lists (uso real 2026-09-23 «añadir el brócoli a mi lista de la compra»): an
# entry of a list is a local task and the list it goes on travels as its details,
# so «qué hay en mi lista de la compra» finds it by that name (task.search reads
# titles and details). No list store is added to the catalog.
_LIST_NAME = (
    r"(?P<list>(?:lista|list)(?:\s+(?:de(?:\s+la|\s+los|\s+las|l)?|para(?:\s+la|\s+el)?|of|for)\s+[^,;.!?]{1,60}?)?"
    r"|(?:shopping|grocery|to-?do|todo|packing)\s+list)"
)
_LIST_ENTRY = re.compile(
    r"^(?:(?:por\s+favor|please)\s*,?\s+)?"
    r"(?:a[nñ]ad[eií](?:me|r)?|a[nñ][aá]deme|agreg[aá](?:me|r)?|agr[eé]game|p[oó]n(?:me|er)?|pone(?:me)?|"
    r"met[eé](?:me|r)?|m[eé]teme|apunt[aá](?:me|r)?|ap[uú]ntame|anot[aá](?:me|r)?|an[oó]tame|"
    r"inclu(?:ye|ir)|sum[aá](?:le|r)?|add|put)\s+"
    r"(?P<item>\S.{0,200}?)\s+(?:a|al|en|to|on|in|into)\s+(?:(?:mi|la|tu|nuestra|my|the|our)\s+)?"
    + _LIST_NAME
    + r"[\s.!?]*$",
    re.IGNORECASE,
)
# A playlist or a list of songs is music, not a list of things to do or buy.
_LIST_NOT_TASKS = (
    r"\b(?:canciones?|temas?|musica|songs?|music|videos?|reproduccion|playlists?|favoritos|favorites|"
    r"spotify|youtube|inicio|startup|contactos?|contacts?|bloqueados?|blocked)\b"
)
# «agregar un nuevo elemento a la lista»: an entry that names nothing.
_UNNAMED_LIST_ENTRY = (
    r"(?:(?:un|una|unos|unas|el|la|otro|otra|algun|alguna|a|an|another|the|some)\s+)?(?:(?:nuev[oa]s?|new)\s+)?"
    r"(?:elementos?|articulos?|items?|cosas?|algo|productos?|entradas?|something|things?|entry|entries|products?)"
)


def list_entry_request(text: str) -> tuple[str, str] | None:
    """(entry, list) of «añade X a mi lista de la compra», «pon hamburguesa en mi lista de
    comestibles», «add milk to my shopping list», in the person's own writing; None for a
    playlist, a pointed entry («esto», «esa canción») or any other shape."""

    found = _LIST_ENTRY.match(_request_body_surface(text).strip())
    if found is None:
        return None
    item = found.group("item").strip(" ,;:\"'«»“”")
    listed = found.group("list").strip(" ,;:\"'«»“”")
    folded_item = _fold(item)
    if (
        not item
        or _has(f"{folded_item} {_fold(listed)}", _LIST_NOT_TASKS)
        or _has(folded_item, r"^(?:esto|eso|esta|este|esa|ese|estas|estos|esas|esos|aquello|it|this|that|these|those)\b")
        or re.fullmatch(_UNNAMED_LIST_ENTRY, folded_item) is not None
    ):
        return None
    return item, listed


_LIST_CREATION = re.compile(
    r"^(?:(?:por\s+favor|please)\s*,?\s+)?"
    r"(?:(?:quiero|quisiera|necesito|tengo\s+que|i\s+(?:need|want)\s+to|let's)\s+)?"
    r"(?:crea|creame|crear|haz|hazme|hacer|arma|armame|armar|empieza|empezar|comienza|comenzar|"
    r"inicia|iniciar|abre|abrir|create|make|start|nueva|new)\s+"
    r"(?:(?:una|un|la|a|the)\s+)?(?:(?:nueva|new)\s+)?(?:lista|list)"
    r"(?:\s+(?:nueva|new))?(?P<name>\s+(?:de(?:\s+la|\s+los|\s+las|l)?|para(?:\s+la|\s+el)?|of|for)\s+[^,;.!?]{1,60})?"
    r"[\s.!?]*$"
)


def list_creation_without_items(folded: str) -> str | None:
    """«por favor crea una nueva lista», «necesito hacer una lista de la compra»: a list
    with nothing on it yet. The list as named («lista de la compra», «lista»), or None;
    what goes on it is asked (a list is its entries, ``list_entry_request``)."""

    body = _strip_request_envelope(folded).strip(" ¿?¡!.,")
    if _has(folded, _LIST_NOT_TASKS):
        return None
    found = _LIST_CREATION.match(body)
    if found is not None:
        return "lista" + (found.group("name") or "")
    # «agregar un nuevo elemento a la lista», «puedes agregar un artículo a mi lista
    # de compras»: an entry that names nothing asks the same thing.
    entry = _LIST_ENTRY.match(body)
    if entry is not None and re.fullmatch(_UNNAMED_LIST_ENTRY, entry.group("item").strip()) is not None:
        return entry.group("list").strip()
    return None


# Uso real 2026-09-23 (tanda 2): the person's lists read back. «do i have cheese on my
# shopping list if not please add it» became a conversation answering «No, no hay queso …
# Se añadirá.» with nothing read or added; «decir la lista», «is my todo list free» and
# «tengo algo en mi lista de cosas por hacer» were asked back or answered with nonsense.
# A list is its entries (``list_entry_request``): the to-do list with no other name is
# every open task (task.list); a list named otherwise is the tasks that name it
# (task.search reads titles and details), and one entry asked about is searched by itself.
_TODO_LIST = (
    r"(?:(?:to-?do|todo|task|tasks|chores?)\s+list|list\s+of\s+(?:things\s+to\s+do|tasks|to-?dos|chores)|"
    r"lista\s+de\s+(?:tareas|pendientes|quehaceres|to-?dos?|cosas\s+(?:por|que|para)\s+hacer)|lista|list)"
)
_NAMED_LIST = (
    r"(?:lista|list)\s+(?:de(?:\s+la|\s+los|\s+las|l)?|para(?:\s+la|\s+el)?|of|for)\s+[a-z0-9'-]+(?:\s+[a-z0-9'-]+){0,3}"
    r"|[a-z0-9'-]+(?:\s+[a-z0-9'-]+)?\s+list"
)
# «la lista de los planetas» is public knowledge; with the article only the to-do list
# and the shopping list are the person's.
_HOUSEHOLD_LIST = (
    r"lista\s+de(?:\s+la|\s+las)?\s+(?:compras?|supermercado|super|mercado|comestibles)|(?:shopping|grocery|groceries)\s+list"
)
_OWN_LIST = (
    rf"(?:(?:mi|my)\s+(?P<list>{_TODO_LIST}|{_NAMED_LIST})|(?:la|the)\s+(?P<the_list>{_HOUSEHOLD_LIST}|{_TODO_LIST}))"
)
# Another store the person keeps is read by its own operation («my list of reminders»).
_LIST_OF_ANOTHER_STORE = (
    r"\b(?:recordatorios?|reminders?|alarmas?|alarms?|notas?|notes?|eventos?|events?|citas?|appointments?|"
    r"calendario|calendar|correos?|e-?mails?|mails?|archivos?|files?|carpetas?|folders?|ventanas?|windows?|"
    r"procesos?|process(?:es)?|apps?|aplicaciones?|programas?|programs?|descargas?|downloads?|juegos?|games?|"
    r"redes|networks?|wifi|dispositivos?|devices?|pestanas?|tabs?)\b"
)
_ANYTHING = r"(?:algo|alguna\s+cosa|cosas|algun\s+pendiente|pendientes|tareas|anything|something|stuff|any\s+(?:items?|things?|tasks?))"
_WHOLE_LIST_READ = (
    rf"que\s+(?:hay|tengo|queda|quedan|llevo|puse|anote)\s+(?:en|dentro\s+de)\s+{_OWN_LIST}",
    rf"(?:que|cual)\s+es\s+(?:lo|la\s+(?:cosa|tarea))\s+(?:siguiente|proxim[oa]|primer[oa]?|ultim[oa])\s+(?:en|de)\s+{_OWN_LIST}",
    rf"(?:dime|decime|di|decir|dame|lee|leeme|leer|repite|repiteme|repetir|repasa|repasame|muestra|muestrame|mostrame|"
    rf"mostrar|ensename|revisa|revisame|revisar|consulta|consultar|recita)\s+(?:lo\s+que\s+(?:hay|tengo)\s+en\s+)?"
    rf"{_OWN_LIST}(?:\s+(?:otra\s+vez|de\s+nuevo))?",
    rf"(?:dejame|quiero|quisiera|me\s+gustaria|necesito|puedo)\s+(?:escuchar|oir|ver|saber|revisar|leer|consultar|repasar)\s+"
    rf"(?:lo\s+que\s+(?:hay|tengo)\s+en\s+)?{_OWN_LIST}",
    rf"(?:tengo|hay)\s+{_ANYTHING}\s+(?:en|dentro\s+de)\s+{_OWN_LIST}",
    rf"tengo\s+(?=mi\s){_OWN_LIST}",
    rf"(?:esta|sigue)\s+(?:vacia|libre|llena)\s+{_OWN_LIST}",
    rf"{_OWN_LIST}\s+(?:esta|sigue)\s+(?:vacia|libre|llena)",
    rf"(?:what(?:'s|s|\s+is|\s+are)|what\s+(?:do|did)\s+i\s+(?:have|put)|what\s+have\s+i\s+got)\s+(?:(?:left|still)\s+)?"
    rf"(?:on|in)\s+{_OWN_LIST}",
    rf"what(?:'s|s|\s+is)\s+(?:the\s+)?(?:next|first|last|top)(?:\s+(?:thing|item|task|entry))?\s+(?:on|in)\s+{_OWN_LIST}",
    rf"(?:read|tell|show|repeat|say|give|recite|check|review)(?:\s+(?:me|out))?\s+(?:what(?:'s|\s+is)\s+(?:on|in)\s+)?"
    rf"{_OWN_LIST}(?:\s+(?:back|out|again|aloud))*(?:\s+to\s+me)?",
    rf"(?:let\s+me|i\s+(?:want|need|would\s+like)\s+to|can\s+i)\s+(?:hear|see|check|review|read)\s+{_OWN_LIST}",
    rf"(?:is|are)\s+{_OWN_LIST}\s+(?:free|empty|clear|done|full|finished|complete)",
    rf"(?:do\s+i\s+have|have\s+i\s+got|is\s+there|are\s+there)\s+{_ANYTHING}\s+(?:(?:left|still)\s+)?(?:on|in)\s+{_OWN_LIST}",
)
_ENTRY = r"(?P<item>(?!(?:que|de|a|en|para|to|of)\b)\S.{0,80}?)"
_LIST_ENTRY_PRESENCE = (
    rf"(?:(?:revisa|mira|fijate|comprueba|verifica|chequea)\s+si\s+)?(?:tengo|hay|esta|estan|puse|anote|apunte)\s+"
    rf"{_ENTRY}\s+(?:en|dentro\s+de)\s+{_OWN_LIST}",
    rf"(?:do\s+i\s+have|have\s+i\s+got|did\s+i\s+(?:put|add|write\s+down))\s+{_ENTRY}\s+(?:on|in)\s+{_OWN_LIST}",
    rf"(?:check|see|find\s+out|tell\s+me)\s+(?:if|whether)\s+(?:i\s+have\s+)?{_ENTRY}\s+(?:(?:is|are)\s+)?(?:on|in)\s+{_OWN_LIST}",
    rf"(?:is|are)\s+{_ENTRY}\s+(?:on|in)\s+{_OWN_LIST}",
)
# «if not please add it», «y si no está, agrégalo»: the entry goes on the list only when
# the read finds it absent.
_ADD_IF_ABSENT = (
    r"(?P<tail>\s*[,;?.]?\s*[¿¡]?(?:(?:y|and)\s+)?"
    r"(?:if\s+not|if\s+(?:it|they)(?:'s|'re|\s+is|\s+are)\s+not(?:\s+there)?|if\s+(?:it|they)\s+(?:isn'?t|aren'?t)(?:\s+there)?|"
    r"otherwise|si\s+no(?:\s+(?:esta|estan|lo\s+tengo|la\s+tengo|hay|es\s+asi))?|sino|de\s+lo\s+contrario|en\s+caso\s+contrario)"
    r"\s*[,;]?\s*(?:(?:please|por\s+favor)\s*,?\s+)?"
    r"(?:add|put|include|anade(?:l[oa]s?)?|agrega(?:l[oa]s?)?|pon(?:l[oa]s?)?|apunta(?:l[oa]s?)?|anota(?:l[oa]s?)?|"
    r"suma(?:l[oa]s?)?|incluye(?:l[oa]s?)?)"
    r"(?:\s+(?:it|them|lo|la|los|las))?(?:\s+(?:to|on|a|en)\s+(?:it|the\s+list|la\s+lista|ella|my\s+list|mi\s+lista))?"
    r"(?:\s*,?\s*(?:please|por\s+favor))?)?"
)
_LIST_READ_OPENER = r"^[¿?¡!\s]*(?:(?:olly|alexa|bax[yi]|oye|hey)\s*,?\s+)?(?:(?:please|por\s+favor)\s*,?\s+)?"


@dataclass(frozen=True, slots=True)
class ListRead:
    """A read of one of the person's lists: its operation, the search query (None for
    the whole to-do list), the list and the entry asked about as said, the clause that
    puts that entry on the list when the read finds it absent («if not please add it»,
    empty when none) and the read without that clause."""

    operation: str
    query: str | None
    list_name: str
    entry: str | None
    absent_clause: str
    read_text: str


def list_read_request(text: str) -> ListRead | None:
    """«qué hay en mi lista de la compra», «decir la lista», «is my todo list free», «do i
    have cheese on my shopping list if not please add it», in the person's own writing;
    None for a playlist, another store («my list of reminders»), a pointed entry or any
    other shape."""

    surface = _request_body_surface(text).strip()
    tokens = surface.split()
    folded = " ".join(_fold(token) for token in tokens)
    opener = re.match(_LIST_READ_OPENER, folded)
    body = folded[opener.end():] if opener is not None else folded
    offset = len(folded) - len(body)

    starts = [found.start() for found in re.finditer(r"\S+", folded)]

    def literal(start: int, end: int) -> str:
        # The folded body keeps the surface's words one for one, so the words a span
        # touches are the person's own words.
        rest = folded[offset + start:]
        start += len(rest) - len(rest.lstrip(" ,;:?.!¿¡"))
        first = sum(1 for index in starts if index <= offset + start) - 1
        last = sum(1 for index in starts if index < offset + end)
        return " ".join(tokens[max(first, 0):last]).strip(" ,;:\"'«»“”¿?¡!.")

    found = None
    entry: str | None = None
    for pattern in _WHOLE_LIST_READ:
        found = re.fullmatch(pattern + r"(?:\s*,?\s*(?:please|por\s+favor|porfa))?[\s.!?]*", body)
        if found is not None:
            break
    if found is None:
        for pattern in _LIST_ENTRY_PRESENCE:
            found = re.fullmatch(pattern + _ADD_IF_ABSENT + r"(?:\s*,?\s*(?:please|por\s+favor|porfa))?[\s.!?]*", body)
            if found is not None:
                break
        if found is None:
            return None
        item = found.group("item")
        if re.fullmatch(_ANYTHING + r"|" + _UNNAMED_LIST_ENTRY, item) is not None:
            entry = None
        elif re.match(r"(?:esto|eso|esta|este|esa|ese|estas|estos|esas|esos|aquello|it|this|that|these|those)\b", item):
            return None
        else:
            entry = re.sub(
                r"^(?:el|la|los|las|un|una|unos|unas|the|an?|some|any)\s+(?=\S)", "",
                literal(found.start("item"), found.end("item")), flags=re.IGNORECASE,
            )
    group = "list" if found.group("list") is not None else "the_list"
    listed = found.group(group)
    if _has(f"{entry or ''} {listed}", _LIST_NOT_TASKS) or _has(listed, _LIST_OF_ANOTHER_STORE):
        return None
    tail = found.groupdict().get("tail")
    if tail and entry is None:
        return None
    list_name = literal(found.start(group), found.end(group))
    if entry is not None:
        operation, query = "task.search", entry
    elif re.fullmatch(_TODO_LIST, listed) is not None:
        operation, query = "task.list", None
    else:
        operation, query = "task.search", list_name
    if tail:
        return ListRead(
            operation, query, list_name, entry,
            literal(found.start("tail"), found.end("tail")), literal(0, found.start("tail")),
        )
    return ListRead(operation, query, list_name, entry, "", surface)


def _bare_note_inventory_request(text: str) -> bool:
    """Recognize a complete, verbless request for the person's own notes."""

    folded = _strip_request_envelope(_fold(text))
    return _note_inventory_object(folded) and re.fullmatch(
        r"[¿?¡!\s]*(?:(?:mis|my)\s+(?:notas|notes)(?:\s+(?:guardadas|saved))?|"
        r"(?:tengo|do\s+i\s+have)\s+(?:alguna|algunas|any)?\s*(?:notas?|notes?)"
        r"(?:\s+(?:guardadas?|saved))?)[\s.!?]*",
        folded,
        re.IGNORECASE,
    ) is not None


def _note_inventory_object(text: str) -> bool:
    """True when the person is listing notes, not asking for Notepad."""

    remainder = re.sub(_NOTEPAD_OBJECT, " ", text, flags=re.IGNORECASE)
    return bool(
        re.search(
            r"\b(?:notas?|notes?|apuntes?|anotaciones?|memos?)\b",
            remainder,
            re.IGNORECASE,
        )
    )


# A day said with the wake-up time («mañana», «el lunes», «esta semana»).
_WAKE_DAY = (
    r"(?:(?:el|este|esta|next|this|el\s+proximo|la\s+proxima)\s+)?"
    r"(?:hoy|today|manana|tomorrow|pasado\s+manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|semana|week)"
)


def _wake_alarm_request(text: str) -> bool:
    """Recognize a direct wake-up alarm with one explicit clock (its part of the day
    said, «a las seis y cuarto de la mañana») or one duration, and at most a day."""

    folded = _strip_request_envelope(_fold(text))
    found = re.fullmatch(
        r"(?:i\s+need\s+you\s+to\s+)?"
        r"(?:(?:wake|get)\s+me(?:\s+up)?|despiertame|despertame|levantame)\s+"
        r"(?P<when>\S.*?)[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if found is None:
        return False
    when = found.group("when")
    if re.fullmatch(rf"(?:in|en|dentro\s+de|within)\s+{_RELATIVE_DURATION_PATTERN}", when):
        return True
    clock = spoken_clock(when)
    return (
        clock is not None
        and clock.resolved
        and re.fullmatch(
            rf"(?:{_WAKE_DAY}\s+)?{re.escape(clock.literal)}(?:\s+{_WAKE_DAY})?", when,
        ) is not None
    )


def _bounded_calendar_list_query(text: str) -> bool:
    """Recognize a read-only calendar question with one bounded time scope."""

    folded = _fold(text)
    absolute_range = _absolute_calendar_range_parts(folded)
    if not _has(folded, _BOUNDED_TEMPORAL_SELECTOR) and absolute_range is None:
        return False
    head = _request_head(folded)
    calendar_domain = _has(
        folded,
        r"\b(?:calendario|calendar|evento|eventos|event|events|"
        r"reunion|reuniones|meeting|meetings|cita|citas|"
        r"appointment|appointments)\b",
    )
    if calendar_domain and (
        _head_is(head, _LIST)
        or _head_is(
            head,
            r"(?:cuando|when|revisa|revisar|review|check|consulta|consultar)",
        )
    ):
        return True
    if (
        absolute_range is not None
        and calendar_domain
        and _has(
            folded,
            r"\b(?:what|which)\s+(?:meetings|events|appointments)\s+"
            r"(?:occurred|happened|took\s+place)\b",
        )
    ):
        return True
    if _head_is(head, r"(?:eventos|events)"):
        return True
    return _has(
        folded,
        (
            r"^[^\w]*(?:what is going on|que (?:sucede|pasa)|"
            r"anything i should do|tengo algo que hacer|"
            r"hay algo que (?:hacer|tenga que hacer))\b"
        ),
    )


_ORDINAL_INDEX = {
    "primera": 1,
    "primero": 1,
    "first": 1,
    "segunda": 2,
    "segundo": 2,
    "second": 2,
    "tercera": 3,
    "tercero": 3,
    "third": 3,
    "cuarta": 4,
    "cuarto": 4,
    "fourth": 4,
    "quinta": 5,
    "quinto": 5,
    "fifth": 5,
    "sexta": 6,
    "sexto": 6,
    "sixth": 6,
    "septima": 7,
    "septimo": 7,
    "seventh": 7,
    "octava": 8,
    "octavo": 8,
    "eighth": 8,
}


_CARDINAL_NUMBER = {
    "dos": 2,
    "two": 2,
    "tres": 3,
    "three": 3,
    "cuatro": 4,
    "four": 4,
    "cinco": 5,
    "five": 5,
    "seis": 6,
    "six": 6,
    "siete": 7,
    "seven": 7,
    "ocho": 8,
    "eight": 8,
}


_ORDINAL_WORD = "|".join(_ORDINAL_INDEX)


# The same note body can be introduced by a preposition or by a participle.
# ``Cedar containing north`` and ``Cedar con contenido norte`` name one note
# each; treating only the prepositional form as enumerable made an otherwise
# complete four-note mission collapse to a single create.
# Spanglish mixes the preposition and the noun freely, so ``con content`` and
# ``with contenido`` name a body just as ``con contenido`` does.
_NOTE_CONTENT_INTRODUCER = (
    r"(?:(?:con|with)\s+(?:contenido|content)|containing|conteniendo|"
    r"que\s+(?:contenga|diga))"
)


def _fully_enumerated_named_note_titles(text: str) -> tuple[str, ...]:
    """Extract a bounded ``title + content`` list without inventing labels."""

    head = _request_head(text)
    if not _head_is(head, _CREATE):
        return ()
    count_match = _match(
        text,
        r"\b(?P<count>dos|two|tres|three|cuatro|four|cinco|five|"
        r"seis|six|siete|seven|ocho|eight|[2-8])\s+"
        r"(?:(?:private|local|privadas?|locales?)\s+)?(?:notas|notes)\s*:\s*",
    )
    if count_match is None:
        return ()
    raw_count = count_match.group("count")
    count = _CARDINAL_NUMBER.get(
        raw_count, int(raw_count) if raw_count.isdigit() else 0
    )
    body = text[count_match.end() :]
    titles = tuple(
        " ".join(found.group("title").strip(" ,.;:").split())
        for found in re.finditer(
            # A serial comma keeps its conjunction: ``, and Birch`` must not
            # name a note ``and birch``.
            r"(?:^|,\s*(?:(?:y|and)\s+)?|\s+(?:y|and)\s+)"
            r"(?P<title>[a-z0-9][a-z0-9 _-]{0,79}?)\s+"
            rf"(?:{_NOTE_CONTENT_INTRODUCER})\s+\S",
            body,
            re.IGNORECASE,
        )
    )
    if (
        len(titles) != count
        or any(not title for title in titles)
        or len(set(titles)) != len(titles)
    ):
        return ()
    return titles


def _fully_enumerated_note_create_count(text: str) -> int | None:
    """Return an exact bounded count only for individually labelled notes."""

    head = _request_head(text)
    if not _head_is(head, _CREATE):
        return None
    count_match = _match(
        text,
        r"\b(?P<count>dos|two|tres|three|cuatro|four|cinco|five|"
        r"seis|six|siete|seven|ocho|eight|[2-8])\s+"
        r"(?:(?:private|local|privadas?|locales?)\s+)?(?:notas|notes)\b",
    )
    if count_match is None:
        return None
    raw_count = count_match.group("count")
    count = _CARDINAL_NUMBER.get(
        raw_count, int(raw_count) if raw_count.isdigit() else 0
    )
    labelled = [
        _ORDINAL_INDEX[found.group("ordinal")]
        for found in re.finditer(
            rf"\b(?:la|el|the)?\s*(?P<ordinal>{_ORDINAL_WORD})\s+"
            r"(?:titulad[oa]|llamad[oa]|titled|entitled|named|called)\b",
            text,
            re.IGNORECASE,
        )
    ]
    if labelled != list(range(1, count + 1)):
        named = _fully_enumerated_named_note_titles(text)
        if len(named) != count:
            return None
    return count


def _fully_enumerated_note_read_order(
    text: str,
    total_count: int | None = None,
) -> tuple[int, ...]:
    """Return an explicit, duplicate-free ordinal read order."""

    head = _request_head(text)
    if not _head_is(head, _READ):
        return ()
    ordered: list[int] = []
    for found in re.finditer(
        rf"\b(?:la|el|the)?\s*(?P<ordinal>{_ORDINAL_WORD}|middle|last)\s+"
        r"(?:nota|note)\b",
        text,
        re.IGNORECASE,
    ):
        word = found.group("ordinal")
        if word == "middle":
            if total_count is None or total_count < 3 or total_count % 2 == 0:
                return ()
            ordered.append((total_count + 1) // 2)
        elif word == "last":
            if total_count is None:
                return ()
            ordered.append(total_count)
        else:
            ordered.append(_ORDINAL_INDEX[word])
    if len(ordered) < 2 or len(set(ordered)) != len(ordered):
        return ()
    return tuple(ordered)


def _named_note_dependency_order(text: str) -> tuple[int, ...]:
    """Map a complete named read list to its unique named creation list."""

    clauses = _request_clauses(text)
    created: tuple[str, ...] = ()
    create_index = -1
    for index, clause in enumerate(clauses):
        titles = _fully_enumerated_named_note_titles(clause)
        if titles:
            if created:
                return ()
            created = titles
            create_index = index
    if not created or create_index + 1 >= len(clauses):
        return ()
    read_text = " y ".join(clauses[create_index + 1 :])
    if not _head_is(_request_head(read_text), _READ):
        return ()
    references = tuple(
        " ".join(found.group("title").strip(" ,.;:").split())
        for found in re.finditer(
            r"\b(?:la|the)?\s*(?:nota|note)\s+"
            r"(?P<title>[a-z0-9][a-z0-9 _-]{0,79}?)"
            r"(?=\s*(?:,|[.!?]|$|\b(?:y|and)\b))",
            read_text,
            re.IGNORECASE,
        )
    )
    if len(references) != len(created):
        return ()
    order: list[int] = []
    for reference in references:
        matches = [
            index
            for index, title in enumerate(created, 1)
            if title == reference or title.startswith(reference + " ")
        ]
        if len(matches) != 1:
            return ()
        order.append(matches[0])
    if set(order) != set(range(1, len(created) + 1)):
        return ()
    return tuple(order)


def _individually_authored_note_create_clauses(clauses: Iterable[str]) -> int:
    """Count clauses that each author exactly one note with its own body."""

    return sum(
        1
        for clause in clauses
        if _head_is(_request_head(clause), _CREATE)
        and _has(clause, r"\b(?:nota|note)s?\b")
        and _has(clause, rf"\b{_NOTE_CONTENT_INTRODUCER}\b")
    )


def _has_fully_enumerated_note_cardinality(
    clauses: Iterable[str],
    expected_count: int,
) -> bool:
    clauses = tuple(clauses)
    if any(
        _fully_enumerated_note_create_count(clause) == expected_count
        for clause in clauses
    ):
        return True
    # ``una nota Luna con content claro y otra nota Sol con content brillante``
    # states the same cardinality as one enumerated list of two, only spread
    # across two clauses that each carry their own title and body. Requiring a
    # single enumerating clause rejected a request that was fully authored, so
    # conserve the count when every note is individually written out.
    return _individually_authored_note_create_clauses(clauses) == expected_count


def enumerated_note_dependency_order(text: str) -> tuple[int, ...]:
    """Return a complete user-authored mapping from reads to created notes.

    The mapping is available only when one bounded creation list labels every
    note in ascending ordinal order and one later read list names every label
    exactly once. Partial, duplicate, or standalone ordinal references remain
    untrusted and return an empty tuple.
    """

    folded = _fold(text)
    clauses = _request_clauses(folded)
    named_order = _named_note_dependency_order(folded)
    if named_order:
        return named_order
    creates = tuple(
        (index, count)
        for index, clause in enumerate(clauses)
        if (count := _fully_enumerated_note_create_count(clause)) is not None
    )
    if len(creates) != 1:
        return ()
    create_index, count = creates[0]
    read_text = " y ".join(clauses[create_index + 1 :])
    order = _fully_enumerated_note_read_order(read_text, count)
    if len(order) != count or set(order) != set(range(1, count + 1)):
        return ()
    return order


_NOTEPAD_OBJECT = r"\b(?:(?:bloc|app|coso)\s+de\s+notas|notepad)\b"


def _latest_notification_selector(text: str) -> bool:
    return _has(
        _fold(text),
        r"\b(?:latest|last|most recent|newest|ultima|ultimo|mas reciente|"
        r"recien (?:cread[ao]|programad[ao])|just (?:set|created|scheduled))\b",
    )


def _active_alarm_stop_request(text: str) -> bool:
    """Recognize only a standalone imperative to stop the active alarm."""

    return _has(
        _fold(text),
        r"^[^\w]*para\s+(?:(?:la|el)\s+)?alarma"
        r"(?:\s*[,;:]?\s+(?:por favor|please))?[\s,;:.!?]*$",
    )


def session_single_alarm_rewrite(
    text: str,
    previous_user_texts: Sequence[str],
) -> str | None:
    """REOPEN1993 H0011 «cancelá la alarma» (owner: ask which alarm «unless BAXY
    already set one in this session»): when exactly one previous request of
    this conversation set an alarm and none cancelled one since, «la alarma» is
    that alarm and the order reads as the latest-alarm cancellation. Returns the
    text with the selector made explicit, or None when the question stands."""

    folded = _fold(text)
    if not folded or _has(folded, r"\b(?:alarms|alarmas)\b") or not _has(folded, r"\b(?:alarm|alarma)\b"):
        return None
    if _has(folded, _CLOCK_TIME_SELECTOR) or _latest_notification_selector(folded):
        return None
    if re.search(r"\d", folded) or _has(
        folded,
        r"\b(?:de|a|para|at|for)\s+(?:las?\s+)?(?:una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)\b",
    ):
        # «cancelá la alarma de las 7» names its alarm; nothing to resolve.
        return None
    head_cancel = _head_is(
        _request_head(folded),
        r"(?:delete|remove|cancel|erase|elimina|eliminar|borra|borrar|quita|quitar|cancela|cancelar|"
        r"cancelame|cancelamela|cancelala|borrame|borrala|quitame|quitala|eliminame|eliminala)",
    )
    if not head_cancel and not _alarm_turn_off_request(folded):
        return None
    alarms_set = 0
    for previous in previous_user_texts[:6]:
        previous_folded = _fold(previous)
        if not previous_folded:
            continue
        if _has(
            previous_folded,
            r"\b(?:cancel|cancela|cancelar|cancelame|borra|quita|elimina|delete|remove|apaga|desactiva)\b",
        ) and _has(previous_folded, r"\b(?:alarm|alarma|alarms|alarmas)\b"):
            # The most recent request wins: a cancellation after the setting
            # leaves nothing that «la alarma» could name.
            return None
        if _has(
            previous_folded,
            r"\b(?:alarma|alarm|despertame|despiertame|wake\s+me|timer|temporizador|conta|cuenta)\b",
        ) and _has(
            previous_folded,
            r"\b(?:pon|pone|ponme|poneme|programa|crea|set|put|despertame|despiertame|wake|conta|cuenta|start)\b",
        ):
            alarms_set += 1
    if alarms_set != 1:
        return None
    rewritten = re.sub(r"\b(la|una|mi|el)\s+(alarma)\b", r"\1 ultima \2", text, count=1, flags=re.IGNORECASE)
    if rewritten == text:
        rewritten = re.sub(r"\b(the|my|an?)\s+(alarm)\b", r"\1 last \2", text, count=1, flags=re.IGNORECASE)
    return rewritten if rewritten != text else None


def _alarm_turn_off_request(text: str) -> bool:
    """Recognize an alarm cancellation paraphrase even with a modal head."""

    folded = _fold(text)
    return _has(folded, r"\b(?:alarm|alarma)\b") and _has(
        folded,
        r"\b(?:turn(?:ed)?\s+of+|turn(?:ed)?\s+off|apaga|apagar|"
        r"deactivate|deactivates|desactiva|desactivar)\b",
    )


def _exact_local_reminder_title(text: str) -> str | None:
    """Return a bounded literal title only for one exact local reminder."""

    folded = _fold(text).strip()
    if _has(folded, r"\b(?:recordatorios|reminders)\b") or _has(
        folded, _CLOCK_TIME_SELECTOR
    ):
        return None
    patterns = (
        (
            r"^[¿?¡!\s]*(?:(?:please|por favor)\s+)?"
            r"(?:delete|remove|cancel|erase|elimina|eliminar|borra|borrar|"
            r"quita|quitar|cancela|cancelar)\s+"
            r"(?:(?:the|a|an|el|la|un|una)\s+)?"
            r"(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)[\s.!?]*$"
        ),
        (
            r"^[¿?¡!\s]*(?:(?:the|el|la)\s+)?"
            r"(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)\s+"
            r"(?:needs?\s+to\s+be|has\s+to\s+be|"
            r"necesita\s+(?:ser\s+)?|se\s+(?:tiene|debe)\s+que\s+)"
            r"\s*"
            r"(?:deleted|removed|cancelled|canceled|eliminad[oa]|borrad[oa]|"
            r"cancelad[oa]|eliminar|borrar|cancelar)[\s.!?]*$"
        ),
        (
            r"^[¿?¡!\s]*(?:find|busca|buscar|encuentra|encontrar)\s+"
            r"(?:(?:the|el|la)\s+)?(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)\s+(?:and|y)\s+"
            r"(?:delete|remove|cancel|erase|eliminalo|borrarlo|quitarlo|"
            r"cancelarlo|remove\s+it|delete\s+it|cancel\s+it)[\s.!?]*$"
        ),
        (
            r"^[^\w]*(?:no necesito|i (?:do not|don't) need)\s+"
            r"(?P<title>.+?)[,;]\s*"
            r"(?:cancela|elimina|borra|cancel|delete|remove)\s+"
            r"(?:(?:este|el|this|the)\s+)?(?:recordatorio|reminder)[\s.!?]*$"
        ),
        (
            r"^[^\w]*(?P<title>.+?)\s+"
            r"(?:se\s+(?:cancelo|cancelaron)|(?:was|were)\s+cancelled)\s+"
            r"(?:asi que|por lo que|so)\s+"
            r"(?:(?:este|el|this|the)\s+)?(?:recordatorio|reminder)\s+"
            r"(?:se\s+(?:tiene|debe)\s+que\s+|needs?\s+to\s+be\s+)?"
            r"(?:eliminar|borrar|cancelar|deleted|removed|cancelled)[\s.!?]*$"
        ),
    )
    for pattern in patterns:
        found = re.match(pattern, folded, re.IGNORECASE)
        if found is None:
            continue
        title = re.sub(
            r"(?:\s+please|\s+por favor)$",
            "",
            found.group("title").strip(" \t\r\n.,;:!?\"'"),
            flags=re.IGNORECASE,
        ).strip()
        if title and title not in {
            "a reminder",
            "el recordatorio",
            "it",
            "one",
            "please",
            "por favor",
            "that",
            "this",
        }:
            return title
    return None


def _review_calendar_message_and_direct_reminder_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
) -> None:
    """Append complete scheduling and messaging requests with literal data."""

    calendar_domain = _has(
        folded,
        r"\b(?:calendario|calendar|evento|eventos|event|events|"
        r"reunion|reuniones|meeting|meetings|cita|citas|appointment|appointments)\b",
    )
    temporal = (
        _has(
            folded,
            _BOUNDED_TEMPORAL_SELECTOR,
        )
        or _absolute_calendar_range_parts(folded) is not None
    )
    if temporal and _bounded_calendar_list_query(folded):
        _append(
            matches,
            folded,
            "calendar.event.list",
            (
                rf"\b(?:{_LIST}|cuando|when|eventos|events)\b|"
                r"\bduring(?=\s+the\s+timeframe)\b|"
                r"\b(?:revisa|revisar|review|check|consulta|consultar)\b|"
                r"\b(?:what is going on|que (?:sucede|pasa)|"
                r"what\s+(?:meetings|events|appointments)\s+"
                r"(?:occurred|happened|took\s+place)|"
                r"anything i should do|tengo algo que hacer|"
                r"hay algo que (?:hacer|tenga que hacer))\b"
            ),
        )
    if (
        calendar_domain
        and temporal
        and _head_is(
            head,
            rf"(?:{_CREATE}|programa|programar|programame|schedule|"
            r"agenda|agendar|agendame)",
        )
        and (
            _has(
                folded,
                r"\b(?:llamad[oa]|titulad[oa]|called|named)\s+\S+",
            )
            or _has(folded, r"\b(?:reunion|meeting|evento|event)\b")
        )
        and _has(
            folded,
            r"\b(?:de|desde|from)\s+(?:las\s+)?(?:\d{1,2}|"
            r"una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
            r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
            r"(?:\s*(?:am|pm))?\s+(?:a|hasta|to)\s+(?:las\s+)?"
            r"(?:\d{1,2}|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|"
            r"diez|once|doce|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve)\b",
        )
    ):
        _append(
            matches,
            folded,
            "calendar.event.create",
            rf"\b(?:{_CREATE}|programa|programar|programame|schedule|"
            r"agenda|agendar|agendame)\b",
        )

    if (
        (
            _head_is(
                head,
                r"(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind)",
            )
            and _has(
                folded,
                r"^[¿?¡!\s]*(?:recuerdame|recuerdamelo|recordame|recordamelo|"
                r"avisame|remind\s+me)\b.+",
            )
            or _has(folded, rf"^[¿?¡!\s]*{TASK_REMINDER_HEAD}\s+.+")
        )
        and (temporal or _has(folded, _DEICTIC_DAY))
    ):
        _append(
            matches,
            folded,
            "reminder.create",
            r"\b(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind|"
            r"recuerda|recorda|acordate|acuerdate|remember)\b",
        )

    if (
        temporal
        and not any(entry[2] == "reminder.create" for entry in matches)
        and re.match(
            # «Dentro de doce minutos, recordame …»: the duration leads and the
            # reminder head follows it (TIME1189/011).
            rf"^[¿?¡!\s]*(?:en|in|dentro\s+de|within)\s+{_RELATIVE_DURATION_PATTERN},?\s+"
            r"(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind\s+me)\b.+",
            folded,
        )
    ):
        _append(
            matches,
            folded,
            "reminder.create",
            r"\b(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind)\b",
        )

    if (
        temporal
        and _count_down_request(folded)
        and not any(entry[2] == "notification.schedule" for entry in matches)
    ):
        _append(
            matches,
            folded,
            "notification.schedule",
            r"\b(?:conta|cuenta|contame|cuentame|count)\b",
        )

    if (
        temporal
        and _head_is(
            head,
            r"(?:programa|programar|programame|schedule|pon|poner|ponme|pone|"
            r"poneme|pongame|set|arranca|inicia|start|alarma|alarm|"
            r"temporizador|timer)",
        )
        and _has(
            folded,
            r"\b(?:alarma|alarmas|alarm|alarms|temporizador|"
            r"temporizadores|timer|timers|aviso|avisos)\b",
        )
    ):
        _append(
            matches,
            folded,
            "notification.schedule",
            r"\b(?:programa|programar|programame|schedule|pon|poner|ponme|pone|"
            r"poneme|pongame|set|arranca|inicia|start|alarma|alarm|"
            r"temporizador|timer)\b",
        )

    if (
        temporal
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and not any(entry[2] == "reminder.create" for entry in matches)
        and _head_is(
            head,
            r"(?:pon|ponme|pone|poneme|pongame|crea|crear|programa|programar|"
            r"set|schedule|recordatorio|reminder)",
        )
    ):
        _append(
            matches,
            folded,
            "reminder.create",
            r"\b(?:pon|ponme|pone|poneme|pongame|crea|crear|programa|programar|"
            r"set|schedule|recordatorio|reminder)\b",
        )

    cancel_notification = (
        (
            _head_is(
                head,
                r"(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
                r"elimina|eliminar|delete|borra|borrar)",
            )
            or _has(folded, r"^get\s+rid\s+of\b")
        )
        and _has(folded, r"\b(?:alarma|alarm|recordatorio|reminder)\b")
        and not _has(
            folded,
            r"\b(?:alarmas|alarms|recordatorios|reminders)\b",
        )
    )
    exact_local_reminder_title = _exact_local_reminder_title(folded)
    exact_local_reminder_lookup = (
        (
            _head_is(
                head,
                r"(?:ver|ve|muestra|muestrame|ensena|show|see|view|find|busca)",
            )
            or _has(folded, r"^can i (?:see|view)\b")
        )
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and _has(folded, r"\b(?:otra vez|de nuevo|nuevamente|again)\b")
        and _has(
            folded,
            r"\b(?:recordatorio|reminder)\s+(?:de|para|sobre|for|about)\s+\S",
        )
    )
    if exact_local_reminder_lookup:
        _append(
            matches,
            folded,
            "reminder.resolve.exact",
            r"\b(?:ver|ve|muestra|muestrame|ensena|show|see|view|find|busca)\b",
        )
    if exact_local_reminder_title is not None:
        _append(
            matches,
            folded,
            "reminder.delete",
            r"\b(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
            r"elimina|eliminar|delete|borra|borrar|find|busca|encuentra)\b",
        )
    elif cancel_notification and (
        _has(folded, _CLOCK_TIME_SELECTOR) or _latest_notification_selector(folded)
    ):
        operation = (
            "notification.cancel.at"
            if _has(folded, _CLOCK_TIME_SELECTOR)
            else "notification.cancel.latest"
        )
        _append(
            matches,
            folded,
            operation,
            r"\b(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
            r"elimina|eliminar|delete|borra|borrar|get rid of)\b",
        )

    send_head = _head_is(
        head,
        r"(?:envia|enviar|manda|mandar|dile|decile|tell|send)",
    )
    explicit_channel = _has(
        folded,
        r"\b(?:whatsapp|wsp|discord|signal|telegram)\b",
    )
    explicit_payload = _has(
        folded,
        r"\b(?:mensaje|message)\s+[«\"'‘“]?[a-z0-9].+",
    )
    explicit_recipient = _has(
        folded,
        r"\b(?:a|para|to)\s+[a-z0-9][a-z0-9 ._-]{0,80}\s+"
        r"(?:el\s+|the\s+)?(?:mensaje|message)\b|"
        r"\b(?:envia|manda|send)\s+[a-z0-9][a-z0-9 ._-]{0,80}\s+"
        r"(?:el\s+|the\s+)?(?:whatsapp\s+)?(?:mensaje|message)\b",
    ) and not _has(
        folded,
        r"\b(?:a|para|to)\s+(?:ellos|ellas|les|them)\b|"
        r"\b(?:send|envia|manda)\s+(?:them|les)\b",
    )
    tell_shape = _has(
        folded,
        r"^[¿?¡!\s]*(?:(?:dile|decile)\s+a\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:(?:en|por)\s+(?:whatsapp|wsp|discord)\s+)?que|"
        r"tell\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:on\s+(?:whatsapp|discord)\s+)?that)\s+\S.+",
    ) and not _has(
        folded,
        r"^[¿?¡!\s]*(?:dile|decile)\s+a\s+(?:ellos|ellas|les)\b",
    )
    if (
        send_head
        and explicit_channel
        and ((explicit_payload and explicit_recipient) or tell_shape)
    ):
        _append(
            matches,
            folded,
            "message.send",
            r"\b(?:envia|enviar|manda|mandar|dile|decile|tell|send)\b",
        )


_AGENDA_LISTING = (
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:que|what)\s+(?:tengo|hay|do i have|have i got|is there|do i have got)|"
    r"(?:decime|dime|contame|cuentame|tell me|mostrame|muestrame|show me)\s+(?:que\s+(?:tengo|hay)|what\s+(?:i have|there is|is)))\s+"
    r"(?:(?:agendad[oa]s?|programad[oa]s?|planead[oa]s?|planificad[oa]s?|anotad[oa]s?|scheduled|planned|on\s+(?:my|the)\s+agenda|en\s+(?:la|mi)\s+agenda)"
    r"(?:\s+(?:para|for)\s+(?:hoy|manana|today|tomorrow|esta\s+semana|this\s+week))?"
    r"|(?:para|for)\s+(?:hoy|today)\s+(?:agendad[oa]s?|programad[oa]s?|scheduled|planned|en\s+(?:la|mi)\s+agenda))[\s?!.]*$"
)
