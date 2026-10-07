"""Live 2026-10-07 (v2-s13): «y ahora andá a configuración» after a mission in a chat application.

The contextual decider took the application from the conversation and restated «En <app>, haz clic en
Configuración.», but chose a lone ``input.visible.click``: the click went to whatever window was in front and the
person read «No se confirmó si la acción … funcionó, por lo que debes verificar…». A restatement the mission reader
reads as a step inside an application is that mission (the screen decides it, its final says «no pude» with the cause
or the verified result); one of the mission's own primitives chosen alone is a piece of it. A restatement that names
no application keeps the decider's own choice.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import missions
from baxy_mind.semantic.decider import ContextDecision

ROOT = Path(__file__).resolve().parents[1]
APPS = ("Discord", "Steam", "Bloc de notas")
OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
) + ("mission.computer.use",)
HISTORY = [
    {"role": "user", "content": "en Discord andá al canal general"},
    {"role": "assistant", "content": "No pude ir al canal general porque no lo encontré en la pantalla."},
    {"role": "user", "content": "no"},
    {"role": "assistant", "content": "Lo dejas ahí."},
]


def _tool(operation: str) -> dict[str, Any]:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The decider answers what it is given; every other model call is neutral."""

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


def _decided(text: str, decision: ContextDecision) -> dict[str, Any]:
    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    return sidecar._context_decided_result(
        {"id": "s13", "text": text, "history": [*HISTORY, {"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=APPS,
    )


@pytest.mark.parametrize(
    ("restated", "chosen"),
    [
        # the live turn
        ("En Discord, haz clic en Configuración.", "input.visible.click"),
        ("En Discord, ve a configuración.", "input.visible.click"),
        ("En Discord, ve a configuración.", "app.open"),
        # the application said after the place: the last «en» frames it
        ("Haz clic en Configuración en Discord.", "input.visible.click"),
    ],
)
def test_a_follow_up_restated_inside_the_application_is_the_mission(restated: str, chosen: str) -> None:
    result = _decided("y ahora andá a configuración", ContextDecision(restated, "action", (chosen,), ""))

    assert result["kind"] == "action"
    assert result["operation"] == "mission.computer.use"
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == restated
    # The engine's arguments come from the restatement: the application of the conversation and its goal.
    mission = missions.mission_request(result["objective"], APPS)
    assert mission is not None and mission.application == "Discord"


def test_a_restatement_that_names_no_application_keeps_the_decider_choice() -> None:
    restated = "Haz clic en Aceptar."
    assert resolve_explicit_effects(restated, OPERATIONS, APPS) is None or (
        resolve_explicit_effects(restated, OPERATIONS, APPS).operations != ("mission.computer.use",)
    )
    result = _decided("aceptá", ContextDecision(restated, "action", ("input.visible.click",), ""))

    assert result["operation"] == "input.visible.click"


def test_a_typed_operation_the_decider_chose_is_never_replaced_by_the_engine() -> None:
    # Only the mission's own primitives are pieces of it; a catalog operation keeps its typed route (D21).
    restated = "En Discord, ve a configuración."
    result = _decided("y ahora andá a configuración", ContextDecision(restated, "action", ("web.search",), ""))

    assert result["operation"] == "web.search"


@pytest.mark.parametrize(
    ("text", "application", "goal"),
    [
        ("hacé clic en Ajustes en Steam", "Steam", "hacer clic en ajustes"),
        ("andá a la biblioteca en Steam", "Steam", "ir a biblioteca"),
    ],
)
def test_the_application_said_after_the_last_place_frames_the_mission(text: str, application: str, goal: str) -> None:
    mission = missions.mission_request(text, APPS)

    assert mission is not None
    assert (mission.application, missions.fold(mission.goal)) == (application, goal)


# Live v2-x12: «abrí la calculadora» → «ahora ponela en modo científica»; the decider closed it as a limit («Pon la
# Calculadora en modo científico.») and the engine ran the bare words in no application: «no vi ningún control».
X12_APPS = ("Calculadora", "Discord", "Paint", "Bloc de notas")


def _followed(conversation: list[str], text: str, decision: ContextDecision) -> dict[str, Any]:
    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    history: list[dict[str, str]] = []
    for said in conversation:
        history += [{"role": "user", "content": said}, {"role": "assistant", "content": "Listo."}]
    return sidecar._context_decided_result(
        {"id": "x12", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=X12_APPS,
    )


_LIMIT = ContextDecision("Pon la Calculadora en modo científico.", "limit", (), "")


@pytest.mark.parametrize(
    ("conversation", "text", "application", "goal"),
    [
        # the live turn
        (["abrí la calculadora"], "ahora ponela en modo científica", "Calculadora", "activar modo cientifica"),
        (["open the calculator"], "and switch it to dark mode", "Calculadora", "activar dark mode"),
        (["abrí Discord"], "y ahora andá a configuración", "Discord", "ir a configuracion"),
        # after a mission, and after a step that inherited it
        (["en Discord andá al canal general"], "y ahora andá a configuración", "Discord", "ir a configuracion"),
        (["abrí la calculadora", "ahora ponela en modo científica"], "y ahora hacé clic en Historial", "Calculadora",
         "hacer clic en historial"),
    ],
)
def test_a_follow_up_without_application_is_the_mission_in_the_conversation_application(
    conversation: list[str], text: str, application: str, goal: str,
) -> None:
    result = _followed(conversation, text, _LIMIT)

    assert result["kind"] == "action"
    assert result["operation"] == "mission.computer.use"
    mission = missions.mission_request(result["objective"], X12_APPS)
    assert mission is not None and mission.application == application
    assert missions.fold(mission.goal) == goal
    # The arguments the engine gets: the application, the reader's goal and its check, as for the one-turn order.
    grounded = sidecar._ground_explicit_arguments("mission.computer.use", result["objective"], _MISSION_SCHEMA, X12_APPS)
    assert grounded is not None
    assert (grounded["application"], missions.fold(grounded["goal"])) == (application, goal)
    assert grounded["successCheck"] == mission.success_check


_MISSION_SCHEMA = {
    "type": "object",
    "properties": {
        "application": {"type": ["string", "null"]},
        "budgetSteps": {"type": ["integer", "null"]},
        "goal": {"type": "string"},
        "successCheck": {"type": ["string", "null"]},
    },
    "required": ["goal"],
    "additionalProperties": False,
}


def test_the_x12_follow_up_checks_the_mode_as_the_one_turn_order() -> None:
    inherited = missions.follow_up_in_application(
        "ahora ponela en modo científica", ["abrí la calculadora"], OPERATIONS, X12_APPS,
    )
    one_turn = missions.mission_request("abrí la calculadora y ponela en modo científica", X12_APPS)

    assert inherited is not None and one_turn is not None
    mission = missions.mission_request(inherited, X12_APPS)
    assert mission is not None
    assert (mission.application, mission.goal, mission.success_check) == (
        one_turn.application, one_turn.goal, one_turn.success_check,
    )


def test_a_typed_operation_the_decider_chose_for_the_step_keeps_its_route() -> None:
    result = _followed(["abrí Discord"], "y ahora andá a configuración",
                       ContextDecision("Abre la configuración de Windows.", "action", ("system.settings.status",), ""))

    assert result["operation"] != "mission.computer.use"


@pytest.mark.parametrize(
    ("conversation", "text"),
    [
        ([], "ahora ponela en modo científica"),  # no application in the conversation
        (["qué hora es"], "ahora ponela en modo científica"),
        (["abrí la calculadora", "poné música de Queen"], "ponela en modo científica"),  # something else came after
        (["abrí la calculadora y el bloc de notas"], "ponela en modo científica"),  # which one is the decider's
        (["abrí la calculadora"], "subí el volumen"),  # no step inside a window
        (["abrí la calculadora"], "activá el modo avión"),  # a typed operation of its own
        (["abrí la calculadora"], "andá a youtube.com"),  # a site
    ],
)
def test_a_follow_up_with_no_application_to_inherit_stays_the_decider_s(conversation: list[str], text: str) -> None:
    assert missions.follow_up_in_application(text, conversation, OPERATIONS, X12_APPS) is None


def test_a_follow_up_naming_another_application_uses_that_application() -> None:
    text = "ponela en modo científica en Paint"
    assert missions.follow_up_in_application(text, ["abrí la calculadora"], OPERATIONS, X12_APPS) is None
    mission = missions.mission_request(text, X12_APPS)
    assert mission is not None and mission.application == "Paint"
