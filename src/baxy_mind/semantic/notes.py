"""Notes and tasks: notes, reminders, timers, alarms, agenda and calendar. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence
from .grammar import TASK_REMINDER_HEAD, _RELATIVE_DURATION_PATTERN, _fold, _match, _has, _strip_request_envelope, _request_body_surface, _request_head, _head_is, _LIST, _READ, _CREATE, _request_clauses
from .intent import EffectIntent, _append
from .normalize import _accent_folded_with_punctuation
from .temporal import _absolute_calendar_range_parts, _DEICTIC_DAY, _CLOCK_TIME_SELECTOR, _BOUNDED_TEMPORAL_SELECTOR, CLOCK_PHRASE, EventTiming, event_timing, spoken_clock, is_window_phrase, says_a_window


# --- The person's own agenda, read (uso real 2026-09-23) --------------------------------------------
# «qué tengo por venir», «tengo algo programado para el cuatro de julio», «qué tengo que hacer esta
# semana», «cuál es mi horario para el día», «cuándo es mi brunch con Jennifer», «próximos eventos en
# calendario», «what's my schedule like today» went to a clarification, a web search, a knowledge reply
# or «eso no lo hago». What the person has planned is their own data: it is read from the calendar
# (``semantic.temporal.agenda_window`` bounds it: the window said, or what is coming).
AGENDA_NOUN = (
    r"(?:calendarios?|calendars?|agendas?|horarios?|schedules?|planes|plans?|eventos?|events?|reuniones|"
    r"reunion|meetings?|citas?|appointments?|compromisos?|commitments?|actividades|activities)"
)
_AGENDA_PARTICIPLE = (
    r"(?:planead[oa]s?|programad[oa]s?|agendad[oa]s?|previst[oa]s?|anotad[oa]s?|apuntad[oa]s?|"
    r"planned|scheduled|booked|set\s+up|set|lined\s+up|going\s+on|coming\s+up|on)"
)
# Heads that change the agenda or ask for something else: not a read of it.
_AGENDA_CHANGE_HEAD = (
    r"(?:crea|crear|anade|anadir|agrega|agregar|pon|poner|pone|programa|programar|agendar|establece|"
    r"establecer|fija|fijar|marca|marcar|marque|apunta|apuntar|anota|anotar|reserva|reservar|bloquea|borra|"
    r"borrar|elimina|eliminar|cancela|cancelar|quita|quitar|mueve|mover|cambia|cambiar|reprograma|"
    r"reprogramar|recuerda|recorda|avisa|notifica|despierta|busca|buscar|abre|abrir|add|put|schedule|set|"
    r"create|make|book|mark|block|delete|remove|cancel|clear|erase|move|change|reschedule|remind|notify|"
    r"alert|wake|search|find|open|planificar|planear|plan)"
)
_AGENDA_QUESTION_HEAD = (
    r"(?:que|cual|cuales|cuando|donde|como|cuanto|cuanta|cuantos|cuantas|a|what|which|when|where|how|dime|"
    r"decime|dame|muestra|muestrame|mostrame|ensename|lee|leeme|revisa|consulta|mira|tell|show|give|read|"
    r"check|list|lista|listame|hay|tengo|tenemos|habra|tendre|do|does|is|are|will|have|any)"
)
# A schedule that is not the person's own («el horario del cine», «the movie schedule», «algún evento
# en el centro»): public information, looked up elsewhere.
_PUBLIC_SCHEDULE = (
    r"\b(?:cine|cines|peliculas?|movies?|cinema|cartelera|tv|television|tele|bus|buses|autobus|tren|trenes|"
    r"trains?|metro|vuelos?|flights?|partidos?|concierto|conciertos|concerts?|tienda|tiendas|stores?|"
    r"shops?|biblioteca|library|museo|museum|centro|ciudad|city|downtown|town|cerca|nearby|near|"
    r"elecciones|elections?|noticias|news|farmacia|pharmacy|banco|bank|clima|weather|mundo|world|pais|country)\b"
)
_AGENDA_DETERMINER = r"(?:algo|anything|something|algun|alguna|algunos|algunas|any|some|nada|nothing|un|una|a|an)"
_AGENDA_HAVE = (
    r"(?:(?:yo\s+)?(?:tengo|tenemos|tendre|tendremos)(?:\s+yo)?|hay|habra|do\s+i\s+have|have\s+i\s+got|"
    r"will\s+i\s+have|is\s+there|are\s+there|will\s+there\s+be|do\s+we\s+have|i\s+have)"
)


# Words that make an agenda sentence a reminder, a notice or a clean-up of it, never a read: «necesito que
# me recuerden las reuniones del lunes», «limpia mi agenda para hoy» (uso real 2026-09-24).
AGENDA_NOT_A_READ = (
    r"\b(?:recuerd[a-z]*|recordar[a-z]*|recordame|recordamelo|remind[a-z]*|avisa(?:me|rme)?|avisen|avise|"
    r"notifica(?:me|rme)?|limpia|limpiar|limpie|limpiame|despeja|despejar|despeje|vacia|vaciar|vacie|clear|wipe)\b"
)
_READ_OF_EVENT_HEAD = (
    r"(?:que|cual|cuales|cuando|donde|quien|quienes|cuanto|a|what|which|when|where|who|dime|decime|"
    r"cuentame|contame|hablame|tell|mas|more|is|are|will|does|do)"
)
# The person's own event, said without «mi» (uso real 2026-09-24): «la reunión vespertina que tengo con
# John», «the meeting I have»; «cuándo está programada la boda», «when is the party scheduled», «the event
# scheduled on the first of january»; «la reunión de ayer», «la cena de esta noche», «today's meeting».
OWN_EVENT_NOUN = (
    r"(?:reunion|reuniones|meetings?|citas?|appointments?|eventos?|events?|compromisos?|commitments?|cena|"
    r"almuerzo|comida|desayuno|brunch|lunch|dinner|breakfast|fiestas?|party|parties|boda|wedding|cumpleanos|"
    r"birthday|entrevistas?|interviews?|examen|exam|clases?|class|turno|sesion|session|llamadas?|calls?|"
    r"videollamadas?|practicas?|practice|entrenamientos?|training)"
)
_OWN_EVENT = re.compile(
    rf"\b{OWN_EVENT_NOUN}(?:\s+\w+)?\s+(?:que\s+(?:yo\s+)?(?:tengo|tenemos|tendre|tenia|teniamos)|"
    r"(?:that\s+)?(?:i|we)\s+(?:have|had|'ve\s+got|am\s+having))\b|"
    rf"\b{OWN_EVENT_NOUN}\b.*\b(?:programad[oa]s?|agendad[oa]s?|planead[oa]s?|scheduled|planned|booked)\b|"
    rf"\b(?:programad[oa]s?|agendad[oa]s?|planead[oa]s?|scheduled|planned|booked)\b.*\b{OWN_EVENT_NOUN}\b|"
    rf"(?:^|\b(?:la|el|las|los|the)\s+(?:\w+\s+)?){OWN_EVENT_NOUN}(?:\s+\w+)?(?:\s+(?:de|con|with|of)\s+\w+)?\s+"
    r"(?:(?:de|del|of|on|for)\s+)?"
    r"(?:hoy|ayer|anteayer|anoche|manana|pasado\s+manana|esta\s+(?:manana|tarde|noche)|este\s+\w+|"
    r"(?:el\s+)?(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)|today|yesterday|tomorrow|tonight|"
    r"this\s+(?:morning|afternoon|evening)|(?:on\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b|"
    rf"\b(?:today|yesterday|tomorrow|tonight|this\s+(?:morning|afternoon|evening))'?s\s+(?:\w+\s+)?{OWN_EVENT_NOUN}\b|"
    # The meeting or the appointment is the person's unless it is someone's («la reunión del G20»).
    r"\b(?:la|las|el|los|the|esta|this)\s+(?:\w+\s+)?(?:reunion|reuniones|meetings?|appointments?)\b"
    r"(?!\s+(?:de|del|of)\b)"
)


def own_event_reference(text: str) -> bool:
    """Whether a request names an event of the person's own agenda without a possessive (see above); never a
    public one («el concierto de esta noche», «the match today» are ``_PUBLIC_SCHEDULE``)."""

    folded = _fold(text)
    return _OWN_EVENT.search(folded) is not None and not _has(folded, _PUBLIC_SCHEDULE)


def _window_tail(tail: str) -> bool:
    """Nothing after the agenda words, or only the window they are asked for."""

    tail = tail.strip()
    return not tail or is_window_phrase(tail)


def agenda_read_request(text: str) -> bool:
    """A question about the person's own agenda: what they have (planned, to do, coming up), their
    schedule or plans for a window, when their own event is, their next events. Not a change to the
    agenda, not BAXY's own alarms (``_AGENDA_LISTING``), not a public schedule, not a statement that
    goes on to ask something else («tengo una cita mañana, recuérdame»)."""

    envelope = _strip_request_envelope(_fold(text))
    # «up coming events»: the transcription splits the word.
    folded = re.sub(r"\bup\s+coming\b", "upcoming", envelope.strip(" ¿?¡!.,;:"))
    if (
        not folded
        or re.match(_AGENDA_LISTING, envelope) is not None
        or folded.startswith(("no ", "not "))
        # «dame un recordatorio veinticuatro horas antes de mi reunión»: BAXY's own alarms and
        # reminders are scheduled and listed by their own readers.
        or _has(folded, r"\b(?:recordatorios?|reminders?|alarmas?|alarms?|alertas?|alerts?|avisos?|"
                        r"notificacion(?:es)?|notifications?|despertador)\b")
        # «cuántos contactos tengo en mi agenda»: the address book, not the calendar (messaging.contact_book_request).
        or _has(folded, r"\b(?:contactos?|contacts?|telefonos|numeros\s+de\s+telefono|phone\s+numbers)\b")
        or _has(folded, AGENDA_NOT_A_READ)
    ):
        return False
    head = _request_head(folded)
    if _head_is(head, _AGENDA_CHANGE_HEAD) or any(
        _head_is(_request_head(clause), _AGENDA_CHANGE_HEAD) for clause in _request_clauses(folded)[1:]
    ):
        return False
    asked = "?" in text or _head_is(head, _AGENDA_QUESTION_HEAD)
    own = re.search(
        rf"\b(?:mi|mis|my)\s+(?:(?:proxim[oa]s?|siguientes?|next|upcoming)\s+)?(?:\w+\s+)?{AGENDA_NOUN}\b", folded,
    )
    if own is not None:
        # «cuál es mi horario para el día», «mi horario para el siete de julio está completamente
        # abierto», «what's my schedule like today», «dónde es mi reunión del viernes», «my work schedule».
        return (
            asked
            or says_a_window(folded)
            or re.fullmatch(rf"(?:mi|mis|my)\s+(?:\w+\s+)?{AGENDA_NOUN}", folded) is not None
        )
    if ("?" in text or _head_is(head, _READ_OF_EVENT_HEAD)) and own_event_reference(folded):
        # Uso real 2026-09-24 «a qué hora es la reunión vespertina que tengo con John», «cuándo está
        # programada la boda», «when is the party scheduled», «qué pasó en la reunión de ayer».
        return True
    if re.match(
        r"(?:has|habias|have\s+you|did\s+you)\s+(?:anadido|agregado|puesto|programado|agendado|creado|anotado|"
        rf"added|put|scheduled|created|booked|set\s+up)\b.*\b{OWN_EVENT_NOUN}\b",
        folded,
    ):
        # «has añadido una reunión con Tomás para mañana», «have you added a meeting with Tom tomorrow»:
        # whether it is there is read from the agenda.
        return True
    busy = re.fullmatch(
        r"(?:(?:am|are|will)\s+(?:i|we)\s+(?:be\s+)?|(?:estoy|estare|estamos|estaremos|voy\s+a\s+estar)\s+)"
        r"(?:busy|free|available|booked|occupied|ocupad[oa]s?|libres?|disponibles?)\b(?P<tail>.*)",
        folded,
    )
    if busy is not None:
        # «am I busy this weekend», «estoy ocupado este fin de semana»: whether the agenda has something.
        # Said without a window, only the English question asks it («estoy ocupado» is a statement).
        tail = busy.group("tail")
        return _window_tail(tail) and bool(tail.strip() or folded.startswith(("am ", "are ", "will ")))
    somewhere = re.fullmatch(
        r"(?:(?:yo\s+)?(?:tengo|tenemos)\s+que\s+(?:estar|ir)\s+(?:en\s+|a\s+)?(?:algun\s+(?:lado|lugar|sitio)|"
        r"alguna\s+parte)|do\s+(?:i|we)\s+(?:have|need)\s+to\s+(?:be|go)\s+(?:somewhere|anywhere))\b(?P<tail>.*)",
        folded,
    )
    if somewhere is not None:
        # «tengo que estar en algún lado entre las ocho de la mañana y las cinco de la tarde hoy».
        return _window_tail(somewhere.group("tail"))
    how_is = re.fullmatch(
        rf"(?:como|how)\s+(?:(?:tengo|tenemos)\s+(?:el|la)\s+(?:dia|semana|{AGENDA_NOUN})|"
        rf"(?:esta|va|luce|pinta|is|does|looks?)\s+(?:el|la|the)\s+{AGENDA_NOUN})\b(?P<tail>.*)",
        folded,
    )
    if how_is is not None:
        # «cómo tengo el horario de hoy», «cómo luce la agenda del viernes»; «cómo está el día hoy» is the
        # weather, not the agenda.
        return _window_tail(how_is.group("tail"))
    if re.search(
        r"^(?:cuando|a\s+que\s+hora|what\s+time|when|how\s+long|cuanto(?:\s+tiempo)?)\s+"
        r"(?:es|son|sera|seran|empieza|comienza|termina|dura|durara|is|are|will|does|do|starts?|ends?)\b.*"
        r"\b(?:mi|mis|my)\b",
        folded,
    ):
        # «cuándo es mi brunch con Jennifer», «what time is my flight»: the person's own event.
        return True
    if re.search(
        r"^(?:como|how)\s+(?:sera|es|va\s+a\s+ser|se\s+ve|luce|pinta|will|is|looks?)\s+(?:be\s+)?(?:mi|my)\s+"
        r"(?:dia|day|semana|week|proxima\s+semana|next\s+week|manana|tomorrow|fin\s+de\s+semana|weekend)\b"
        r"|^what'?s?\s+(?:is\s+)?my\s+(?:day|week|weekend)\s+like\b",
        folded,
    ):
        # «cómo será mi próxima semana».
        return True
    if _has(folded, _PUBLIC_SCHEDULE):
        return False
    if re.search(rf"\b(?:proxim[oa]s?|siguientes|upcoming|next)\s+(?:\w+\s+)?{AGENDA_NOUN}\b", folded) and (
        asked or re.match(r"(?:(?:los|las|the)\s+)?(?:proxim[oa]s|siguientes|upcoming|next)\b", folded)
    ):
        # «próximos eventos en calendario», «cuáles son los próximos tres eventos».
        return True
    listed = re.fullmatch(
        rf"(?:(?:any|some|algun[oa]?s?|tod[oa]s\s+(?:l[oa]s|mis)|all(?:\s+(?:the|my))?|el|la|los|las|the)\s+"
        rf"(?:\w+\s+)?)?{AGENDA_NOUN}\b(?P<tail>.*)",
        re.sub(rf"^(?:{_LIST}|cuentame|contame|dame|tell\s+me|give\s+me)\s+", "", folded),
    )
    if (
        listed is not None
        and (listed.group("tail").strip() or re.fullmatch(r"(?:horarios?|agenda|schedules?)", folded))
        and _window_tail(listed.group("tail"))
    ):
        # «any meeting on friday», «cuéntame todos los eventos entre hoy y el veintiuno», «horario»,
        # «el calendario de mayo»: the agenda nouns and the window they are asked for.
        return True
    marker = rf"(?:(?:que\s+hacer|to\s+do|por\s+venir|pendientes?|{_AGENDA_PARTICIPLE})\b)"
    what_have = re.fullmatch(
        rf"(?:que|what)\s+{_AGENDA_HAVE}\s+(?P<marker>{marker}\s*)?(?:yo\s+)?(?P<tail>.*)", folded,
    )
    if what_have is not None and (what_have.group("marker") or what_have.group("tail")):
        # «qué tengo por venir», «qué tengo que hacer esta semana», «qué hay hoy», «what do I have today».
        return _window_tail(what_have.group("tail"))
    noun_first = re.fullmatch(
        rf"(?:que|what|which|cuales|cuantas|cuantos|how\s+many)\s+{AGENDA_NOUN}\s+"
        rf"(?:{_AGENDA_HAVE}|(?:esta|estan|is|are)\s+{_AGENDA_PARTICIPLE}|{_AGENDA_PARTICIPLE})?\s*(?P<tail>.*)",
        folded,
    )
    if noun_first is not None:
        # «qué eventos hay la semana que viene», «qué reunión está programada para hoy».
        return _window_tail(noun_first.group("tail"))
    have = re.fullmatch(
        rf"(?:{_AGENDA_HAVE})\s+(?P<det>{_AGENDA_DETERMINER}\s+)?(?:(?:de\s+)?{AGENDA_NOUN}\b\s*)?"
        rf"(?P<marker>{marker}\s*)?(?P<tail>.*)",
        folded,
    )
    if have is not None and (have.group("det") or re.match(rf"(?:{_AGENDA_HAVE})\s+{AGENDA_NOUN}\b", folded)):
        # «tengo algo planeado», «tengo algo programado para el cuatro de julio», «hay algún evento
        # para los próximos tres meses», «do I have anything set for the fourth of July».
        indefinite = (have.group("det") or "").strip() in {"un", "una", "a", "an"}
        return (
            (have.group("marker") is not None or bool(have.group("tail").strip()) or asked)
            and (asked or not indefinite)
            and _window_tail(have.group("tail"))
        )
    if re.match(r"(?:cual|what)\s+(?:es\s+)?(?:el|the)\s+plan\b|what'?s\s+the\s+plan\b", folded):
        # «cuál es el plan hoy».
        return _window_tail(re.sub(r"^.*?\bplan\b", "", folded))
    return bool(
        re.match(
            rf"(?:{_LIST}|dame|lee|leeme|revisa|consulta|mira|tell\s+me|give\s+me|read|check|show)\s+(?:me\s+)?"
            r"(?:el|la|the)\s+(?:calendario|agenda|calendar)\b",
            folded,
        )
        and _window_tail(re.sub(r"^.*?\b(?:calendario|agenda|calendar)\b", "", folded))
    )


# Uso real 2026-09-24 «do i have any reminders pending», «tengo alarmas puestas para mañana»: whether BAXY holds
# reminders or alarms is a read of them (reminders are listed by ``reminder.list``, alarms by
# ``notification.list``).
# Tanda 7b «what have I got set right now?» after a timer and a reminder, rewritten as «what alarms, timers and
# reminders have I got set right now?»: a timer is a scheduled alarm, several kinds are asked together, and «what
# … have I got» asks the same as «do I have». Each kind named is its read.
_INVENTORY_KIND = r"(?:reminders?|recordatorios?|alarms?|alarmas?|timers?|temporizador(?:es)?)"
_INVENTORY_KINDS = rf"{_INVENTORY_KIND}(?:\s*,?\s*(?:(?:and|y|or|o|&)\s+)?{_INVENTORY_KIND})*"
_INVENTORY_HAVE = r"(?:do\s+(?:i|we)\s+have|have\s+(?:i|we)\s+got|are\s+there|is\s+there|(?:yo\s+)?(?:tengo|tenemos)|hay)"
_REMINDER_INVENTORY = re.compile(
    rf"(?:{_INVENTORY_HAVE}\s+(?:(?:any|some|algun[oa]?s?)\s+)?{_INVENTORY_KINDS}"
    rf"|(?:what|which|que|cuales|cuantos|cuantas)\s+{_INVENTORY_KINDS}\s+{_INVENTORY_HAVE})"
    r"(?:\s+(?:pendientes?|pending|programad[oa]s?|puest[oa]s?|set|scheduled|activ[oa]s?|active|right\s+now|now|"
    r"ya|todavia|hasta\s+ahora|so\s+far|already|"
    r"ahora(?:\s+mismo)?|(?:for|para|pa)\s+(?:today|tomorrow|tonight|hoy|manana|esta\s+noche)|today|tomorrow|tonight|"
    r"hoy|manana))*"
)


def reminder_inventory_question(text: str) -> tuple[str, ...]:
    """The reads a question about BAXY's own reminders, alarms or timers asks for (see above); () for any other."""

    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.,")
    if _REMINDER_INVENTORY.fullmatch(folded) is None:
        return ()
    kinds = re.findall(_INVENTORY_KIND, folded)
    reads = []
    if any(not kind.startswith("r") for kind in kinds):
        reads.append("notification.list")
    if any(kind.startswith("r") for kind in kinds):
        reads.append("reminder.list")
    return tuple(reads)


