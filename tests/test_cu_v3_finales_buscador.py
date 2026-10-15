"""Lote en vivo r11 (2026-10-08), tarea finales-buscador.

v3-43 (Panel de control): «abre el panel de control» → «entra a Sistema y seguridad» → «luego a opciones de energía y
dime qué plan está activo». The second turn ended «Listo, lo hice en «Panel de control»» (a final that names no step)
after its verified click on «Sistema y seguridad»; the third was planned as a click plus ``vision.describe`` and ended
«No puedo decir qué plan de energía está activo porque la visión no está configurada» while the window's controls held
the plan. A step with a read of the screen it reaches is the mission (its post-read reads the window), an elliptic
«luego a X» after a going is going there, and a click part is told by its verified click.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import missions
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import context_decision

ROOT = Path(__file__).resolve().parents[1]
APPS = ("Panel de control", "Control Panel", "Calculadora", "Bloc de notas")
OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
) + ("mission.computer.use",)
V343 = ["abre el panel de control", "entra a Sistema y seguridad"]


def _tool(operation: str) -> dict[str, Any]:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def detect_response_language(self, _text):
        return "es"

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _decided(conversation: list[str], text: str, decision: ContextDecision) -> dict[str, Any]:
    history: list[dict[str, str]] = []
    for said in conversation:
        history += [{"role": "user", "content": said}, {"role": "assistant", "content": "Listo."}]
    return context_decision._context_decided_result(
        {"id": "v3-43", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]),
        application_names=APPS,
    )


# The live turn 3: the decider's restatement and its choice.
LIVE_RESTATED = "En el Panel de control, haz clic en «Opciones de energía» y dime qué plan de energía está activo."


@pytest.mark.parametrize(
    "chosen",
    [
        ("input.visible.click", "vision.describe"),  # the live choice
        ("input.visible.click", "capture.screenshot", "vision.describe"),
        ("input.visible.click", "capture.screenshot", "ocr.read"),
    ],
)
def test_a_step_with_a_read_of_the_screen_it_reaches_is_the_mission(chosen: tuple[str, ...]) -> None:
    result = _decided(V343, "luego a opciones de energía y dime qué plan está activo",
                      ContextDecision(LIVE_RESTATED, "action", chosen, ""))

    assert result["kind"] == "action"
    assert result["operation"] == "mission.computer.use"
    assert "vision.describe" not in result["effectOperations"]
    mission = missions.mission_request(result["objective"], APPS)
    assert mission is not None and mission.application == "Panel de control"
    # The question travels with the goal: the mission's post-read answers it from the window.
    assert "responder" in mission.goal


def test_a_read_of_the_screen_alone_keeps_its_route() -> None:
    # Contracase: a capture or a description the person asks for is the person's, not the engine's.
    result = _decided(V343, "sacale una captura y describímela",
                      ContextDecision("Haz una captura de pantalla y descríbela.", "action",
                                      ("capture.screenshot", "vision.describe"), ""))

    assert result.get("operation") != "mission.computer.use"
    assert "mission.computer.use" not in (result.get("effectOperations") or [])


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        ("escribe hola y sácame una captura de pantalla", "Escribe «hola» y haz una captura de pantalla."),
        ("type hello and take a screenshot", "Type «hello» and take a screenshot."),
        ("escribí hola y después un pantallazo de la ventana", "Escribe «hola» y captura la ventana."),
    ],
)
def test_a_capture_the_person_asks_for_beside_a_step_keeps_the_plan(text: str, restated: str) -> None:
    # Review finding 2: the mission keeps no capture to give; a capture the words ask for is the person's.
    capture = "capture.active.window" if "ventana" in text else "capture.screenshot"
    result = _decided(["abre el bloc de notas"], text,
                      ContextDecision(restated, "action", ("input.text.type", capture), ""))

    assert result.get("operation") != "mission.computer.use"
    assert capture in (result.get("effectOperations") or [result.get("operation")])


@pytest.mark.parametrize(
    ("text", "reads"),
    [
        ("dime qué plan está activo", True),
        ("and tell me what it says", True),
        ("sácame una captura", False),
        ("take a screenshot of it", False),
        ("tomale una foto a la pantalla", False),
    ],
)
def test_the_captures_are_the_mission_s_reads_only_when_unasked(text: str, reads: bool) -> None:
    from baxy_mind.semantic.patterns import mission_reads

    assert ("capture.screenshot" in mission_reads(text)) is reads
    assert {"vision.describe", "ocr.read"} <= mission_reads(text)


def test_a_step_and_a_read_whose_restatement_names_no_application_keep_the_plan() -> None:
    # Contracase: nothing places the step in an application; the decider's plan stands.
    result = _decided([], "hacé clic en aceptar y decime qué dice",
                      ContextDecision("Haz clic en «Aceptar» y dime qué dice la pantalla.", "action",
                                      ("input.visible.click", "vision.describe"), ""))

    assert result["kind"] == "plan"
    assert "mission.computer.use" not in result["effectOperations"]


@pytest.mark.parametrize(
    ("conversation", "text", "english", "goal"),
    [
        (V343, "luego a opciones de energía y dime qué plan está activo", False,
         "ir a opciones de energia; y responder: dime qué plan está activo"),
        (V343, "y después a Hardware y sonido", False, "ir a hardware y sonido"),
        (["open Control Panel", "go to System and Security"], "then to Power Options and tell me which plan is active",
         True, "ir a power options; y responder: tell me which plan is active"),
    ],
)
def test_a_place_alone_after_a_going_is_going_there(
    conversation: list[str], text: str, english: bool, goal: str,
) -> None:
    inherited = missions.follow_up_in_application(text, conversation, OPERATIONS, APPS, english=english)

    assert inherited is not None
    mission = missions.mission_request(inherited, APPS)
    assert mission is not None and mission.goal == goal


@pytest.mark.parametrize(
    ("conversation", "text"),
    [
        (V343, "y a las cinco recordame llamar a mamá"),  # a clock
        (V343, "luego a las 5"),
        (V343, "a ver qué hay"),  # an idiom, no link of sequence
        (V343, "y a vos qué te parece"),  # a person
        (V343, "a mi mamá mandale hola"),
        (["abrí el bloc de notas", "escribí hola"], "luego a archivo"),  # the step before went nowhere
        (["abrí la calculadora", "qué hora es"], "luego a historial"),  # the request before is no going
        # Review of finales-buscador (finding 4): a pronoun or a pointing word is no place.
        (V343, "luego a él"),
        (V343, "después a ella"),
        (V343, "luego a ellos"),
        (V343, "luego a eso"),
        (["open Control Panel", "go to System and Security"], "then to us"),
        (["open Control Panel", "go to System and Security"], "then to it"),
    ],
)
def test_an_elliptic_follow_up_needs_a_going_before_and_a_place(conversation: list[str], text: str) -> None:
    assert missions.follow_up_in_application(text, conversation, OPERATIONS, APPS) is None


@pytest.mark.parametrize("text", ["después al final de la lista", "luego al principio", "then to the bottom",
                                  "then to the top of the page"])
def test_an_end_of_what_is_shown_is_no_place_to_go(text: str) -> None:
    # Review of finales-buscador (finding 4): «al final de la lista» is a scroll, never «ir a final de la lista».
    inherited = missions.follow_up_in_application(text, V343, OPERATIONS, APPS, english=text.startswith("then"))
    mission = missions.mission_request(inherited, APPS) if inherited is not None else None

    assert mission is None or not mission.goal.startswith("ir a ")


# v3-10 (OneNote, «search my onenote notebooks for receta»): the model clicked the ribbon's «Búsqueda de Microsoft»
# (TellMeTextBox: the box of the application's commands and help) and typed «receta» there. The views are the
# window's own controls as the live run and a UIA read of the same window gave them (2026-10-08).
_ONENOTE_FRAME = [
    {"i": 0, "kind": "Button", "name": "Atrás", "state": ""},
    {"i": 1, "kind": "Button", "name": "Deshacer", "state": ""},
    {"i": 2, "kind": "Edit", "name": "Búsqueda de Microsoft ", "state": "", "value": ""},
    {"i": 3, "kind": "TabItem", "name": "Inicio", "state": "selected"},
    {"i": 4, "kind": "TabItem", "name": "Insertar", "state": ""},
    {"i": 5, "kind": "TabItem", "name": "Vista", "state": ""},
    {"i": 6, "kind": "TreeItem", "name": "PERSONA en INSTITUTO EJEMPLO", "state": "selected"},
    {"i": 7, "kind": "TreeItem", "name": "Nueva sección 1", "state": ""},
    {"i": 8, "kind": "Button", "name": "Agregar página", "state": ""},
    {"i": 9, "kind": "ListItem", "name": "Sin título", "state": "selected"},
    {"i": 10, "kind": "Document", "name": "Título de página", "state": ""},
]
ONENOTE_LIVE = {"window": {"title": "Sin título - OneNote", "process": "ONENOTE", "focused": None},
                "controls": _ONENOTE_FRAME, "text": {}}
# The same window with the notes' own search in its navigation pane (the «Buscar» button the UIA read listed).
ONENOTE_WITH_SEARCH = {
    **ONENOTE_LIVE, "controls": [*_ONENOTE_FRAME, {"i": 11, "kind": "Button", "name": "Buscar", "state": ""}],
}
SEARCH_GOAL = "search my onenote notebooks for receta"


def _validated(act: dict, view: dict, goal: str = SEARCH_GOAL, history: list | None = None) -> dict:
    return cu_validate.validate_decision(act, view=view, last_failed=None, application_names=("OneNote",),
                                history=history or [], goal=goal)


@pytest.mark.parametrize("name", ["Búsqueda de Microsoft", "Microsoft Search", "Tell me what you want to do",
                                  "¿Qué desea hacer?", "Dime qué deseas hacer", "Search commands",
                                  "Buscar comandos y ayuda"])
def test_the_box_of_commands_and_help_is_known_by_its_name(name: str) -> None:
    assert cu_lookup._command_box({"kind": "Edit", "name": name})


@pytest.mark.parametrize("name", ["Buscar", "Buscar en blocs de notas (Ctrl+E)", "Search notebooks", "Search",
                                  "Buscar un chat o iniciar uno nuevo", "Búsqueda de empleo"])
def test_a_search_of_content_is_no_command_box(name: str) -> None:
    assert not cu_lookup._command_box({"kind": "Edit", "name": name})


def test_the_live_click_on_the_command_box_goes_to_the_notes_search() -> None:
    step = _validated({"act": "click", "text": "Búsqueda de Microsoft", "i": 2, "why": ""}, ONENOTE_WITH_SEARCH)

    assert step["operation"] == "input.visible.click"
    assert step["arguments"]["label"] == "Buscar"


def test_with_no_other_search_the_model_is_told_what_the_command_box_is() -> None:
    clicked = _validated({"act": "click", "text": "Búsqueda de Microsoft", "i": 2, "why": ""}, ONENOTE_LIVE)
    assert clicked["operation"] == "none" and clicked["code"] == "command_box"
    # The live step 2: «receta» typed into the command box that had the keyboard.
    focused = {**ONENOTE_LIVE, "window": {**ONENOTE_LIVE["window"], "focused": {
        "kind": "Edit", "name": "Búsqueda de Microsoft", "value": "", "i": 2}}}
    typed = _validated({"act": "type", "text": "receta", "why": ""}, focused,
                       history=[{"step": 1, "operation": "input.visible.click", "ok": True,
                                 "label": "Búsqueda de Microsoft"}])
    assert typed["operation"] == "none" and typed["code"] == "command_box"


def test_a_command_goal_may_use_the_command_box() -> None:
    # Contracase: a goal that is no search of content keeps the model's choice.
    step = _validated({"act": "click", "text": "Búsqueda de Microsoft", "i": 2, "why": ""}, ONENOTE_LIVE,
                      goal="activar la regla")
    assert step["operation"] == "input.visible.click"
    assert step["arguments"]["label"].strip() == "Búsqueda de Microsoft"


def test_the_window_s_search_is_looked_for_before_the_command_box() -> None:
    assert cu_lookup._search_affordance(ONENOTE_WITH_SEARCH, [])["name"] == "Buscar"
    # Alone, the command box is still a place to look a command up in.
    assert cu_lookup._search_affordance(ONENOTE_LIVE, [])["name"].strip() == "Búsqueda de Microsoft"


# v3-11 (OneNote, «en onenote crea una pagina nueva»): twelve presses, «Crear una nueva sección» and «Agregar página»
# again and again, left four sections nobody asked for. The view is OneNote's navigation as the UIA read listed it.
ONENOTE_NAV = {
    "window": {"title": "Sin título - OneNote", "process": "ONENOTE", "focused": None},
    "controls": [
        {"i": 0, "kind": "TreeItem", "name": "PERSONA en INSTITUTO EJEMPLO", "state": "selected"},
        {"i": 1, "kind": "TreeItem", "name": "Nueva sección 6", "state": "selected"},
        {"i": 2, "kind": "TreeItem", "name": "Crear una nueva sección", "state": ""},
        {"i": 3, "kind": "Button", "name": "Agregar página", "state": ""},
        {"i": 4, "kind": "Button", "name": "Ordenar páginas", "state": ""},
        {"i": 5, "kind": "ListItem", "name": "Sin título", "state": "selected"},
        {"i": 6, "kind": "Document", "name": "Título de página", "state": ""},
    ],
    "text": {},
}
PAGE_GOAL = "crea una pagina nueva"


def _pressed(name: str, *, brought_new: bool = True) -> dict:
    return {"step": 1, "operation": "input.visible.click", "label": name, "name": name, "ok": True,
            "broughtNew": brought_new, "changed": True}


def test_a_command_that_creates_another_thing_than_the_goal_s_is_not_pressed() -> None:
    step = _validated({"act": "click", "text": "Crear una nueva sección", "i": 2, "why": ""}, ONENOTE_NAV, PAGE_GOAL)

    assert step["operation"] == "none" and step["code"] == "creates_other"


def test_the_command_that_creates_the_goal_s_thing_is_pressed_once() -> None:
    first = _validated({"act": "click", "text": "Agregar página", "i": 3, "why": ""}, ONENOTE_NAV, PAGE_GOAL)
    assert first["operation"] == "input.visible.click" and first["arguments"]["label"] == "Agregar página"
    # It brought a new page; pressing it again creates another one.
    again = _validated({"act": "click", "text": "Agregar página", "i": 3, "why": ""}, ONENOTE_NAV, PAGE_GOAL,
                       history=[_pressed("Agregar página")])
    assert again["operation"] == "none" and again["code"] == "creates_again"


@pytest.mark.parametrize(
    ("goal", "history"),
    [
        ("crea 3 paginas nuevas", [_pressed("Agregar página")]),  # the goal says how many
        ("crea tres paginas", [_pressed("Agregar página")]),
        (PAGE_GOAL, [_pressed("Agregar página", brought_new=False)]),  # the press brought nothing new
        ("hacer clic en agregar pagina", []),  # no creating goal, first press
    ],
)
def test_a_creating_command_is_pressed_when_nothing_says_otherwise(goal: str, history: list) -> None:
    step = _validated({"act": "click", "text": "Agregar página", "i": 3, "why": ""}, ONENOTE_NAV, goal, history)

    assert step["operation"] == "input.visible.click"


@pytest.mark.parametrize(("goal", "name", "index"), [
    ("crea una seccion nueva", "Crear una nueva sección", 2),  # the goal's own thing
    (PAGE_GOAL, "Ordenar páginas", 4),  # no creating command
])
def test_contracases_of_the_creation_guard(goal: str, name: str, index: int) -> None:
    step = _validated({"act": "click", "text": name, "i": index, "why": ""}, ONENOTE_NAV, goal)

    assert step["operation"] == "input.visible.click"


def test_an_english_creating_goal_is_read_the_same() -> None:
    view = {**ONENOTE_NAV, "controls": [{"i": 0, "kind": "TreeItem", "name": "New Section", "state": ""},
                                        {"i": 1, "kind": "Button", "name": "Add Page", "state": ""}]}
    other = _validated({"act": "click", "text": "New Section", "i": 0, "why": ""}, view, "create a new page")
    assert other["code"] == "creates_other"
    page = _validated({"act": "click", "text": "Add Page", "i": 1, "why": ""}, view, "create a new page")
    assert page["operation"] == "input.visible.click"


# Review of finales-buscador (finding 1): the goal keeps the person's words, the window speaks its own language. A
# creating command is refused only when another one of the view names what the goal asks.
@pytest.mark.parametrize(("goal", "name"), [
    ("create a new folder", "Nueva carpeta"),
    ("create a new page", "Agregar página"),
    ("create a new note", "Nueva nota"),
    ("create a new tab", "Nueva pestaña"),
    ("crear una lista de reproduccion", "Crear playlist"),
    ("crear una nota", "Agregar página"),
    ("crear un correo", "Nuevo mensaje"),
    ("crear un evento", "Nueva reunión"),
    ("crear un recordatorio", "Nueva tarea"),
])
def test_a_creating_command_alone_is_pressed_whatever_the_goal_s_words(goal: str, name: str) -> None:
    view = {**ONENOTE_NAV, "controls": [{"i": 0, "kind": "Button", "name": name, "state": ""},
                                        {"i": 1, "kind": "Button", "name": "Ordenar", "state": ""}]}
    step = _validated({"act": "click", "text": name, "i": 0, "why": ""}, view, goal)

    assert step["operation"] == "input.visible.click"


@pytest.mark.parametrize("goal", ["create a new page", "add a page", "haz una pagina nueva", "hazme una página"])
def test_a_goal_in_another_language_or_with_haz_still_refuses_the_other_thing(goal: str) -> None:
    # The live view of v3-11 (Spanish) with the goal in English or with «haz»: «Agregar página» names the page.
    other = _validated({"act": "click", "text": "Crear una nueva sección", "i": 2, "why": ""}, ONENOTE_NAV, goal)
    assert other["operation"] == "none" and other["code"] == "creates_other"
    page = _validated({"act": "click", "text": "Agregar página", "i": 3, "why": ""}, ONENOTE_NAV, goal)
    assert page["operation"] == "input.visible.click"


def test_haz_clic_is_no_creating_goal() -> None:
    step = _validated({"act": "click", "text": "Crear una nueva sección", "i": 2, "why": ""}, ONENOTE_NAV,
                      "haz clic en agregar pagina")
    assert step["operation"] == "input.visible.click"


def test_creates_again_reads_the_app_s_own_click_record() -> None:
    # The App records a click with its arguments («label», «index»), never a «name», and notes «broughtNew» on it
    # (ComputerUseMission.NoteWhatTheClickBrought).
    record = {"step": 1, "operation": "input.visible.click", "source": "model", "label": "Agregar página",
              "index": 3, "ok": True, "broughtNew": True}
    again = _validated({"act": "click", "text": "Agregar página", "i": 3, "why": ""}, ONENOTE_NAV, PAGE_GOAL,
                       history=[record])
    assert again["operation"] == "none" and again["code"] == "creates_again"
    undecided = {key: value for key, value in record.items() if key != "broughtNew"}
    first = _validated({"act": "click", "text": "Agregar página", "i": 3, "why": ""}, ONENOTE_NAV, PAGE_GOAL,
                       history=[undecided])
    assert first["operation"] == "input.visible.click"


# Review of finales-buscador (finding 3): a «type» with «field» is judged by the field it names, not by the focus.
_TITLE_FOCUSED = {**ONENOTE_LIVE, "window": {**ONENOTE_LIVE["window"], "focused": {
    "kind": "Document", "name": "Título de página", "i": 10}}}
_COMMAND_BOX_FOCUSED = {**ONENOTE_LIVE, "window": {**ONENOTE_LIVE["window"], "focused": {
    "kind": "Edit", "name": "Búsqueda de Microsoft", "value": "", "i": 2}}}
_NOTES_SEARCH_FIELD = {"i": 11, "kind": "Edit", "name": "Buscar", "state": "", "value": ""}


def test_a_typed_field_naming_the_command_box_is_refused_with_the_focus_elsewhere() -> None:
    typed = _validated({"act": "type", "text": "receta", "field": "Búsqueda de Microsoft", "why": ""}, _TITLE_FOCUSED)
    assert typed["operation"] == "none" and typed["code"] == "command_box"
    with_search = {**_TITLE_FOCUSED, "controls": [*_ONENOTE_FRAME, _NOTES_SEARCH_FIELD]}
    moved = _validated({"act": "type", "text": "receta", "field": "Búsqueda de Microsoft", "why": ""}, with_search,
                       goal="buscar receta")
    assert moved["operation"] == "input.visible.click" and moved["arguments"]["label"] == "Buscar"


def test_a_lone_command_box_is_still_the_routine_s_search() -> None:
    # Review of finales-buscador (finding 5): where the «Microsoft Search» box also searches the content (a mail
    # window) and is the view's only search, the search goal is not left without a place: the routine's own search
    # (also the literal fallback after the model's refusals) still clicks it and types the query there.
    view = {"window": {"title": "Bandeja de entrada", "process": "MAIL", "focused": None}, "text": {}, "controls": [
        {"i": 0, "kind": "Button", "name": "Nuevo correo", "state": ""},
        {"i": 1, "kind": "Edit", "name": "Microsoft Search", "state": "", "value": ""},
        {"i": 2, "kind": "ListItem", "name": "Factura octubre", "state": ""},
    ]}
    clicked = cu_rules.deterministic_step(goal="buscar factura", view=view, history=[])
    assert clicked is not None and clicked["arguments"]["label"] == "Microsoft Search"
    typed = cu_rules.deterministic_step(goal="buscar factura", view=view, history=[
        {"step": 1, "operation": "input.visible.click", "ok": True, "label": "Microsoft Search", "index": 1}])
    assert typed is not None and typed["operation"] == "input.text.type" and typed["arguments"]["text"] == "factura"


def test_a_typed_field_naming_the_content_search_stands_with_the_focus_on_the_command_box() -> None:
    view = {**_COMMAND_BOX_FOCUSED, "controls": [*_ONENOTE_FRAME, _NOTES_SEARCH_FIELD]}
    typed = _validated({"act": "type", "text": "receta", "field": "Buscar", "why": ""}, view, goal="buscar receta")

    assert typed["operation"] == "input.text.type" and typed["arguments"]["field"] == "Buscar"
