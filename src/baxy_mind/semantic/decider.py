"""The contextual decider: the model reads the whole conversation and the catalog and decides the turn.

Fase 3.5b «comprensión natural» (F2–F3, 2026-09-25): the model deciding alone, with the conversation as it is,
the catalog of every operation and the owner's rules, decided better than the readers, the shortlist, the native
selector and the gates put together (DEV-B 204/253 against 182/253; follow-ups that depend on the previous turn
61/66 against 40/66). It first restates the last message as a complete request (what the arguments step reads),
then decides: operations of the catalog, one short question, conversation, or a limit said plainly. It proposes;
the kernel still authorizes and the provider executes (invariant 1).

This module is the reading: the policy, the catalog as the decider sees it and the closed output. The model call
is ``llm.LlmRuntime.decide_in_context``.
"""

from __future__ import annotations

import functools
import json
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, Callable, Iterable, NamedTuple

from .grammar import _CARDINAL_WORDS, spoken_cardinal
from .normalize import fold, fold_in_place, spelled_out
from .quantities import _UNITS, measures
from .temporal import (
    _SPOKEN_DATE, _TOMORROW, _WEEKDAYS, MONTH_NUMBERS, SpokenDate, _day_value, bare_hour_with_its_part, spoken_clocks,
    taken_back_time,
)

DECISIONS = ("action", "clarify", "talk", "limit")

# The owner's rules (00_IDENTIDAD, REGLAS_ORO of the comprensión sets): what is public is looked up, what is the
# person's is never looked up, a complete request is not asked again, a relative amount without a number is asked,
# a limit is said plainly, a missing personal datum is asked.
POLICY = (
    "Eres el decisor de BAXY, un asistente tipo Jarvis que vive en un PC con Windows. Lees la conversación y "
    "decides qué hacer con el ÚLTIMO mensaje de la persona. No ejecutas nada: sólo decides.\n\n"
    "Decisiones posibles:\n"
    "- \"action\": ejecutar una o varias operaciones del catálogo (lista abajo) que cubren lo pedido.\n"
    "- \"clarify\": hacer UNA pregunta corta porque falta de verdad algo que cambia el resultado.\n"
    "- \"talk\": contestar hablando, sin tocar el PC: conocimiento estable, charla, escribir contenido (código, "
    "recetas, listas, cuentos, traducciones), cálculos y conversiones, consejos, hablar de ti mismo, agradecer.\n"
    "- \"limit\": decir en llano que eso no lo haces (no está en el catálogo).\n\n"
    "Reglas:\n"
    "1. Lo público se busca: lo que cambia o no se sabe de memoria con seguridad (clima, noticias, deportes, "
    "precios, dólar, horarios, estrenos, datos de una persona, empresa o lugar concretos, opiniones sobre una obra) "
    "→ action con web.search (o weather.current para el clima, web.news.headlines para titulares). Lo estable "
    "(definiciones, cómo se hace algo, matemáticas, traducir, convertir unidades) → talk. Si la persona pide "
    "buscar o investigar algo público, es action con web.search; si nombra el buscador o el navegador como lugar "
    "(«búscalo en Google», «en el navegador»), es action con browser.navigate a su página de resultados.\n"
    "2. Lo propio no se busca en la web: datos de la persona (sus notas, recordatorios, alarmas, tareas, agenda, "
    "archivos, lo que suena en su PC), preguntas sobre ti o sobre lo que acabas de decir → la operación que lo lee, "
    "o talk, o clarify.\n"
    "3. Lo completo no se repregunta: si el mensaje trae lo necesario, action. Un valor por defecto razonable (el "
    "clima de aquí, algo de música) no es una duda.\n"
    "4. Cantidad relativa sin número («súbele un poco», «baja el brillo», «más fuerte») → clarify (cuánto). Con "
    "número o nivel → action.\n"
    "5. Vives en un PC: no controlas luces ni aparatos de la casa, no haces llamadas telefónicas ni SMS, no pides "
    "comida, taxis, compras ni reservas, no manejas el móvil ni relojes → limit. Lo que una operación del catálogo "
    "sí hace (por ejemplo mensajes por una app del PC, reproducir en un servicio de streaming, abrir una app) se "
    "hace con esa operación.\n"
    "6. Si falta un dato de la persona («¿llueve donde vive mi hermana?») → clarify.\n"
    "7. Erratas, sin tildes, dictado sin puntuación y spanglish se entienden como la persona quiso decir.\n"
    "8. Un mensaje que depende de lo anterior («¿y en Santiago?», «ahora en javascript», «20 minutos antes de "
    "eso», «súbele otro poco», «esa no, otra», «sí, dale», «10») se decide con la conversación: la misma operación "
    "con el valor nuevo, o talk que reusa lo que respondiste. Si acabas de preguntar algo y la persona contesta, "
    "completa ese pedido. Tras una corrección («sí, pero…», «no, …») no repitas la misma operación con los mismos "
    "valores: aplica lo que cambia.\n"
    "9. Charla, gracias, quejas y reacciones → talk.\n\n"
    "Catálogo (operación: qué hace):\n"
)

FORMAT = (
    "\nResponde sólo con JSON: {\"request\": el último pedido reescrito como pedido completo y autónomo con lo que "
    "aporta la conversación, en el idioma de la persona, \"decision\": ..., \"operations\": [...] (vacía si no es "
    "action), \"question\": la pregunta corta si es clarify, si no \"\"}."
)

# Fase 3.5b M42 (D33): the decision and the values the person already gave travel in one output. Each catalog line
# names the operation's fields (identifiers left out: the kernel resolves them), so the arguments step no longer asks
# for a time, a name or a folder the message or the conversation gave (spent FINAL: 12 actions asked again).
FORMAT_WITH_ARGUMENTS = (
    "\nResponde sólo con JSON: {\"request\": el último pedido reescrito como pedido completo y autónomo con lo que "
    "aporta la conversación, en el idioma de la persona, \"decision\": ..., \"operations\": [...] (vacía si no es "
    "action), \"arguments\": {operación: {campo: valor}} con los valores que el mensaje o la conversación YA dan "
    "para los campos entre paréntesis (horas, duraciones, nombres, carpetas, títulos, textos; nunca inventes uno; "
    "{} si no hay), \"question\": la pregunta corta si es clarify, si no \"\"}."
)

FAMILY_TITLES = {
    "app": "aplicaciones", "audio": "sonido", "backup": "copias", "bluetooth": "bluetooth", "browser": "navegador",
    "calculator": "calculadora", "calendar": "agenda", "capture": "capturas", "clipboard": "portapapeles",
    "display": "pantalla", "email": "correo", "filesystem": "archivos", "game": "juegos", "input": "teclado y clics",
    "media": "música y video", "memory": "memoria privada", "message": "mensajes", "network": "red", "note": "notas",
    "notification": "alarmas y recordatorios", "ocr": "leer texto en pantalla", "office": "documentos",
    "package": "programas", "peripheral": "periféricos", "reminder": "recordatorios", "routine": "rutinas",
    "streaming": "streaming", "system": "sistema", "task": "tareas y listas", "vision": "describir la pantalla",
    "weather": "clima", "web": "web", "wifi": "wifi", "window": "ventanas",
}

# Model turns kept from the conversation, and characters per turn: the prompt stays inside one server slot.
HISTORY_TURNS = 4
HISTORY_CHARACTERS = 1500
# M49: each value the decider writes is bounded; one that reaches the bound was cut by the grammar (M67).
ARGUMENT_VALUE_CHARACTERS = 120
# M128 (D58; windows v4i-devF/v4i-devD: 4 of 612 BAXY messages): when every draft of a reply was refused, the App puts
# a neutral marker with the diagnostic code in BAXY's place (``MainWindowViewModel.CompositionFailureFallback``,
# «⚠ (no_response;retry_exhausted)»). It is the App's diagnostic, not something BAXY said, and the decider was trained
# and measured on conversations without it: F-w22-t3 «the signed one» after «summarize the lease PDF in there?» → ⚠
# was read as a file to open (file.open) where the isolated decider read the PDF.
_COMPOSITION_FAILURE_MARKER = re.compile(r"⚠ \([^()\n]+\)")


@functools.cache
def _composition_failure_lines() -> frozenset[str]:
    """Live 2026-10-07: the App now leaves the operation floor's data line in the marker's place
    (``compositionFailures``); it is the App's line, not BAXY's reply either. r22: so is the line for a turn
    sent while the mind's model was not up (``mindStartup``)."""

    from ..operation_floor import floor_data

    data = floor_data()
    return frozenset(
        text
        for key in ("compositionFailures", "mindStartup")
        for line in data.get(key, {}).values()
        for text in line.values()
    )


def _is_composition_failure(content: str) -> bool:
    return _COMPOSITION_FAILURE_MARKER.fullmatch(content) is not None or content in _composition_failure_lines()


@dataclass(frozen=True, slots=True)
class ContextDecision:
    request: str
    decision: str
    operations: tuple[str, ...]
    question: str
    arguments: tuple[tuple[str, Any], ...] = ()


