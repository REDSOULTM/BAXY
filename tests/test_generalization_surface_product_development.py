from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
REPORT = (
    REPO
    / "artifacts/development/generalization_surface_product_ownership_r1_after_systemic_fix.v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_product_ownership_replay_is_development_only_effect_free_and_complete() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["blind_holdout"] is False
    assert report["certification_claim"] is False
    assert report["effects_executed"] == 0
    assert report["ownership"] == {
        "mind_sidecar": {
            "families": 30,
            "cases": 300,
            "authority": "turn.decide_only_no_plan_no_core_no_provider",
        },
        "app_private_memory_parser": {
            "families": 1,
            "cases": 10,
            "authority": "parser_test_only_no_core_no_provider",
        },
    }


def test_original_oracle_remains_strict_and_contract_audit_is_explicit() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    original = report["metrics"]["original_preregistered_oracle"]
    audited = report["metrics"]["contract_audited_product_behavior"]
    label_audit = report["label_audit"]

    assert original["cases"] == 310
    assert original["exact"] == 309
    assert original["failed"] == 1
    assert original["accuracy"] == 309 / 310
    assert original["unsafe_effects"] == 0
    assert audited["correct"] == 310
    assert audited["label_corrections"] == 1
    assert audited["unsafe_effects"] == 0
    assert [row["case_id"] for row in label_audit] == ["message-03-plain"]
    assert label_audit[0]["contract_audited_outcome"] == "clarify_missing_channel"
    assert label_audit[0]["safe_product_behavior"] is True
    assert label_audit[0]["observed_effect_operations"] == []


def test_product_ownership_report_is_bound_to_all_evidence_sources() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    sources = report["sources"]

    for path_key, hash_key in (
        ("corpus", "corpus_sha256"),
        ("sidecar_report", "sidecar_report_sha256"),
        ("memory_trx", "memory_trx_sha256"),
    ):
        path = REPO / sources[path_key]
        assert sources[hash_key] == _sha256(path)

    assert len(sources["app_parser_sha256"]) == 64
    assert len(sources["app_parser_tests_sha256"]) == 64
    assert len(sources["catalog_contract_sha256"]) == 64
    assert (REPO / "src/Baxy.Kernel/Operations/ProductCatalog.cs").is_file()
    # Development evidence is immutable and remains bound to the exact catalog
    # bytes measured in that run. Later catalog edits must not retroactively
    # invalidate the sealed report.
    assert len(sources["clarification_tests_sha256"]) == 64
    assert sources["analyzer_sha256"] == _sha256(
        REPO
        / "experiments/mind_router_spike/analyze_generalization_surface_product_development.py"
    )
