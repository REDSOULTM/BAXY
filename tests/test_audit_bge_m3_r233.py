from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_bge_m3_r233.py"


def _module():
    spec = importlib.util.spec_from_file_location("r233", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r233_rejects_fixed_top_k_without_opening_the_model() -> None:
    report = _module().build()
    assert report["deduction"]["contradiction"] is True
    assert report["deduction"]["candidates_per_query"] == 8
    assert report["verdict"] == "rejected_before_model_import_or_r228_opening"
    assert report["constraints"]["model_started"] is False
    assert report["constraints"]["r228_opened"] is False


def test_r233_published_audit_matches_builder() -> None:
    module = _module()
    output = ROOT / "artifacts/audit/bge_m3_r233_structural_abstention_rejection.json"
    assert json.loads(output.read_text(encoding="utf-8")) == module.build()
