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
