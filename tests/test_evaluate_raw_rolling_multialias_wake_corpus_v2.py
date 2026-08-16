from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_raw_rolling_multialias_wake_corpus_v2.py"
)
SPEC = importlib.util.spec_from_file_location("rolling_multialias_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_same_window_consensus_accepts_two_aliases_together() -> None:
    accepted, index, primary, secondary = MODULE.same_window_consensus(
        np.asarray(
            [
                [0.8, -0.2, -1.0, -2.0],
                [0.7, 0.4, -0.5, -1.0],
            ],
            dtype=np.float32,
        )
    )
    assert accepted is True
    assert index == 1
    assert primary == pytest.approx(0.7)
    assert secondary == pytest.approx(0.4)


def test_same_window_consensus_rejects_aliases_from_different_windows() -> None:
    accepted, index, primary, secondary = MODULE.same_window_consensus(
        np.asarray(
            [
                [2.0, -0.1, -1.0, -2.0],
                [-1.0, 2.0, 0.1, -2.0],
            ],
            dtype=np.float32,
        )
    )
    assert accepted is False
    assert index is None
    assert primary == pytest.approx(2.0)
    assert secondary == pytest.approx(0.1)


def test_same_window_consensus_rejects_non_finite_logits() -> None:
    with pytest.raises(ValueError, match="rolling_multialias_logits_invalid"):
        MODULE.same_window_consensus(
            np.asarray([[0.8, np.nan, 0.4, -1.0]], dtype=np.float32)
        )


def test_continuous_rolling_windows_scan_a_long_clip() -> None:
    audio = np.zeros(5 * MODULE.SAMPLE_RATE, dtype=np.float32)
    windows = MODULE.continuous_rolling_windows(audio)

    assert len(windows) == 17
    assert all(window.shape == (3 * MODULE.SAMPLE_RATE,) for window in windows)


def test_continuous_rolling_windows_preserve_exact_three_second_contract() -> None:
    audio = np.zeros(3 * MODULE.SAMPLE_RATE, dtype=np.float32)
    assert len(MODULE.continuous_rolling_windows(audio)) == 9
