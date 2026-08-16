from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "score_wake_verifier_product_capture_blind_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "score_wake_verifier_product_capture_blind_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _evidence() -> dict[str, object]:
    stt = {name: (name[0] * 64) for name in MODULE.STT_FILES}
    preregistration = {
        "schema": "baxy.wake-verifier-negative-holdout-preregistration.v1",
        "candidate_bundle_sha256": "a" * 64,
        "positive_development_report_sha256": "b" * 64,
        "stage1_model_sha256": "c" * 64,
        "verifier_manifest_sha256": "d" * 64,
        "ffmpeg_sha256": "e" * 64,
        "stt_files_sha256": stt,
        "gate": {
            "minimum_exposure_hours": 29.9,
            "far_confidence_gte": 0.95,
            "far_upper_confidence_per_hour_lte": 0.1,
        },
        "candidate_frozen": True,
        "product_operating_point": True,
        "negative_holdout_scored": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    positive = {
        "schema": "baxy.wake-verifier-product-capture-development.v1",
        "sources": {
            "corpus_manifest_sha256": "f" * 64,
            "stage1_model_sha256": "c" * 64,
            "verifier_manifest_sha256": "d" * 64,
            "ffmpeg_sha256": "e" * 64,
            "stt_files_sha256": stt,
        },
        "metrics": {
            "positive_accepted": 14,
            "positive_total": 14,
            "hard_negative_false_accepts": 0,
            "gate_passed": True,
        },
        "product_operating_point": True,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    negative = {
        "schema": "baxy.wake-verifier-negative-holdout-gate.v1",
        "preregistration_sha256": "0" * 64,
        "verifier_manifest_sha256": "d" * 64,
        "metrics": {
            "exposure_hours": 100.59,
            "negative_false_activations": 0,
            "far_confidence": 0.95,
            "far_upper_confidence_per_hour": 0.0298,
        },
        "negative_gate_passed": True,
        "candidate_frozen": True,
        "product_operating_point": True,
        "candidate_development_use": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    return {
        "preregistration": preregistration,
        "preregistration_sha256": "0" * 64,
        "positive_development": positive,
        "positive_development_sha256": "b" * 64,
        "negative_holdout": negative,
        "negative_holdout_sha256": "1" * 64,
        "candidate_bundle_sha256": "a" * 64,
        "corpus_manifest_sha256": "f" * 64,
        "stage1_model_sha256": "c" * 64,
        "verifier_manifest_sha256": "d" * 64,
        "stt_files_sha256": stt,
        "ffmpeg_sha256": "e" * 64,
    }


def test_release_evidence_accepts_only_complete_frozen_chain() -> None:
    MODULE.validate_release_evidence(**_evidence())


def test_release_evidence_rejects_failed_negative_gate() -> None:
    evidence = _evidence()
    evidence["negative_holdout"]["negative_gate_passed"] = False

    with pytest.raises(ValueError, match="negative_holdout_gate_invalid"):
        MODULE.validate_release_evidence(**evidence)


def test_release_evidence_rejects_positive_report_hash_mismatch() -> None:
    evidence = _evidence()
    evidence["positive_development_sha256"] = "9" * 64

    with pytest.raises(
        ValueError, match="positive_development_report_sha256"
    ):
        MODULE.validate_release_evidence(**evidence)


def test_select_blind_records_requires_frozen_four_plus_one_shape() -> None:
    records = [
        {"partition": "blind", "label": "positive"}
        for _ in range(MODULE.EXPECTED_POSITIVE_COUNT)
    ]
    records.append({"partition": "blind", "label": "hard_negative"})
    corpus = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "blind_partition_was_not_scored": True,
        "records": records,
    }

    assert MODULE.select_blind_records(corpus) == records
    records.pop()
    with pytest.raises(ValueError, match="partition_shape_invalid"):
        MODULE.select_blind_records(corpus)


def test_summary_requires_every_positive_and_zero_negative_false() -> None:
    records = [
        {"label": "positive", "detected": True},
        {"label": "positive", "detected": True},
        {"label": "hard_negative", "detected": False},
    ]
    assert MODULE.summarize(records)["gate_passed"] is True
    records[0]["detected"] = False
    assert MODULE.summarize(records)["gate_passed"] is False
