from __future__ import annotations

from scripts.build_compound_execution_holdout_r1 import (
    ALLOWED_OPERATIONS,
    build_cases,
    case_contract_sha256,
    validate_cases,
)


def test_compound_execution_r1_matrix_is_bounded_and_complete() -> None:
    cases = build_cases("RUNID", "DOCUMENT")

    validate_cases(cases)
    assert len(case_contract_sha256()) == 64
    assert sum(len(case["expected"]) for case in cases) == 27
    assert {
        operation
        for case in cases
        for operation in case["expected"]
    } <= ALLOWED_OPERATIONS


def test_compound_execution_r1_has_no_exact_objective_from_the_existing_gate() -> None:
    from scripts.run_llm_plan_execution_gate import build_cases as prior_cases

    current = {
        " ".join(str(case["objective"]).lower().split())
        for case in build_cases("RUNID", "DOCUMENT")
    }
    prior = {
        " ".join(str(case["objective"]).lower().split())
        for case in prior_cases("RUNID", "DOCUMENT")
    }

    assert current.isdisjoint(prior)
