"""Uso real v3 ronda 19 (pedido al motor; tandas r17 t2/t3): what reaches the computer-use engine carries the
conversation's application and the shape of the order — a follow-up framed in the application the conversation is in
without its correction, a typed piece that leaves a said value unserved handed to the engine, the relative «que tengo
abierto» read as no question, «abre X que quiero ver Y» as opening X and going to Y, and «<objeto> en/con <atributo>»
as two sub-goals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import effect_intent
from baxy_mind.semantic import decider, dialogue, missions
from baxy_mind.semantic.normalize import fold
from baxy_mind import decided_arguments
from baxy_mind import engine_handoff

APPS = tuple(
    json.loads((Path(__file__).parent / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"]
)
CATALOG = effect_intent.build_application_catalog_index(APPS)

C03_T1 = "abre configuracion que quiero ver lo de la pantalla"
C04 = (
    "abre configuracion y ve a pantalla",
    "ahi ponle la escala en 125",
    "no espera se ve muy grande, regresala como estaba",
    "te dije la escala no el brillo, regresa la escala a 100",
)
T3_C02 = "en el excel que tengo abierto seleccioná la fila 1 y ponela en negrita"
C10 = "en word poné el titulo en negrita y centralo"
C11 = "abre paint y elige el lapiz con color azul"

TOOLS = {operation: {} for operation in ("mission.computer.use", "input.visible.click", "audio.volume", "app.open")}


def _history(*said: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": text} for text in said]


def _limit(said: str, *before: str) -> dict[str, object]:
    turn = {
        "type": "turn.result", "id": "r19", "kind": "conversation", "conversationKind": "unsupported",
        "operation": None, "intentOperations": [], "effectOperations": [], "question": "", "reply": "No puedo.",
    }
    return engine_handoff._engine_for_an_unserved_order(
        turn, {"id": "r19", "text": said, "history": _history(*before, said)}, TOOLS, APPS,
    )


def _typed(said: str, operation: str, *before: str) -> dict[str, object]:
    turn = {
        "type": "turn.result", "id": "r19", "kind": "action", "operation": None, "intentOperations": [operation],
        "effectOperations": [operation], "question": "", "reply": "", "objective": said,
    }
    return engine_handoff._engine_for_an_unserved_order(
        turn, {"id": "r19", "text": said, "history": _history(*before, said)}, TOOLS, APPS,
    )


# ------------------------------------------------------------------ (a) a follow-up framed in the conversation's app

def test_c04_t4_a_limit_with_no_restatement_frames_the_conversations_application_without_the_correction() -> None:
    result = _limit(C04[3], *C04[:3])
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == "en Configuración, regresa la escala a 100"


def test_c04_t4_the_engines_destination_is_the_conversations_application() -> None:
    goal = missions.follow_up_for_the_engine(C04[3], C04[:3], APPS)
    assert goal == "en Configuración, regresa la escala a 100"
    assert missions.free_form_arguments(goal, APPS, C04[:3])["application"] == "Configuración"


@pytest.mark.parametrize(
    ("said", "goal"),
    [
        ("ahi ponle la escala en 125", "en Configuración, ponle la escala en 125"),
        ("no, ponle 125", "en Configuración, ponle 125"),
    ],
)
def test_a_preamble_is_no_part_of_the_engines_goal(said: str, goal: str) -> None:
    assert missions.follow_up_for_the_engine(said, C04[:1], APPS) == goal


def test_an_english_follow_up_is_framed_in_english() -> None:
    assert (
        missions.follow_up_for_the_engine("wait, set the scale to 125", ("open settings and go to display",), APPS,
                                          english=True)
        == "in Configuración, set the scale to 125"
    )


def test_contracase_the_conversation_that_left_spotify_is_never_framed_in_spotify() -> None:
    before = ("abre spotify", "abre configuracion y ve a pantalla")
    assert missions.follow_up_for_the_engine(C04[1], before, APPS) == "en Configuración, ponle la escala en 125"
    assert "Spotify" not in str(_limit(C04[3], *before, C04[1], C04[2])["objective"])


@pytest.mark.parametrize("before", [(), ("cual es la capital de francia",)])
def test_contracase_a_follow_up_with_no_application_in_the_conversation_invents_none(before: tuple[str, ...]) -> None:
    assert missions.follow_up_for_the_engine("ponle la escala en 125", before, APPS) is None
    kept = _typed("ponle la escala en 125", "input.visible.click", *before)
    assert kept["effectOperations"] == ["input.visible.click"]


@pytest.mark.parametrize("said", ["¿cuál es la capital de Francia?", "no, cual es la capital de francia", "gracias"])
def test_contracase_a_question_or_a_remark_after_an_application_is_no_order_in_it(said: str) -> None:
    assert missions.follow_up_for_the_engine(said, ("abrí Spotify",), APPS) is None


def test_contracase_words_that_name_their_application_stay_theirs() -> None:
    assert missions.follow_up_for_the_engine("en paint ponle 125", C04[:1], APPS) is None


# --------------------------------------------------------------- (b) a typed piece that leaves the said value unserved

def test_c04_t2_one_click_for_a_said_value_is_the_engines_in_the_conversations_application() -> None:
    result = _typed(C04[1], "input.visible.click", C04[0])
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == "en Configuración, ponle la escala en 125"


def test_the_value_rule_reads_the_operations_surface() -> None:
    assert decider.leaves_the_said_value(("input.visible.click",), "ahi ponle la escala en 125")
    # Contracaso: typing carries the value said; a typed operation of its own is no piece; no number, no value.
    assert not decider.leaves_the_said_value(("input.text.type",), "escribí 125")
    assert not decider.leaves_the_said_value(("audio.volume",), "subí el volumen a 30")
    assert not decider.leaves_the_said_value(("input.visible.click",), "ahi tocá pantalla")


def test_contracase_a_typed_operation_that_carries_the_value_keeps_its_route() -> None:
    kept = _typed("subí el volumen a 30", "audio.volume", *C04[:1])
    assert kept["effectOperations"] == ["audio.volume"]


def test_contracase_a_click_with_no_value_said_keeps_its_route() -> None:
    kept = _typed("ahi tocá pantalla", "input.visible.click", C04[0])
    assert kept["effectOperations"] == ["input.visible.click"]


# ------------------------------------------------------------- (c) the relative «que tengo abierto» is no question

def test_t3_c02_the_open_relative_is_no_question_and_the_order_is_read() -> None:
    assert missions.application_question(T3_C02, APPS) is None
    assert missions.framed_clause(T3_C02, APPS) == "selecciona la fila 1 y ponela en negrita"
    mission = missions.mission_request(T3_C02, APPS)
    assert mission is not None and mission.application == "Excel"
    assert [(step.goal, step.free) for step in mission.steps] == [("seleccionar fila 1", False), ("ponela en negrita", True)]


def test_the_open_relative_in_english() -> None:
    assert missions.framed_clause("in the excel that I have open select row 1", APPS) == "select row 1"


@pytest.mark.parametrize("text", ["en excel ¿qué tengo abierto?", "in excel, what do I have open?"])
def test_contracase_what_is_open_asked_alone_is_still_a_question(text: str) -> None:
    assert missions.application_question(text, APPS) is not None


# ------------------------------------------------------------- (c) «abre X que quiero ver Y» opens X and goes to Y

@pytest.mark.parametrize(
    ("text", "goal"),
    [
        (C03_T1, "ir a pantalla"),
        ("abre configuracion para ver la parte de la pantalla", "ir a pantalla"),
        ("abre configuracion para ver los ajustes de pantalla", "ir a pantalla"),
        ("open settings so I can see the display section", "ir a display"),
        ("open settings so I can see the part about display", "ir a display"),
    ],
)
def test_c03_t1_opening_an_application_to_see_a_place_goes_there(text: str, goal: str) -> None:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.application == "Configuración" and mission.goal == goal


def test_c03_t1_the_limit_hands_the_engine_the_order_it_reads() -> None:
    result = _limit(C03_T1)
    assert result["effectOperations"] == ["mission.computer.use"]
    assert missions.mission_request(str(result["objective"]), APPS).application == "Configuración"


def test_contracase_opening_alone_is_no_mission() -> None:
    assert missions.mission_request("abre configuración", APPS) is None
    assert missions.request_shape("abre configuracion", CATALOG) == "abre configuracion"
    result = _typed("abre configuración", "app.open")
    assert result["effectOperations"] == ["app.open"]


def test_contracase_an_application_not_installed_is_not_opened_to_see() -> None:
    assert missions.request_shape("abre la puerta que quiero ver la calle", CATALOG) == "abre la puerta que quiero ver la calle"


# ---------------------------------------------------------------- (c) «<objeto> en/con <atributo>»: two sub-goals

def test_c10_the_title_in_bold_is_the_title_selected_and_bold_turned_on() -> None:
    mission = missions.mission_request(C10, APPS)
    assert mission is not None and mission.application == "Word"
    assert [step.goal for step in mission.steps] == ["seleccionar titulo", "activar negrita", "centralo"]
    assert mission.steps[1].success_check == "control:negrita:on"


def test_c11_the_pencil_with_blue_is_the_pencil_and_the_colour_blue() -> None:
    mission = missions.mission_request(C11, APPS)
    assert mission is not None and mission.application == "Paint"
    assert [step.goal for step in mission.steps] == ["seleccionar lapiz", "seleccionar azul"]
    assert all("lapiz con color" not in str(step.success_check) for step in mission.steps)


@pytest.mark.parametrize(
    ("text", "goals"),
    [
        ("in word put the title in bold", ["seleccionar title", "activar bold"]),
        ("open paint and pick the pencil with blue colour", ["seleccionar pencil", "seleccionar blue"]),
    ],
)
def test_the_attribute_split_in_english(text: str, goals: list[str]) -> None:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and [step.goal for step in mission.steps] == goals


@pytest.mark.parametrize(
    "clause",
    [
        "pone el modo avion",
        "selecciona la opcion con mas memoria",
        "pone la vista previa",
        # A text to write keeps its words: «en negrita» there is no format applied.
        "escribi el titulo en negrita",
        "type the title in bold",
        # An attribute no list holds is no attribute.
        "pone la alarma en siete",
        # A pronoun stays one free sub-goal: what it points at may not be selected.
        "ponelo en negrita",
    ],
)
def test_contracase_no_attribute_no_split(clause: str) -> None:
    assert missions.request_shape(clause, CATALOG) == clause


def test_contracase_airplane_mode_stays_one_switch() -> None:
    mission = missions.mission_request("en configuración poné el modo avión", APPS)
    assert mission is not None and mission.goal == "activar modo avion" and not mission.steps


# ------------------------------------------------------------- revisión r19: contracasos de la revisión adversarial

TOOLS_R = {
    operation: {}
    for operation in (
        "mission.computer.use", "input.visible.click", "input.key.press", "file.open", "input.pointer.control",
        "clipboard.copy",
    )
}


@pytest.mark.parametrize(
    "said", ["no, nada", "no, déjalo", "no, olvídalo", "no, para", "no, leave it", "sí, dale", "espera, olvidalo"],
)
def test_contracase_a_refusal_or_a_cancel_after_an_application_is_never_the_engines_goal(said: str) -> None:
    assert missions.follow_up_for_the_engine(said, ("abre spotify",), APPS) is None
    result = _limit(said, "abre spotify")
    assert "Spotify" not in str(result.get("objective"))


@pytest.mark.parametrize("said", ["no, nada", "no, déjalo", "no, olvídalo", "no, para", "no, leave it"])
def test_contracase_a_cancel_after_an_application_reaches_no_engine(said: str) -> None:
    assert _limit(said, "abre spotify")["effectOperations"] == []


def test_a_correction_with_an_order_after_the_no_is_still_framed() -> None:
    assert missions.follow_up_for_the_engine("no, regresa la escala a 100", C04[:1], APPS) == (
        "en Configuración, regresa la escala a 100"
    )


@pytest.mark.parametrize(
    ("said", "operation", "before"),
    [
        ("apretá el 7", "input.visible.click", "abre la calculadora"),
        ("tocá el botón 7", "input.visible.click", "abre la calculadora"),
        ("click on button 7", "input.visible.click", "open calculator"),
        ("press 5", "input.key.press", "abre la calculadora"),
        ("dale clic a la opción 2", "input.visible.click", "abre configuracion"),
        ("abrí el archivo ventas 2024", "file.open", "abre excel"),
        ("bajá 3 veces", "input.pointer.control", "abre chrome"),
        ("copiá el 125", "clipboard.copy", "abre la calculadora"),
    ],
)
def test_contracase_a_number_that_names_or_counts_what_is_touched_keeps_the_typed_piece(
    said: str, operation: str, before: str,
) -> None:
    assert not decider.leaves_the_said_value((operation,), said)
    turn = {
        "type": "turn.result", "id": "r19", "kind": "action", "operation": None, "intentOperations": [operation],
        "effectOperations": [operation], "question": "", "reply": "", "objective": said,
    }
    kept = engine_handoff._engine_for_an_unserved_order(
        turn, {"id": "r19", "text": said, "history": _history(before, said)}, TOOLS_R, APPS,
    )
    assert kept["effectOperations"] == [operation]


@pytest.mark.parametrize(
    "said", ["regresala a 100", "set the scale to 125", "dejá el brillo en 40", "ahi ponle la escala en 125"],
)
def test_a_number_said_as_an_attributes_value_is_left_by_a_click(said: str) -> None:
    assert decider.leaves_the_said_value(("input.visible.click",), said)


def test_contracase_a_click_whose_own_target_is_the_number_carries_it() -> None:
    assert not decider.leaves_the_said_value(("input.visible.click",), "ponle la escala en 125", (("target", "125"),))


@pytest.mark.parametrize(
    "text",
    [
        "en chrome decime qué tengo abierto ahora",
        "en chrome qué tengo abierto en las pestañas",
        "en spotify qué tengo abierto ahora mismo?",
        "in chrome tell me what i have open right now",
        "in excel what do i have open in the sheet",
    ],
)
def test_contracase_what_is_open_asked_with_more_words_is_still_a_question(text: str) -> None:
    assert missions.application_question(text, APPS) is not None
    assert "abiert" in str(missions.framed_clause(text, APPS)) or "open" in str(missions.framed_clause(text, APPS))


def test_contracase_a_relative_not_said_after_an_application_keeps_its_words() -> None:
    said = "cerra todo lo que tengo abierto y abri chrome"
    assert missions.request_shape(said, CATALOG) == said


def test_the_open_relative_without_that_in_english_after_the_application() -> None:
    assert missions.request_shape("in the excel i have open select row 1", CATALOG) == "in the excel select row 1"


# ------------------------------------------------------------- revisión adversarial 2: sondas de la revisión

@pytest.mark.parametrize(
    ("said", "before"),
    [
        ("no, déjalo así", "abre spotify"),
        ("no, cancela eso", "abre spotify"),
        ("no, dejalo nomas", "abre spotify"),
        ("no, dejalo ahí", "abre spotify"),
        ("no, déjalo como está", "abre configuracion y ve a pantalla"),
        ("mejor déjalo así", "abre spotify"),
        ("no, leave it as it is", "open spotify"),
        ("no, olvidate de eso", "abre spotify"),
        ("forget about it", "open spotify"),
    ],
)
def test_a_call_off_with_how_things_stay_reaches_no_engine(said: str, before: str) -> None:
    assert dialogue.calls_off(said)
    assert missions.follow_up_for_the_engine(said, (before,), APPS) is None
    assert not missions.engine_can_try(said, APPS)
    result = _limit(said, before)
    assert result["effectOperations"] == []


@pytest.mark.parametrize(
    "said",
    ["no, deja la escala en 100", "cancela la suscripción", "deja de reproducir", "no, regresa la escala a 100",
     "leave the window on the left"],
)
def test_contracase_an_order_with_a_leaving_verb_is_no_call_off(said: str) -> None:
    assert not dialogue.calls_off(said)


OPEN_TO_FIND_OUT = (
    "abre la calculadora para ver cuanto es 5 por 8",
    "abre whatsapp para ver si me escribio mi mama",
    "abre configuracion para ver si hay actualizaciones",
    "abre spotify que quiero ver si hay musica nueva",
    "abre chrome que quiero ver el clima",
    "open chrome to check my email",
    "abre configuracion para ver lo que hay en pantalla",
)
ALL_OPERATIONS = tuple(
    str(row.get("operation") or row.get("name")) if isinstance(row, dict) else str(row)
    for row in json.loads(
        (Path(decider.__file__).parent.parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
) + ("mission.computer.use",)


@pytest.mark.parametrize("text", OPEN_TO_FIND_OUT)
def test_contracase_opening_to_find_something_out_is_no_place_to_go(text: str) -> None:
    folded = fold(text)
    assert missions.request_shape(folded, CATALOG) == folded
    mission = missions.mission_request(text, APPS)
    assert mission is None or not mission.goal.startswith("ir a")
    assert effect_intent.resolve_explicit_effects(text, ALL_OPERATIONS, APPS) is None


@pytest.mark.parametrize(
    "text",
    [
        "en el excel, que tengo abierto, seleccioná la fila 1",
        "en excel, que tengo abierto selecciona la fila 1",
    ],
)
def test_the_open_relative_after_a_comma_is_no_question(text: str) -> None:
    assert missions.application_question(text, APPS) is None
    assert missions.framed_clause(text, APPS) == "selecciona la fila 1"


def test_the_open_relative_after_a_comma_in_english() -> None:
    assert missions.framed_clause("in excel, that I have open, select row 1", APPS) == "select row 1"


def test_contracase_what_is_open_asked_after_a_comma_is_still_a_question() -> None:
    assert missions.application_question("en excel, ¿qué tengo abierto?", APPS) is not None
    assert missions.application_question("en chrome, que tengo abierto en las pestañas?", APPS) is not None


# ------------------------------------------------------------- revisión adversarial 3: sondas de la revisión

# B1: what is seen bare is content to see or play, a document to open or a while, never a place of the
# application: the turn keeps its words for the decider, as in the base. «abre configuracion para ver la pantalla» and
# «open settings so I can see the display» read the same as «abre word para ver el informe»; said without a part of
# the application they are the decider's too.
OPEN_TO_SEE_CONTENT = (
    "abre youtube para ver videos de gatos",
    "open youtube to see funny cat videos",
    "abre youtube para ver el ultimo video de mrbeast",
    "abre youtube para ver un video de cocina",
    "abre youtube que quiero ver musica",
    "abre word para ver el informe",
    "abre excel para ver las ventas",
    "abre chrome para ver partidos de futbol",
    "abre paint para ver la imagen",
    "abre configuracion para ver la pantalla",
    "open settings so I can see the display",
)


@pytest.mark.parametrize("text", OPEN_TO_SEE_CONTENT)
def test_contracase_opening_to_see_content_is_no_place_to_go(text: str) -> None:
    folded = fold(text)
    assert missions.request_shape(folded, CATALOG) == folded
    mission = missions.mission_request(text, APPS)
    assert mission is None or not mission.goal.startswith("ir a")
    assert effect_intent.resolve_explicit_effects(text, ALL_OPERATIONS, APPS) is None


@pytest.mark.parametrize("text", ["open youtube to see the funny part", "open chrome to see the new tab"])
def test_contracase_a_part_or_a_tab_seen_keeps_its_words(text: str) -> None:
    assert missions.request_shape(fold(text), CATALOG) == fold(text)


def test_contracase_opening_to_watch_a_while_is_no_place_to_go() -> None:
    folded = fold("abre youtube pa ver un rato")
    assert missions.request_shape(folded, CATALOG) == folded
    mission = missions.mission_request(folded, APPS)
    assert mission is None or mission.goal != "ir a un rato"


# B2: asking to leave things as they WERE is undoing, never calling off (c04 T3 «regresala como estaba» said with
# «dejar»); the engine gets it, framed in the conversation's application when the order reads as one (an imperative
# with its pronoun), else with the person's words as in the base.
@pytest.mark.parametrize(
    ("said", "goal"),
    [
        ("déjalo como estaba", "en Configuración, déjalo como estaba"),
        ("deja todo como estaba", "deja todo como estaba"),
        ("leave it as it was", "leave it as it was"),
    ],
)
def test_leaving_it_as_it_was_is_undoing_and_reaches_the_engine(said: str, goal: str) -> None:
    assert not dialogue.calls_off(said)
    assert missions.engine_can_try(said, APPS)
    result = _limit(said, *C04[:2])
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == goal


# A bare «cancelá» or «leave» may press a dialog's Cancel or leave a call: it reaches the engine, as in the base.
@pytest.mark.parametrize(("said", "before"), [("cancelá", "abre configuracion"), ("leave", "open discord")])
def test_a_bare_cancel_or_leave_is_an_order_in_the_application(said: str, before: str) -> None:
    assert not dialogue.calls_off(said)
    assert missions.engine_can_try(said, APPS)
    assert _limit(said, before)["effectOperations"] == ["mission.computer.use"]


@pytest.mark.parametrize("said", ["no, cancelá", "cancela eso", "no, leave it", "just leave it", "olvidalo"])
def test_contracase_a_cancel_with_a_lead_or_an_object_still_calls_off(said: str) -> None:
    assert dialogue.calls_off(said)


# B3: the last gate of every turn reads the values the decider gave the turn's pieces: a click whose target carries
# the said number keeps its typed route end to end; with no values given, the click still leaves the value.
@pytest.mark.parametrize(
    ("said", "before", "arguments"),
    [
        (C04[1], C04[0], (("target", "125 %"),)),
        ("set it to 2", "open spotify", (("target", "2"),)),
        ("poné la velocidad a 2", "abre youtube", (("target", "Velocidad 2"),)),
    ],
)
def test_the_last_gate_keeps_a_click_that_carries_the_said_value(
    said: str, before: str, arguments: tuple[tuple[str, str], ...], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(decided_arguments, "_DECIDED_ARGUMENTS", {})
    decided_arguments._remember_decided_arguments(said, ("input.visible.click",), arguments)
    kept = _typed(said, "input.visible.click", before)
    assert kept["effectOperations"] == ["input.visible.click"]


def test_the_last_gate_hands_over_a_click_whose_values_leave_the_said_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(decided_arguments, "_DECIDED_ARGUMENTS", {})
    decided_arguments._remember_decided_arguments(C04[1], ("input.visible.click",), (("target", "Pantalla"),))
    result = _typed(C04[1], "input.visible.click", C04[0])
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == "en Configuración, ponle la escala en 125"
