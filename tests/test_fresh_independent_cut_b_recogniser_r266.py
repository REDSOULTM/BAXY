from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifacts/audit/fresh_independent_cut_b_recogniser_r266.json"
RUNNER = ROOT / "experiments/mind_router_spike/run_fresh_independent_cut_b_recogniser_r266.py"


def test_r266_records_the_single_rejected_majority_recogniser_measurement() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))

    assert report["verdict"] == (
        "rejected_independent_cut_b_recogniser_reach_majority_or_higher"
    )
    assert report["predecessor"]["r265_output_created"] is False
    assert report["population"]["rows"] == 114
    assert report["observed"]["resolved_expected"] == 66
    assert report["observed"]["resolved_other"] == 2
    assert report["observed"]["unresolved"] == 46
    assert report["observed"]["recogniser_reach"] == 66 / 114
    assert report["interpretation"]["population_can_exercise_model_path"] is False
    assert report["recogniser_surface"]["alias_catalogue_operations"] == 158
    assert report["recogniser_surface"]["expected_rows_with_no_alias_for_at_least_one_operation"] == 21
    assert report["constraints"]["model_started"] is False
    assert report["constraints"]["r228_opened"] is False


def test_r266_result_matches_the_runner_that_the_preregistration_sealed() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))

    assert report["identities"]["runner_sha256"] == hashlib.sha256(
        RUNNER.read_bytes()
    ).hexdigest()
