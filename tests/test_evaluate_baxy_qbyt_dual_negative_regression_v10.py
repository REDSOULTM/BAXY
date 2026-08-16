from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_qbyt_dual_negative_regression_v10.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_qbyt_dual", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_combined_guard_requires_sequence_boundary() -> None:
    assert not MODULE.combine_secondary_evidence(
        explicit_sequence_allowed=False, qbyt_accepted=True, plain_accepted=True
    )


def test_combined_guard_accepts_either_independent_second_pass() -> None:
    assert MODULE.combine_secondary_evidence(
        explicit_sequence_allowed=True, qbyt_accepted=True, plain_accepted=False
    )
    assert MODULE.combine_secondary_evidence(
        explicit_sequence_allowed=True, qbyt_accepted=False, plain_accepted=True
    )