# --- Something put on the agenda (uso real 2026-09-23) ------------------------------------------------
# «añade una reunión con Tom a mi calendario para las nueve de la mañana», «programa una reunión para el
# martes que viene a las once con Joan», «set me a meeting next tuesday at eleven am with jesse», «marca
# abril veinte como el cumpleaños de mi hermano» were refused, asked how long the meeting lasts, or
# read as nothing. An event is created with what was said: a start with no end lasts an hour, a date
# with no clock that marks a day (a birthday, a holiday) takes the whole day. Only a time never said is
# asked, and a repetition the calendar cannot hold is said, never dropped.
_EVENT_NOUN = (
    r"(?:reunion|reuniones|meetings?|citas?|appointments?|eventos?|events?|llamadas?|calls?|conference\s+call|"
    r"videollamadas?|comida|almuerzo|cena|desayuno|brunch|lunch|dinner|breakfast|practicas?|practice|"
    r"entrenamientos?|training|clases?|class|fiestas?|party|cumpleanos|birthday|vacaciones|vacation|holidays?|"
    r"feriado|festivo|aniversario|anniversary|entrevistas?|interview|examen|exam|turno|sesion|session|"
    r"conferencia|conference|webinar|visita|visit|viaje|trip|boda|wedding|cena|junta|quedada)"
)
# A day the calendar marks whole: no clock is missing for it.
_WHOLE_DAY_NOUN = (
    r"\b(?:cumpleanos|birthday|vacaciones|vacation|holidays?|feriado|festivo|aniversario|anniversary|"
    r"dia\s+libre|day\s+off|dia\s+de|boda|wedding|viaje|trip)\b"
)
_EVENT_HEAD = (
    r"(?:crea|crear|creame|anade|anadir|anademe|anademe|agrega|agregar|agregame|pon|poner|ponme|pone|poneme|"
    r"programa|programar|programame|agenda|agendar|agendame|establece|establecer|establecerme|fija|fijar|"
    r"fijame|marca|marcar|marcame|marque|reserva|reservar|reservame|bloquea|bloquear|incluye|incluir|"
    r"organiza|organizar|arma|armar|haz|hazme|hacer|add|put|schedule|set|create|make|book|mark|block|plan|arrange|"
    # «anota este evento en mi calendario»: a note unless the calendar is named (see agenda_event_request).
    r"anota|anotar|anotame|apunta|apuntar|apuntame)"
)
_NOTE_HEADS = frozenset(("anota", "anotar", "anotame", "apunta", "apuntar", "apuntame"))
# Heads that name the agenda by themselves: whatever they schedule at a time that repeats («programa una
# oración al mediodía todos los viernes») is on the agenda, even when it is no event noun.
_AGENDA_HEADS = frozenset(("agenda", "agendar", "agendame", "schedule", "programa", "programar", "programame"))
_EVENT_ENVELOPE = re.compile(
    r"^(?:(?:will|would|can|could)\s+you\s+|(?:puedes|podes|podrias|quiero|quisiera|necesito|"
    r"i\s+(?:want|need|would\s+like)(?:\s+to)?|let'?s)\s+)?"
    rf"(?P<head>{_EVENT_HEAD})(?:me|nos|le|lo|la)?\s+(?:(?:me|nos|us)\s+)?"
    r"(?:(?:que|that)\s+(?:tengo|tenemos|hay|i\s+have|we\s+have|there\s+is)\s+)?"
)
# Heads that also mean doing the thing now («haz la cena», «make a call», «pon la comida»).
_WEAK_EVENT_HEADS = frozenset(
    ("haz", "hazme", "hacer", "make", "pon", "poner", "ponme", "pone", "poneme", "put", "set", "arma", "armar")
)
_DESIRED_EVENT = re.compile(
    r"^(?:(?:yo\s+)?(?:quiero|quisiera|necesito)|i\s+(?:want|need|would\s+like))\s+"
    rf"(?=(?:(?:una?|an?)\s+)?(?:\w+\s+)?{_EVENT_NOUN}\b)"
)
_MEETING_VERB = re.compile(r"^(?:reunirme|reunirnos|juntarme|juntarnos|quedar|meet)\s+(?:con|with)\s+\S")
_CALENDAR_PLACE = (
    r"\b(?:a|al|en|to|in|on|into)\s+(?:(?:mi|el|la|the|my|tu|your)\s+)?(?:calendario|calendar|agenda)\b"
)
_NOT_AN_EVENT = (
    r"\b(?:alarmas?|alarms?|despertador|recordatorios?|reminders?|temporizador|timer|notas?|notes?|"
    r"tareas?|tasks?|listas?|lists?|musica|music|cancion|song|volumen|volume|brillo|brightness|"
    r"recuerdame|recordame|avisame|notificame|remind\s+me|alert\s+me|notify\s+me)\b"
)
_TITLE_EDGE = (
    r"(?:un|una|unos|unas|el|la|los|las|lo|a|an|the|mi|my|para|for|en|in|on|at|de|del|como|as|que|that|to|"
    r"y|and|por\s+favor|please|nueva|nuevo|new)"
)


