from __future__ import annotations

import json

from experiments.mind_router_spike import (
    build_compound_execution_current_tree_r5 as campaign,
)


def test_current_tree_compound_r5_matrix_is_bounded_unique_and_fresh() -> None:
    cases = campaign.build_cases("RUNID", "DOCUMENT")

    campaign.validate_cases(cases)
    assert len(campaign.case_contract_sha256()) == 64
    assert len(cases) == 6
    assert sum(len(case["expected"]) for case in cases) == 25
    current = {" ".join(str(case["objective"]).casefold().split()) for case in cases}
    assert current.isdisjoint(campaign._prior_objectives())


def test_current_tree_compound_r5_covers_every_dependent_clause_shape() -> None:
    """R5 exists to measure the repair R4 exposed, not to avoid it."""

    objectives = " ".join(
        str(case["objective"]).casefold()
        for case in campaign.build_cases("RUNID", "DOCUMENT")
    )

    assert "termina con" in objectives
    assert "finish by" in objectives
    assert "otra nota" in objectives
    assert "lee la primera" in objectives
    assert "containing" in objectives
    assert "status y" in objectives
    assert "léela" in objectives


def test_current_tree_compound_r5_has_exact_dependency_and_effect_boundaries() -> None:
    cases = campaign.build_cases("RUNID", "DOCUMENT")

    assert any("spanglish" in str(case["name"]) for case in cases)
    assert any(str(case["name"]).endswith("_en") for case in cases)
    assert all(
        len(case["expected"]) == len(case["dependency_positions"]) for case in cases
    )
    assert all(set(case["confirm"]) <= {"note.create"} for case in cases)
    assert all(set(case["expected"]) <= campaign.ALLOWED_OPERATIONS for case in cases)


def test_current_tree_compound_r5_was_opened_exactly_once_under_its_seal() -> None:
    """Guard the seal and the safety floor, never the absence of a result."""

    assert campaign.PREREGISTRATION.exists()
    assert campaign.OUTPUT.exists()

    manifest = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    assert manifest["blind_holdout"] is True
    assert manifest["preregistered_before_measurement"] is True
    assert manifest["supersedes"]["reuse_for_promotion_forbidden"] is True
    # The contract may never be edited to match the result it produced.
    assert manifest["population"]["case_contract_sha256"] == (
        campaign.case_contract_sha256()
    )

    report = json.loads(campaign.OUTPUT.read_text(encoding="utf-8"))
    summary = report["summary"]
    assert summary["status"] == "passed"
    assert summary["total"] == 6
    assert summary["passed"] == 6
    assert summary["failed"] == 0
    assert summary["verified_steps"] == 25
    assert summary["real_llm_plan_cases_passed"] == 6
    assert summary["ambiguous_effects"] == 0
