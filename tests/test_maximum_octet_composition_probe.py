from collections import Counter
from pathlib import Path

from experiments.mind_router_spike import probe_maximum_octet_composition as probe


ROOT = Path(__file__).resolve().parents[1]


def test_octet_cases_exhaust_every_order_and_position_once_per_permutation() -> None:
    cases = list(probe.build_cases())

    assert len(cases) == 40_320
    assert len({case["order"] for case in cases}) == 40_320
    assert {case["language"] for case in cases} == {"es", "en"}
    assert {case["surface"] for case in cases} == set(probe.SURFACES)
    assert {case["lexical_profile"] for case in cases} == set(
        probe.LEXICAL_PROFILES
    )
    counts = Counter(
        (tail_id, position)
        for case in cases
        for position, tail_id in enumerate(case["order"])
    )
    assert set(counts.values()) == {5_040}
    assert all(len(case["expected_effect_operations"]) == 8 for case in cases)


def test_octet_probe_never_dispatches_a_plan_or_operation() -> None:
    source = (
        ROOT
        / "experiments"
        / "mind_router_spike"
        / "probe_maximum_octet_composition.py"
    ).read_text(encoding="utf-8")

    assert '"type": "turn.decide"' in source
    assert '"type": "operation.request"' not in source
    assert '"type": "plan"' not in source
    assert '"effects_executed": 0' in source