_REPEAT_UNITS = {
    **dict.fromkeys(
        ("dia", "dias", "day", "days", "diariamente", "a diario", "daily", "manana", "mananas", "morning",
         "mornings", "tarde", "tardes", "afternoon", "afternoons", "noche", "noches", "night", "nights",
         "evening", "evenings"),
        "daily",
    ),
    **dict.fromkeys(("hora", "horas", "hour", "hours", "hourly"), "hourly"),
}


def said_repetition(text: str) -> str | None:
    """The repetition a scheduling request says («todos los días», «cada hora», «every friday»): the catalog's
    recurrence («daily», «hourly»), «unsupported» for one no alarm or reminder can hold, None when none is said.
    Uso real 2026-09-24 «recordarme que tengo que levantarme a las cinco de la mañana cada día» was scheduled once."""

    recurrence = event_timing(_fold(text)).recurrence
    return None if recurrence is None else _REPEAT_UNITS.get(recurrence, "unsupported")


@dataclass(frozen=True)
class AgendaEvent:
    """One thing the person asks to put on their agenda: ``title`` in their own words, ``timing`` as
    said (``semantic.temporal.EventTiming``), whether it takes the whole day, and the fields still to
    ask (empty when it can be created as said)."""

    title: str
    timing: EventTiming
    whole_day: bool
    missing: tuple[str, ...]
    # «todos los días», «cada hora»: a repetition the calendar cannot hold but a repeating reminder
    # can («daily», «hourly», the catalog's recurrence); None for a single event.
    repeat: str | None = None


