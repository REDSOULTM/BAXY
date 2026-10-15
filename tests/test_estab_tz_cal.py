"""Encargo TZ-CAL: «esa no es la de programador wey, sigue en la estandar, cambiala» took two routes on one commit.

Tandas z1/z2 on the notebook (main 8d90cc2d0 = fable/estab-fase3 98980536d), conversation t3-c18: t1 «abre la
calculadora», t2 «ahora ponla en modo programador» (reached in both), t3 the correction. The Calculator WAS in
Programador (the independent judge of z1): the person is wrong.

- z1: t2 switched the mode and its check closed on ``page:programador``; the screen excerpt after it never writes the
  mode, and ``_read_by_the_check`` only read ``header:``/``control:…:selected``. Nothing held, the decider decided a
  limit (restating «Cambia la Calculadora a modo Programador.»), and the coverage gate handed the engine the reproach's
  own words: it pressed «Operadores estándar», wrote «0 Menos (» in the Calculator and stopped (7,9 s).
- z2: the Calculator opened already in Programador, the check closed on ``control:programador:selected``: held. The
  4B writer's draft «El programa sigue en modo Programador.» died as ``invented`` and its retry «Aquí tienes el nombre:
  Programador.» was published (1,2 s).

Now every place atom the check read on the screen holds the state (``page:``, ``title:``, ``mark:`` beside
``header:`` and a control on), and a held state is said with its own sentence (data «heldFact.state»), never drafted:
both runs answer «Ya está en «Programador»…» without pressing anything. Contracaso: with Estándar truly on the screen,
or only a click's receipt behind the check, the last mission is done again on its request
(``DialogueState.denied_state_again``), never on the reproach's words.
"""

from __future__ import annotations

import copy

import pytest

from baxy_mind import turn_audit, turn_decide
from baxy_mind.deterministic_finals import _held_fact_final
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue

T3 = "esa no es la de programador wey, sigue en la estandar, cambiala"
OPENED = "Listo, abrí la Calculadora."
REQUEST = "en Calculadora, ponla en modo programador"
SUCCESS_CHECK = (
    "control:modo programador:on|control:programador:selected|title:programador|page:programador|header:programador|"
    "control:programmer:selected|title:programmer|page:programmer|header:programmer|mark:programador|mark:programmer"
)

# t2's mission result as each run recorded it (compose_audit.jsonl, stage floor_first, payload «seen» and situation).
Z1_T2 = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "activar modo programador", "application": "Calculadora", "reached": True,
        "successCheck": SUCCESS_CHECK, "satisfiedBy": "page:programador",
        "screen": {
            "title": "Calculadora",
            "values": [
                {"name": "Decimal 0", "state": "selected"},
                {"name": "Teclado numérico completo", "state": "selected"},
                {"name": "No hay nada guardado en la memoria. Memoria", "state": "selected"},
                {"name": "Calculadora", "value": "Calculadora"},
            ],
            "numbers": ["Hexadecimal 0", "Decimal 0", "Octal 0", "Binario 0", "Se muestra 0"],
            "lines": ["Memoria", "memoria.", "MS", "Desplazamiento de bits v", "c", "Calculadora"],
        },
    },
}
Z1_T2_TOLD = "Listo, estoy en «Programador»."
Z2_T2 = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "activar modo programador", "application": "Calculadora", "reached": True,
        "successCheck": SUCCESS_CHECK, "satisfiedBy": "control:programador:selected", "arrivedAs": "Programador",
        "window": {"title": "Calculadora", "focused": {"kind": "ListItem", "name": "Estándar Calculadora"}},
        "screen": {
            "title": "Calculadora",
            "values": [
                {"name": "Programador Calculadora", "state": "selected"},
                {"name": "Decimal 0", "state": "selected"},
                {"name": "Teclado numérico completo", "state": "selected"},
                {"name": "No hay nada guardado en la memoria. Memoria", "state": "selected"},
                {"name": "Calculadora", "value": "Calculadora"},
                {"name": "Vertical", "value": "0"},
            ],
            "numbers": ["Hexadecimal 0", "Decimal 0", "Octal 0", "Binario 0"],
            "lines": ["Memoria", "memoria.", "MS", "its", "its v", "Calculadora"],
        },
    },
}
Z2_T2_TOLD = "«Programador» ya estaba elegido en «Calculadora»."


@pytest.fixture(autouse=True)
def _no_turn_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(turn_audit, "_append_turn_audit", lambda row: None)


