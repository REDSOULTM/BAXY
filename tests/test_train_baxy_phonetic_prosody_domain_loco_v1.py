from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "wake_validation"
    / "train_baxy_phonetic_prosody_domain_loco_v1.py"
)
SPEC = importlib.util.spec_from_file_location("phonetic_prosody", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
TRAINER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRAINER)


def records() -> list[dict[str, object]]:
    values = []
    for corpus in ("a", "b", "c"):
        for label in ("positive", "negative"):
            for index in range(10):
                values.append(
                    {
                        "corpus": corpus,
                        "label": label,
                        "audioSha256": f"{corpus}-{label}-{index:02d}",
                    }
                )
    return values


def test_split_is_complete_disjoint_and_deterministic() -> None:
    first = TRAINER.deterministic_split(records(), "c")
    second = TRAINER.deterministic_split(records(), "c")
    fit, calibration, held = first

    assert first == second
    assert len(fit) == 32
    assert len(calibration) == 8
    assert len(held) == 20
    assert not (set(fit) & set(calibration))
    assert not ((set(fit) | set(calibration)) & set(held))
    assert len(set(fit) | set(calibration) | set(held)) == 60


def test_threshold_is_above_all_negative_scores() -> None:
    scores = np.asarray([0.2, 0.8, 0.4, 0.7])
    labels = np.asarray([0, 1, 0, 1])

    threshold = TRAINER.threshold_above_negative_scores(scores, labels)

    assert threshold > 0.4
    assert np.sum(scores[labels == 0] >= threshold) == 0


def test_threshold_requires_finite_negatives() -> None:
    with pytest.raises(ValueError, match="calibration_negatives_invalid"):
        TRAINER.threshold_above_negative_scores(
            np.asarray([np.nan, 0.4]), np.asarray([0, 1])
        )


def test_v17_paths_are_forbidden() -> None:
    with pytest.raises(ValueError, match="physical_v17_forbidden"):
        TRAINER.forbid_v17([Path("D:/sealed/physical_v17")])


def test_summary_computes_baseline_and_combined_metrics() -> None:
    sample = records()[:3]
    sample[0]["label"] = "positive"
    sample[1]["label"] = "negative"
    sample[2]["label"] = "positive"
    baseline = {
        str(sample[0]["audioSha256"]): True,
        str(sample[1]["audioSha256"]): True,
        str(sample[2]["audioSha256"]): False,
    }

    result = TRAINER.summarize(
        sample,
        [0, 1, 2],
        np.asarray([0.9, 0.1, 0.8]),
        0.5,
        baseline,
    )

    assert result["modelPositiveAccepted"] == 2
    assert result["modelNegativeFalseActivations"] == 0
    assert result["baselinePositiveAccepted"] == 1
    assert result["baselineNegativeFalseActivations"] == 1
    assert result["combinedPositiveAccepted"] == 1
    assert result["combinedNegativeFalseActivations"] == 0
