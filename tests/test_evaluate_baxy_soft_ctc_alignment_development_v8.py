from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_soft_ctc_alignment_development_v8.py"
)
SPEC = importlib.util.spec_from_file_location("soft_ctc_v8", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def log_probabilities(path: list[int], classes: int = 7) -> np.ndarray:
    probabilities = np.full((len(path), classes), 0.002, dtype=np.float64)
    for frame, token in enumerate(path):
        probabilities[frame, token] = 0.988
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return np.log(probabilities)


def test_local_viterbi_prefers_the_temporally_ordered_sequence() -> None:
    values = log_probabilities([0, 1, 0, 2, 0, 3, 0, 4, 0, 5, 0, 0])
    ordered = MODULE.best_local_ctc_viterbi_score(
        values, (1, 2, 3, 4, 5), blank_id=0
    )
    reversed_score = MODULE.best_local_ctc_viterbi_score(
        values, (5, 4, 3, 2, 1), blank_id=0
    )
    assert ordered > reversed_score


def test_local_viterbi_ignores_unrelated_leading_and_trailing_frames() -> None:
    core = [0, 1, 0, 2, 0, 3, 0, 4, 0, 5, 0]
    short = MODULE.best_local_ctc_viterbi_score(
        log_probabilities(core), (1, 2, 3, 4, 5), blank_id=0
    )
    padded = MODULE.best_local_ctc_viterbi_score(
        log_probabilities([6] * 12 + core + [6] * 15),
        (1, 2, 3, 4, 5),
        blank_id=0,
    )
    assert abs(short - padded) < 1e-12


def test_policy_factory_keeps_local_diagnostic_and_guarded_authority_distinct() -> None:
    policies = MODULE.additional_policy_factory(
        established=False,
        fixed=True,
        full_hot=True,
        observation={
            "maximumSoftLocalCtcMargin": 0.5,
            "maximumFusionPassingSoftLocalCtcMargin": 0.5,
        },
    )
    assert policies[MODULE.threshold_name("softLocalOnly", 0.5)] is True
    assert policies[MODULE.threshold_name("guardedSoftLocal", 0.5)] is True
    assert policies[MODULE.threshold_name("softLocalOnly", 0.75)] is False


def test_guard_rejects_when_only_a_nonfusion_view_has_local_alignment() -> None:
    policies = MODULE.additional_policy_factory(
        established=False,
        fixed=True,
        full_hot=True,
        observation={
            "maximumSoftLocalCtcMargin": 0.5,
            "maximumFusionPassingSoftLocalCtcMargin": -0.5,
        },
    )
    assert policies[MODULE.threshold_name("softLocalOnly", 0.25)] is True
    assert policies[MODULE.threshold_name("guardedSoftLocal", 0.25)] is False


def test_threshold_names_are_stable_across_signs() -> None:
    assert MODULE.threshold_name("guard", -0.25) == "guard_m0025"
    assert MODULE.threshold_name("guard", 0.0) == "guard_p0000"
    assert MODULE.threshold_name("guard", 1.5) == "guard_p0150"
