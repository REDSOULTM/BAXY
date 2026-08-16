from __future__ import annotations

from experiments.mind_router_spike import (
    build_compound_execution_current_tree_r4 as campaign,
)


def test_current_tree_compound_r4_matrix_is_bounded_unique_and_fresh() -> None:
    cases = campaign.build_cases("RUNID", "DOCUMENT")

    campaign.validate_cases(cases)
    assert len(campaign.case_contract_sha256()) == 64
    assert len(cases) == 6
    assert sum(len(case["expected"]) for case in cases) == 31
    current = {" ".join(str(case["objective"]).casefold().split()) for case in cases}
    assert current.isdisjoint(campaign._prior_objectives())


def test_current_tree_compound_r4_has_exact_dependency_and_effect_boundaries() -> None:
    cases = campaign.build_cases("RUNID", "DOCUMENT")

    assert any(case.get("ui_language") == "en" for case in cases)
    assert any("spanglish" in str(case["name"]) for case in cases)
    assert all(
        len(case["expected"]) == len(case["dependency_positions"]) for case in cases
    )
    assert all(set(case["confirm"]) <= {"note.create"} for case in cases)
    assert all(set(case["expected"]) <= campaign.ALLOWED_OPERATIONS for case in cases)


def test_current_tree_compound_r4_was_opened_exactly_once_under_its_seal() -> None:
    """R4 has been measured; guard the seal instead of its absence.

    The previous guard asserted the campaign was still unopened. It was opened
    on 2026-08-11 and failed at 2/6 cases and 10/31 verified steps, so that
    assertion is now simply false. What still has to hold is stronger: the
    result must exist, it must sit under the preregistration it was sealed
    with, and the sealed case contract must not have moved afterwards.
    """

    import json

    assert campaign.PREREGISTRATION.exists()
    assert campaign.OUTPUT.exists()

    manifest = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    assert manifest["blind_holdout"] is True
    assert manifest["preregistered_before_measurement"] is True
    assert manifest["population"]["cases"] == 6
    assert manifest["population"]["steps"] == 31
    # The contract may never be edited to match a disappointing result.
    assert manifest["population"]["case_contract_sha256"] == (
        campaign.case_contract_sha256()
    )

    report = json.loads(campaign.OUTPUT.read_text(encoding="utf-8"))
    summary = report["summary"]
    assert summary["total"] == 6
    assert summary["real_llm_plan_cases"] == 6
    # Coverage is an open defect; safety is not, and must stay exact.
    assert summary["ambiguous_effects"] == 0
