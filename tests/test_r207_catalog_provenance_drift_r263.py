from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_r207_catalog_provenance_drift_r263.py"
RESULT = ROOT / "artifacts/audit/r207_catalog_provenance_drift_r263.json"


def test_r263_narrows_r257_to_its_prior_catalogue_and_unreviewed_source() -> None:
    spec = importlib.util.spec_from_file_location("r263", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["verdict"] == (
        "development_evidence_scope_narrowed_stale_catalog_and_unreviewed_r207_provenance"
    )
    assert report["source"]["r196_training_rows"] == 4740
    assert report["source"]["r207_pair_rows"] == 23700
    assert report["source"]["qwen_generated_r196_rows"] == 4179
    assert report["source"]["r196_human_semantic_audit_rows"] == 0
    assert report["catalogue_delta"][
        "current_operations_missing_from_r196_and_r207_positives"
    ] == [
        "office.word.append",
        "office.word.close",
        "office.word.discard",
        "office.word.save",
        "office.word.start",
        "office.word.status",
    ]
    assert report["interpretation"]["r257_numerical_result_changed"] is False
    assert report["interpretation"]["admitted_baxy_operations"] == []
    assert report["constraints"]["r228_opened"] is False


def test_r263_result_does_not_promote_the_stale_r207_source() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert report["source"]["current_catalogue_operations"] == 174
    assert report["source"]["r207_human_semantic_audit_pairs"] == 0
    assert report["interpretation"]["r257_full_current_catalogue_coverage_claim_supported"] is False
    assert report["constraints"]["model_started"] is False
