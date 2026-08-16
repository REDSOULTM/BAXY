from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np


def _candidate_module():
    return importlib.import_module(
        "experiments.mind_router_spike.measure_dual_representation_oos_recovery"
    )


def test_zero_inside_loss_threshold_preserves_every_calibration_inside_row() -> None:
    candidate = _candidate_module()
    inside_probabilities = np.asarray([0.21, 0.83, 0.54], dtype=np.float64)

    threshold = candidate.zero_inside_loss_threshold(inside_probabilities)

    assert threshold < 0.21
    assert np.all(inside_probabilities >= threshold)
    assert 0.20 < threshold


def test_synthetic_outliers_mix_different_supported_families_deterministically() -> None:
    candidate = _candidate_module()
    features = np.asarray(
        [
            [1.0, 0.0],
            [0.8, 0.2],
            [0.0, 1.0],
            [0.2, 0.8],
        ],
        dtype=np.float64,
    )
    families = ("alpha", "alpha", "beta", "beta")

    first = candidate.synthetic_cross_family_outliers(
        features,
        families,
        count=8,
        random_state=41,
    )
    second = candidate.synthetic_cross_family_outliers(
        features,
        families,
        count=8,
        random_state=41,
    )

    assert first.shape == (8, 2)
    np.testing.assert_array_equal(first, second)
    assert np.all(first >= 0.0)
    assert np.all(first <= 1.0)


def test_dual_gate_separates_semantic_and_lexical_joint_signal() -> None:
    candidate = _candidate_module()
    inside = np.asarray(
        [
            [0.9, 0.1, 0.9, 0.1],
            [0.8, 0.2, 0.8, 0.2],
            [0.1, 0.9, 0.1, 0.9],
            [0.2, 0.8, 0.2, 0.8],
        ],
        dtype=np.float64,
    )
    outside = np.asarray(
        [
            [0.5, 0.5, -0.8, -0.8],
            [0.5, 0.5, -0.9, -0.7],
            [0.4, 0.6, -0.7, -0.9],
            [0.6, 0.4, -0.9, -0.9],
        ],
        dtype=np.float64,
    )

    gate = candidate.fit_dual_representation_gate(
        inside,
        outside,
        random_state=43,
    )
    probabilities = gate.inside_probability(np.vstack((inside, outside)))

    assert np.all(probabilities[: len(inside)] > 0.5)
    assert np.all(probabilities[len(inside) :] < 0.5)


def test_public_training_loader_excludes_historical_private_rows(
    tmp_path: Path,
) -> None:
    candidate = _candidate_module()
    source = tmp_path / "runtime.jsonl"
    rows = [
        {
            "text": "tell me the time",
            "families": ["system"],
            "provenance": {"dataset": "MASSIVE v1.1"},
        },
        {
            "text": "water the garden",
            "families": [],
            "provenance": {"dataset": "PRESTO v1"},
        },
        {
            "text": "private historical row",
            "families": ["note"],
            "provenance": {"dataset": "historical"},
        },
    ]
    source.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    loaded = candidate.load_public_training_rows(source)

    assert [row.text for row in loaded] == [
        "tell me the time",
        "water the garden",
    ]
    assert [row.inside_catalogue for row in loaded] == [True, False]


def test_candidate_without_oracle_outside_gain_is_rejected_as_ineffective() -> None:
    candidate = _candidate_module()

    verdict = candidate.candidate_verdict(
        public_inside_rejected=0,
        served_rows_lost=(),
        outside_rows_newly_zero=(),
    )

    assert verdict == "rejected_no_target_gain"


def test_nonlinear_dual_gate_learns_xor_boundary() -> None:
    candidate = _candidate_module()
    inside = np.asarray(
        [
            [0.0, 0.0],
            [0.05, 0.02],
            [1.0, 1.0],
            [0.95, 0.98],
        ],
        dtype=np.float64,
    )
    outside = np.asarray(
        [
            [0.0, 1.0],
            [0.05, 0.98],
            [1.0, 0.0],
            [0.95, 0.02],
        ],
        dtype=np.float64,
    )

    gate = candidate.fit_nonlinear_dual_representation_gate(
        inside,
        outside,
        random_state=47,
        solver="lbfgs",
    )
    probabilities = gate.inside_probability(np.vstack((inside, outside)))

    assert np.all(probabilities[: len(inside)] > 0.8)
    assert np.all(probabilities[len(inside) :] < 0.2)
