from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_ccby_wake_ctc_cascade_development.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_ccby_wake_ctc_cascade_development", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConstantPredictor:
    def __init__(self, score: float) -> None:
        self.score = score

    def predict(self, _audio: np.ndarray) -> dict[str, float]:
        return {"baxy": self.score}


def test_livekit_proposal_is_explicitly_permissive() -> None:
    proposal = MODULE.first_livekit_proposal(
        ConstantPredictor(0.06), np.zeros(16_000, np.float32), threshold=0.05
    )

    assert proposal is not None
    assert proposal["score"] == pytest.approx(0.06)


def test_validate_inputs_rejects_any_blind_access_marker() -> None:
    corpus = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "records": [
            {
                "partition": "development",
                "label": "positive",
                "output_relative_path": "development/positive/a.wav",
            }
        ],
    }
    audit = {
        "schema": "baxy.ccby-wake-parakeet-development-audit.v1",
        "partition": "development",
        "blind_human_partition_accessed": True,
        "corpus_manifest_sha256": "a" * 64,
        "records": [],
    }

    with pytest.raises(ValueError, match="cascade_blind_boundary_is_not_clean"):
        MODULE.validate_inputs(
            corpus, audit, corpus_manifest_sha256="a" * 64
        )


def test_summary_requires_full_recall_and_zero_confusable_hits() -> None:
    passed = MODULE.summarize(
        [
            {"label": "positive", "stage1_proposed": True, "detected": True},
            {
                "label": "hard_negative",
                "stage1_proposed": True,
                "detected": False,
            },
        ]
    )
    failed = MODULE.summarize(
        [
            {"label": "positive", "stage1_proposed": True, "detected": True},
            {
                "label": "hard_negative",
                "stage1_proposed": True,
                "detected": True,
            },
        ]
    )

    assert passed["development_gate_passed"] is True
    assert failed["development_gate_passed"] is False

