import importlib.util
import sys
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PROBE = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "probe_maximum_octet_plan_materialization.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_maximum_octet_plan_materialization",
    PROBE,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_octet_plan_cases_balance_factors_positions_and_ordered_adjacencies():
    cases = MODULE.build_cases()
    tail_ids = tuple(
        str(tail["tail_id"])
        for tail in (*MODULE.READ_ONLY_TAILS, *MODULE.ACTION_TAILS)
    )
    position_counts = Counter()
    adjacency_counts = Counter()
    for case in cases:
        assert len(case["order"]) == 8
        assert len(case["expected_operations"]) == 8
        assert len(case["expected_arguments"]) == 8
        for position, tail_id in enumerate(case["order"]):
            position_counts[(tail_id, position)] += 1
        adjacency_counts.update(zip(case["order"], case["order"][1:]))

    assert len(cases) == MODULE.CASE_COUNT == 30
    assert len({tuple(case["order"]) for case in cases}) == 30
    assert Counter(case["language"] for case in cases) == {"es": 15, "en": 15}
    assert set(Counter(case["surface"] for case in cases).values()) == {6}
    assert set(Counter(case["lexical_profile"] for case in cases).values()) == {10}
    assert all(
        position_counts[(tail_id, position)] > 0
        for tail_id in tail_ids
        for position in range(8)
    )
    assert all(
        adjacency_counts[(left, right)] > 0
        for left in tail_ids
        for right in tail_ids
        if left != right
    )


def test_octet_plan_probe_never_dispatches_core_or_provider_effects():
    source = PROBE.read_text(encoding="utf-8")
    assert '"type": "turn.decide"' in source
    assert '"type": "plan"' in source
    for forbidden in (
        '"type": "operation.request"',
        '"type": "plan.ground"',
        "CoreProcessClient",
        "subprocess.Popen",
    ):
        assert forbidden not in source


def test_octet_plan_validator_rejects_argument_cross_contamination():
    case = MODULE.build_cases()[0]
    steps = []
    for index, (operation, arguments) in enumerate(
        zip(case["expected_operations"], case["expected_arguments"]),
        1,
    ):
        steps.append(
            {
                "id": f"step_{index}",
                "operation": operation,
                "purpose": "verified fixture",
                "dependsOn": [],
                "argumentsMode": "literal",
                "arguments": dict(arguments),
            }
        )
    valid = {"type": "plan.result", "kind": "plan", "steps": steps}
    assert MODULE._validate_plan(case, valid) == []

    list_index = case["expected_operations"].index("task.list")
    steps[list_index]["arguments"] = {"limit": 17}
    assert f"arguments_mismatch:{list_index}" in MODULE._validate_plan(case, valid)
