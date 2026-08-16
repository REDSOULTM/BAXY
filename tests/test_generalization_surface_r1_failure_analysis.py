from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl"
BLIND_RESULT = REPO / "artifacts/holdout/generalization_surface_holdout_r1.json"
DEVELOPMENT = (
    REPO / "artifacts/development/generalization_surface_r1_failures.v1.jsonl"
)
ANALYSIS = (
    REPO
    / "artifacts/holdout/generalization_surface_holdout_r1_failure_analysis.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_r1_failures_are_opened_as_development_without_rewriting_blind_rows() -> None:
    corpus = {str(row["case_id"]): row for row in _jsonl(CORPUS)}
    result = json.loads(BLIND_RESULT.read_text(encoding="utf-8"))
    expected_ids = {
        str(row["case_id"])
        for row in result["rows"]
        if not row["exact_turn_correct"]
    }
    promoted = _jsonl(DEVELOPMENT)

    assert len(promoted) == result["metrics"]["failed"] == 120
    assert {str(row["case_id"]) for row in promoted} == expected_ids
    assert all(row["development_only"] is True for row in promoted)
    assert all("blind_generalization_surface_cut_b_r1_opened" == row["source_cut"] for row in promoted)
    assert all(row["text"] == corpus[str(row["case_id"])]["text"] for row in promoted)
    assert sum(bool(row["unsafe_effect"]) for row in promoted) == 20


def test_r1_failure_analysis_is_hash_bound_and_effect_free() -> None:
    report = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    source = report["source"]
    output = report["development_output"]

    assert report["effects_executed"] == 0
    assert report["authority"] == "offline_analysis_only_no_sidecar_no_plan_no_core_no_provider"
    assert source["corpus_sha256"] == _sha256(CORPUS)
    assert source["blind_result_sha256"] == _sha256(BLIND_RESULT)
    assert source["raw_audit_sha256"] == _sha256(
        REPO / source["raw_audit"]
    )
    assert source["analyzer_sha256"] == _sha256(REPO / source["analyzer"])
    assert output["sha256"] == _sha256(DEVELOPMENT)
    assert output["rows"] == report["metrics"]["failures"] == 120


def test_stage_aware_attribution_accounts_for_every_promoted_failure() -> None:
    report = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    causes = report["metrics"]["by_cause"]

    assert sum(causes.values()) == report["metrics"]["failures"]
    assert causes["retrieval"] == 55
    assert causes["decision"] == 13
    assert causes["recovery"] == 11
    assert causes["veto:domain_grounding"] == 23
    assert causes["veto:compound_conservation"] == 12
    assert causes["veto:action_grounding"] == 6
