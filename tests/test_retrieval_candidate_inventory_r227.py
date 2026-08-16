from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "experiments/mind_router_spike/audit_retrieval_candidate_inventory_r227.py"
)
ARTIFACT = ROOT / "artifacts/audit/retrieval_candidate_inventory_r227.json"


def _module():
    spec = importlib.util.spec_from_file_location("r227", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r227_rejects_direct_adoption_from_old_development_evidence() -> None:
    report = _module().build()
    evidence = report["existing_qwen_development_evidence"]
    assert evidence["loo_accuracy"] == 0.883
    assert evidence["loo_dangerous_failures"] == 28
    assert (
        report["verdict"]["qwen_embedding_direct_retriever"]
        == "rejected_for_adoption_without_new_evidence"
    )
    assert report["constraints"]["model_started"] is False


def test_r227_published_inventory_matches_builder() -> None:
    assert json.loads(ARTIFACT.read_text(encoding="utf-8")) == _module().build()
