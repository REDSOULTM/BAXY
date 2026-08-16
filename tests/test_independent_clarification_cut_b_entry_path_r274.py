from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifacts/audit/independent_clarification_cut_b_entry_path_r274.json"
RUNNER = (
    ROOT
    / "experiments/mind_router_spike/measure_independent_clarification_cut_b_entry_path_r274.py"
)


def _result() -> dict[str, object]:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_r274_prices_both_ordered_deterministic_effect_gates() -> None:
    report = _result()

    assert report["verdict"] == (
        "development_r270_can_exercise_raw_model_decision_after_two_effect_gates"
    )
    assert report["population"]["rows"] == 93
    assert report["recogniser_surface"]["catalogue_operations"] == 174
    assert report["observed"]["explicit_clarification"] == 0
    assert report["observed"]["explicit_effect"] == 14
    assert report["observed"]["model_decision_candidate_after_two_effect_gates"] == 79
    assert report["observed"]["model_decision_candidate_reach"] == 79 / 93
    assert report["interpretation"]["population_can_exercise_raw_model_decision"] is True
    assert report["interpretation"]["model_started"] is False


def test_r274_keeps_the_language_cut_without_request_text_or_identifiers() -> None:
    report = _result()

    assert report["observed"]["by_language"] == {
        "en": {
            "rows": 31,
            "explicit_clarification": 0,
            "explicit_effect": 5,
            "model_decision_candidate_after_two_effect_gates": 26,
        },
        "es": {
            "rows": 31,
            "explicit_clarification": 0,
            "explicit_effect": 4,
            "model_decision_candidate_after_two_effect_gates": 27,
        },
        "spanglish": {
            "rows": 31,
            "explicit_clarification": 0,
            "explicit_effect": 5,
            "model_decision_candidate_after_two_effect_gates": 26,
        },
    }
    assert report["population"]["request_texts_retained"] is False
    assert report["population"]["request_identifiers_retained"] is False
    assert "case_id" not in json.dumps(report, ensure_ascii=False)


def test_r274_result_matches_the_sealed_runner_and_zero_effect_constraints() -> None:
    report = _result()

    assert report["identities"]["runner_sha256"] == hashlib.sha256(
        RUNNER.read_bytes()
    ).hexdigest()
    assert report["constraints"]["model_started"] is False
    assert report["constraints"]["providers_enabled"] is False
    assert report["constraints"]["effects_executed"] == 0
