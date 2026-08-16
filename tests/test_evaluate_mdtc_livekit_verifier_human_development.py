from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mdtc_livekit_verifier_human_development.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mdtc_livekit_verifier_human_development", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_product_windows_reproduces_product_timeline() -> None:
    audio = np.ones(8000, np.float32)

    windows, ends = MODULE.product_windows(audio)

    assert windows.shape[1] == 32000
    assert ends[0] == 0.0
    assert ends[1] == 0.25
    assert np.count_nonzero(windows[0]) == 0
    assert np.count_nonzero(windows[2]) == 8000


def test_human_zero_false_point_requires_strict_separation() -> None:
    result = MODULE.human_zero_false_point(
        [
            {"label": "positive", "maximum_student_score": 0.8},
            {"label": "positive", "maximum_student_score": 0.7},
            {"label": "hard_negative", "maximum_student_score": 0.6},
        ]
    )

    assert result["possible"] is True
    assert result["recall"] == 1.0
    assert result["hard_negative_false_accepts"] == 0


def test_human_zero_false_point_reports_uncovered_positive() -> None:
    result = MODULE.human_zero_false_point(
        [
            {"label": "positive", "maximum_student_score": None},
            {"label": "hard_negative", "maximum_student_score": 0.2},
        ]
    )

    assert result == {
        "possible": False,
        "reason": "stage1_did_not_cover_every_positive",
    }
