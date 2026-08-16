from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifacts/audit/independent_clarification_cut_b_recogniser_r272.json"
RUNNER = (
    ROOT
    / "experiments/mind_router_spike/run_independent_clarification_cut_b_recogniser_r272.py"
)


def _result() -> dict[str, object]:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_r272_records_the_single_read_only_r270_recogniser_measurement() -> None:
    report = _result()

    assert report["verdict"] == (
        "development_independent_clarification_recogniser_effect_reach_below_limit"
    )
    assert report["population"]["rows"] == 93
    assert report["recogniser_surface"]["catalogue_operations"] == 174
    assert report["observed"]["resolved_any"] == 14
    assert report["observed"]["resolved_intended"] == 10
    assert report["observed"]["resolved_other"] == 4
    assert report["observed"]["unresolved"] == 79
    assert report["observed"]["recogniser_effect_reach"] == 14 / 93
    assert report["interpretation"]["population_can_exercise_model_path"] is True
    assert report["interpretation"]["model_path_measured"] is False


def test_r272_reports_the_language_cut_without_request_text_or_identifiers() -> None:
    report = _result()

    assert report["observed"]["by_language"] == {
        "en": {
            "rows": 31,
            "resolved_any": 5,
            "resolved_intended": 4,
            "resolved_other": 1,
            "unresolved": 26,
        },
        "es": {
            "rows": 31,
            "resolved_any": 4,
            "resolved_intended": 2,
            "resolved_other": 2,
            "unresolved": 27,
        },
        "spanglish": {
            "rows": 31,
            "resolved_any": 5,
            "resolved_intended": 4,
            "resolved_other": 1,
            "unresolved": 26,
        },
    }
    assert report["population"]["request_texts_retained"] is False
    assert report["population"]["request_identifiers_retained"] is False
    assert "case_id" not in json.dumps(report, ensure_ascii=False)


def test_r272_result_matches_the_runner_and_records_zero_effect_execution() -> None:
    report = _result()

    assert report["identities"]["runner_sha256"] == hashlib.sha256(
        RUNNER.read_bytes()
    ).hexdigest()
    assert report["constraints"]["model_started"] is False
    assert report["constraints"]["providers_enabled"] is False
    assert report["constraints"]["effects_executed"] == 0