def _event_title(body: str, folded_body: str, cut: list[tuple[int, int]]) -> str:
    """The person's words for the event: the body without the cut spans (the order, the calendar,
    the time), trimmed of the articles and prepositions left at its edges."""

    tokens = list(re.finditer(r"\S+", folded_body))
    words = body.split()
    if len(words) != len(tokens):
        words = [token.group() for token in tokens]
    kept = [
        word for word, token in zip(words, tokens)
        if not any(start < token.end() and token.start() < end for start, end in cut)
    ]
    title = " ".join(kept).strip(" ,;:.!?¿¡\"'«»")
    # «un evento llamado Revisión»: what follows the naming word is the title («llamada con Ana» is a call).
    named = re.search(
        r"\b(?!(?:un|una|el|la|a|an|the)\b)\w+\s+(?:llamad[oa]|titulad[oa]|called|named|titled)\s+"
        r"(?P<name>(?!(?:con|with|a|al|de|del|para|por|en|hoy|manana)\b)\S.*)$",
        _fold(title),
    )
    if named is not None:
        title = " ".join(title.split()[len(_fold(title)[: named.start("name")].split()):])
    edge = re.compile(rf"^(?:{_TITLE_EDGE})\s+|\s+(?:{_TITLE_EDGE})$", re.IGNORECASE)
    while True:
        folded_title = _fold(title)
        found = edge.search(folded_title)
        if found is None:
            break
        title = (
            " ".join(title.split()[len(found.group().split()):]) if found.start() == 0
            else " ".join(title.split()[: len(title.split()) - len(found.group().split())])
        ).strip(" ,;:.!?\"'«»")
    return title if re.search(r"[^\W\d_]", title) else ""


def agenda_event_request(text: str) -> AgendaEvent | None:
    """A request to put one event on the agenda, or None. Its title is what the person named (with
    whom, where), its time is read by ``event_timing``; what is missing is what was never said."""

    body = _request_body_surface(text).strip().rstrip(" .!?")
    folded_body = _fold(body)
    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.,")
    if folded_body.split() != folded.split():
        body, folded_body = folded, folded
    if not folded or folded.startswith(("no ", "not ", "don't ", "dont ")):
        return None
    calendar_place = re.search(_CALENDAR_PLACE, folded_body)
    envelope = _EVENT_ENVELOPE.match(folded_body)
    lead_end = 0
    if envelope is not None:
        head = envelope.group("head")
        rest = folded_body[envelope.end():]
        # «pon una alarma», «añade leche a la lista»: an order about something else. «anota/apunta» is
        # a note unless the calendar is named; a bare «set/put/make» needs the event as its object.
        # 742 H0256/H0288/H0629 «crea una carpeta llamada proyectos»: «llamada» after the thing it names is
        # the participle («named»), not a phone call; «otra llamada con Ana» still is one.
        object_is_event = re.match(
            rf"(?:(?:un|una|el|la|mi|a|an|the|my|nueva|new)\s+)*"
            rf"(?:\S+\s+(?!llamad[oa]s?\s+(?!(?:con|a|al|de|del|para|por|en|hoy|manana)\b)\S))?{_EVENT_NOUN}\b",
            rest,
        )
        # Uso real 2026-09-24 «pon duele como el cielo» (a song) was asked when the event starts: what is
        # marked «como/as» something is a day only when a day was said before it.
        marked = re.search(r"\b(?:como|as)\s+(?:(?:el|la|mi|my|a|an|the)\s+)?\S", rest)
        marks_a_day = marked is not None and says_a_window(rest[: marked.start()]) and head in {
            "marca", "marcar", "marcame", "marque", "mark", "pon", "poner", "ponme", "pone", "poneme", "put", "set"
        }
        if (_has(rest, _NOT_AN_EVENT) or head in _NOTE_HEADS) and calendar_place is None:
            return None
        rest_timing = event_timing(rest)
        if (
            object_is_event is None
            and calendar_place is None
            and not marks_a_day
            # «programa una oración al mediodía todos los viernes»: an agenda head with a time said.
            and not (head in _AGENDA_HEADS and rest_timing.start is not None and rest_timing.recurrence is not None)
        ):
            return None
        if (
            head in _WEAK_EVENT_HEADS
            and calendar_place is None
            and not marks_a_day
            and event_timing(rest).start is None
            and not says_a_window(rest)
            and not re.search(r"\b(?:con|with)\s+\S", rest)
        ):
            # «haz la cena», «haz una llamada a mamá», «pon la comida»: doing the thing now, not putting
            # it on the agenda; with a time, a companion or the calendar named it is an event.
            return None
        lead_end = envelope.end()
    elif (desired := _DESIRED_EVENT.match(folded_body)) is not None:
        lead_end = desired.end()
    elif _MEETING_VERB.match(folded_body) is not None:
        lead_end = 0
    else:
        return None
    timing = event_timing(folded_body)
    cut = [(0, lead_end), *timing.spans]
    if calendar_place is not None:
        cut.append(calendar_place.span())
    title = _event_title(body, folded_body, cut)
    if re.fullmatch(rf"(?:este|esta|ese|esa|aquel|aquella|this|that)\s+{_EVENT_NOUN}", _fold(title)):
        # «anota este evento en mi calendario»: an event pointed at is not named; what it is is asked.
        title = ""
    said_day = says_a_window(folded_body)
    whole_day = timing.start is None and said_day and _has(folded_body, _WHOLE_DAY_NOUN + r"|\b(?:como|as)\b")
    missing: list[str] = []
    if not title:
        missing.append("event_title")
    repeat = _REPEAT_UNITS.get(timing.recurrence or "")
    bounded = re.search(
        r"\b(?:cada|todos\s+los|todas\s+las|every|each)\s+\w+\s+"
        r"(?P<bound>(?:de|del|of|durante|during|hasta|until|this|esta|este|next)\s+.+)$",
        folded_body,
    )
    if (timing.recurrence is not None and repeat is None) or (
        repeat is not None and bounded is not None and says_a_window(bounded.group("bound"))
    ):
        # «cada miércoles de marzo»: neither the calendar nor a reminder repeats weekly; «todos los días de
        # esta semana» (uso real 2026-09-24): nor stops repeating at a date. The question says so and offers
        # what can be done.
        missing.append("repetition_the_calendar_cannot_hold")
    elif timing.start is None and not whole_day:
        missing.append("start_time" if said_day or timing.end is not None else "event_date_and_time")
    elif timing.start is not None and not timing.start.resolved:
        missing.append("am_pm_or_part_of_day_for_supplied_hour")
    return AgendaEvent(title, timing, whole_day, tuple(missing), repeat)


# «tengo una reunión el miércoles a las nueve de la mañana, envíame un recordatorio», «tengo cita a las
# cinco de la tarde, recuérdamelo» (uso real 2026-09-23): the event is stated, then a reminder of it asked.
_STATED_EVENT_REMINDER = re.compile(
    rf"^(?:(?:yo\s+)?tengo|i\s+have)\s+(?P<title>.+?)\s+(?P<due>{CLOCK_PHRASE})\s*[,.;]?\s+(?:y\s+)?"
    r"(?:(?:enviame|mandame|dame|ponme|hazme|send\s+me|give\s+me|set)\s+(?:un|una|a|an)\s+"
    r"(?:recordatorio|reminder|aviso|alerta|notificacion|alert|notification)\b[^,;]*|"
    r"recuerdamelo|recordamelo|avisame|remind\s+me(?:\s+(?:of|about)\s+it)?)[\s.!?]*$"
)


