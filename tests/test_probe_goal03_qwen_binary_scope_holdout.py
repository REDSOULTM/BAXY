from __future__ import annotations

from experiments.mind_router_spike.probe_goal03_qwen_binary_scope_holdout import (
    NO_OPERATION,
    binary_payload,
    fail_closed_selection,
    summarize,
)


DESCRIPTIONS = {
    "app.open": "Open an application.",
    "system.time": "Read current system time.",
}


def test_binary_decision_is_first_and_uses_one_inference_schema() -> None:
    payload = binary_payload("open calculator", list(DESCRIPTIONS), DESCRIPTIONS)
    schema = payload["response_format"]["json_schema"]["schema"]

    assert list(schema["properties"])[0] == "scope_decision"
    assert schema["properties"]["scope_decision"]["enum"] == ["action", "none"]
    assert schema["required"][0] == "scope_decision"
    assert payload["chat_template_kwargs"] == {"enable_thinking": True}


def test_fail_closed_selection_accepts_only_consistent_branches() -> None:
    candidates = ["app.open", "system.time"]

    assert fail_closed_selection(
        {"scope_decision": "action", "effect_operations": ["app.open"]},
        candidates,
    ) == ("action", ["app.open"], True)
    assert fail_closed_selection(
        {"scope_decision": "none", "effect_operations": [NO_OPERATION]},
        candidates,
    ) == ("none", [], True)


def test_fail_closed_selection_rejects_mixed_or_contradictory_branches() -> None:
    candidates = ["app.open", "system.time"]

    assert fail_closed_selection(
        {
            "scope_decision": "action",
            "effect_operations": [NO_OPERATION, "app.open"],
        },
        candidates,
    ) == ("action", [], False)
    assert fail_closed_selection(
        {"scope_decision": "none", "effect_operations": ["app.open"]},
        candidates,
    ) == ("none", [], False)
    assert fail_closed_selection(
        {"scope_decision": "action", "effect_operations": ["unknown"]},
        candidates,
    ) == ("action", [], False)


def test_summary_applies_preregistered_synthetic_gates() -> None:
    positives = [
        {
            "expected_operation": "app.open",
            "selected_expected": index < 431,
            "selected_operations": ["app.open"] if index < 431 else [],
            "schema_consistent": True,
        }
        for index in range(477)
    ]
    negatives = [
        {
            "expected_operation": "__no_action__",
            "selected_expected": False,
            "selected_operations": ["system.time"] if index < 42 else [],
            "schema_consistent": True,
        }
        for index in range(307)
    ]

    result = summarize([*positives, *negatives], "synthetic")

    assert result["accepted"] is True
    assert result["decision"] == "accepted_for_real_holdout"
    assert result["positive"]["selected_expected"] == 431
    assert result["no_action"]["selected_action_calls"] == 42
