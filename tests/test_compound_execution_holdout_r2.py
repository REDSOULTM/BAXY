from __future__ import annotations

from scripts.build_compound_execution_holdout_r1 import build_cases as r1_cases
from scripts.build_compound_execution_holdout_r2 import (
    ALLOWED_OPERATIONS,
    build_cases,
    case_contract_sha256,
    validate_cases,
)


def test_compound_execution_r2_matrix_is_bounded_and_catalog_real() -> None:
    cases = build_cases("RUNID", "DOCUMENT")

    validate_cases(cases)
    assert len(case_contract_sha256()) == 64
    assert sum(len(case["expected"]) for case in cases) == 27
    assert {
        operation
        for case in cases
        for operation in case["expected"]
    } <= ALLOWED_OPERATIONS


def test_compound_execution_r2_has_zero_exact_r1_objective_overlap() -> None:
    current = {
        " ".join(str(case["objective"]).lower().split())
        for case in build_cases("RUNID", "DOCUMENT")
    }
    prior = {
        " ".join(str(case["objective"]).lower().split())
        for case in r1_cases("RUNID", "DOCUMENT")
    }

    assert current.isdisjoint(prior)
