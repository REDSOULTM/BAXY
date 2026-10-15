"""Los límites de partida (dueño 2026-10-10) que la misión dice sin actuar a medias, leídos de las palabras de la persona.

- Un sub-objetivo que es un límite declarado (el clic derecho, el formato de la cinta: negrita, tablas y similares) se
  lee sobre su ACTO (``act_limit``: el verbo que encabeza una cláusula de acto, nunca lo dictado, citado o buscado) y
  se marca ``steps[].limit``: la App hace los anteriores, la parte segura, y para al llegar sin mirar ni actuar.
- Un lugar que es el de un dispositivo («ir a Wi-Fi») lleva ``steps[].requires``: la App lo lee y para si el equipo no
  lo tiene.
- Una búsqueda dentro de un lugar cuyos datos dicen que no se puede buscar ahí (app_places «search»: false; L3, g1:
  el buscador de la biblioteca de Steam) se marca ``place_search``; antes va el sub-objetivo de ir a ese lugar.
- Una lista que no acaba se descubre al actuar (``long_list_reached``).
- «guarda esto» sin aplicación ni ventana nombrada se pregunta (``asks_which_window``), y la respuesta que nombra la
  ventana sigue el pedido (``which_window_answer``).
Arrastrar y dibujar es el límite del contrato de «sin operación» (``semantic.drag``). Las lecturas, las causas y las
frases son datos (``data/operation_floor.v1.json`` «computerUse.limits», causas «computer_use_limit_<límite>»).
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Iterable

from .. import effect_intent
from . import app_places
from .drag import act_clauses
from .missions import (
    fold,
    going_to,
    mission_destination,
    names_the_window_in_front,
    said_application,
    saved_on_screen_check,
)

_FLOOR = Path(__file__).resolve().parent.parent / "data" / "operation_floor.v1.json"
# The decision code of a step that stops on a limit («limit:long_list»); the App stops with «computer_use_limit_<id>».
LIMIT_CODE = "limit:"
LIMIT_STOP = "computer_use_limit_"
DEVICE_STOP = LIMIT_STOP + "device"
# Estabilización L3: a search inside a place whose data say it cannot be searched (app_places «search»: false).
PLACE_SEARCH = "place_search"
PLACE_SEARCH_STOP = LIMIT_STOP + PLACE_SEARCH


@functools.lru_cache(maxsize=1)
def limits_data() -> dict:
    return json.loads(_FLOOR.read_text(encoding="utf-8"))["computerUse"]["limits"]


@functools.lru_cache(maxsize=1)
def _kinds() -> tuple[tuple[str, re.Pattern[str], re.Pattern[str] | None], ...]:
    return tuple(
        (kind, re.compile(rules["act"]), re.compile(rules["except"]) if "except" in rules else None)
        for kind, rules in limits_data()["kinds"].items()
    )


@functools.lru_cache(maxsize=1)
def _shortcuts() -> dict[str, re.Pattern[str]]:
    """Review of L2, C6 (decided): the key a limit's act may be done with when the person says it («con Ctrl+B»)."""

    return {
        kind: re.compile(rules["shortcut"]) for kind, rules in limits_data()["kinds"].items() if "shortcut" in rules
    }


def act_limit(goal: object) -> str | None:
    """The declared limit a goal or a clause asks for as an act («context_menu», «format»), or None. Only a clause that
    starts with the limit's own act counts: «poné el título en negrita», «haceme clic derecho en notas.txt», «insert a
    table», never «escribí Informe en negrita», «buscá clic derecho no funciona», «centrá el mapa», a format said in
    a named dialog («desde el cuadro de diálogo de Fuente»: its controls are on screen) or with its shortcut («con
    Ctrl+B»: the engine presses the key)."""

    said = fold(goal)
    clauses = act_clauses(goal)
    shortcuts = _shortcuts()
    for kind, act, excepted in _kinds():
        if (excepted is not None and excepted.search(said)) or (kind in shortcuts and shortcuts[kind].search(said)):
            continue
        if any(act.match(clause) for clause in clauses):
            return kind
    return None


def required_device(goal: object) -> str | None:
    """The device a sub-goal needs, when the place it goes to or switches is the device's own («ir a wi-fi», «go to
    Wi-Fi settings», «abrir la configuración de wifi», «activar el bluetooth»): the device named whole, never a section
    that only mentions it («Bluetooth y dispositivos» exists without a radio) nor a text written about it."""

    data = limits_data()
    found = re.match(data["deviceGoal"], fold(goal))
    if found is None:
        return None
    place = found.group("place").strip(" «»\"'“”")
    return next((device for device, entry in data["devices"].items() if place in entry["names"]), None)