class _Model:
    """The decider and the writer as z2 met them: any decision is a failure of the test, any draft is counted."""

    def __init__(self) -> None:
        self.drafts = 0

    def compose_user_message(self, *_args: object, **_kwargs: object) -> str:
        self.drafts += 1
        return "Aquí tienes el nombre: Programador."

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"the turn reached the model ({name})")


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation, "risk": "read_only",
            "description": f"Authenticated catalog leaf {operation}.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def _state(t2: dict, told: str) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    opened = {"kind": "operation", "operation": "app.open", "polarity": "success", "verified": True,
              "succeeded": True, "observed": {"appId": "windows.calculator", "displayName": "Calculadora"}}
    state.expect("abre la calculadora", ["app.open"])
    state.record(opened)
    state.told(opened, OPENED)
    state.expect(REQUEST, ["mission.computer.use"])
    state.record(t2)
    state.told(t2, told)
    return state


def _turn(t2: dict, told: str, text: str = T3) -> tuple[dict, _Model]:
    model = _Model()
    history = [
        {"role": "user", "content": "abre la calculadora"}, {"role": "assistant", "content": OPENED},
        {"role": "user", "content": "ahora ponla en modo programador"}, {"role": "assistant", "content": told},
        {"role": "user", "content": text},
    ]
    result = turn_decide._prepare_turn_result(
        {"id": "tz", "text": text, "history": history},
        llm=model, planner_catalog=PlannerCatalog([_tool("mission.computer.use"), _tool("app.close")]), encoder=lambda _texts: (),
        tool_by_name={"mission.computer.use": {}}, application_names=("Calculadora", "Calculator"),
        dialogue_state=_state(t2, told),
    )
    return result, model


@pytest.mark.parametrize(("t2", "told", "named"), [
    (Z1_T2, Z1_T2_TOLD, "programador"),
    (Z2_T2, Z2_T2_TOLD, "Programador"),
])
def test_z1_and_z2_say_what_the_screen_read_and_press_nothing(t2: dict, told: str, named: str) -> None:
    result, model = _turn(t2, told)

    assert result["kind"] == "conversation" and result["effectOperations"] == []
    assert result["reply"] == f"Ya está en «{named}»: es lo que muestra la pantalla."
    assert model.drafts == 0


def test_z1_page_atom_is_read_by_the_check() -> None:
    assert _state(Z1_T2, Z1_T2_TOLD).already_holds(T3) == dialogue.AlreadyHolds("state", named="programador")


def test_z2_names_the_place_arrived_at_not_the_navigation_entry() -> None:
    assert _state(Z2_T2, Z2_T2_TOLD).already_holds(T3) == dialogue.AlreadyHolds("state", named="Programador")


def test_the_held_state_sentence_in_english() -> None:
    situation = {"alreadyHolds": {"kind": "state", "named": "Programmer"}}
    assert _held_fact_final(situation, "en") == "It is already on «Programmer»: that is what the screen shows."


# --------------------------------------------------------------------------- contracasos


def _with_standard_on_screen(t2: dict) -> dict:
    shown = copy.deepcopy(t2)
    shown["observed"]["screen"]["values"].append({"name": "Modo de calculadora Estándar", "value": "Estándar"})
    return shown


@pytest.mark.parametrize("t2", [Z1_T2, Z2_T2])
def test_standard_truly_on_screen_does_the_mission_again_on_its_request(t2: dict) -> None:
    result, model = _turn(_with_standard_on_screen(t2), Z1_T2_TOLD)

    assert result["kind"] == "plan" and result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == REQUEST
    assert model.drafts == 0


def test_a_click_receipt_alone_does_the_mission_again() -> None:
    receipt = copy.deepcopy(Z1_T2)
    receipt["observed"]["satisfiedBy"] = "stepDone:input.visible.click:programador"
    state = _state(receipt, Z1_T2_TOLD)

    assert state.already_holds(T3) is None
    assert state.denied_state_again(T3) == REQUEST
    result, _ = _turn(receipt, Z1_T2_TOLD)
    assert result["objective"] == REQUEST


@pytest.mark.parametrize("text", [
    "esa no es la de programador, ponla en científica",
    "sigue en la estandar",
    "esa no es la de científica, sigue en la estandar",
    "y ahora ciérrala",
])
def test_no_denial_of_the_verified_state_is_done_again(text: str) -> None:
    state = _state(_with_standard_on_screen(Z1_T2), Z1_T2_TOLD)

    assert state.denied_state_again(text) is None


def test_a_mission_that_did_not_reach_is_never_done_again_here() -> None:
    failed = copy.deepcopy(Z1_T2)
    failed["observed"]["reached"] = False

    assert _state(failed, "No pude hacerlo.").denied_state_again(T3) is None
    assert dialogue.correction_already_holds(failed, T3) is None
