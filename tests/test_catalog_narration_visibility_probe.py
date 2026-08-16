from pathlib import Path

from experiments.mind_router_spike.probe_catalog_narration_visibility import (
    FAMILY_SUBJECTS,
    FORBIDDEN_TERMS,
    build_cases,
)


ROOT = Path(__file__).resolve().parents[1]


def test_narration_subjects_are_bound_to_core_and_cover_each_mode() -> None:
    source = (
        ROOT / "src/Baxy.Core/Operations/ProductOperationNarrator.cs"
    ).read_text(encoding="utf-8")
    capabilities = [
        {"name": f"{family}.probe"}
        for family in FAMILY_SUBJECTS
    ]

    cases = build_cases(capabilities)

    assert len(cases) == 2 * len(FAMILY_SUBJECTS)
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["intent"] for case in cases} == {"status", "error"}
    assert all(subject in source for subject in FAMILY_SUBJECTS.values())
    assert "operación" in FORBIDDEN_TERMS
    assert all(case["budget_seconds"] in {5.0, 10.0} for case in cases)