def with_declared_limits(arguments: dict[str, object] | None) -> dict[str, object] | None:
    """The mission's arguments with the first sub-goal that is a declared limit marked (``limit``; nothing after it is
    kept, it is never reached) and each one whose place needs a device marked (``requires``). A mission of one goal so
    marked carries it as its one step (the App keeps a single goal's budget for it). Unchanged otherwise."""

    if not isinstance(arguments, dict) or not isinstance(arguments.get("goal"), str):
        return arguments
    steps = arguments.get("steps")
    if isinstance(steps, list) and steps:
        items = [dict(step) for step in steps if isinstance(step, dict)]
    else:
        items = [{
            "goal": arguments["goal"],
            "application": arguments.get("application"),
            "successCheck": arguments.get("successCheck"),
        }]
    # Review of L2, C6 (decided): the shortcut the person gives in the request holds for the sub-goal the reader made of
    # it («poné negrita con Ctrl+B» → «activar negrita»): the engine presses that key, no limit.
    whole = fold(arguments["goal"])
    excused = {kind for kind, shortcut in _shortcuts().items() if shortcut.search(whole)}
    marked: list[dict[str, object]] = []
    changed = False
    for item in items:
        limit = act_limit(item.get("goal"))
        limit = None if limit in excused else limit
        application = item.get("application") or arguments.get("application")
        place = app_places.search_limit(application, item.get("goal"), arguments["goal"]) if limit is None else None
        if place is not None:
            limit = PLACE_SEARCH
            marked.extend(_going_first(application, place, marked))
        device = required_device(item.get("goal")) if limit is None else None
        if limit is not None:
            item["limit"] = limit
        if device is not None:
            item["requires"] = device
        changed = changed or limit is not None or device is not None
        marked.append(item)
        if limit is not None:
            break
    return {**arguments, "steps": marked} if changed else arguments


def _going_first(application: object, place: str, before: list[dict[str, object]]) -> list[dict[str, object]]:
    """Estabilización L3 («buscá Cuphead en mi biblioteca de Steam»): the sub-goal that goes to the place a search
    limit stands in, when no sub-goal before it does: the mission goes there, the safe part, and then says the limit."""

    name = app_places.first_name(application, place)
    went = going_to(name) if name else None
    if went is None or any(app_places.goes_to(application, item.get("goal"), place) for item in before):
        return []
    return [{"goal": went[0], "application": application, "successCheck": went[1]}]


def long_list_reached(history: Iterable[dict]) -> bool:
    """A list that does not end: the sub-goal's wheel scrolls that moved it («longListScrolls», verified, no item named
    by UI Automation) are spent and its goal still does not show. Only for a goal that looks for an item of a list
    (``computer_use._looks_in_a_list``), never a counted scroll nor a page (``counted_scroll``)."""

    moved = [
        step for step in history
        if isinstance(step, dict) and step.get("operation") == "input.scroll" and not step.get("label")
        and step.get("ok") is True and step.get("changed") is not False and step.get("surfaceChanged") is not False
    ]
    return len(moved) >= int(limits_data()["longListScrolls"])


def counted_scroll(text: object) -> bool:
    """Review of L2, C1: a scroll the person counted or bounded by a page («bajá 5 veces», «scroll down five times»,
    «bajá hasta el final de la página»): it is done as said, never cut as a list that does not end (data
    «countedScroll»)."""

    return re.search(limits_data()["countedScroll"], fold(text)) is not None


def asks_which_window(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    prior_requests: Iterable[str] = (),
) -> bool:
    """«guarda esto», «save this», «guardá esto como baxy-nota1.txt en Documentos»: a save of what the screen shows and
    nothing else (data «whichWindowOrder», or the save-as of ``saved_on_screen_check``: never «guarda esto en tu memoria:
    …», «… en el portapapeles», «… en mis contactos», «guarda esto: mañana…»), with no application said nor in the
    conversation and no window pointed at («en esta ventana»)."""

    said = effect_intent._strip_request_envelope(fold(text)).strip()
    if not said or re.search(r"[\"«»“”]", said):
        return False
    if re.match(limits_data()["whichWindowOrder"], said) is None and saved_on_screen_check(str(text or "")) is None:
        return False
    if names_the_window_in_front(said):
        return False
    return mission_destination(str(text or ""), application_names, tuple(prior_requests)) is None


def which_window_question(english: bool) -> str:
    return str(limits_data()["en" if english else "es"]["whichWindow"])


def asked_which_window(reply: object) -> bool:
    """BAXY's reply was the which-window question (either language)."""

    said = " ".join(str(reply or "").split())
    return said in {which_window_question(False), which_window_question(True)}


def asked_which_window_in_english(reply: object) -> bool:
    """Review of L2, C5: the question was asked in English, so the request framed by its answer is said in English."""

    return " ".join(str(reply or "").split()) == which_window_question(True)


def which_window_answer(
    text: str,
    asked: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    english: bool = False,
) -> str | None:
    """Review of L, H8d: the answer to «¿En cuál ventana?» that names the window («en el Bloc de notas», «en esta
    ventana») is the request asked about, framed there («en Bloc de notas, guardá esto como …»); None for any other
    message (a new request, a «no»), which goes its own way. Review of L2, C5: the window in front said bare («esta
    ventana», «en esta», «this one»; data «frontAnswers»), the application's name or alias alone («Notepad»), and the
    frame in the conversation's language (data «answerApp», «answerFront»)."""

    said = fold(text).strip(" .!?¡¿")
    if not said or len(said.split()) > 6:
        return None
    frames = limits_data()["en" if english else "es"]
    if said in limits_data()["frontAnswers"] or names_the_window_in_front(said):
        return frames["answerFront"].format(asked=asked)
    if said.split()[0] in _ANSWER_LEADS:
        # A place said («en el Bloc de notas», «in Word», «la del bloc de notas porfa»).
        application = mission_destination(str(text or ""), application_names)
    else:
        # Review of L2, C5: the application's name or alias alone («Notepad», «Bloc de notas»), read as the place it
        # names; «poné música en Spotify» is a new request, not a name.
        named = said_application(f"en {said}", application_names)
        application = named.name if named is not None and named.whole and fold(named.said) == said else None
    return None if application is None else frames["answerApp"].format(app=application, asked=asked)


_ANSWER_LEADS = frozenset({"en", "in", "on", "dentro", "el", "la", "the", "ahi", "alli", "there"})