def stated_event_reminder(text: str) -> tuple[str, str] | None:
    """(title, moment) of an event stated and then asked to be reminded of, in the person's writing."""

    body = _request_body_surface(text).strip()
    folded = _fold(body)
    found = _STATED_EVENT_REMINDER.match(folded)
    clock = spoken_clock(found.group("due")) if found is not None else None
    if found is None or clock is None or not clock.resolved:
        return None
    words = body.split()

    def original(group: str) -> str:
        start = len(folded[: found.start(group)].split())
        return " ".join(words[start : start + len(found.group(group).split())]).strip(" ,;")

    return original("title"), original("due")


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
            # «una hora antes de la reunión»: counted from an event whose time is not said.
            r"(?:\s+(?:from now|desde ahora))?\b(?!\s+(?:antes|despues|before|after)\b)",
        )
        or _has(folded, r"\b\d{4}-\d{2}-\d{2}t\d{2}:\d{2}(?::\d{2})?\S*\b")
    )


_ALARM_CLOCK = (
    r"(?:[0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|eleven|twelve|una?|dos|tres|cuatro|cinco|seis|siete|"
    r"ocho|nueve|diez|once|doce)(?::[0-5][0-9])?"
)
_ALARM_PERIOD = (
    r"(?:a\.?\s*m\.?|p\.?\s*m\.?|de\s+la\s+manana|de\s+la\s+tarde|de\s+la\s+noche|"
    r"in\s+the\s+morning|in\s+the\s+afternoon|in\s+the\s+evening)"
)
# Plural alarms with their times: «set alarms for 2pm and 3pm», «pon alarmas a las 7 y a las 8 de la mañana», «set
# two alarms, one at 5pm and one at 6pm», «set an alarm for 2pm and another for 3pm», also asked as a wish («i want
# you to…», «quiero que me pongas…»).
_MULTIPLE_ALARMS = re.compile(
    r"[^\w]*(?:(?:i\s+(?:want|need|would\s+like)|i'?d\s+like)\s+you\s+to\s+|(?:quiero|necesito)\s+que\s+(?:me\s+)?)?"
    r"(?:record|create|set|schedule|make|add|crea|crear|creame|programa|programar|programame|pon|ponme|poner|"
    r"ponerme|configura|configurar|configurame|activa|activame|agrega|anade|pongas|programes|crees|configures|actives)"
    r"\s+(?:(?:the|las?|two|three|four|dos|tres|cuatro|some|unas|an?|una)\s+)?(?:alarmas?|alarms?)\b\s*,?\s*"
    r"(?P<items>\S.*)",
    re.IGNORECASE,
)
_ALARM_ITEM_SEPARATOR = re.compile(r"\s*(?:,\s*(?:and\s+|y\s+)?|\s(?:and|y|e)\s)\s*")
_ALARM_ITEM = re.compile(
    r"(?:(?:one|another|the\s+other|una|otra|la\s+otra)\s+)?(?:(?:for|at|a|para)\s+)?(?:las?\s+)?"
    rf"(?P<clock>{_ALARM_CLOCK})(?:\s*(?P<period>{_ALARM_PERIOD}))?[\s.!?]*",
    re.IGNORECASE,
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
    request = _MULTIPLE_ALARMS.fullmatch(folded)
    if request is None:
        return None
    # Tanda 6 «i want you to set alarms for 2pm and 3pm» was asked «What time…?»: each time may carry its own
    # period, and a period said only after the last time is shared by all of them («for 3 and 4 in the afternoon»).
    found = [_ALARM_ITEM.fullmatch(part) for part in _ALARM_ITEM_SEPARATOR.split(request.group("items"))]
    if any(item is None for item in found):
        return None
    periods = [item.group("period") for item in found]
    if periods[-1] is not None and not any(periods[:-1]):
        periods = [periods[-1]] * len(periods)
    items = [(item.group("clock"), period) for item, period in zip(found, periods)]
    clocks = tuple(clock for clock, _ in items)
    if not 2 <= len(clocks) <= 8 or len(set(items)) != len(items) or any(period is None for _, period in items):
        return None
    for clock in clocks:
        hour_text = clock.split(":", 1)[0]
        if hour_text.isdigit() and not 1 <= int(hour_text) <= 12:
            return None
    noun = "alarma a las" if _has(folded, r"\balarmas?\b") else "alarm at"
    evidence = tuple(f"{noun} {clock} {period.strip()}" for clock, period in items)
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
    r"(?P<list>(?:listas?|lists?)(?:\s+(?:de(?:\s+la|\s+los|\s+las|l)?|para(?:\s+la|\s+el)?|of|for)\s+[^,;.!?]{1,60}?)?"
    # Tanda 4 2026-09-24 «please put the meeting with carla on my to do list»: the ear writes «to do» apart.
    # Dev set 2 «add buy groceries to my to do list for today»: the day said after the list is part of its name.
    r"|(?:shopping|grocery|to[\s-]?do|todo|task|packing)\s+list(?:\s+(?:for|from)\s+(?:today|tomorrow|tonight|this\s+week))?)"
)
# The list an entry goes on or comes off: whose it is, or a new one («put pencil on a new grocery list»).
_LIST_DETERMINER = r"(?:(?:mi|la|tu|nuestra|una|esta|my|the|our|a|this)\s+)?(?:(?:nueva|new)\s+)?"
# The person's verb as said to a friend or with «usted» («por favor agregue este artículo a la lista»).
_LIST_VERB = (
    r"^(?:(?:por\s+favor|please)\s*,?\s+)?"
    r"(?:a[nñ]ad[eií](?:me|r)?|a[nñ][aá]deme|a[nñ]ada|agreg[aá](?:me|r)?|agr[eé]game|agregue|p[oó]n(?:me|er)?|pon[eé](?:me)?|"
    r"ponga|met[eé](?:me|r)?|m[eé]teme|meta|apunt[aá](?:me|r)?|ap[uú]ntame|apunte|anot[aá](?:me|r)?|an[oó]tame|anote|"
    r"inclu(?:ye|ir|ya)|sum[aá](?:le|r)?|add|put|include|insert)\s+"
)
_LIST_CLOSE = r"(?:\s*,?\s*(?:please|pls|plz|por\s+favor|porfa))?[\s.!?]*$"
_LIST_ENTRY = re.compile(
    _LIST_VERB + r"(?P<item>\S.{0,200}?)\s+(?:a|al|en|to|on|in|into)\s+" + _LIST_DETERMINER + _LIST_NAME + _LIST_CLOSE,
    re.IGNORECASE,
)
# Tanda 8 «apúntame en la lista de la compra huevos, leche y pan de molde» was asked for a note: the list named
# first and the entries after it. Its name is then one word after «de» («lista de la compra», «lista del súper»),
# since nothing else marks where the name ends and the entries begin.
_LIST_ENTRY_AFTER = re.compile(
    _LIST_VERB + r"(?:a|al|en|to|on|in|into)\s+" + _LIST_DETERMINER
    + r"(?P<list>(?:listas?|lists?)(?:\s+(?:de(?:\s+la|\s+los|\s+las|l)?|para(?:\s+la|\s+el)?)\s+(?!(?:la|los|las|el)\b)\w+)?|"
    r"(?:shopping|grocery|to[\s-]?do|todo|task|packing)\s+list)"
    r"\s*[,:]?\s+(?P<item>(?!(?:de|del|para|of|for)\b)\S.{0,200}?)" + _LIST_CLOSE,
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
    # Dev set 2 «añade esto a la lista», «por favor agregue este artículo a la lista»: an entry only pointed at
    # names nothing either.
    r"|(?:esto|eso|aquello|it|this|that)|(?:este|esta|ese|esa|estos|estas|esos|esas|this|that|these|those)\s+\S+"
)


# Tanda 4 «add flour to my shopping list if it's not already on it» was asked back: an entry to add only when
# the list does not have it yet. The condition closes the order and says the entry may already be there (a
# negation, «ya/already/yet», or something missing). The list is read first (``list_read_request``).
_ABSENCE_CONDITION = re.compile(
    r"\s*[,;]?\s*(?P<condition>(?:(?:only|solo|solamente)\s+)?"
    r"(?:if|si|unless|a\s+menos\s+que|salvo\s+que|en\s+caso\s+de\s+que)\b"
    r"(?=[^,;.!?]*\b(?:no|not|isn'?t|aren'?t|don'?t|doesn'?t|ya|already|todavia|aun|yet|falta|faltan|missing)\b)"
    r"[^,;.!?]{1,80}?)[\s.!?]*$"
)


