"""v3 erratas en el nombre de la app (regla del dueño: lo mal dicho lo arregla BAXY), pasada r9.

- v3-19 «abre el adminsitrador de tareas y ordena los procesos por memoria»: the decider planned app.open and its
  argument was grounded only by the exact resolver, over the whole order, so BAXY asked which application. The one
  resolver (semantic.missions.said_application) now grounds app.open: the frame's slot up to the next clause, with its
  typing slips, a slip of another name of it (data/app_aliases.v1.json) and the head frame «<app>: …».
- v3-26 «abrí el visr de eventos y en Sistema buscame un evento con ID 6005»: the name was read; a narrowed route chose
  web.search and the coverage gate kept it, because the search was taken for a request of its own. When the typed
  readers read the whole order as one mission, no clause was read apart.
- Sweep of the bank (scripts/cu_live/cases/*.turns) with synthetic slips: an ordinary word beside a function word
  («el panel de miniaturas», «abri el editor de la imagen») names no application.

Spanish, English and spanglish twins; each rule has its counter-case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from baxy_mind.semantic import arguments, catalog, missions
from baxy_mind import engine_handoff
from baxy_mind import plan_shape
from baxy_mind import argument_grounding

ROOT = Path(__file__).resolve().parents[1]
START = tuple(json.loads((ROOT / "tests" / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"])
INDEX = catalog.build_application_catalog_index(START)
OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
)
TOOLS = {operation: {} for operation in dict.fromkeys((*OPERATIONS, "mission.computer.use"))}


def _opened(text: str, names: tuple[str, ...] = START) -> str | None:
    found = arguments._explicit_arguments_from_evidence("app.open", text, names)
    return (found or {}).get("appId")  # type: ignore[return-value]


def _turn(kind: str, operations: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "turn.result", "id": "e1", "kind": kind, "operation": operations[0] if kind == "action" else None,
        "intentOperations": list(operations), "effectOperations": list(operations), "question": "", "reply": "",
    }


def _gate(text: str, turn: dict[str, Any]) -> dict[str, Any]:
    message = {"id": "e1", "text": text, "history": [{"role": "user", "content": text}]}
    return engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, START)


# ------------------------------------------------------------ app.open by the one resolver (v3-19)


@pytest.mark.parametrize(
    ("text", "application"),
    [
        # v3-19 as said (r9: «¿Cuál es el nombre o título de la aplicación que deseas abrir?»)
        ("abre el adminsitrador de tareas y ordena los procesos por memoria", "Administrador de tareas"),
        # the same order spelled right was not grounded either: «y ordena …» is no clause the opener cut
        ("abre el administrador de tareas y ordena los procesos por memoria", "Administrador de tareas"),
        ("abre el visr de eventos", "Visor de eventos"),
        # English: a slip of the application's other name
        ("open the task manger and sort by memory", "Administrador de tareas"),
        ("open the event vewer and in System find event ID 6005", "Visor de eventos"),
        # spanglish
        ("abrí el adminsitrador de tareas and sort by memory", "Administrador de tareas"),
        # a later clause's word is no name: «luego a memoria» is no «Diagnóstico de memoria de Windows»
        ("abre el admnistrador de tareas, ve a rendimiento, luego a memoria y dime la velocidad",
         "Administrador de tareas"),
    ],
)
def test_app_open_takes_the_application_a_misspelled_frame_names(text: str, application: str) -> None:
    assert _opened(text) == application


@pytest.mark.parametrize(
    "text",
    [
        # a condition is no order to open now (independent review M1)
        "si se cierra steam, abre discord",
        # a name the catalog does not know, and one only mentioned later, open nothing
        "abre el zorblax y copiá el título de onenote",
        # an ordinary word one letter from a one-word name stays that word
        "en stream escribí hola y abrí el chat",
    ],
)
def test_app_open_takes_no_application_that_was_not_named(text: str) -> None:
    assert _opened(text) is None


@pytest.mark.parametrize(
    "text",
    [
        # Revisión 1: one word of a name is no name said; a Windows function or an application not installed opens
        # nothing (before: «Reset the Visual Studio 2022 Experimental Instance», which erases it with no dialog)
        "open reset this pc",
        "open the experimental instance and log in",
        "abre el reset de visual studio",
        # a name's first word with more said after it: the uninstaller of what was said is not the generic one
        "abre el uninstall de deskflow",
        # elevation never asked for (Unidad de recuperación)
        "abre opciones de recuperacion",
        "abre la recuperacion de apps",
        "open recovery options",
        # another application taken for the one said (a false success)
        "abre windows update",
        "open windows update",
        "abre la asistencia rapida",
        "abre la ayuda rapida",
        "abre el panel de nvidia",
        "open nvidia control panel",
        "abre el registro de eventos",
        "open user account control",
        "open the downloads folder",
        # spanglish
        "abrí el windows update and check for updates",
        # Revisión 6: an ordinary word alone, by any reader (Editor del Registro asks for elevation)
        "abre el editor",
        "open the editor",
    ],
)
def test_app_open_takes_no_application_a_word_of_it_reaches(text: str) -> None:
    assert _opened(text) is None


@pytest.mark.parametrize(
    ("text", "application"),
    [
        # Twins of the counter-cases: the whole name said opens it
        ("abre el editor del registro", "Editor del Registro"),
        ("open registry editor", "Editor del Registro"),
        ("abre el editr del registro y anda a HKEY_CURRENT_USER", "Editor del Registro"),
        # Revisión 4: a place said before the open verb is no application opened
        ("copiá lo que dice en word y abrí el bloc de notas", "Bloc de notas"),
        ("en discord no hay nada, abre steam", "Steam"),
        ("copy what it says in word and open notepad", "Bloc de notas"),
        # Revisión 2: the one turned down at the head is not what is opened
        ("spotify, mejor abre discord", "Discord"),
        ("Terminal, mejor abre powershell", "Windows PowerShell"),
        ("spotify, better open discord", "Discord"),
    ],
)
def test_app_open_takes_what_the_open_verb_names(text: str, application: str) -> None:
    assert _opened(text) == application


def test_a_slip_as_near_two_names_opens_neither() -> None:
    # «team» is as near to Steam as to Teams: BAXY asks which (APPS1495), never opens one of them.
    assert _opened("abre el team y escribile a juan", ("Steam", "Microsoft Teams")) is None
    # Twins: each name said whole, or one slip that reaches only it, opens it.
    assert _opened("abre teams y escribile a juan", ("Steam", "Microsoft Teams")) == "Microsoft Teams"
    assert _opened("abre el steam y anda a la tienda", ("Steam", "Microsoft Teams")) == "Steam"


# ------------------------------------------------------------ the plan's app.open step (v3-19, pasada r15b)

_APP_OPEN_SCHEMA = {
    "type": "object", "properties": {"appId": {"type": "string"}}, "required": ["appId"], "additionalProperties": False,
}


@pytest.mark.parametrize(
    ("objective", "operations", "application"),
    [
        # r15b live: the decider planned app.open + system.process.list; no reader read that pair
        ("abre el adminsitrador de tareas y ordena los procesos por memoria", ("app.open", "system.process.list"),
         "Administrador de tareas"),
        # the decider's own rewrite of the same order
        ("Abre el Administrador de tareas y ordena los procesos por memoria.", ("app.open", "system.process.list"),
         "Administrador de tareas"),
        ("open the task manger and sort the processes by memory", ("app.open", "system.process.list"),
         "Administrador de tareas"),
        ("abrí el visr de eventos y en Sistema buscame un evento con ID 6005", ("app.open", "mission.computer.use"),
         "Visor de eventos"),
    ],
)
def test_a_planned_opening_with_no_clause_read_takes_the_application_the_order_names(
    objective: str, operations: tuple[str, ...], application: str,
) -> None:
    # What r15b ran: the readers do not read the pair, so the step's purpose is the placeholder and names nothing.
    found = plan_shape._plan_effects_read(objective, operations, (*OPERATIONS, "mission.computer.use"), [], INDEX)
    if found is None:
        purpose = plan_shape._explicit_plan_skeleton(operations)["steps"][0]["purpose"]
        assert argument_grounding._ground_explicit_arguments("app.open", purpose, _APP_OPEN_SCHEMA, START) is None
    got = plan_shape._the_plans_only_opening("app.open", operations, objective, _APP_OPEN_SCHEMA, START)
    assert got == {"appId": application}


@pytest.mark.parametrize(
    ("objective", "operations"),
    [
        # two openings: each step keeps its own clause, none is guessed from the whole order
        ("abre el bloc de notas y abre la calculadora", ("app.open", "app.open")),
        # a condition opens nothing now (independent review M1)
        ("si se cierra steam, abre discord y lista los procesos", ("app.open", "system.process.list")),
        # a name the catalog does not know
        ("abre el zorblax y ordena los procesos por memoria", ("app.open", "system.process.list")),
    ],
)
def test_counter_case_a_planned_opening_takes_nothing_the_order_does_not_name_alone(
    objective: str, operations: tuple[str, ...],
) -> None:
    assert plan_shape._the_plans_only_opening("app.open", operations, objective, _APP_OPEN_SCHEMA, START) is None
    assert plan_shape._the_plans_only_opening("system.process.list", operations, objective, {}, START) is None


# ------------------------------------------------------------ the one resolver


@pytest.mark.parametrize(
    ("text", "application"),
    [
        # v3-39 with and without a slip: the head frame «<app>: …» before «open settings» (the Terminal's own page)
        ("windows terminal: open settings and tell me which profile is the default", "Terminal"),
        ("windows termnal: open settings and tell me which profile is the default", "Terminal"),
        ("en el panel de control andá a programas", "Panel de control"),
        ("abre el editor del registro", "Editor del Registro"),
    ],
)
def test_the_application_said(text: str, application: str) -> None:
    assert missions.resolve_application(text, INDEX) == application


@pytest.mark.parametrize(
    "text",
    [
        # t-drag-2 in PowerPoint: «panel de» is no «Panel de control»
        "En el panel de miniaturas arrastra la diapositiva «Tres» para que quede la primera",
        # v3-16 with «fotos» misspelled after «en»: «el editor de la imagen» is no «Editor del Registro»
        "en ftos abri el editor de la imagen que tengo abierta y ponele un filtro blanco y negro",
        # a head that names no application stays text
        "notas: comprar pan",
    ],
)
def test_an_ordinary_word_names_no_application(text: str) -> None:
    assert missions.resolve_application(text, INDEX) is None


@pytest.mark.parametrize(
    ("text", "destination"),
    [
        # Revisión 2: an application turned down at the head, or named as what the order acts on, frames nothing
        ("Edge, no. Abre chrome y buscá recetas de pan", "Google Chrome"),
        ("Spotify, no: abrí Discord y andá al canal general", "Discord"),
        ("word, mejor abre excel y crea una tabla", "Excel"),
        ("Steam, ciérralo y abre Discord", "Discord"),
        ("Edge, nah, open chrome and search bread recipes", "Google Chrome"),
        ("Steam, close it and open Discord", "Discord"),
        ("word, mejor open excel and create a table", "Excel"),
        # Twins: a head that frames the order still does (v3-39)
        ("windows terminal: open settings and tell me which profile is the default", "Terminal"),
        ("windows terminal: abrí la configuración y decime cuál es el perfil por defecto", "Terminal"),
    ],
)
def test_the_mission_happens_where_the_person_wants_it(text: str, destination: str) -> None:
    assert missions.mission_destination(text, START, ()) == destination


# ------------------------------------------------------------ the coverage gate (v3-26)


@pytest.mark.parametrize(
    ("text", "objective"),
    [
        ("abrí el visr de eventos y en Sistema buscame un evento con ID 6005",
         "abrí el Visor de eventos y en Sistema buscame un evento con ID 6005"),
        ("abrí el visor de eventos y en Sistema buscame un evento con ID 6005",
         "abrí el visor de eventos y en Sistema buscame un evento con ID 6005"),
        ("open the event viewer and in System find event ID 6005",
         "open the event viewer and in System find event ID 6005"),
        ("abrí el visr de eventos and in System search event 6005",
         "abrí el Visor de eventos and in System search event 6005"),
    ],
)
def test_a_search_inside_the_application_named_is_the_engine_s(text: str, objective: str) -> None:
    result = _gate(text, _turn("action", ("web.search",)))
    assert result["effectOperations"] == ["mission.computer.use"], result
    assert result["objective"] == objective


@pytest.mark.parametrize(
    ("text", "turn"),
    [
        # the search engine is the place named: the search is the request
        ("abrí el visor de eventos y buscame en google qué es el evento 6005", _turn("action", ("web.search",))),
        # a request of its own the typed readers read apart beside the application
        ("abre discord y recordame en 10 minutos llamar a pedro", _turn("plan", ("app.open", "reminder.create"))),
        ("abrime steam porfa y de paso fijate que hora es", _turn("plan", ("app.open", "system.time"))),
        # Revisión 3: the typed readers read the order as one mission, but a clause said apart asked it
        ("abrí el visor de eventos y buscame en la web qué significa el evento 41", _turn("action", ("web.search",))),
        ("abre el visor de eventos, filtra por errores y apaga el wifi", _turn("action", ("wifi.radio.set",))),
        ("abre el visor de eventos, filtra por errores y despues bajame el volumen",
         _turn("action", ("audio.volume",))),
        ("abre powerpoint, crea una diapositiva y buscame en la web fotos de gatos", _turn("action", ("web.search",))),
        ("abre el visor de eventos y busca en la web el evento 6005 y guardalo en una nota",
         _turn("plan", ("web.search", "note.create"))),
        ("open the event viewer, filter by errors and turn off the wifi", _turn("action", ("wifi.radio.set",))),
        ("open the event viewer and search the web for event 41", _turn("action", ("web.search",))),
        ("abrí el visor de eventos and search the web for event 41", _turn("action", ("web.search",))),
    ],
)
def test_the_gate_keeps_a_request_of_its_own(text: str, turn: dict[str, Any]) -> None:
    assert _gate(text, turn) is turn
