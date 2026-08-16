from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_qbye_ctc_sequence_tuning_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_qbye_ctc_sequence_tuning_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_batched_ctc_matches_single_sequence_forward_probability() -> None:
    probabilities = np.asarray(
        [[0.6, 0.4], [0.5, 0.5], [0.7, 0.3]], dtype=np.float64
    )
    log_probabilities = np.log(probabilities)
    batched = MODULE.batch_ctc_sequence_log_probabilities(
        log_probabilities, [[1]], blank_id=0
    )
    expected_probability = 0.73
    assert np.exp(batched[0]) == pytest.approx(expected_probability)


def test_empty_ctc_hypothesis_is_fail_closed() -> None:
    values = np.log(np.asarray([[0.5, 0.5]], dtype=np.float64))
    result = MODULE.batch_ctc_sequence_log_probabilities(values, [[]], blank_id=0)
    assert np.isneginf(result[0])
