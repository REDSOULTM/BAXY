"""Pasada r15b2 (2026-10-09): falsos éxitos de la pasada r15b que las rondas 16–17 no cubrían, la parte de la mente.

v3-35 «crea una nota rapida nueva» → «ponle: pagar la luz» → «ahora ponla de color morado»: el turno 1 leyó note.create
(la ruta explicit_effects, recuperación léxica) y preguntó título y contenido; el turno 2 guardó «Pagar la luz» en las
notas de BAXY y dijo «He creado la nota titulada «Pagar la luz»…» mientras Notas rápidas no tenía ninguna (plum.sqlite).
«una nota rápida» es una de Notas rápidas: la orden es de esa aplicación (``missions.application_said_as_object``), y el
portón de cobertura se la da al motor como a «en notas rápidas anotá …».
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import computer_use_finals
from baxy_mind import visible_defect
from baxy_mind.semantic import missions
from baxy_mind.semantic.decider import ContextDecision

from test_cu_v3_cobertura import APPS, _decided

# The live turn 1 of v3-35 (turn_audit: explicit_effects, note.create, a question for its title and content).
V3_35_T1 = "crea una nota rapida nueva"
CLARIFY = {
    "type": "turn.result", "id": "t1", "kind": "clarify", "operation": "note.create",
    "intentOperations": ["note.create"], "effectOperations": [], "reply": "",
    "question": "¿Qué contenido y título deseas para la nota?",
}


@pytest.mark.parametrize("said", [V3_35_T1, "crea una nueva nota rápida", "create a new sticky note",
                                  "hazme una nota rápida"])
def test_v3_35_a_thing_said_by_the_applications_name_is_made_in_it(said: str) -> None:
    assert missions.application_said_as_object(said, APPS) == "Notas rápidas"
    assert missions.place_application(said, APPS) == "Notas rápidas"
    result = _decided(said, ContextDecision("Crea una nota.", "action", ("note.create",), ""))
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == said


def test_v3_35_twin_the_question_for_baxys_note_is_no_question_the_order_needs() -> None:
    from baxy_mind.engine_handoff import _engine_for_an_unserved_order

    tools = {"mission.computer.use": {}, "note.create": {}}
    tried = _engine_for_an_unserved_order(dict(CLARIFY), {"id": "t1", "text": V3_35_T1}, tools, APPS)
    assert tried["kind"] == "plan" and tried["effectOperations"] == ["mission.computer.use"]
    assert tried["objective"] == V3_35_T1


@pytest.mark.parametrize("said", [
    "crea una nota nueva",                 # names no application: BAXY's own notes
    "crea una nota que diga comprar pan",
    "busca fotos de gatos",                 # no article: «fotos» is what is looked for, not Fotos
    "abre una terminal",                    # an open verb's slot is app.open's own reading
    "crea una nota rápida y después abre spotify",  # more than one clause: the decider's
])
def test_contracase_no_application_said_as_the_thing_made(said: str) -> None:
    assert missions.application_said_as_object(said, APPS) is None


# Review of the branch: only a verb that makes a thing (``lexicon.MAKE_VERBS``) says it is made in the application of
# that name; buying, recommending, explaining, saying, putting on or looking up one names no place to work in.
APPS_REVIEW = APPS + ("Cámara", "Música")


@pytest.mark.parametrize("said", [
    "compra una camara",
    "recomiendame una terminal",
    "explicame una nota rapida",
    "dime una nota rapida",
    "ponme una musica",
    "busca un terminal",
])
def test_contracase_a_verb_that_makes_nothing_names_no_application(said: str) -> None:
    assert missions.application_said_as_object(said, APPS_REVIEW) is None
    assert missions.place_application(said, APPS_REVIEW) is None
    assert missions.said_in_place(said, APPS_REVIEW) is None


def test_contracase_a_search_for_an_applications_name_stays_a_web_search() -> None:
    result = _decided("busca un terminal", ContextDecision("Busca un terminal.", "action", ("web.search",), ""))
    assert result["effectOperations"] == ["web.search"]


def test_contracase_a_plain_note_keeps_its_typed_route_and_its_question() -> None:
    from baxy_mind.engine_handoff import _engine_for_an_unserved_order

    result = _decided("crea una nota nueva", ContextDecision("Crea una nota.", "action", ("note.create",), ""))
    assert result["effectOperations"] == ["note.create"]
    tools = {"mission.computer.use": {}, "note.create": {}}
    asked = dict(CLARIFY)
    assert _engine_for_an_unserved_order(asked, {"id": "t1", "text": "crea una nota nueva"}, tools, APPS) is asked


# v3-22 t3 «¿cuáles tienen impacto alto?»: the decider looked at the Task Manager (input.visible.controls); the window
# runs as administrator and the read listed only its frame. The draft defined «impacto alto» from nowhere and passed.
ELEVATED_READ = {
    "kind": "operation", "operation": "input.visible.controls", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {
        "version": 2, "ok": True, "error": "",
        "window": {"title": "Administrador de tareas", "process": "Taskmgr", "requested": True, "foreground": True,
                   "elevated": True, "focused": {"kind": "Pane", "name": "TaskManagerMain", "nameSource": "", "i": 3}},
        "controls": [{"i": 0, "kind": "Pane", "name": "DesktopWindowXamlSource", "zone": "C"},
                     {"i": 1, "kind": "Pane", "name": "Filter Control Glass Window", "zone": "T"},
                     {"i": 2, "kind": "Pane", "name": "Glass Window", "zone": "TR"},
                     {"i": 3, "kind": "Pane", "name": "TaskManagerMain", "state": "focused", "zone": "C"},
                     {"i": 4, "kind": "TitleBar", "name": "Administrador de tareas", "zone": "TL"}],
        "controlCount": 5, "authority": "windows_uia_snapshot_ocr_zones",
    },
}
IMPACT_SAID = "¿cuáles tienen impacto alto?"


def test_v3_22_t3_a_look_at_an_elevated_window_is_told_as_its_limit() -> None:
    told = computer_use_finals._elevated_read_floor(ELEVATED_READ, "es", IMPACT_SAID)
    assert told == ("No pude hacerlo en «Administrador de tareas»: esa aplicación corre como administrador y Windows no "
                    "deja que otra aplicación la controle.")
    told_en = computer_use_finals._elevated_read_floor(ELEVATED_READ, "en", "which ones have high impact?")
    assert told_en.startswith("I couldn't do it in «Administrador de tareas»")
    situation = json.dumps(ELEVATED_READ, ensure_ascii=False)
    assert visible_defect.compose_visible_defect(told, "status", IMPACT_SAID, {"situation": situation}) == ""


def test_contracase_a_window_read_whole_or_with_text_is_drafted() -> None:
    plain = copy.deepcopy(ELEVATED_READ)
    del plain["observed"]["window"]["elevated"]
    assert computer_use_finals._elevated_read_floor(plain, "es", IMPACT_SAID) == ""
    read = copy.deepcopy(ELEVATED_READ)
    read["observed"]["text"] = {"C": ["Steam", "Alto"]}
    assert computer_use_finals._elevated_read_floor(read, "es", IMPACT_SAID) == ""
    assert computer_use_finals._elevated_read_floor({**ELEVATED_READ, "operation": "app.open"}, "es", IMPACT_SAID) == ""


# Review of the branch: the read of an elevated window keeps its frame (title, process, that it is elevated), which
# answers a question about the window itself; telling that as the limit would be a failure that never happened.
@pytest.mark.parametrize("said", [
    "¿qué ventana tengo delante?", "¿cómo se llama esta ventana?", "¿en qué app estoy?", "what window is this?",
    "¿cuál es la ventana activa?", "¿corre como administrador?", "¿qué tengo abierto?",
])
def test_contracase_a_question_about_the_window_itself_is_drafted(said: str) -> None:
    from baxy_mind.semantic import windows

    assert windows.asks_about_the_window_frame(said)
    assert computer_use_finals._elevated_read_floor(ELEVATED_READ, "es", said) == ""
    assert computer_use_finals._elevated_read_floor(ELEVATED_READ, "en", said) == ""


@pytest.mark.parametrize("said", [
    IMPACT_SAID, "¿qué dice la ventana?", "¿qué programas tienen impacto alto?", "¿qué app consume más?",
    "what does the window say?", "¿cuál es el nombre del programa con más memoria?",
])
def test_a_question_about_what_the_window_shows_is_the_limit(said: str) -> None:
    from baxy_mind.semantic import windows

    assert not windows.asks_about_the_window_frame(said)
    told = computer_use_finals._elevated_read_floor(ELEVATED_READ, "es", said)
    assert told.startswith("No pude hacerlo en «Administrador de tareas»")