_PLAIN_CATALOG = pathlib.Path(__file__).resolve().parents[1] / "data" / "decider_catalog.es.v1.json"


@functools.cache
def plain_descriptions() -> dict[str, str]:
    """One line per operation in the words a person uses (F4 M2).

    The technical description confused siblings («sesión SMTC» for pause and next, absolute and relative
    volume, opening an app and playing inside it). Written in a clean room from the technical catalog only;
    an operation it lacks keeps its own first sentence.
    """

    try:
        data = json.loads(_PLAIN_CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    operations = data.get("operations") if isinstance(data, dict) else None
    return {str(k): str(v) for k, v in operations.items()} if isinstance(operations, dict) else {}


_OPERATION_SURFACE = pathlib.Path(__file__).resolve().parents[1] / "data" / "operation_surface.v1.json"


@functools.cache
def _surfaces() -> tuple[dict[str, str], frozenset[str], frozenset[str]]:
    try:
        data = json.loads(_OPERATION_SURFACE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, frozenset(), frozenset()
    operations = data.get("operations") if isinstance(data, dict) else None
    elsewhere = data.get("elsewhere") if isinstance(data, dict) else None
    made = data.get("made_in_applications") if isinstance(data, dict) else None
    return (
        {str(k): str(v) for k, v in operations.items()} if isinstance(operations, dict) else {},
        frozenset(str(item) for item in elsewhere) if isinstance(elsewhere, list) else frozenset(),
        frozenset(str(item) for item in made) if isinstance(made, list) else frozenset(),
    )


@functools.cache
def _kept_on_their_route() -> frozenset[str]:
    try:
        data = json.loads(_OPERATION_SURFACE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    kept = data.get("kept_on_their_route") if isinstance(data, dict) else None
    return frozenset(str(item) for item in kept) if isinstance(kept, list) else frozenset()


def keeps_its_route(operation: str) -> bool:
    """Corrección ronda 5 (seguridad): an operation the coverage gate never hands to the engine, said inside an
    application or not (``kept_on_their_route`` in ``data/operation_surface.v1.json``: system.power,
    shell.command.run, uninstalling, emptying the trash…): its own route confirms or refuses before it acts."""

    return operation in _kept_on_their_route()


@functools.cache
def _asked_by_name() -> dict[str, tuple[str, ...]]:
    try:
        data = json.loads(_OPERATION_SURFACE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    named = data.get("asked_by_name") if isinstance(data, dict) else None
    if not isinstance(named, dict):
        return {}
    return {str(k): tuple(fold(str(item)) for item in v) for k, v in named.items() if isinstance(v, list)}


def unasked_operations(operations: Iterable[str], text: str) -> tuple[str, ...]:
    """v3-27 r9: the operations asked only by naming their object (``asked_by_name`` in the surface data) whose object
    ``text`` never names: «abre el mapa de caracteres y copia el símbolo del euro» does not ask the on-screen keyboard."""

    folded = f" {' '.join(re.findall(r'[a-z0-9]+', fold(text)))} "
    named = _asked_by_name()
    return tuple(
        operation for operation in operations
        if operation in named
        and not any(f" {' '.join(re.findall(r'[a-z0-9]+', words))} " in folded for words in named[operation])
    )


@functools.cache
def _said_by_verb() -> dict[str, tuple[tuple[str, ...], ...]]:
    try:
        data = json.loads(_OPERATION_SURFACE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    said = data.get("said_by_verb") if isinstance(data, dict) else None
    if not isinstance(said, dict):
        return {}
    return {
        str(operation): tuple(
            tuple(re.findall(r"[a-z0-9*]+", fold(str(entry)))) for entry in entries if str(entry).strip()
        )
        for operation, entries in said.items()
        if isinstance(entries, list)
    }


def _says(words: tuple[str, ...], entry: tuple[str, ...]) -> bool:
    """Whether ``entry`` (folded words; a trailing * is a word start) is said in ``words``, its words together."""

    def same(word: str, said: str) -> bool:
        return word.startswith(said[:-1]) if said.endswith("*") else word == said

    size = len(entry)
    return size > 0 and any(
        all(same(words[start + offset], entry[offset]) for offset in range(size))
        for start in range(len(words) - size + 1)
    )


def primitives_unsaid(operations: Iterable[str], text: str) -> bool:
    """Ronda 20 P3 (pasada r18, v3-11 t1 «en onenote crea una pagina nueva» → one input.visible.click on «Página»):
    whether ``operations`` are only primitives of the screen whose verbs the person never said (``said_by_verb`` in
    the surface data: «clic», «pulsá», «escribí», «tecla»…). Then the typed route is the decider's paraphrase of the
    order, not the order. False for no operation, for one the data does not list (taken as said) and when any of
    them is said: «en onenote haz clic en Agregar página», «escribí hola»."""

    chosen = tuple(operations)
    said_by = _said_by_verb()
    if not chosen or any(operation not in said_by for operation in chosen):
        return False
    words = _words(text)
    return not any(_says(words, entry) for operation in chosen for entry in said_by[operation])


def primitives_said_unchosen(operations: Iterable[str], text: str) -> tuple[str, ...]:
    """Ronda 21 (pasada r18, t-drag-1 «arrastrá lista.txt adentro de la carpeta archivo, en baxy-prueba-v3» → the
    sandbox's filesystem.move on the decider's unfaithful restatement): the screen's own primitives whose verbs the
    person's words say (``said_by_verb``) and that no chosen operation is. Empty when every one said was chosen."""

    chosen = set(operations)
    words = _words(text)
    return tuple(
        operation for operation, entries in _said_by_verb().items()
        if operation not in chosen and any(_says(words, entry) for entry in entries)
    )


_RESTATED_QUOTE = re.compile(r"«([^«»]+)»|“([^“”]+)”|\"([^\"]+)\"")


def without_unsaid_quotes(request: str, said: str) -> str:
    """Ronda 21 (pasada r18, v3-65 «cambiala a la vista estandar» → «haz clic en «Vista estándar»», a control the
    window does not have): a quotation in the decider's restatement whose words the person never said together is the
    decider's own naming, never a literal label; it stays as plain words. A quotation of the person's own words
    («hacé clic en Sistema» → «Sistema») keeps its quotes."""

    said_words = _words(said)

    def keep(found: re.Match[str]) -> str:
        quoted = next(group for group in found.groups() if group is not None)
        return found.group(0) if _says(said_words, _words(quoted)) else quoted

    return _RESTATED_QUOTE.sub(keep, request)


class _ServedWhereSaid(NamedTuple):
    remembered: frozenset[str]
    served: frozenset[str]
    settings: frozenset[str]
    whole_pc: tuple[str, ...]
    holders: tuple[tuple[str, ...], ...]


def _words(text: str | None) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", fold(text or "")))


@functools.cache
def _served_where_said() -> _ServedWhereSaid:
    try:
        data = json.loads(_OPERATION_SURFACE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}

    def listed(key: str) -> tuple[str, ...]:
        value = data.get(key)
        return tuple(str(item) for item in value) if isinstance(value, list) else ()

    return _ServedWhereSaid(
        frozenset(listed("remembered_from_any_application")),
        frozenset(listed("served_from_any_application")),
        frozenset(fold(item) for item in listed("system_settings_applications")),
        tuple(" ".join(_words(item)) for item in listed("whole_pc_objects") if _words(item)),
        tuple(_words(item) for item in listed("applications_holding_their_own") if _words(item)),
    )


def system_settings_application(name: str | None) -> bool:
    """Whether an installed application's catalog name is the PC's own settings window
    (``system_settings_applications``): what is said in it about the system is the system's, not its own control."""

    return name is not None and fold(name).strip() in _served_where_said().settings


def _holds_its_own(name: str | None) -> bool:
    """Whether an installed application keeps the person's own notes, reminders, alarms or calendar
    (``applications_holding_their_own``: a listed name's words, in order, inside the catalog name's)."""

    said = _words(name)
    return any(
        said[start:start + len(listed)] == listed
        for listed in _served_where_said().holders
        for start in range(len(said) - len(listed) + 1)
    )


# A clause that goes on after its place with «de/del/of …» was said in a longer place: «en configuración de Spotify …»
# is Spotify's settings, not the PC's (revisión ruta-tipada 7); «en configuración del PC …» is still the PC's.
_GENITIVE = frozenset({"de", "del", "of"})
_ARTICLES = frozenset({"el", "la", "the", "mi", "my", "este", "esta", "this"})


def _of_another_place(words: tuple[str, ...], whole_pc: tuple[str, ...]) -> bool:
    if not words or words[0] not in _GENITIVE:
        return False
    rest = words[1:]
    if rest and rest[0] in _ARTICLES:
        rest = rest[1:]
    return not (rest and rest[0] in {object_words.split()[-1] for object_words in whole_pc})


def kept_where_said(
    operations: Iterable[str],
    place: str | None,
    clause_read: Iterable[str] | Callable[[], Iterable[str]],
    clause: str | None,
) -> frozenset[str]:
    """Ruta tipada en app (auditoría 2026-10-08): of the typed operations chosen for an order of one clause said inside
    an application (``place``), those the application is only where the person believes it is done, so they keep their
    route (``served_where_said_purpose`` in ``data/operation_surface.v1.json``):
    - BAXY's own memory, and BAXY's own reminders and alarms the typed readers read in the clause without its place
      (``clause_read``, ``clause``), said in an application that keeps none of its own («en Word ponme un recordatorio a
      las 5»; «en Outlook creá un recordatorio» and «en Discord recordale a Juan…» stay the engine's);
    - a system operation the typed readers read in that clause when the place is the PC's own settings window («en
      Configuración bajá el brillo al 30», never «en configuración de Spotify…») or the clause names the whole PC as
      its object («en Spotify silenciá el PC»; a bare «todo» is no PC: «en Teams silenciá todo»).
    Any other is the application's own control, the engine's there («en OBS silenciá el audio del escritorio»).
    ``clause_read`` may be a callable: the clause is then read only when an operation needs it (revisión 6)."""

    served = _served_where_said()
    surfaces = _surfaces()[0]
    operations = tuple(operations)
    holder = _holds_its_own(place)
    words = _words(clause)
    padded = f" {' '.join(words)} "
    at_settings = system_settings_application(place) and not _of_another_place(words, served.whole_pc)
    names_whole_pc = any(f" {object_words} " in padded for object_words in served.whole_pc)
    needs_reading = tuple(
        operation for operation in operations
        if (operation in served.served and not holder)
        or (surfaces.get(operation) == "system" and (at_settings or names_whole_pc))
    )
    read: frozenset[str] = frozenset()
    if needs_reading and clause:
        read = frozenset(clause_read() if callable(clause_read) else clause_read)
    return frozenset(
        operation for operation in operations
        if (operation in served.remembered and not holder) or (operation in needs_reading and operation in read)
    )


def made_in_an_application(operations: Iterable[str]) -> bool:
    """Ronda 21 (v3-35): whether a chosen operation makes in BAXY's own store what applications also make
    (``made_in_applications``: a note, a document, a presentation, a text file)."""

    return bool(set(operations) & _surfaces()[2])


def operation_surface(operation: str) -> str | None:
    """Where an operation acts (``data/operation_surface.v1.json``): «app», «piece», «own_store», «files», «system» or
    «web»; None for one the data does not list."""

    return _surfaces()[0].get(operation)


@functools.cache
def _value_pieces() -> frozenset[str]:
    try:
        data = json.loads(_OPERATION_SURFACE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    listed = data.get("value_pieces") if isinstance(data, dict) else None
    return frozenset(str(item) for item in listed) if isinstance(listed, list) else frozenset()


_SAID_NUMBER = re.compile(r"(?<![a-z0-9])\d+(?:[.,]\d+)?(?![a-z0-9])")
# Revisión r19: a number said as the value an attribute takes — «la escala en 125», «regresala a 100», «set the scale
# to 125» — after the attribute said with its article (or a verb's object pronoun) and a preposition of value. Never
# the name or the count of what is touched: «apretá el 7», «tocá el botón 7», «la opción 2», «ventas 2024», «3 veces».
_ATTRIBUTE_VALUE = re.compile(
    r"(?<![a-z0-9])(?:(?:el|la|los|las|the|its|su|sus)\s+[a-z]+(?:\s+[a-z]+)?|[a-z]+[aeiour](?:lo|la|los|las)|it|them)"
    r"\s+(?:en|a|al|hasta|to|at)\s+(?P<value>\d+(?:[.,]\d+)?)(?![a-z0-9])(?!\s*(?:veces|vez|times)(?![a-z]))"
)


def _carried_numbers(arguments: Iterable[tuple[str, Any]]) -> frozenset[str]:
    return frozenset(
        number for _, value in arguments for number in _SAID_NUMBER.findall(spelled_out(fold(str(value))))
    )


def leaves_the_said_value(
    operations: Iterable[str], text: str, arguments: Iterable[tuple[str, Any]] = (),
) -> bool:
    """Uso real v3 ronda 19 (t2-c04 T2 «ahi ponle la escala en 125» → one click on «pantalla»): the request says a
    number as the value of an attribute (``_ATTRIBUTE_VALUE``) and every operation chosen is a piece of the screen
    (``operation_surface``) that carries no value said (``value_pieces`` in the surface data: the text typed), nor
    holds that number among its own ``arguments`` (a click on «7», a key «5»). A typed operation of its own («subí el
    volumen a 30» → audio.volume) is no piece and carries it; a number that names or counts what is touched («apretá
    el 7», «bajá 3 veces», «el archivo ventas 2024») is the piece's own target."""

    chosen = tuple(operations)
    if not chosen:
        return False
    values = {found.group("value") for found in _ATTRIBUTE_VALUE.finditer(spelled_out(fold(text)))}
    if not values or values <= _carried_numbers(arguments):
        return False
    pieces = _value_pieces()
    return all(operation_surface(operation) == "piece" and operation not in pieces for operation in chosen)


def order_served_elsewhere(
    operations: Iterable[str],
    clauses: int,
    *,
    doing_in_place: bool = False,
    kept_in_place: Iterable[str] = (),
    read_apart: Iterable[str] = (),
    kept: Iterable[str] = (),
    unasked: Iterable[str] = (),
    read_in_place: Iterable[str] = (),
) -> str | None:
    """v3 ronda 3 (lectura L1, falsos éxitos M5, lugar M4): why the typed operations chosen for an order said inside an
    installed application do not serve it, or None when they do.

    «elsewhere»: every operation that acts somewhere that is not the application (BAXY's own notes or a presentation
    it writes itself, the whole PC's sound, the web) serves what was said inside it: v3-01 «abre powerpoint… ponle de
    titulo…» → document.presentation.create, v3-08 «abrí onenote, creá una página…» → note.create. Only what an
    application itself makes (``made_in_applications``) serves a later clause of an order that opens one and goes on;
    any other (the time, the weather, a reminder, the wifi) is a request of its own there («abrime Steam y fijate qué
    hora es»), unless the order is one clause said inside the application (``doing_in_place``: «en OBS Studio silenciá
    el micrófono») and that application is not only where the person believes it is done (``kept_in_place``,
    ``kept_where_said``: «en Configuración bajá el brillo al 30», «en Word ponme un recordatorio»). One the typed readers read apart in the order (``read_apart``: «abre Discord y recordame…» →
    app.open + reminder.create) is never taken from it unless the order is that one clause said inside the
    application (then nothing was read apart: v3-24 «en el visor de eventos filtra…» read alone as web.search), and an
    order that mixes one of those with the application's
    work is left whole to the decider. One the order never asks for (``unasked``: no typed reader reads it there and
    the order never names its object, ``unasked_operations``) is no request of its own either: v3-27 r9 «abre el mapa
    de caracteres y copia el símbolo del euro» → input.keyboard.open opened the on-screen keyboard and nothing else.
    «partial»: they are only pieces of what a person does on the screen (open, click, type, open a file) and fewer
    than the clauses ordered: v3-38 «en la terminal andá a configuración y cambiá el tema…» → one click. An operation
    the data does not list is taken as serving it.
    Corrección ronda 5 (seguridad): an operation that keeps its own route (``keeps_its_route``, or one the caller
    passes in ``kept``: its catalog risk is confirmed) always serves it: «en la terminal ejecutá shutdown /s /t 0» →
    shell.command.run, «en la terminal apagá la computadora» → system.power confirm or refuse; the engine would not.
    """

    chosen = tuple(operations)
    if not chosen:
        return None
    held = frozenset(kept)
    if any(keeps_its_route(operation) or operation in held for operation in chosen):
        return None
    surfaces, elsewhere, made = _surfaces()
    apart = frozenset(read_apart)
    never_asked = frozenset(unasked) - apart
    kinds = [surfaces.get(operation) for operation in chosen]
    away = [operation for operation, kind in zip(chosen, kinds) if kind in elsewhere]
    if away:
        # v3 ronda 5 (lectura M1, v3-24 «en el visor de eventos filtra…» → web.search, v3-53 «en obs silencia el audio
        # del escritorio» → audio.mute): an order of one clause said inside the application has no other clause to be
        # read apart from; the typed readers reading that same clause alone is no request of its own.
        # Erratas r9 (v3-26 «abrí el visr de eventos y en Sistema buscame un evento con ID 6005» → web.search): when
        # the typed readers read the whole order as one mission in the application, an operation only a clause headed
        # by a place inside it reads (``read_in_place``: semantic.missions.read_only_in_a_place) is that mission's;
        # one a clause said apart reads («y buscame en la web …», «y apaga el wifi») or none reads («y después bajame
        # el volumen») is still a request of its own (revisión 3).
        in_place = frozenset(read_in_place) if apart == {"mission.computer.use"} else frozenset()
        held_in_place = frozenset(kept_in_place) if doing_in_place else frozenset()
        inside = all(
            operation not in held_in_place
            and (
                doing_in_place or operation in in_place or operation in never_asked
                or (operation not in apart and operation in made)
            )
            for operation in away
        )
        return "elsewhere" if inside else None
    if all(kind == "piece" for kind in kinds) and clauses > len(chosen):
        return "partial"
    return None


def asks_for_the_application_itself(operations: Iterable[str], clauses: int) -> bool:
    """v3 ronda 5 (lectura M2): a question about a value an operation needs, asked for an order said inside an
    application, is the application's own when every operation it is about acts on that application as a whole
    service («app» in the surface data: «en Spotify subí el volumen» → ¿cuánto?, owner rule) and covers each clause
    ordered. A question for an operation that acts elsewhere or is only a piece of the order is no question the
    order needs: the engine does it in the application."""

    chosen = tuple(operations)
    if not chosen:
        return False
    surfaces, _, _ = _surfaces()
    return all(surfaces.get(operation) == "app" for operation in chosen) and clauses <= len(chosen)


def catalog_line(name: str, description: str) -> str:
    """What the decider reads of one operation: its line in the person's words, or its description's first sentence."""

    return plain_descriptions().get(name) or description.split(". ")[0].rstrip(".")


def catalog_prompt(
    tools: Iterable[tuple[str, str]],
    signatures: dict[str, tuple[str, ...]] | None = None,
) -> str:
    """The system prompt for ``(name, description)`` operations, the same bytes for the same catalog.

    With ``signatures`` (M42) each line names the operation's argument fields and the output asks for their values.
    """

    families: dict[str, list[str]] = {}
    for name, description in sorted(tools):
        first = catalog_line(name, description)
        fields = (signatures or {}).get(name) or ()
        signature = f"({', '.join(fields)})" if fields else ""
        families.setdefault(name.split(".", 1)[0], []).append(f"- {name}{signature}: {first[:140]}")
    catalog = "\n".join(f"[{FAMILY_TITLES.get(f, f)}]\n" + "\n".join(lines) for f, lines in families.items())
    return POLICY + catalog + (FORMAT if signatures is None else FORMAT_WITH_ARGUMENTS)


def argument_signature(schema: dict[str, Any]) -> tuple[str, ...]:
    """The fields the decider may fill for one operation: optional ones marked «?», identifiers left out."""

    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return ()
    required = set(schema.get("required") or ())
    return tuple(
        name + ("" if name in required else "?")
        for name in properties
        if isinstance(name, str) and not (name.endswith("Id") and name != "appId")
    )


def response_schema(operations: Iterable[str], *, with_arguments: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "request": {"type": "string", "maxLength": 300},
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "operations": {"type": "array", "items": {"type": "string", "enum": sorted(operations)}, "maxItems": 3},
        "question": {"type": "string", "maxLength": 200},
    }
    closed = {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    if not with_arguments:
        return closed
    # M49 (lat49): the values are decoded only when the decision is an action, each one bounded; a talk, a question
    # or a limit writes no arguments at all (M42 as first shipped cost +0.8 s p50 on every turn in the app).
    other = {
        **closed,
        "properties": {
            **properties,
            "decision": {"type": "string", "enum": [d for d in DECISIONS if d != "action"]},
            "operations": {"type": "array", "items": {"type": "string"}, "maxItems": 0},
        },
    }
    action_properties = {
        "request": properties["request"],
        "decision": {"type": "string", "enum": ["action"]},
        "operations": properties["operations"],
        "arguments": {
            "type": "object",
            "additionalProperties": {"type": ["string", "number", "boolean"], "maxLength": ARGUMENT_VALUE_CHARACTERS},
        },
        "question": properties["question"],
    }
    action = {**closed, "properties": action_properties, "required": list(action_properties)}
    return {"anyOf": [action, other]}


def messages(system: str, text: str, history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """The conversation as it was, without the current message when the history already ends with it.

    M125 (D58; window v4i-devF F-s002: the app's decider read 42 prompt tokens where the isolated one read 23, the 19
    of «Hola, soy BAXY. ¿En qué puedo ayudarte hoy?»): what BAXY says before the person has said anything (the
    welcome of every new conversation, a start-up notice) is not a turn of the conversation, and the decider was
    trained and measured without it. It came first in the history of every first and second turn.

    M128 (D58): nor is the App's composition-failure marker (``_COMPOSITION_FAILURE_MARKER``) BAXY's reply; the
    person's request before it stays, so what they ask next still has its referent.
    """

    prior = [
        turn for turn in (history or [])
        if turn.get("role") in {"user", "assistant"} and turn.get("content")
        and not (turn.get("role") == "assistant" and _is_composition_failure(str(turn["content"])))
    ]
    prior = prior[next((index for index, turn in enumerate(prior) if turn.get("role") == "user"), len(prior)):]
    if prior and prior[-1].get("role") == "user" and prior[-1].get("content") == text:
        prior = prior[:-1]
    prior = prior[-HISTORY_TURNS:]
    return [
        {"role": "system", "content": system},
        *({"role": turn["role"], "content": str(turn["content"])[:HISTORY_CHARACTERS]} for turn in prior),
        {"role": "user", "content": text},
    ]


def parse(content: str, operations: Iterable[str]) -> ContextDecision:
    """The decision the model wrote; an action whose operations are not served is not an action."""

    raw = json.loads(content)
    served = set(operations)
    decision = raw.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"decisión desconocida: {decision!r}")
    chosen = tuple(dict.fromkeys(op for op in raw.get("operations") or [] if op in served))
    if decision == "action" and not chosen:
        raise ValueError("una acción sin operaciones del catálogo")
    return ContextDecision(
        request=" ".join(str(raw.get("request") or "").split()),
        decision=decision,
        operations=chosen if decision == "action" else (),
        question=" ".join(str(raw.get("question") or "").split()),
        arguments=_decided_arguments(raw.get("arguments"), chosen) if decision == "action" else (),
    )


def _decided_arguments(value: Any, operations: tuple[str, ...]) -> tuple[tuple[str, Any], ...]:
    """The scalar values the decider read, flat: the model writes them keyed by operation or not."""

    if not isinstance(value, dict):
        return ()
    flat: dict[str, Any] = {}
    for key, item in value.items():
        if key in operations and isinstance(item, dict):
            for field, inner in item.items():
                flat.setdefault(str(field), inner)
        elif isinstance(item, (str, int, float, bool)):
            flat.setdefault(str(key), item)
    return tuple((name, item) for name, item in flat.items() if isinstance(item, (str, int, float, bool)))


# --- Fidelity of the restatement (Fase 3.5b M64) ---------------------------------------------------------------------
# v3d-final and v3f-final F-w01-t4 «¿y cuánto sale más o menos ese pisco en el líder? el mistral de 35» was restated
# «¿Cuánto sale el pisco Mistral de 350 ml en el líder?», and «350 ml» travelled as the objective to the search and to
# the reply; F-s054 «Estará storming mañana» became «…mañana en Santiago?» and the weather of a city nobody named was
# read; F-w05-t3 «apúntamelo como recordatorio un mes antes» got «el 1 de octubre», a date nobody gave. The restatement
# joins the message with the conversation; a number, a unit, a date, a clock time or a proper name that neither the
# person nor BAXY said is the model's, not the person's.
#
# What counts as said: every turn of the conversation the decider read (the person's and BAXY's) and the message. A
# number is said in digits or in words («treinta y cinco» is 35, «la mitad» of a level is 50, the current year); a
# clock time or a date is said, or is one a said duration or day word puts from now or from a said clock («en 20
# minutos», «20 minutos antes de eso», «mañana»); a unit is said, or the same unit in other words («l» for «litros»);
# a name is said in any case, with or without its hyphen («NeYo» → «Ne-Yo»), as an abbreviation of a said word
# («control» → «Ctrl»), or completing a said name through «de/del» («ñuñoa» → «Ñuñoa»). What the catalog line of
# the chosen operation names is its world, not an introduction: «sonido del PC» for audio.mute, «on Netflix» for
# streaming.play.named (Netflix or Disney+, whose title reader needs the service written after the title).
_DAY_WORDS_OF_A_NAME = frozenset(
    {*MONTH_NUMBERS, *(name for names in _WEEKDAYS for name in names), "i", "i'm", "i'd", "i'll", "i've"}
)
_NAME_CONNECTOR = frozenset({"de", "del", "la", "las", "los", "of", "the"})
_LEVEL_WORDS = (
    (re.compile(r"\b(?:mitad|half)\b"), 50),
    (re.compile(r"\b(?:maxim[oa]|al\s+tope|full|max)\b"), 100),
    (re.compile(r"\bminim[oa]\b"), 0),
    (re.compile(r"\b(?:un\s+cuarto|a\s+quarter)\b"), 25),
    (re.compile(r"\b(?:tres\s+cuartos|three\s+quarters)\b"), 75),
)
_DEGREES = frozenset({"grado", "grados", "degree", "degrees"})
_NUMERAL = re.compile(
    r"(?<![\w.,])(?P<number>\d+(?:[.,]\d+)*)(?:st|nd|rd|th)?(?P<sign>\s*[°º%])?(?:\s+(?P<unit>[a-z]+)\b)?"
)
_NAME_WORD = re.compile(r"[\w'’-]+")
# M105: the nationalities that qualify a currency or a team, lower case in Spanish; ``stem`` is shared with the
# country's name («colombianos» / «Colombia», «chileno» / «Chile», «mexican» / «México»). Folded.
_DEMONYM = re.compile(
    r"\b(?P<stem>colombian|mexican|argentin|chilen|chilean|uruguay|peruan|peruvian|venezolan|ecuatorian|ecuadorian|"
    r"bolivian|paraguay|cuban|dominican|filipin|philippin|brasilen|brazilian|canadiense|canadian|australian|"
    r"estadounidense|japones|japanese)(?:o|a|os|as|es|s|e)?\b"
)
# A file named with its extension («lista.txt», «informe final.docx» is «final.docx»), folded; web addresses
# («youtube.com») are no files.
_FILE_NAME = re.compile(
    r"(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.(?:txt|md|csv|json|xml|log|ini|pdf|docx?|xlsx?|pptx?|odt|ods|odp|rtf|png|jpe?g|"
    r"gif|bmp|webp|svg|tiff?|ico|mp3|wav|flac|ogg|m4a|mp4|mkv|avi|mov|webm|zip|rar|7z|exe|msi|bat|ps1|py|js|html?|css)"
    r"(?!\w)(?!\.\w)"
)
# What a removed complement leaves hanging in front of it: its preposition and its article.
_LEAD_IN = re.compile(
    r"(?:\s*,)?\s+(?:en|de|del|para|por|a|al|con|in|at|on|from|for|near|of|with)(?:\s+(?:el|la|las|los|the))?\s*$",
    re.IGNORECASE,
)
_ARTICLES_AS_ONE = frozenset({"un", "una", "uno", "one", "a", "an"})


@dataclass(frozen=True, slots=True)
class Fidelity:
    """What travels as the objective: the restatement, the restatement without what it brought, or the message."""

    request: str
    introduced: tuple[str, ...] = ()
    kind: str = "kept"  # kept | trimmed | person


def _values(token: str) -> set[Fraction]:
    """«5.000» is 5000 and 5; «3,5» is 3.5."""

    found: set[Fraction] = set()
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        found.add(Fraction(int(re.sub(r"\D", "", token))))
    if token.count(".") + token.count(",") <= 1:
        try:
            found.add(Fraction(token.replace(",", ".")))
        except (ValueError, ZeroDivisionError):
            pass
    return found


def _spoken_values(words: list[str], *, articles: bool = True) -> set[Fraction]:
    """The numbers runs of number words say («treinta y cinco» → 35), and each number word alone; without
    ``articles`` a lone «un», «una» or «a» is an article, not a one."""

    found: set[Fraction] = set()
    run: list[str] = []
    for word in [*words, ""]:
        if word in _CARDINAL_WORDS or (run and word in {"y", "and"}):
            run.append(word)
            continue
        while run and run[-1] in {"y", "and"}:
            run.pop()
        if run and (articles or len(run) > 1 or run[0] not in _ARTICLES_AS_ONE):
            whole = spoken_cardinal(" ".join(run))
            if whole is not None:
                found.add(Fraction(whole))
            for single in run:
                value = None if single in {"y", "and"} else spoken_cardinal(single)
                if value is not None and (articles or single not in _ARTICLES_AS_ONE):
                    found.add(Fraction(value))
        run = []
    return found


def _numbers_said(folded: str, *, articles: bool = True) -> set[Fraction]:
    found = {value for token in re.findall(r"\d+(?:[.,]\d+)*", folded) for value in _values(token)}
    return found | _spoken_values(re.findall(r"[a-z0-9]+", folded), articles=articles)


def _said_days(folded: str, now: datetime) -> set[tuple[int, int]]:
    """(day, month) of the dates the words put from today: «hoy», «mañana», «ayer», a weekday, «en 3 días»."""

    offsets = set()
    if re.search(r"\b(?:hoy|today|tonight)\b", folded):
        offsets.add(0)
    if re.search(_TOMORROW, folded):
        offsets.add(1)
    if re.search(r"\bpasado\s+manana\b|\bday\s+after\s+tomorrow\b", folded):
        offsets.add(2)
    if re.search(r"\b(?:ayer|yesterday)\b", folded):
        offsets.add(-1)
    for index, names in enumerate(_WEEKDAYS):
        if re.search(rf"\b(?:{'|'.join(names)})\b", folded):
            offsets.add((index - now.weekday()) % 7)
    for measure in measures(folded):
        if measure.dimension == (0, 1, 0, 0) and measure.value % 86400 == 0:
            offsets.update({int(measure.value // 86400), -int(measure.value // 86400)})
    days = {((now + timedelta(days=offset)).day, (now + timedelta(days=offset)).month) for offset in offsets}
    # M144 (DEV-H v4p H-w13-t2 «pa el quince, tipo ocho am…» restated «…el 15 de octubre a las 8:00…» → the person's
    # words were the objective and «¿Cuándo es el quince?» was asked): a day of the month said alone is that day of the
    # next month it comes in (``SpokenDate.on_or_after``, the reminders' own reading).
    for found in _SPOKEN_DATE.finditer(re.sub(r"(?<=[a-z])-(?=[a-z])", " ", folded)):
        if found.group("day_alone"):
            on = SpokenDate("", _day_value(found.group("day_alone")), None, None, False).on_or_after(now.date())
            if on is not None:
                days.add((on.day, on.month))
    return days


# M127 (DEV-C v4i C-w10-t5 «listo recuérdemelo el día antes a las 6 de la tarde» after «La cita que aparece es el 3 de
# octubre…», restated «Recuérdame el 2 de octubre a las 18:00 la cita del 3 de octubre.» → the person's words were the
# objective and the reminder was titled «listo recuerdemelo el dia antes»): days the message counts before or after
# another day («el día antes», «dos días después», «la víspera», «the day before»).
_SAID_DAY_OFFSET = re.compile(
    r"\b(?:(?P<count>un|una|one|a|dos|two|tres|three|\d{1,2})\s+)?(?:(?:el|the)\s+)?(?:dias?|days?)\s+"
    r"(?P<sign>antes|despues|before|after|earlier|later)\b"
    r"|\b(?:el\s+)?dia\s+(?P<sign2>anterior|siguiente)\b|\b(?:la\s+)?(?P<eve>vispera)\b"
)
_DAY_OFFSET_COUNTS = {"un": 1, "una": 1, "one": 1, "a": 1, "dos": 2, "two": 2, "tres": 3, "three": 3}


def _day_offsets(folded_message: str) -> set[int]:
    """The signed day counts ``folded_message`` says one day is from another (``_SAID_DAY_OFFSET``)."""

    offsets: set[int] = set()
    for found in _SAID_DAY_OFFSET.finditer(folded_message):
        count = found.group("count")
        days = 1 if count is None else _DAY_OFFSET_COUNTS.get(count, int(count) if count.isdecimal() else 1)
        word = found.group("sign") or found.group("sign2") or "antes"
        offsets.add(-days if word in {"antes", "before", "earlier", "anterior"} else days)
    return offsets


def _days_counted_from(dates: set[tuple[int, int]], offsets: set[int], now: datetime) -> set[tuple[int, int]]:
    """(day, month) of each date said moved by each day count said."""

    found: set[tuple[int, int]] = set()
    for day, month in dates:
        try:
            base = datetime(now.year, month, day)
        except ValueError:
            continue
        for offset in offsets:
            moved = base + timedelta(days=offset)
            found.add((moved.day, moved.month))
    return found


def _one_letter_dropped(said: str, word: str) -> bool:
    """``said`` is ``word`` written with one of its letters left out («exel» / «excel»), never its first one."""

    return (
        len(said) >= 4
        and len(word) == len(said) + 1
        and said[0] == word[0]
        and any(word[:index] + word[index + 1:] == said for index in range(1, len(word)))
    )


def _dates(folded: str) -> list[tuple[int, int, int, int]]:
    """(start, end, day, month) of each date said with its month («el 1 de octubre», «november 10th»)."""

    found = []
    for match in _SPOKEN_DATE.finditer(re.sub(r"(?<=[a-z])-(?=[a-z])", " ", folded)):
        month = match.group("month") or match.group("month_first")
        digits = re.match(r"\d+", match.group("day") or match.group("day_after") or "")
        if month is None or digits is None:
            continue
        found.append((match.start(), match.end(), int(digits.group()), MONTH_NUMBERS[month]))
    return found


def _subsequence(short: str, long: str) -> bool:
    letters = iter(long)
    return all(letter in letters for letter in short)


# M156 (DEV-I v4u I-s038 «abreme el afinity foto ese pa editar una imajen» restated «Abre Affinity Photo.» → «Photo»
# judged a name nobody said, the person's words kept and «¿Cuál es el nombre exacto de la aplicación…?»): the ear and
# the keyboard write a name as it sounds in Spanish — «foto» for «Photo», «afinity» for «Affinity», «imajen» for
# «imagen», «Tokio» for «Tokyo» (M110's «y» for «i», which this replaces). Spellings of one sound are one key; the
# doubled letter is one.
_SOUND_SPELLINGS = (
    (r"ph", "f"), (r"th", "t"), (r"c(?=[ei])", "s"), (r"ck|qu|c", "k"), (r"z", "s"), (r"g(?=[ei])", "j"),
    (r"ll", "y"), (r"y", "i"), (r"v", "b"), (r"(?<![cs])h", ""), (r"(\w)\1+", r"\1"),
)


def _sound_key(word: str) -> str:
    """The folded ``word`` as it sounds (see above): «Photo» and «foto», «Affinity» and «afinity» share one key."""

    key = word
    for spelling, sound in _SOUND_SPELLINGS:
        key = re.sub(spelling, sound, key)
    return key


def _introduced_spans(
    request: str, said: list[str], world: list[str], now: datetime,
) -> list[tuple[int, int, str]]:
    """(start, end, what) of each number, unit, date, clock time or proper name of ``request`` nobody said; the
    ``world`` lines count for names only (their «una hora» is no duration the person gave)."""

    folded_request = fold_in_place(request)
    said_text = spelled_out(fold("\n".join(said)))
    said_words = re.findall(r"[a-z0-9]+", said_text)
    said_set = set(said_words)
    # M127 (DEV-C v4i C-p07-t2 «…parking near U Street?» → «Is there handicap parking Street?»): a name is matched
    # against the words as written too; the chat spelling (``spelled_out``) reads that «U» as «you».
    named_words = said_words + re.findall(r"[a-z0-9]+", fold("\n".join(said))) + re.findall(
        r"[a-z0-9]+", fold("\n".join(world)),
    )
    named_set = set(named_words)
    stems = {word[:4] for word in named_words}
    named_by_sound = {_sound_key(word) for word in named_set if len(word) >= 4}
    glued = {first + second for first, second in zip(named_words, named_words[1:])}
    numbers = _numbers_said(said_text) | {Fraction(now.year)}
    numbers |= {Fraction(value) for pattern, value in _LEVEL_WORDS if pattern.search(said_text)}
    said_units = {_UNITS[word] for word in said_words if word in _UNITS}
    durations = {m.value for line in said for m in measures(fold(line)) if m.dimension == (0, 1, 0, 0)}
    said_clocks = {(c.hour % 12) * 60 + c.minute for line in said for c in spoken_clocks(fold(line))}
    said_dates = {(day, month) for line in said for _, _, day, month in _dates(fold(line))}
    said_dates |= _said_days(said_text, now)
    # M127 (C-w10-t5): «el día antes» of a day said is said, as a clock less a duration said is (``derived`` below).
    said_dates |= _days_counted_from(said_dates, _day_offsets(fold(said[0]) if said else ""), now)

    spans: list[tuple[int, int, str]] = []
    covered: list[tuple[int, int]] = []

    def inside(start: int) -> bool:
        return any(first <= start < last for first, last in covered)

    for start, end, day, month in _dates(folded_request):
        covered.append((start, end))
        if (day, month) not in said_dates:
            spans.append((start, end, request[start:end]))
    for found in _SPOKEN_DATE.finditer(re.sub(r"(?<=[a-z])-(?=[a-z])", " ", folded_request)):
        # M144: «el día 13» of the restatement is the next 13th, judged as the dates with their month above (in digits:
        # «the second song» counts no day).
        if not found.group("day_alone") or not found.group("day_alone")[:1].isdigit() or inside(found.start("day_alone")):
            continue
        on = SpokenDate("", _day_value(found.group("day_alone")), None, None, False).on_or_after(now.date())
        covered.append((found.start("day_alone"), found.end("day_alone")))
        if on is None or (on.day, on.month) not in said_dates:
            spans.append((found.start("day_alone"), found.end("day_alone"),
                          request[found.start("day_alone"):found.end("day_alone")]))
    # «media hora antes de eso» is only earlier, «dentro de una hora» only later (v3f-devD D-w02-t3 «…antes de eso» after
    # «las 10» was restated «a las 10:30»); a message that says neither may go either way.
    message = fold(said[0]) if said else ""
    signs = tuple(
        sign for sign, word in ((-1, r"antes|before|earlier"), (1, r"despues|after|later|dentro"))
        if re.search(rf"\b(?:{word})\b", message)
    ) or (1, -1)
    bases = said_clocks | {(now.hour % 12) * 60 + now.minute}
    derived = {(base + sign * int(duration // 60)) % 720 for base in bases for duration in durations for sign in signs}
    # M137b (DEV-G v4n G-w22-t5 «actually make it 8» after «…Tuesday evening…» restated «…Tuesday at 8 PM…»): the bare
    # hour the message moves a notification to, in the part of the day the conversation said (or D61b/D61 gives it).
    another_day = bool(_said_days(fold(request), now) - {(now.day, now.month)}) or bool(_dates(folded_request))
    for clock in spoken_clocks(folded_request):
        start = folded_request.find(clock.literal)
        if start < 0 or inside(start):
            continue
        end = start + len(clock.literal)
        covered.append((start, end))
        dial = (clock.hour % 12) * 60 + clock.minute
        if dial not in said_clocks and dial not in derived and not bare_hour_with_its_part(
            clock, said[0] if said else "", reversed(said[1:]), another_day=another_day, now=now,
        ):
            spans.append((start, end, request[start:end]))
    for match in _NUMERAL.finditer(folded_request):
        if inside(match.start()):
            continue
        unit = match.group("unit")
        sign = (match.group("sign") or "").strip()
        if sign in {"°", "º"} or unit in _DEGREES:
            unit_said = bool(_DEGREES & said_set) or "°" in said_text or "º" in said_text
        elif unit in _UNITS:
            unit_said = unit in said_set or _UNITS[unit] in said_units
        else:
            unit_said = True
        if unit in _UNITS or unit in _DEGREES:
            end = match.end()
        else:
            end = match.end("sign") if sign else match.end("number")
        if not (_values(match.group("number")) & numbers) or not unit_said:
            spans.append((match.start(), end, request[match.start():end]))

    said_files = {found.group(0) for found in _FILE_NAME.finditer(fold("\n".join(said)))}
    for match in _FILE_NAME.finditer(folded_request):
        # Lectura-ruta (r9 t-drag-1 «arrastrá lista.txt adentro de la carpeta archivo» restated «Mueve archivo.txt…»):
        # a file named by its extension is said only as a whole; its words said apart («archivo», «.txt») are not it.
        if not inside(match.start()) and match.group(0) not in said_files:
            covered.append((match.start(), match.end()))
            spans.append((match.start(), match.end(), request[match.start():match.end()]))
    for match in _DEMONYM.finditer(folded_request):
        # M105 (DEV-D v4a D-w03-t4 «ya. dolar hoy?» in a Chilean conversation → «¿Cuánto vale hoy el dólar en pesos
        # colombianos?»): a nationality is a name written in lower case; the country it belongs to nobody said.
        # A capitalised one («Argentina», «Colombian») is a name, judged with the names below.
        if inside(match.start()) or match.group("stem")[:4] in stems or request[match.start()].isupper():
            continue
        spans.append((match.start(), match.end(), request[match.start():match.end()]))
    words = list(_NAME_WORD.finditer(request))
    for index, word in enumerate(words):
        text = word.group(0)
        if not text[:1].isupper() or inside(word.start()):
            # M137b: «PM» of «at 8 PM» is part of a clock (or a date) judged above as one, never a name.
            continue
        lead = request[:word.start()].rstrip().rstrip("¿¡\"«“'(").rstrip()
        key = fold(text)
        if not lead or lead[-1] in ".!?:;" or key in _DAY_WORDS_OF_A_NAME:
            continue
        bare = re.sub(r"[-'’]", "", key)
        if bare[:4] in stems or bare in glued or bare in named_set:
            continue
        if len(bare) >= 4 and _sound_key(bare) in named_by_sound:
            # M110 (DEV-F v4d F-w03-t4 «qué hora es en Tokyo» restated «…en Tokio?», trimmed to «¿Qué hora es
            # ahora?» and the clock of here was read): a name spelled with «i» for «y» is the name said. M156: any
            # spelling of the same sound is (``_sound_key``).
            continue
        if len(bare) >= 2 and any(
            len(said_word) >= len(bare) + 2 and said_word[0] == bare[0] and _subsequence(bare, said_word)
            for said_word in named_set
        ):
            continue
        if len(bare) >= 4 and any(_one_transposition(bare, said_word) for said_word in said_set):
            # M111 (DEV-F v4d F-s003 «abreme el wrod» restated «Abre Word.» → asked which application): two letters
            # swapped are the same word mistyped or misheard (owner rule 2026-09-19: BAXY fixes what was said wrong).
            continue
        if not re.search(r"(?i)\b(?:a|al|para|con|to|for|with)$", lead) and any(
            _one_letter_dropped(said_word, bare) for said_word in said_set
        ):
            # M127 (DEV-C v4i C-w16-t1 «regaleme el exel abierto» restated «Abre Excel.» → «¿Cuál es el nombre exacto de
            # la aplicación…?»): a word said with one letter left out is the name it misses it from (same owner rule).
            # Never a person addressed («escríbele a Marta» for «a mara» is someone else).
            continue
        # «Ñuñoa» for «ñuñoa»: the name continues a said name through «de/del».
        back = index - 1
        while back >= 0 and fold(words[back].group(0)) in _NAME_CONNECTOR:
            back -= 1
        if back < index - 1 and back >= 0 and words[back].group(0)[:1].isupper():
            if re.sub(r"[-'’]", "", fold(words[back].group(0)))[:4] in stems:
                continue
        spans.append((word.start(), word.end(), text))
    return sorted(spans)


def _one_transposition(word: str, said: str) -> bool:
    """``word`` is ``said`` with two neighbouring letters swapped («word» / «wrod»)."""

    if len(word) != len(said) or word == said:
        return False
    differ = [index for index, (first, second) in enumerate(zip(word, said)) if first != second]
    return (
        len(differ) == 2
        and differ[1] == differ[0] + 1
        and word[differ[0]] == said[differ[1]]
        and word[differ[1]] == said[differ[0]]
    )


def _trimmed(request: str, spans: list[tuple[int, int, str]]) -> str | None:
    """The request without each introduced complement and the preposition that led to it; None when one of them is
    not a complement («Abre Spotify») or too little would be left."""

    # A name of several words is one complement: «en Nueva York».
    merged: list[list[int]] = []
    for start, end, _ in spans:
        if merged and re.fullmatch(r"[\s,]*", request[merged[-1][1]:start]):
            merged[-1][1] = end
        else:
            merged.append([start, end])
    result = request
    for start, end in reversed(merged):
        if request[start:end].islower() and _DEMONYM.fullmatch(fold(request[start:end])) is not None:
            # M105 (DEV-D v4a D-w03-t4): a nationality nobody said qualifies the noun before it («en pesos
            # colombianos» → «en pesos»); the noun stays.
            result = result[:start] + result[end:]
            continue
        lead = _LEAD_IN.search(result[:start])
        if lead is None:
            # M93 (DEV-D v3u D-w08-t2 «y cuando juega el sigiente» after «el América» → «¿Cuándo juega el Club América
            # su próximo partido?»): a capitalised word the decider put in front of a name that was said («Club
            # América») is a title of that name; the name said stays and the word goes. Anything else is no complement.
            follows = re.match(r"\s+([^\W\d_][\w'’-]*)", result[end:])
            if (
                follows is None
                or not follows.group(1)[:1].isupper()
                or not re.fullmatch(r"(?:[^\W\d_][\w'’-]*\s*)+", request[start:end])
            ):
                return None
            result = result[:start] + result[end:].lstrip()
            continue
        result = result[:lead.start()] + result[end:]
    result = re.sub(r"\s+([?.!,;:])", r"\1", " ".join(result.split()))
    result = re.sub(r",([?.!])", r"\1", result).strip(" ,")
    content = [word for word in re.findall(r"[a-z0-9]+", fold(result)) if len(word) > 2]
    return result if len(content) >= 2 else None


# M178 (DEV-F v5d F-w46-t4 «a las 5 y 40» after «bueno, poneme una alarma para ese día bien temprano», the day being
# the Saturday of the forecasts, restated «Pon una alarma el sábado 26 de octubre a las 5:40.» → the person's «a las 5
# y 40» was the objective and «¿Cuándo y qué quieres que recuerde la alarma?» was asked): a date nobody said written
# right after a weekday that was said is the model's reckoning of that weekday; the weekday stays, the date goes.
_WEEKDAY_BEFORE_A_DATE = re.compile(
    rf"\b(?P<weekday>{'|'.join(name for names in _WEEKDAYS for name in names)})\s*,?\s*(?:(?:the|el)\s+)?$"
)


def _said_weekday_without_its_date(request: str, spans: list[tuple[int, int, str]], said: list[str]) -> str | None:
    """``request`` without each date of ``spans`` that follows a weekday said in ``said`` («el sábado 26 de octubre» →
    «el sábado»); None when no span is such a date."""

    folded_request = fold_in_place(request)
    said_words = set(re.findall(r"[a-z]+", fold("\n".join(said))))
    dates = {(start, end) for start, end, _, _ in _dates(folded_request)}
    result = request
    dropped = False
    for start, end, _ in sorted(spans, reverse=True):
        if (start, end) not in dates:
            continue
        before = _WEEKDAY_BEFORE_A_DATE.search(folded_request[:start])
        if before is None or before.group("weekday") not in said_words:
            continue
        # The comma or article between the weekday and the date goes with the date.
        result = result[:before.end("weekday")] + result[end:]
        dropped = True
    if not dropped:
        return None
    return re.sub(r"\s+([?.!,;:])", r"\1", " ".join(result.split()))


def faithful_request(
    request: str,
    text: str,
    conversation: Iterable[str],
    *,
    world: Iterable[str] = (),
    now: datetime | None = None,
) -> Fidelity:
    """The decider's restatement as the objective, only with what was said (M64).

    ``conversation`` is every turn the decider read; ``world`` the catalog lines of the operations it chose. What the
    restatement brought is taken out when it is a complement («…mañana en Santiago?» → «…mañana?») and every number
    the message states stays in the result; otherwise the objective is the person's message, which the steps after
    the decider read with the conversation as they always do.
    """

    request = " ".join(str(request or "").split())
    if not request:
        return Fidelity(request)
    now = now or datetime.now()
    taken_back = taken_back_time(str(text or ""))
    if taken_back is not None:
        # M76 (DEV-D v3l D-s097 «… en 2 , no espera en 3 minutos» restated «Pon un temporizador de 2 minutos…»): a
        # number the person said and took back is said, but not asked for. A restatement that keeps it and loses the
        # time that stands is not the request.
        restated = _numbers_said(fold(request))
        kept = _numbers_said(fold(taken_back.kept))
        dropped = _numbers_said(fold(taken_back.taken_back)) - kept
        if dropped & restated and not kept & restated:
            return Fidelity(" ".join(str(text or "").split()), (taken_back.taken_back,), "person")
    said = [str(text or ""), *(str(line or "") for line in conversation)]
    lines = [str(line or "") for line in world]
    spans = _introduced_spans(request, said, lines, now)
    if not spans:
        return Fidelity(request)
    introduced = tuple(dict.fromkeys(what for _, _, what in spans))
    weekday_kept = _said_weekday_without_its_date(request, spans, said)
    if (
        weekday_kept is not None
        and not _introduced_spans(weekday_kept, said, lines, now)
        and _numbers_said(fold(text), articles=False) <= _numbers_said(fold(weekday_kept))
    ):
        return Fidelity(weekday_kept, introduced, "trimmed")
    trimmed = _trimmed(request, spans)
    if (
        trimmed is not None
        and not _introduced_spans(trimmed, said, lines, now)
        and _numbers_said(fold(text), articles=False) <= _numbers_said(fold(trimmed))
    ):
        return Fidelity(trimmed, introduced, "trimmed")
    carried = _with_the_conversation_name(request, spans, str(text or ""), [str(line or "") for line in conversation])
    if (
        carried is not None
        and not _introduced_spans(carried, said, lines, now)
        and _numbers_said(fold(text), articles=False) <= _numbers_said(fold(carried))
    ):
        return Fidelity(carried, introduced, "carried")
    return Fidelity(" ".join(str(text or "").split()), introduced, "person")


# Words that carry no content of their own: a restatement may add or drop them freely.
_FUNCTION_WORDS = frozenset({
    "para", "pero", "porque", "como", "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso", "unos", "unas",
    "sobre", "desde", "hasta", "donde", "cuando", "tambien", "solo", "todo", "toda", "todos", "todas", "mismo",
    "with", "that", "this", "these", "those", "from", "have", "will", "your", "about", "into", "then", "than",
    "there", "their", "they", "what", "when", "which", "would", "could", "should",
})


# M147 (DEV-F v4m–v4q F-w05-t5 «pone algo de javiera mena en spotify» → the decider's «Javier Mené», every round, and
# another artist played): a name the person wrote, respelled by the model a letter or two off, is the person's. Each of the
# model's words must be a near miss of the said word in its place (the same word folded, or at most one edit in four
# letters, two in eight); the run is returned as the person wrote it.
_SAID_WORD = re.compile(r"[^\W_][\w'’.-]*")


def _near_miss(model: str, said: str) -> bool:
    if model == said:
        return True
    if min(len(model), len(said)) < 4:
        return False
    return _edit_distance(model, said) <= max(1, min(len(model), len(said)) // 4)


def as_the_person_spelled(value: str, said: Iterable[str]) -> str | None:
    """The run of the person's words that ``value`` respells (see above); None when ``value`` is said as it is, or no run
    of the same length matches every word."""

    wanted = [fold(word) for word in _SAID_WORD.findall(str(value or ""))]
    if not wanted or len(wanted) > 8:
        return None
    for line in said:
        text = str(line or "")
        if " ".join(wanted) in " ".join(fold(word) for word in _SAID_WORD.findall(text)):
            return None
    for line in said:
        text = str(line or "")
        found = list(_SAID_WORD.finditer(text))
        for start in range(len(found) - len(wanted) + 1):
            run = found[start:start + len(wanted)]
            if all(_near_miss(model, fold(match.group(0))) for model, match in zip(wanted, run)):
                return text[run[0].start():run[-1].end()]
    return None


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def said_in_other_words(value: str, said: Iterable[str], *, now: datetime | None = None) -> bool:
    """M118 (D58, DEV-F F-w28-t4 «ponme algo de lo-fi pa concentrarme» → query «lo-fi para concentrarse», F-w01-t4 the
    draft «…con 10 minutos de retraso porque tengo dentista antes», F-s022 details «…porque el viaje a Cancún…» after
    «el trip a Cancún»): a free text the decider wrote is what was said, in its own words, when it brings no number,
    unit, date, clock time or name nobody said (``_introduced_spans``, the restatement's own check) and at least three
    in four of its content words share their stem with a word said. A literal check dropped these values and the turn
    asked again for what the person had given; the decider is never overruled on words alone."""

    text = " ".join(str(value or "").split())
    lines = [str(line or "") for line in said]
    if not text or not any(line.strip() for line in lines):
        return False
    said_text = spelled_out(fold("\n".join(lines)))
    if any(
        # What is written as it was said (an address «192.168.1.64», «a las 11:30» quoted from BAXY) is said.
        " ".join(spelled_out(fold(what)).split()) not in " ".join(said_text.split())
        for _, _, what in _introduced_spans(text, lines, [], now or datetime.now())
    ):
        return False
    said_stems = {word[:5] for word in re.findall(r"[a-z0-9]+", said_text)}
    content = [
        word for word in re.findall(r"[a-z]+", spelled_out(fold(text)))
        if len(word) >= 4 and word not in _FUNCTION_WORDS
    ]
    if not content:
        return False
    return 4 * sum(word[:5] in said_stems for word in content) >= 3 * len(content)


def _conversation_names(line: str) -> list[str]:
    """The names a line writes: runs of capitalised words that do not open a sentence, joined by «de/del/of…»."""

    names: list[str] = []
    run: list[str] = []
    words = list(_NAME_WORD.finditer(line))
    for word in words:
        text = word.group(0)
        lead = line[:word.start()].rstrip().rstrip("¿¡\"«“'(").rstrip()
        opens = not lead or lead[-1] in ".!?:;"
        if text[:1].isupper() and not opens and fold(text) not in _DAY_WORDS_OF_A_NAME:
            run.append(text)
            continue
        if run and fold(text) in _NAME_CONNECTOR and text[:1].islower():
            run.append(text)
            continue
        if run:
            while run and fold(run[-1]) in _NAME_CONNECTOR:
                run.pop()
            names.append(" ".join(run))
            run = []
    while run and fold(run[-1]) in _NAME_CONNECTOR:
        run.pop()
    if run:
        names.append(" ".join(run))
    return [name for name in names if name]


def _with_the_conversation_name(
    request: str, spans: list[tuple[int, int, str]], text: str, conversation: list[str],
) -> str | None:
    """M105 (DEV-D v4a D-w08-t2 «y cuando juega el sigiente» after «cuanto qedo el america anoche» → «¿Cuándo juega el
    Atlético Nacional el próximo partido?»): the decider put another team where the conversation's own name goes, the
    fidelity check fell back to the bare message, and the search for «y cuando juega el sigiente» answered with Mexico's
    national team. In a short follow-up that names nothing itself, the one name the restatement brought stands where
    the conversation's last name goes: that name replaces it. None when the restatement brought more than one name,
    anything that is no name, or the last two lines of the conversation name nothing."""

    if len(re.findall(r"[\w'’-]+", text)) > 8 or _conversation_names(f". {text}"):
        return None
    merged: list[list[int]] = []
    for start, end, _ in spans:
        if merged and re.fullmatch(r"[\s,]*|\s+(?:de|del|la|las|los|of|the)\s+", request[merged[-1][1]:start]):
            merged[-1][1] = end
        else:
            merged.append([start, end])
    if len(merged) != 1 or not all(what[:1].isupper() for _, _, what in spans):
        return None
    start, end = merged[0]
    lines = [line for line in conversation if line.strip() and " ".join(line.split()) != " ".join(text.split())]
    for line in reversed(lines[-2:]):
        names = _conversation_names(line)
        if names:
            return " ".join((request[:start] + names[-1] + request[end:]).split())
    return None



# M179 (DEV-I v5a–v5d I-w17-t2 «¿y la libra, cómo anda?» after «¿podrías decirme cómo está el dólar hoy, por favor?» →
# restated «¿Cómo está el dólar hoy, por favor?», searched, «No encontré información sobre el tipo de cambio del dólar
# hoy.»): a follow-up that names a new thing with its article («¿y la libra…?», «and the Celtics?») asks the same as the
# request before about that thing. A restatement without it asked the old thing again. Folded, one character for one.
_NEW_THING_FOLLOWUP = re.compile(
    r"^[¿¡\s]*(?:(?:oye|che|bueno|ok|okay|okey|ah|oh|mira|hey|baxy|ya|pues|vale|dale)\b[\s,.:]*)*"
    r"(?:y|and|(?:and\s+)?(?:what|how)\s+about|y\s+que\s+tal(?:\s+(?:con|de))?)\s+"
    r"(?P<thing>(?:el|la|los|las|the)\s+[a-z][a-z'’-]{2,})(?=[\s,.;:?!]|$)"
)
# What follows an article without naming a thing: «y el del Banco Nación», «y el otro», «and the next one».
_NOT_A_THING = frozenset(
    "del que otro otra otros otras mismo misma resto demas siguiente proximo proxima ultimo ultima primero primera "
    "segundo segunda tercero tercera other others rest same next last first second third one ones".split()
)
_ARTICLE_AND_NOUN = re.compile(r"\b(?:el|la|los|las|the)\s+(?P<noun>[a-z][a-z-]{2,})(?P<possessive>['’]s?)?(?![\w'’-])")


def _stem_said(word: str, said: str) -> bool:
    """``word`` (folded) is a word of ``said`` (folded) by its first five letters."""

    return word[:5] in {other[:5] for other in re.findall(r"[a-z0-9]+", said)}


def followup_thing_kept(request: str, text: str, antecedent: str) -> str | None:
    """The restatement with the new thing a follow-up names (see above) where the old one stood; None when the
    restatement keeps the new thing, the message is not such a follow-up, or the old thing is not one article and noun
    of the restatement that the request before said and this message does not."""

    said = " ".join(str(text or "").split())
    folded_said = fold_in_place(said)
    found = _NEW_THING_FOLLOWUP.match(folded_said)
    if found is None:
        return None
    thing = said[found.start("thing"):found.end("thing")]
    noun = folded_said[found.start("thing"):found.end("thing")].split()[-1]
    if noun in _NOT_A_THING:
        return None
    restated = " ".join(str(request or "").split())
    folded_restated = fold_in_place(restated)
    before = fold_in_place(antecedent)
    if not restated or not before.strip() or _stem_said(noun, folded_restated):
        return None
    old = [
        place for place in _ARTICLE_AND_NOUN.finditer(folded_restated)
        if _stem_said(place.group("noun"), before) and not _stem_said(place.group("noun"), folded_said)
    ]
    if len(old) != 1:
        return None
    place = old[0]
    return restated[:place.start()] + thing + restated[place.end("noun"):]


# M179 (DEV-I v5a/v5c/v5d I-w26-t5 «oye y el tecnico de ellos quien es ahora» four turns after «a que hora juega chile
# el martes» → restated «¿Quién es el técnico de ellos ahora?», searched as said, and another team's coach answered):
# «ellos», «their», said of a third party the person and BAXY were talking about, is the one name of the topic this
# conversation last searched («¿A qué hora juega Chile el martes?»). Only when the person said the pronoun too, the
# restatement kept it and names nobody, and that topic names exactly one name.
_THIRD_PARTY = re.compile(r"\b(?P<phrase>de\s+(?:ellos|ellas)|their)\b")


def with_the_searched_name(request: str, text: str, topic: str | None) -> str | None:
    """The restatement with «de ellos / their» said by the name of the last topic searched (see above), or None."""

    restated = " ".join(str(request or "").split())
    folded_restated = fold_in_place(restated)
    pronouns = list(_THIRD_PARTY.finditer(folded_restated))
    if (
        len(pronouns) != 1
        or not topic
        or re.search(r"\b(?:ellos|ellas|their|they|them)\b", fold(text)) is None
        or _conversation_names(f". {restated}")
    ):
        return None
    names = _conversation_names(f". {topic}")
    if len(set(names)) != 1:
        return None
    name, found = names[0], pronouns[0]
    if found.group("phrase") == "their":
        said = f"{name}'" if name.endswith("s") else f"{name}'s"
    else:
        said = f"{restated[found.start():found.start() + 2]} {name}"
    return restated[:found.start()] + said + restated[found.end():]
