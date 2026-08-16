from pathlib import Path

from baxy_mind.planner import conditional_predecessors, required_predecessors
from experiments.mind_router_spike import probe_dependency_grounding_matrix as probe


ROOT = Path(__file__).resolve().parents[1]


def test_grounding_matrix_is_unique_bounded_and_dependency_complete() -> None:
    cases = probe.build_cases()

    assert len(cases) == 19
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert all(case["observations"] for case in cases)
    for case in cases:
        assert len(case["observations"]) == 1
        observation = case["observations"][0]
        assert observation["verified"] is True
        assert observation["status"] == "completed"
        assert observation["operation"] == case["producer"]
        permitted = set(required_predecessors(case["operation"])) | set(
            conditional_predecessors(case["operation"], case["objective"])
        )
        assert case["producer"] in permitted


def test_grounding_matrix_never_dispatches_an_operation() -> None:
    source = (
        ROOT
        / "experiments"
        / "mind_router_spike"
        / "probe_dependency_grounding_matrix.py"
    ).read_text(encoding="utf-8")

    assert '"type": "plan.ground"' in source
    assert '"type": "operation.request"' not in source
    assert '"type": "plan"' not in source
    assert '"effects_executed": 0' in source


def test_argument_match_requires_expected_fields_and_rejects_unknown_extras() -> None:
    case = {
        "expected": {"captureId": "capture_1"},
        "allowed_extra": {"language"},
    }

    assert probe._arguments_match(case, {"captureId": "capture_1"})
    assert probe._arguments_match(
        case,
        {"captureId": "capture_1", "language": "es"},
    )
    assert not probe._arguments_match(case, {"captureId": "decoy"})
    assert not probe._arguments_match(
        case,
        {"captureId": "capture_1", "authority": "admin"},
    )
