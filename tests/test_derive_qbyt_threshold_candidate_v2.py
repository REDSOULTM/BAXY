from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "derive_qbyt_threshold_candidate_v2.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_qbyt_threshold", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_threshold_uses_strict_midpoint() -> None:
    value = MODULE.select_threshold(
        human_qbyt_only_scores=[0.019, 0.021],
        contextual_false_scores=[0.017, 0.018],
    )
    assert value == pytest.approx(0.0185)


def test_select_threshold_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="wake_qbyt_threshold_separation_missing"):
        MODULE.select_threshold(
            human_qbyt_only_scores=[0.018], contextual_false_scores=[0.019]
        )
