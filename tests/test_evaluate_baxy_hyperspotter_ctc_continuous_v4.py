from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_hyperspotter_ctc_continuous_v4.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_hyperspotter_ctc_continuous_v4", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_standardized_uses_only_reference_partition() -> None:
    values, center, scale = MODULE.standardized(
        np.asarray([1.0, 3.0, 100.0]), np.asarray([True, True, False])
    )
    assert center == 2.0
    assert scale == 1.0
    assert np.allclose(values[:2], [-1.0, 1.0])


def test_policy_can_use_ctc_feature_to_remove_legacy_false() -> None:
    policy = MODULE.select_policy(
        labels=np.asarray([1, 1, 0, 0]),
        hyper_scores=np.asarray([3.0, 2.0, 2.5, 1.0]),
        features={"full_clip_margin": np.asarray([1.0, 1.0, -2.0, 0.0])},
    )
    selected = policy["selected"]
    assert selected["positive_hits"] == 2
    assert selected["false_hits"] == 0
    assert selected["beta"] > 0.0


def test_fixed_grids_include_unfused_baseline() -> None:
    assert 0.0 in MODULE.BETA_GRID
    assert MODULE.WINDOW_LENGTHS == tuple(sorted(MODULE.WINDOW_LENGTHS))


def test_vectorized_ctc_matches_scalar_recurrence() -> None:
    rng = np.random.default_rng(4)
    probabilities = rng.random((2, 7, 4))
    probabilities /= probabilities.sum(axis=2, keepdims=True)
    log_probabilities = np.log(probabilities)
    sequence = [1, 2]

    def scalar(values: np.ndarray) -> float:
        states = [0, 1, 0, 2, 0]
        previous = np.full(len(states), -np.inf)
        previous[0] = values[0, 0]
        previous[1] = values[0, 1]
        for frame in range(1, len(values)):
            current = np.full(len(states), -np.inf)
            for state, token in enumerate(states):
                total = previous[state]
                if state > 0:
                    total = np.logaddexp(total, previous[state - 1])
                if state > 1 and token != 0 and token != states[state - 2]:
                    total = np.logaddexp(total, previous[state - 2])
                current[state] = total + values[frame, token]
            previous = current
        return float(np.logaddexp(previous[-1], previous[-2]))

    expected = np.asarray([scalar(value) for value in log_probabilities])
    actual = MODULE.ctc_log_probability_batch(
        log_probabilities, sequence, blank_id=0
    )
    assert np.allclose(actual, expected)
