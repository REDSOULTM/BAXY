import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PROBE = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "probe_long_mission_visible_response.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_long_mission_visible_response",
    PROBE,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_visible_response_probe_is_effect_free_and_covers_long_partial_bilingual_cases():
    source = PROBE.read_text(encoding="utf-8")
    cases = MODULE.build_cases()

    assert len(cases) == 8
    assert {case["intent"] for case in cases} == {
        "status",
        "error",
        "confirmation",
    }
    assert sum("-es" in case["case_id"] for case in cases) >= 3
    assert sum("-en" in case["case_id"] for case in cases) >= 3
    assert any(len(case["facts"].get("requiredFacts", [])) == 8 for case in cases)
    assert any(len(case["facts"].get("requiredFacts", [])) == 12 for case in cases)
    assert MODULE.composition_budget_seconds(
        next(
            case["facts"] for case in cases
            if case["case_id"] == "octet-success-es"
        )
    ) == 10.0
    assert MODULE.composition_budget_seconds(
        next(
            case["facts"] for case in cases
            if case["case_id"] == "partial-failure-es"
        )
    ) == 10.0
    assert "message.compose" in source
    for forbidden_request in (
        '"type": "plan"',
        '"type": "plan.ground"',
        '"type": "turn.decide"',
        '"type": "arguments"',
    ):
        assert forbidden_request not in source


def test_visible_response_validator_rejects_dropped_fact_jargon_and_false_polarity():
    case = next(
        case for case in MODULE.build_cases()
        if case["case_id"] == "partial-failure-es"
    )
    complete = " ".join(case["facts"]["requiredFacts"])
    valid_text = f"No pude completar toda la misión. {complete}"
    valid_reply = {"type": "message.compose.result", "text": valid_text}
    assert MODULE.validate(case, valid_reply, 0.2) == []

    missing = {"type": "message.compose.result", "text": "No pude terminar."}
    assert any(
        error.startswith("missing_fact:")
        for error in MODULE.validate(case, missing, 0.2)
    )

    jargon = {
        "type": "message.compose.result",
        "text": valid_text + " El planner revisó el JSON.",
    }
    assert any(
        error.startswith("forbidden:")
        for error in MODULE.validate(case, jargon, 0.2)
    )

    false_success = {
        "type": "message.compose.result",
        "text": "Completé toda la misión. " + complete,
    }
    assert "missing_required_polarity" in MODULE.validate(
        case,
        false_success,
        0.2,
    )

    status_case = next(
        candidate for candidate in MODULE.build_cases()
        if candidate["case_id"] == "octet-success-es"
    )
    echoed = {
        "type": "message.compose.result",
        "text": (
            status_case["user_text"] + " "
            + " ".join(status_case["facts"]["requiredFacts"])
        ),
    }
    assert "imperative_result" in MODULE.validate(status_case, echoed, 0.2)