def list_entry_request(text: str) -> tuple[str, str] | None:
    """(entry, list) of «añade X a mi lista de la compra», «pon hamburguesa en mi lista de
    comestibles», «add milk to my shopping list», in the person's own writing; None for a
    playlist, a pointed entry («esto», «esa canción»), an entry added only if absent or any
    other shape."""

    surface = _request_body_surface(text).strip()
    if _ABSENCE_CONDITION.search(_fold(surface)) is not None:
        return None
    found = _LIST_ENTRY.match(surface) or _LIST_ENTRY_AFTER.match(surface)
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
    r"(?:(?:crea|creame|crear|haz|hazme|hacer|arma|armame|armar|empieza|empezar|comienza|comenzar|"
    r"inicia|iniciar|create|make|start|nueva|new)\s+(?:(?:una|un|la|a|the)\s+)?"
    # Dev set 2: «abre la lista de la compra» opens the one there is (a read); a list is opened new only as one.
    r"|(?:abre|abrir)\s+(?:(?:una|un)\s+|la\s+(?=nueva\s)))(?:(?:nueva|new)\s+)?(?:lista|list)"
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


# Dev set 2 (2026-09-24): «we're out of paint so take bathroom painting off the list» and «eliminar mi lista de
# tareas pendientes» read the list instead. An entry taken off a list is its task sent to the recoverable trash
# (task.delete, after task.resolve.exact finds it by the title it was added with); a whole list removed is every
# entry at once, which no operation does (``known_unsupported_effect_request``).
# The reason said first («we're out of paint so …», «ya compré el pan, así que …»); a condition is not a reason.
_REMOVAL_LEAD = (
    r"^(?:(?!(?:si|if|cuando|when)\b)[^.!?]{1,160}?[\s,;]+(?:so|as[ií]\s+que|entonces|por\s+eso)[\s,]+)?"
    r"(?:(?:por\s+favor|please)\s*,?\s+)?"
)
# The verbs as written, with or without the accent of an attached pronoun («quítame el arroz de la lista»).
_ENTRY_OFF_VERB = (
    r"(?:elim[ií]n[ae](?:me|r)?|elimine|b[oó]rr[ae](?:me|r)?|borre|qu[ií]t[ae](?:me|r)?|quite|s[aá]c[ae](?:me|r)?|saque|"
    r"t[aá]ch[ae](?:me|r)?|tache|remove|delete|erase|scratch|cross|take|drop)"
)
_WHOLE_LIST_OFF_VERB = (
    r"(?:elim[ií]n[ae](?:me|r)?|elimine|b[oó]rr[ae](?:me|r)?|borre|qu[ií]t[ae](?:me|r)?|quite|vac[ií]a(?:me|r)?|vac[ií]e|"
    r"limpi[ae](?:me|r)?|deshazte\s+de|deshacerme\s+de|remove|delete|erase|clear(?:\s+out)?|empty|get\s+rid\s+of)"
)
_REMOVAL_END = r"(?:\s*,?\s*(?:please|pls|plz|por\s+favor|porfa))?[\s.!?]*$"
_LIST_REMOVAL = (
    re.compile(
        _REMOVAL_LEAD + _ENTRY_OFF_VERB + r"\s+(?P<item>\S.{0,120}?)\s+(?:off(?:\s+of)?|from|out\s+of|de|del)\s+"
        r"(?:(?:mi|la|tu|nuestra|esta|esa|my|the|our|this|that)\s+)?" + _LIST_NAME + _REMOVAL_END,
        re.IGNORECASE,
    ),
    re.compile(
        _REMOVAL_LEAD + r"(?:" + _WHOLE_LIST_OFF_VERB
        + r"\s+(?:(?:toda\s+)?(?:mi|mis|la|las|esta|esa|my|the|this|that)\s+|all\s+(?:of\s+)?(?:my|the)\s+)?|"
        r"(?:i\s+(?:don'?t|do\s+not)\s+(?:want|need)|ya\s+no\s+(?:quiero|necesito))\s+(?:mi|la|esta|esa|my|the|this|that)\s+)"
        + _LIST_NAME + r"(?:\s+(?:any\s*more|ya|m[aá]s))?" + _REMOVAL_END,
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True, slots=True)
class ListRemoval:
    """An entry taken off one of the person's lists, as said (None when the whole list is removed), and the list."""

    entry: str | None
    list_name: str


def list_removal_request(text: str) -> ListRemoval | None:
    """«take bathroom painting off the list», «quita la leche de mi lista de la compra» (an entry), «eliminar la
    lista de cosas por hacer», «i don't want this list any more» (the whole list), in the person's own writing;
    None for a playlist, another store («borra mi lista de alarmas»), a pointed or unnamed entry, or any other
    shape (a negation never matches: the order opens the request)."""

    surface = _request_body_surface(text).strip()
    for pattern in _LIST_REMOVAL:
        found = pattern.match(surface)
        if found is None:
            continue
        listed = found.group("list").strip(" ,;:\"'«»“”")
        item = (found.groupdict().get("item") or "").strip(" ,;:\"'«»“”")
        folded_item = _fold(item)
        if (
            _has(f"{folded_item} {_fold(listed)}", _LIST_NOT_TASKS)
            or _has(_fold(listed), _LIST_OF_ANOTHER_STORE)
            or (item and re.fullmatch(_UNNAMED_LIST_ENTRY, folded_item) is not None)
        ):
            return None
        entry = re.sub(r"^(?:el|la|los|las|un|una|unos|unas|the|an?|some)\s+(?=\S)", "", item, flags=re.IGNORECASE)
        return ListRemoval(entry or None, listed)
    return None


# Uso real 2026-09-23 (tanda 2): the person's lists read back. «do i have cheese on my
# shopping list if not please add it» became a conversation answering «No, no hay queso …
# Se añadirá.» with nothing read or added; «decir la lista», «is my todo list free» and
# «tengo algo en mi lista de cosas por hacer» were asked back or answered with nonsense.
# A list is its entries (``list_entry_request``): the to-do list with no other name is
# every open task (task.list); a list named otherwise is the tasks that name it
# (task.search reads titles and details), and one entry asked about is searched by itself.
# Dev set 2: every list the person keeps («dime qué listas tengo», «puedo comprobar mis listas») is every entry.
_TODO_LIST = (
    r"(?:(?:to[\s-]?do|todo|task|tasks|chores?)\s+list|list\s+of\s+(?:things\s+to\s+do|tasks|to[\s-]?dos|chores)|"
    r"lista\s+de\s+(?:tareas|pendientes|quehaceres|to-?dos?|cosas\s+(?:por|que|para)\s+hacer)|listas|lista|lists|list)"
)
_NAMED_LIST = (
    r"(?:lista|list)\s+(?:de(?:\s+la|\s+los|\s+las|l)?|para(?:\s+la|\s+el)?|of|for)\s+[a-z0-9'-]+(?:\s+[a-z0-9'-]+){0,3}"
    r"|[a-z0-9'-]+(?:\s+[a-z0-9'-]+)?\s+list"
)
# «la lista de los planetas» is public knowledge; with the article only the to-do list
# and the shopping list are the person's.
_HOUSEHOLD_LIST = (
    r"lista\s+(?:de(?:\s+la|\s+las)?|del)\s+(?:compras?|supermercado|super|mercado|comestibles)"
    r"|(?:shopping|grocery|groceries)\s+list"
)
_OWN_LIST = (
    rf"(?:(?:mi|mis|my)\s+(?P<list>{_TODO_LIST}|{_NAMED_LIST})|(?:la|las|the)\s+(?P<the_list>{_HOUSEHOLD_LIST}|{_TODO_LIST})"
    # Dev set 2 «que esta en esta lista especifica», «what is on this specific list»: the list pointed at is
    # the person's list, with no other name.
    r"|(?:esta|esa|this|that)\s+(?:(?:specific|particular)\s+)?(?P<this_list>lista|list)(?:\s+(?:especifica|en\s+particular))?)"
)
# The day the list is for («what is on the list for today»): the whole list is read, its dates with it.
_LIST_DAY = r"(?:\s+(?:for|from|de|para)\s+(?:today|tomorrow|tonight|this\s+week|hoy|manana|esta\s+semana))?"
# Another store the person keeps is read by its own operation («my list of reminders»).
_LIST_OF_ANOTHER_STORE = (
    r"\b(?:recordatorios?|reminders?|alarmas?|alarms?|notas?|notes?|eventos?|events?|citas?|appointments?|"
    r"calendario|calendar|correos?|e-?mails?|mails?|archivos?|files?|carpetas?|folders?|ventanas?|windows?|"
    r"procesos?|process(?:es)?|apps?|aplicaciones?|programas?|programs?|descargas?|downloads?|juegos?|games?|"
    r"redes|networks?|wifi|dispositivos?|devices?|pestanas?|tabs?)\b"
)
_ANYTHING = r"(?:algo|alguna\s+cosa|cosas|algun\s+pendiente|pendientes|tareas|anything|something|stuff|any\s+(?:items?|things?|tasks?))"
# The verbs that ask to see a list, as said to a friend or with «usted» (dev set 2 «comprueba mi lista», «reúne
# mi lista», «abrir mi lista», «bing up my list» — the ear's «bring up»).
_LIST_READ_VERB = (
    r"(?:dime|decime|di|decir|dame|diga|digame|lee|leeme|leer|lea|repite|repiteme|repetir|repasa|repasame|muestra|"
    r"muestrame|mostrame|mostrar|muestre|ensename|revisa|revisame|revisar|revise|consulta|consultar|consulte|recita|"
    r"comprueba|comprobar|compruebe|chequea|chequear|abre|abreme|abrir|abra|reune|reuneme|reunir|trae|traeme|saca|"
    r"sacame|ver)"
)
_LIST_READ_VERB_EN = (
    r"(?:read|tell|show|repeat|say|give|recite|check|review|open|display|(?:bring|pull|bing)\s+up|go\s+over|look\s+at)"
)
# «dime qué listas tengo», «que listas están disponibles ahora», «display available lists», «cuáles fueron las
# últimas cinco listas que hice»: the lists the person keeps, which are their entries.
_LIST_INVENTORY = (
    rf"(?:(?:{_LIST_READ_VERB}|{_LIST_READ_VERB_EN}|list)(?:\s+me)?\s+)?(?:que|cuales|cuantas|what|which|how\s+many)\s+(?P<list>listas|lists)\s+"
    r"(?:tengo|hay|he\s+hecho|hice|he\s+creado|cree|guarde|(?:estan|hay|tengo)\s+disponibles|(?:do\s+)?i\s+have|"
    r"have\s+i\s+(?:made|got|created)|did\s+i\s+(?:make|create)|are\s+(?:there|available|saved))"
    r"(?:\s+(?:ahora(?:\s+mismo)?|(?:right\s+)?now))?",
    rf"(?:{_LIST_READ_VERB}|{_LIST_READ_VERB_EN}|list)(?:\s+me)?\s+(?:(?:all\s+)?(?:my|the)\s+|(?:todas\s+)?(?:mis|las)\s+)?"
    r"(?:available\s+)?(?P<list>lists|listas)(?:\s+(?:disponibles|available))?"
    # «enséñame las listas que tengo», «show me the lists i made».
    r"(?:\s+(?:que\s+(?:tengo|hice|he\s+hecho|cree|he\s+creado|guarde)|(?:that\s+)?i\s+(?:have|made|created|saved)))?",
    r"(?:que|cuales)\s+(?:fueron|son|eran)\s+(?:las|mis)\s+(?:(?:ultimas|primeras)\s+)?(?:\S+\s+)?(?P<list>listas)\s+que\s+"
    r"(?:hice|he\s+hecho|cree|he\s+creado|tengo|guarde)",
    r"what\s+(?:were|are)\s+(?:the|my)\s+(?:(?:last|latest|first)\s+)?(?:\S+\s+)?(?P<list>lists)\s+(?:that\s+)?i\s+"
    r"(?:made|created|have|saved)",
    # «check list»: the list said bare after the verb.
    r"(?:check|review|open|show|display|read|comprueba|revisa|abre|muestra|lee)\s+(?P<list>lista|list)",
)
_AGAIN = r"(?:otra\s+vez|de\s+nuevo|nuevamente)"
_WHOLE_LIST_READ = (
    # Tanda 8 «¿qué llevo ya en la lista de la compra?» (the rewrite of «¿qué llevo ya?»): «ya», «hasta ahora».
    rf"que\s+(?:mas\s+)?(?:hay|tengo|queda|quedan|llevo|puse|anote|esta|estan)"
    rf"(?:\s+(?:ya|ahora|todavia|aun|hasta\s+ahora))?\s+(?:en|dentro\s+de)\s+{_OWN_LIST}",
    rf"(?:que|cual)\s+es\s+(?:lo|la\s+(?:cosa|tarea))\s+(?:siguiente|proxim[oa]|primer[oa]?|ultim[oa])\s+(?:en|de)\s+{_OWN_LIST}",
    rf"(?:que\s+es\s+(?:esto|eso)|what(?:'s|s|\s+is)\s+(?:this|that))\s+(?:en|de|on|in)\s+{_OWN_LIST}",
    # Tanda 8 «vale, léemela otra vez la lista de la compra» (the rewrite of «vale, léemela otra vez»): the list said
    # after its pronoun and «otra vez» before it.
    rf"{_LIST_READ_VERB}(?:mel[oa]s?|l[oa]s?)?(?:\s+{_AGAIN})?\s+(?:lo\s+que\s+(?:hay|tengo)\s+en\s+|el\s+contenido\s+de\s+)?"
    rf"{_OWN_LIST}(?:\s+{_AGAIN})?",
    rf"(?:dejame|quiero|quisiera|me\s+gustaria|necesito|puedo)\s+(?:escuchar|oir|ver|saber|revisar|leer|consultar|repasar|"
    rf"comprobar|chequear|abrir)\s+(?:lo\s+que\s+(?:hay|tengo)\s+en\s+)?{_OWN_LIST}",
    rf"(?:tengo|hay)\s+{_ANYTHING}\s+(?:en|dentro\s+de)\s+{_OWN_LIST}",
    rf"tengo\s+(?=mi\s){_OWN_LIST}",
    rf"(?:esta|sigue)\s+(?:vacia|libre|llena)\s+{_OWN_LIST}",
    rf"{_OWN_LIST}\s+(?:esta|sigue)\s+(?:vacia|libre|llena)",
    rf"(?:what(?:'s|s|\s+is|\s+are)|what\s+(?:do|did)\s+i\s+(?:have|put)|what\s+have\s+i\s+got|"
    rf"what\s+else\s+(?:is|are|do\s+i\s+have|have\s+i\s+got))\s+(?:(?:left|still)\s+)?(?:on|in)\s+{_OWN_LIST}",
    rf"what(?:'s|s|\s+is)\s+(?:the\s+)?(?:next|first|last|top)(?:\s+(?:thing|item|task|entry))?\s+(?:on|in)\s+{_OWN_LIST}",
    rf"{_LIST_READ_VERB_EN}(?:\s+(?:me|out))?\s+(?:what(?:'s|\s+is)\s+(?:on|in)\s+|the\s+contents?\s+of\s+)?"
    rf"{_OWN_LIST}(?:\s+(?:back|out|again|aloud))*(?:\s+to\s+me)?",
    rf"(?:let\s+me|i\s+(?:want|need|would\s+like)\s+to|can\s+i)\s+(?:hear|see|check|review|read|open)\s+{_OWN_LIST}",
    rf"(?:is|are)\s+{_OWN_LIST}\s+(?:free|empty|clear|done|full|finished|complete)",
    rf"(?:do\s+i\s+have|have\s+i\s+got|is\s+there|are\s+there)\s+{_ANYTHING}\s+(?:(?:left|still)\s+)?(?:on|in)\s+{_OWN_LIST}",
    *_LIST_INVENTORY,
    # Dev set 2 «did i make a shopping list», «hice una lista de compra»: whether a named list exists is a search
    # for its name.
    rf"(?:did\s+i\s+(?:make|create|write|start)|have\s+i\s+(?:made|created|got)|do\s+i\s+have|hice|he\s+hecho|cree|"
    rf"he\s+creado|tengo|existe)\s+(?:a|an|una|un|alguna|any)\s+(?P<list>{_NAMED_LIST})",
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
    r"(?:\s+(?:it|them|lo|la|los|las))?(?:\s+(?:to|on|a|en)\s+(?:it|the\s+list|la\s+lista|ella|my\s+list|mi\s+lista)|"
    r"\s+(?:on|there|ahi|alli))?"
    r"(?:\s*,?\s*(?:please|por\s+favor))?)?"
)
_LIST_READ_OPENER = (
    r"^[¿?¡!\s]*(?:(?:olly|alexa|bax[yi]|oye|hey|vale|dale|ok|okay|bueno|venga)\s*,?\s+)*(?:(?:please|por\s+favor)\s*,?\s+)?"
)


@dataclass(frozen=True, slots=True)
class ListRead:
    """A read of one of the person's lists: its operation, the search query (None for
    the whole to-do list), the list and the entry asked about as said, and the clause that
    puts that entry on the list when the read finds it absent («if not please add it»,
    empty when none)."""

    operation: str
    query: str | None
    list_name: str
    entry: str | None
    absent_clause: str


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
        found = re.fullmatch(pattern + _LIST_DAY + r"(?:\s*,?\s*(?:please|por\s+favor|porfa))?[\s.!?]*", body)
        if found is not None:
            break
    if found is None:
        for pattern in _LIST_ENTRY_PRESENCE:
            found = re.fullmatch(pattern + _ADD_IF_ABSENT + r"(?:\s*,?\s*(?:please|por\s+favor|porfa))?[\s.!?]*", body)
            if found is not None:
                break
        if found is None:
            return _list_entry_if_absent(body, literal)
        item = found.group("item")
        if re.match(r"(?:esto|eso|esta|este|esa|ese|estas|estos|esas|esos|aquello|it|this|that|these|those)\b", item):
            return None
        if re.fullmatch(_ANYTHING + r"|" + _UNNAMED_LIST_ENTRY, item) is not None:
            entry = None
        else:
            entry = re.sub(
                r"^(?:el|la|los|las|un|una|unos|unas|the|an?|some|any)\s+(?=\S)", "",
                literal(found.start("item"), found.end("item")), flags=re.IGNORECASE,
            )
    group = next(name for name in ("list", "the_list", "this_list") if found.groupdict().get(name) is not None)
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
    return ListRead(operation, query, list_name, entry, literal(found.start("tail"), found.end("tail")) if tail else "")


def _list_entry_if_absent(body: str, literal: Callable[[int, int], str]) -> ListRead | None:
    """«add flour to my shopping list if it's not already on it», «añade harina a mi lista de la compra si no
    está»: the same read as «do i have flour on my shopping list, if not add it» (see ``_ABSENCE_CONDITION``)."""

    condition = _ABSENCE_CONDITION.search(body)
    if condition is None or condition.start() == 0:
        return None
    found = _LIST_ENTRY.match(body[: condition.start()])
    if found is None:
        return None
    item, listed = found.group("item"), found.group("list")
    if (
        _has(f"{item} {listed}", _LIST_NOT_TASKS)
        or _has(listed, _LIST_OF_ANOTHER_STORE)
        or re.match(r"(?:esto|eso|esta|este|esa|ese|estas|estos|esas|esos|aquello|it|this|that|these|those)\b", item)
        or re.fullmatch(_UNNAMED_LIST_ENTRY, item) is not None
    ):
        return None
    entry = re.sub(
        r"^(?:el|la|los|las|un|una|unos|unas|the|an?|some|any)\s+(?=\S)", "",
        literal(found.start("item"), found.end("item")), flags=re.IGNORECASE,
    )
    return ListRead(
        "task.search", entry, literal(found.start("list"), found.end("list")), entry,
        literal(condition.start("condition"), condition.end("condition")),
    )


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
    r"(?:(?:el|este|esta|next|this|el\s+proximo|la\s+proxima|del|on)\s+)?"
    r"(?:hoy|today|manana|tomorrow|pasado\s+manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|semana|week)"
)
# «despiértame todos los días a las siete»: a wake-up alarm that repeats every day.
_WAKE_REPEAT = r"(?:todos\s+los\s+dias|cada\s+dia|todas\s+las\s+mananas|cada\s+manana|every\s+(?:day|morning)|daily)"


