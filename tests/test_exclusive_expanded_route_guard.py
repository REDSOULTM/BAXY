from __future__ import annotations

from pathlib import Path

import pytest

from experiments.wake_validation.evaluate_exclusive_expanded_route_guard_v1 import (
    _accepted_logmel_records,
    _forbid_v17,
    summarize_guard_records,
)


def test_summarize_guard_records_removes_only_unconfirmed_exclusive_route() -> None:
    result = summarize_guard_records(
        (
            {"upstreamCandidates": [True, False, True], "strictAliasMatched": None},
            {"upstreamCandidates": [False, False, True], "strictAliasMatched": True},
            {"upstreamCandidates": [False, False, True], "strictAliasMatched": False},
        )
    )

    assert result == {
        "currentLogmelAccepted": 3,
        "exclusiveExpandedAccepted": 2,
        "exclusiveExpandedStrictAliasAccepted": 1,
        "guardedLogmelAccepted": 2,
        "removedByGuard": 1,
    }


def test_accepted_logmel_records_binds_declared_count() -> None:
    records = [
        {"accepted": True, "reason": "logmel_verifier"},
        {"accepted": True, "reason": "bounded_direct_lexical_verifier"},
        {"accepted": False, "reason": "candidate_rejected"},
    ]
    assert _accepted_logmel_records({"records": records, "logmelAcceptedFiles": 1}) == [
        records[0]
    ]


def test_accepted_logmel_records_rejects_count_mismatch() -> None:
    with pytest.raises(ValueError, match="logmel_count_mismatch"):
        _accepted_logmel_records({"records": [], "logmelAcceptedFiles": 1})


def test_physical_v17_is_forbidden() -> None:
    with pytest.raises(ValueError, match="physical_v17_forbidden"):
        _forbid_v17(Path("physical_v17"))
