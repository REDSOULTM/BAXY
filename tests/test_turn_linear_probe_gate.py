from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_turn_linear_probe_gate.py"
SPEC = importlib.util.spec_from_file_location("run_turn_linear_probe_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def test_parser_defaults_to_blind_v2_and_v1_predecessor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "validation"])

    args = gate.parse_args()

    assert args.seal == gate.SEAL
    assert args.seal.name == "turn_evidence_final_seal.v2.json"
    assert args.predecessor_seal == gate.PREDECESSOR_SEAL
    assert args.predecessor_seal.name == "turn_evidence_final_seal.v1.json"


def test_linear_gate_rebuilds_canonical_v2_manifest_blindly() -> None:
    seal = gate.load_seal(
        gate.SEAL,
        gate.HOLDOUT,
        gate.PREDECESSOR_SEAL,
    )
    fingerprint = gate.seal_fingerprint(
        seal,
        seal_path=gate.SEAL,
        predecessor_seal=gate.PREDECESSOR_SEAL,
    )

    assert seal["schema"] == gate.SEAL_SCHEMA
    assert seal["final"]["rows"] == 2728
    assert (
        fingerprint["rule_declaration_sha256"]
        == gate.PRODUCTION_RULE_DECLARATION_SHA256
    )
    assert fingerprint["source_ids_sha256"] == seal["final"][
        "source_ids_sha256"
    ]


def test_linear_gate_rejects_mutated_v2_manifest(tmp_path: Path) -> None:
    payload = json.loads(gate.SEAL.read_text(encoding="utf-8"))
    payload["final"]["source_ids_sha256"] = "0" * 64
    broken = tmp_path / "broken-v2.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="reconstrucción criptográfica"):
        gate.load_seal(
            broken,
            gate.HOLDOUT,
            gate.PREDECESSOR_SEAL,
        )


def test_validation_loader_does_not_decode_unselected_test_payload(
    tmp_path: Path,
) -> None:
    holdout = tmp_path / "opaque.jsonl"
    holdout.write_bytes(
        b'{"split":"validation","source_id":"validation-a",'
        b'"text":"safe","mode":"conversation","families":[]}\n'
        b'{"split":"test","source_id":"sealed-a","text":"\xff",'
        b'"mode":"\xfe","families":[]}\n'
    )

    rows = gate.load_holdout_subset(holdout, split="validation")

    assert rows == [
        {
            "split": "validation",
            "source_id": "validation-a",
            "text": "safe",
            "mode": "conversation",
            "families": [],
        }
    ]


def test_balanced_linear_probe_and_temperature_are_deterministic() -> None:
    action = np.tile(np.asarray([[-1.0, 0.0]]), (20, 1))
    conversation = np.tile(np.asarray([[1.0, 0.0]]), (20, 1))
    vectors = np.vstack([action, conversation])
    labels = ["action"] * 20 + ["conversation"] * 20

    classes, coefficients, intercepts, implementation = gate.fit_linear_probe(
        vectors,
        labels,
    )
    logits = gate.logits_for(vectors, coefficients, intercepts)
    expected = np.asarray([classes.index(value) for value in labels])
    temperature = gate.fit_temperature(logits, expected)
    probabilities = gate.probabilities_for(logits, temperature)

    assert classes == ("action", "conversation")
    assert implementation
    assert coefficients.shape == (2, 2)
    assert 0.25 <= temperature <= 4.0
    assert np.array_equal(probabilities.argmax(axis=1), expected)


def test_one_sided_threshold_can_only_emit_conversation() -> None:
    conversation_probabilities = np.asarray(
        [0.99] * 300 + [0.01] * 300,
        dtype=np.float64,
    )
    expected = np.asarray([True] * 300 + [False] * 300)

    threshold, calibration, feasible = gate.choose_conversation_threshold(
        conversation_probabilities,
        expected,
    )
    matrix = np.column_stack(
        [1.0 - conversation_probabilities, conversation_probabilities]
    )
    rows = [
        {"mode": "conversation" if value else "action"}
        for value in expected
    ]
    metrics = gate.one_sided_metrics(matrix, rows, 1, threshold)

    assert feasible
    assert calibration["signal_precision_wilson"]["lower"] >= 0.95
    assert metrics["actionable_signals_emitted"] == 0
    assert metrics["conversation_false_action_wilson"]["upper"] <= 0.01


def test_family_abstention_meets_precision_without_hiding_recall() -> None:
    rows = [
        *[
            {
                "expected_mode": "action",
                "expected_families": ("app",),
                "predicted_family": "app",
                "raw_recall": True,
                "top1_score": 0.95,
                "score_margin": 0.20,
                "family_agreement": 0.95,
                "family_entropy": 0.05,
            }
            for _ in range(100)
        ],
        *[
            {
                "expected_mode": "conversation",
                "expected_families": (),
                "predicted_family": "app",
                "raw_recall": True,
                "top1_score": 0.10,
                "score_margin": 0.0,
                "family_agreement": 0.20,
                "family_entropy": 0.90,
            }
            for _ in range(10)
        ],
    ]

    thresholds, calibration, feasible = gate.choose_family_thresholds(rows)
    metrics = gate.family_metrics(rows, thresholds)

    assert feasible
    assert calibration["metrics"] == metrics
    assert metrics["family_precision_wilson"]["lower"] >= 0.95
    assert metrics["family_recall_wilson"]["lower"] >= 0.30
    assert metrics["actionable_coverage_wilson"]["lower"] >= 0.30


def test_hybrid_conversation_selector_rejects_probe_false_positives() -> None:
    probabilities = np.asarray([0.95] * 400)
    expected = np.asarray([True] * 300 + [False] * 100)
    rows = [
        *[
            {
                "top1_score": 0.95,
                "score_margin": 0.10,
                "conversation_agreement": 1.0,
                "mode_entropy": 0.0,
                "conversation_fraction": 1.0,
            }
            for _ in range(300)
        ],
        *[
            {
                "top1_score": 0.95,
                "score_margin": 0.10,
                "conversation_agreement": 0.0,
                "mode_entropy": 0.0,
                "conversation_fraction": 0.0,
            }
            for _ in range(100)
        ],
    ]

    threshold, knn, metrics, feasible = (
        gate.choose_hybrid_conversation_policy(
            probabilities,
            expected,
            rows,
            7,
        )
    )

    assert feasible
    assert threshold == 0.95
    assert metrics["signal_precision_wilson"]["lower"] >= 0.95
    assert metrics["conversation_recall_wilson"]["lower"] >= 0.30
    assert knn.minimum_conversation_fraction > 0.0
