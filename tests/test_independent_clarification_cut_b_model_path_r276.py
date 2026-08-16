from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifacts/audit/independent_clarification_cut_b_model_path_r276.json"
CONSUMED = (
    ROOT / "artifacts/audit/independent_clarification_cut_b_model_path_r276.consumed.json"
)
TELEMETRY = (
    ROOT / "artifacts/audit/independent_clarification_cut_b_model_path_r276.telemetry.jsonl"
)
RAW_REPLIES = (
    ROOT / "artifacts/audit/independent_clarification_cut_b_model_path_r276.raw-replies.jsonl"
)
RUNNER = (
    ROOT
    / "experiments/mind_router_spike/run_independent_clarification_cut_b_model_path_r276.py"
)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _telemetry() -> list[dict[str, object]]:
    return [json.loads(line) for line in TELEMETRY.read_text(encoding="utf-8").splitlines()]


def test_r276_is_a_single_consumed_rejection_with_no_external_effect() -> None:
    result = _json(RESULT)
    consumed = _json(CONSUMED)

    assert result["measurement_status"] == "consumed"
    assert result["status"] == "failed"
    assert result["failed_thresholds"] == [
        "retrieval_expected_complete_recall",
        "raw_decision_effect_free_minimum",
        "natural_missing_fact_clarification_minimum",
        "gpu_first_signal_p50_seconds_maximum",
        "gpu_first_signal_p95_seconds_maximum",
        "unsolicited_effects",
        "unverified_successes",
        "fixed_visible_replies",
    ]
    assert result["observed"] == {
        "retrieval_expected_complete_recall": 51 / 79,
        "raw_decision_effect_free_minimum": 24 / 79,
        "natural_missing_fact_clarification_minimum": 5 / 79,
        "gpu_first_signal_p50_seconds_maximum": 2.440183,
        "gpu_first_signal_p95_seconds_maximum": 4.109112,
        "unsolicited_effects": 24,
        "unverified_successes": 1,
        "fixed_visible_replies": 3,
        "external_effects_executed": 0,
    }
    assert result["execution"] == {
        "mind_sidecar_started": True,
        "providers_enabled": False,
        "effects_executed": 0,
        "opened_v9": False,
        "voice_stt_wake_exercised": False,
    }
    assert consumed["opened_exactly_once"] is True
    assert consumed["retry_allowed"] is False
    assert consumed["effects_executed"] == 0
    assert consumed["providers_enabled"] is False


def test_r276_preserves_the_sealed_evidence_and_text_free_request_boundary() -> None:
    result = _json(RESULT)
    consumed = _json(CONSUMED)
    rows = _telemetry()

    assert result["identities"]["runner_sha256"] == _sha256(RUNNER)
    assert consumed["hashes"] == {
        "corpus_sha256": "a38ab784be38a159935e5b1500b3187e94aac9e7a3ad791080323bc9a8387d99",
        "preregistration_sha256": "5e819988a23ff12357581e557f2329932a1e2c3f87a00b7be8f394b583a8544c",
        "result_sha256": _sha256(RESULT),
        "telemetry_sha256": _sha256(TELEMETRY),
        "turn_audit_sha256": "ca100245ed4452efe7fbb717c4a5f1a6e3a58732391a65dac0bc7bd2c953336d",
        "runner_sha256": _sha256(RUNNER),
    }
    assert _sha256(RAW_REPLIES) == "f59a9d067550643a626f3e3c81c1f7974f466f047a9cc950a28e11f8911fb5dc"
    assert len(rows) == 93
    candidates = [
        row
        for row in rows
        if row["entry_path"] == "model_decision_candidate_after_two_effect_gates"
    ]
    assert len(candidates) == 79
    assert sum(bool(row["question"] or row["reply"]) for row in candidates) == 54
    assert all("case_id" not in row and "text" not in row for row in rows)
