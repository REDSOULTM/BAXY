from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mdtc_livekit_verifier_student.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mdtc_livekit_verifier_student", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_roc_auc_handles_perfect_and_tied_separation() -> None:
    assert MODULE.roc_auc(np.array([0.8, 0.9]), np.array([0.1, 0.2])) == 1.0
    assert MODULE.roc_auc(np.array([0.5]), np.array([0.5])) == 0.5


def test_zero_false_operating_point_is_strictly_above_negative_tail() -> None:
    result = MODULE.zero_false_operating_point(
        np.array([0.4, 0.8, 0.9]), np.array([0.1, 0.4])
    )

    assert result["threshold"] > 0.4
    assert result["positive_accepted"] == 2
    assert result["positive_recall"] == pytest.approx(2 / 3)
    assert result["negative_false_accepts"] == 0


def test_operating_point_rejects_non_finite_scores() -> None:
    with pytest.raises(ValueError, match="scores_invalid"):
        MODULE.zero_false_operating_point(np.array([np.nan]), np.array([0.1]))


def test_human_exclusion_requires_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exclusion_without_manifest"):
        MODULE.train(
            synthetic_directory=tmp_path,
            hard_feature_manifest_path=tmp_path / "hard.json",
            wekws_directory=tmp_path,
            output_directory=tmp_path / "out",
            hidden_dimension=64,
            epochs=1,
            batch_size=1,
            learning_rate=0.001,
            hard_negative_weight=2.0,
            human_feature_manifest_path=None,
            excluded_human_speaker_group="held_out",
            human_weight=8.0,
            seed=1,
            device="cpu",
        )
