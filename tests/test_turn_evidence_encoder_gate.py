from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_turn_evidence_encoder_gate.py"
SPEC = importlib.util.spec_from_file_location("run_turn_evidence_encoder_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def test_report_paths_are_portable() -> None:
    assert gate.report_path(REPO / "tests" / "data" / "fixture.jsonl") == (
        "tests/data/fixture.jsonl"
    )
    assert gate.report_path(Path("C:/external/private/cache.npy")) == "cache.npy"


def test_batch_knn_scores_all_rows_and_beats_empirical_prior() -> None:
    index = SimpleNamespace(
        _records=(
            SimpleNamespace(
                mode="action",
                families=("app",),
                mission_id="train-app",
                source_id="train:es-ES:app",
            ),
            SimpleNamespace(
                mode="conversation",
                families=(),
                mission_id="train-conversation",
                source_id="train:es-ES:conversation",
            ),
            SimpleNamespace(
                mode="action",
                families=("web",),
                mission_id="train-web",
                source_id="train:en-US:web",
            ),
        ),
        _vectors=np.asarray(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [-1.0, 0.0],
            ],
            dtype=np.float32,
        ),
    )
    vectors = {
        "open calculator": [1.0, 0.0],
        "hello": [0.0, 1.0],
        "search online": [-1.0, 0.0],
    }

    def encoder(texts: list[str]) -> np.ndarray:
        return np.asarray([vectors[text] for text in texts], dtype=np.float32)

    holdout = [
        {
            "text": "open calculator",
            "mode": "action",
            "families": ["app"],
            "split": "test",
            "source_id": "fixture:en-US:1",
            "provenance": {"dataset": "fixture-a"},
        },
        {
            "text": "hello",
            "mode": "conversation",
            "families": [],
            "split": "validation",
            "source_id": "fixture:es-ES:2",
            "provenance": {"dataset": "fixture-b"},
        },
        {
            "text": "search online",
            "mode": "action",
            "families": ["web"],
            "split": "test",
            "source_id": "fixture:en-US:3",
            "provenance": {"dataset": "fixture-a"},
        },
    ]

    rows, summary = gate.evaluate_holdout_knn(
        index,
        holdout,
        encoder,
        batch_size=2,
        neighbors=1,
    )

    assert len(rows) == summary["rows"] == 3
    assert summary["knn"]["mode_accuracy"] == 1.0
    assert summary["knn"]["family_accuracy"] == 1.0
    assert summary["delta"]["mode_accuracy"] > 0
    assert summary["delta"]["mode_macro_f1"] > 0
    assert summary["delta"]["family_accuracy"] > 0
    assert set(summary["slices"]) == {"split", "language", "dataset"}
    assert set(summary["slices"]["language"]) == {"en-US", "es-ES"}
    assert all("confidence" in row for row in rows)


def _selective_row(
    source_id: str,
    *,
    expected_mode: str,
    predicted_mode: str,
    expected_family: str = "",
    predicted_family: str = "",
    confidence: float,
    split: str = "validation",
) -> dict[str, object]:
    signals = gate.TurnEvidenceConfidence(
        neighbor_count=5,
        top1_score=confidence,
        score_margin=confidence / 10.0,
        predicted_mode=predicted_mode,
        mode_agreement=confidence,
        mode_entropy=1.0 - confidence,
        predicted_family=predicted_family,
        family_agreement=confidence,
        family_entropy=1.0 - confidence,
    )
    return {
        "source_id": source_id,
        "expected_mode": expected_mode,
        "expected_families": ((expected_family,) if expected_family else ()),
        "knn_mode": predicted_mode,
        "knn_family": predicted_family,
        "split": split,
        "confidence": signals.to_dict(),
    }


def test_calibration_uses_validation_only_and_abstains_on_low_confidence() -> None:
    validation = [
        *[
            _selective_row(
                f"conversation-{index}",
                expected_mode="conversation",
                predicted_mode="conversation",
                confidence=0.95,
            )
            for index in range(20)
        ],
        *[
            _selective_row(
                f"false-action-{index}",
                expected_mode="conversation",
                predicted_mode="action",
                predicted_family="app",
                confidence=0.10,
            )
            for index in range(2)
        ],
        *[
            _selective_row(
                f"action-{index}",
                expected_mode="action",
                predicted_mode="action",
                expected_family="app",
                predicted_family="app",
                confidence=0.90,
            )
            for index in range(20)
        ],
    ]

    policy, calibration = gate.calibrate_abstention_policy(
        validation,
        runtime_source_sha256="a" * 64,
        encoder_identity="fixture",
        neighbors=5,
        maximum_conversation_false_action_upper=0.20,
        minimum_family_precision_lower=0.70,
        minimum_family_recall_lower=0.60,
        minimum_actionable_coverage_lower=0.60,
    )
    selective = gate.summarize_selective_rows(validation, policy)

    assert calibration["fit_split"] == "validation"
    assert calibration["feasible"]
    assert selective["conversation_false_action_rows"] == 0
    assert selective["selected_rows"] == 40
    assert selective["family_precision"] == 1.0
    assert selective["family_recall"] == 1.0
    assert policy.is_compatible(
        source_sha256="a" * 64,
        encoder_identity="fixture",
    )

    mixed = [
        *validation,
        _selective_row(
            "hidden-test",
            expected_mode="conversation",
            predicted_mode="action",
            predicted_family="app",
            confidence=1.0,
            split="test",
        ),
    ]
    with pytest.raises(ValueError, match="validation"):
        gate.calibrate_abstention_policy(
            mixed,
            runtime_source_sha256="a" * 64,
            encoder_identity="fixture",
            neighbors=5,
            maximum_conversation_false_action_upper=0.20,
            minimum_family_precision_lower=0.70,
            minimum_family_recall_lower=0.60,
            minimum_actionable_coverage_lower=0.60,
        )


def test_zero_sample_wilson_bound_cannot_claim_safety() -> None:
    assert gate.wilson_interval(0, 0) == (0.0, 1.0)


def test_scientific_gate_defaults_are_frozen_before_test_measurement(
    monkeypatch,
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    args = gate.parse_args()

    assert args.maximum_conversation_false_action_upper == 0.01
    assert args.minimum_family_precision_lower == 0.95
    assert args.minimum_raw_family_recall_at_k == 0.98
    assert args.minimum_actionable_coverage_lower == 0.30
    assert args.minimum_family_recall_lower == 0.30
