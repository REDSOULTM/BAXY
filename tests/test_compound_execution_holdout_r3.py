from scripts.build_compound_execution_holdout_r3 import (
    build_cases,
    case_contract_sha256,
    validate_cases,
)


def test_compound_execution_r3_matrix_is_bounded_and_unique() -> None:
    cases = build_cases("RUNID", "DOCUMENT")

    validate_cases(cases)
    assert len(case_contract_sha256()) == 64
    assert len(cases) == 6
    assert sum(len(case["expected"]) for case in cases) == 27
