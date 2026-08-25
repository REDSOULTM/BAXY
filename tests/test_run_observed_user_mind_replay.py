from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_observed_user_mind_replay import (
    expected_contract,
    observed_operations,
    structural_verdict,
    visible_candidate,
)


def mapping(*operations: str, denied: tuple[str, ...] = ()) -> dict:
    return {
        "acceptance_scope": "product_1_0",
        "outcome_type": "mission_must_implement" if operations else "conversation_no_tool",
        "operations": list(operations),
        "denied_operations": list(denied),
        "plan": [],
        "risk": {},
        "provider_roles": [],
        "verification": [],
        "natural_response": "natural",
    }


def test_conversation_requires_model_authored_visible_text_and_zero_authority() -> None:
    turn = {"kind": "conversation", "reply": "Hola.", "operation": None}

    assert visible_candidate(turn) == "Hola."
    assert structural_verdict(mapping(), turn, None, None) == (
        "pass",
        "zero operation authority and non-empty model-authored text",
    )
    assert structural_verdict(
        mapping(), {"kind": "conversation", "reply": ""}, None, None
    )[0] == "fail"


def test_no_effect_contract_rejects_any_operation_authority() -> None:
    turn = {"kind": "action", "operation": "app.open", "reply": ""}

    assert structural_verdict(mapping(), turn, None, {})[0] == "fail"


def test_direct_action_requires_exact_operation_and_grounded_arguments() -> None:
    turn = {"kind": "action", "operation": "audio.volume"}

    assert structural_verdict(mapping("audio.volume"), turn, None, {"level": 20})[0] == "pass"
    assert structural_verdict(mapping("audio.volume"), turn, None, None)[0] == "fail"
    assert structural_verdict(mapping("audio.mute"), turn, None, {"level": 20})[0] == "fail"


def test_plan_requires_exact_order_and_materialized_steps() -> None:
    turn = {"kind": "plan", "effectOperations": ["app.open", "window.manage"]}
    plan = {
        "kind": "plan",
        "steps": [
            {"operation": "app.open", "arguments": {"app": "Steam"}},
            {"operation": "window.manage", "arguments": {"action": "focus"}},
        ],
    }

    assert observed_operations(turn, plan) == ["app.open", "window.manage"]
    assert structural_verdict(mapping("app.open", "window.manage"), turn, plan, None)[0] == "pass"
    assert structural_verdict(mapping("window.manage", "app.open"), turn, plan, None)[0] == "fail"


def test_denied_operation_always_fails() -> None:
    turn = {"kind": "action", "operation": "message.send"}

    assert structural_verdict(
        mapping("message.send", denied=("message.send",)),
        turn,
        None,
        {"recipient": "fixture"},
    )[0] == "fail"


def test_contract_projection_contains_only_reviewed_fields() -> None:
    source = mapping("app.open") | {"message_id": "private", "extra": "private"}

    projected = expected_contract(source)

    assert "message_id" not in projected
    assert "extra" not in projected
    assert projected["operations"] == ["app.open"]
