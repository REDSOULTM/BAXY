from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "run_mdtc_human_group_cross_validation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_mdtc_human_group_cross_validation", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_clip_scores_aggregate_runtime_max_and_teacher_window_max() -> None:
    records = [
        {
            "output_relative_path": "positive.wav",
            "speaker_group": "speaker",
            "clip_label": "positive",
            "teacher_aligned_label": 0,
        },
        {
            "output_relative_path": "positive.wav",
            "speaker_group": "speaker",
            "clip_label": "positive",
            "teacher_aligned_label": 1,
        },
    ]

    result = MODULE.clip_scores(records, np.array([0.9, 0.7]))

    assert result[0]["score"] == pytest.approx(0.9)
    assert result[0]["teacher_aligned_max_score"] == pytest.approx(0.7)


def test_clip_scores_reject_mixed_clip_contract() -> None:
    records = [
        {
            "output_relative_path": "same.wav",
            "speaker_group": "one",
            "clip_label": "positive",
        },
        {
            "output_relative_path": "same.wav",
            "speaker_group": "two",
            "clip_label": "positive",
        },
    ]
    with pytest.raises(ValueError, match="clip_contract_invalid"):
        MODULE.clip_scores(records, np.array([0.1, 0.2]))
