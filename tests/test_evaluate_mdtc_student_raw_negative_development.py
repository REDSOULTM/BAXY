from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mdtc_student_raw_negative_development.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mdtc_student_raw_negative_development", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_summarize_activations_counts_one_event_per_utterance() -> None:
    result = MODULE.summarize_activations(
        [
            {"source_utterance_id": "a"},
            {"source_utterance_id": "a"},
            {"source_utterance_id": "b"},
        ],
        np.array([0.8, 0.9, 0.2]),
        threshold=0.7,
        exposure_hours=2.0,
    )

    assert result["false_activations"] == 1
    assert result["point_false_activations_per_hour"] == 0.5
    assert result["activated_utterances"] == {"a": 0.9}


def test_summarize_activations_reports_zero_event_upper_bound() -> None:
    result = MODULE.summarize_activations(
        [{"source_utterance_id": "a"}],
        np.array([0.1]),
        threshold=0.7,
        exposure_hours=3.0,
    )

    assert result["false_activations"] == 0
    assert result["zero_event_upper_95_fpph"] == pytest.approx(
        -np.log(0.05) / 3.0
    )
