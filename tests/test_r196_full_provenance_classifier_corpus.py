from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "mind_router_spike" / "build_r196_full_provenance_classifier_corpus.py"


def test_r196_preserves_complete_training_population_without_evaluation_overlap(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("r196", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build(tmp_path / "r196.jsonl", tmp_path / "r196.audit.json")
    assert report["counts"] == {"rows": 4740, "labels": 170, "catalog_operation_labels": 169, "learned_abstention_rows": 41, "evaluation_exact_text_overlap": 0, "human_semantic_audit_claimed": 0}