def _wake_alarm_request(text: str) -> bool:
    """Recognize a direct wake-up alarm with one explicit clock (its part of the day
    said, «a las seis y cuarto de la mañana») or one duration, and at most a day."""

    folded = _strip_request_envelope(_fold(text))
    found = re.fullmatch(
        r"(?:i\s+need\s+you\s+to\s+)?"
        r"(?:(?:wake|get)\s+me(?:\s+up)?|despiertame|despertame|levantame|"
        # Uso real 2026-09-24 «i want to wake up at six am tomorrow please», «quiero despertarme a las seis».
        r"(?:i\s+(?:want|need)\s+to|i['’]?d\s+like\s+to|(?:yo\s+)?(?:quiero|necesito))\s+"
        r"(?:wake\s+up|get\s+up|despertarme|levantarme))\s+"
        r"(?P<when>\S.*?)(?:\s*,?\s+(?:please|por\s+favor))?[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if found is None:
        return False
    when = found.group("when")
    if re.fullmatch(rf"(?:in|en|dentro\s+de|within)\s+{_RELATIVE_DURATION_PATTERN}", when):
        return True
    clock = spoken_clock(when)
    day = rf"(?:{_WAKE_DAY}|{_WAKE_REPEAT})"
    return (
        clock is not None
        and clock.resolved
        and re.fullmatch(
            # Uso real 2026-09-23 «despiértame a las seis de la mañana del jueves para tener tiempo
            # para la reunión»: what the alarm is for, said after it, does not change it.
            rf"(?:{day}\s+)?{re.escape(clock.literal)}(?:\s+{day})?"
            r"(?:\s+(?:para|porque|asi|que|to|so|because)\b.*)?",
            when,
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

    # «recuérdame tomar la pastilla todos los días a las nueve»: a reminder repeated daily or hourly is a
    # repeating notification; one repeated otherwise («cada viernes») no operation holds, and is asked.
    repetition = said_repetition(folded)
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
        and repetition != "unsupported"
    ):
        _append(
            matches,
            folded,
            "notification.schedule" if repetition else "reminder.create",
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
        and repetition != "unsupported"
    ):
        _append(
            matches,
            folded,
            "notification.schedule",
            r"\b(?:programa|programar|programame|schedule|pon|poner|ponme|pone|"
            r"poneme|pongame|set|arranca|inicia|start|alarma|alarm|"
            r"temporizador|timer)\b",
        )

    # Uso real 2026-09-23 «establece un recordatorio sobre la reunión de mañana a las nueve de la
    # mañana», «add conference call at four p. m. to my reminders for today».
    reminder_head = (
        r"(?:pon|ponme|pone|poneme|pongame|crea|crear|programa|programar|establece|establecer|fija|fijar|"
        r"agrega|agregar|anade|anadir|add|set|schedule|recordatorio|reminder)"
    )
    if (
        temporal
        and _has(folded, r"\b(?:recordatorios?|reminders?)\b")
        and not any(entry[2] in {"reminder.create", "notification.schedule"} for entry in matches)
        and _head_is(head, reminder_head)
        and repetition != "unsupported"
    ):
        _append(matches, folded, "notification.schedule" if repetition else "reminder.create", rf"\b{reminder_head}\b")

    cancel_notification = (
        (
            _head_is(
                head,
                r"(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
                r"elimina|eliminar|delete|borra|borrar)",
            )
            or _has(folded, r"^get\s+rid\s+of\b")
        )
        # Tanda 7 «actually make it 9» after «set a timer for the pasta, 11 minutes»: a timer is a scheduled
        # alarm too, and «cancel the last timer» cancels it like «cancel the last alarm».
        and _has(folded, r"\b(?:alarma|alarm|recordatorio|reminder|temporizador|timer|aviso)\b")
        and not _has(
            folded,
            r"\b(?:alarmas|alarms|recordatorios|reminders|temporizadores|timers|avisos)\b",
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


def names_the_title(user_text: str) -> bool:
    """The person named what the alarm or reminder is called («llamada…», «titled…», quotes)."""

    return re.search(
        r"\b(?:llamad[oa]|titulad[oa]|nombre|named|called|titled|name)\b|[\"“”«»]",
        user_text,
        re.IGNORECASE,
    ) is not None


# What the person keeps with BAXY or elsewhere and only a read can tell (uso real 2026-09-23, tanda 2; tanda 8
# added the timers and the orders: «You haven't set anything right now.», «Sí, está lista para recoger.»).
# Written accent-folded: the replies are folded before these are read.
_PERSONAL_RECORD_STORE = (
    r"(?:listas?|lists?|notas?|notes?|recordatorios?|reminders?|tareas?|tasks?|pendientes|to-?dos?|agenda|"
    r"calendario|calendar|alarmas?|alarms?|temporizador(?:es)?|timers?|citas?|appointments?|reunion(?:es)?|"
    r"meetings?|correos?|e-?mails?|inbox|bandeja\s+de\s+entrada|pedidos?|orden(?:es)?|orders?|paquetes?|"
    r"packages?|envios?|deliver(?:y|ies)|shipments?)"
)


# The person's own records named in their messages: «apúntame en la lista de la compra …», «mi agenda».
_FIRST_PERSON_MARK = re.compile(r"\b(?:mi|mis|my|me|yo|i|i'm|i've|tengo|llevo|\w+(?:ame|eme|ime|nme))\b")


def names_an_own_record_store(said: object) -> bool:
    """A message that names one of the person's own stores («apúntame en la lista de la compra», «mi agenda»)."""

    folded = _accent_folded_with_punctuation(said).casefold()
    return re.search(rf"\b{_PERSONAL_RECORD_STORE}\b", folded) is not None and _FIRST_PERSON_MARK.search(
        folded
    ) is not None
