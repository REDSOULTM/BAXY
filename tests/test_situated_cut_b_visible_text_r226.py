from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "experiments/mind_router_spike/audit_situated_cut_b_visible_text_r226.py"
)
ARTIFACT = (
    ROOT / "artifacts/audit/situated_cut_b_r215_model_path_r225.visible-text-r226.json"
)


def _module():
    spec = importlib.util.spec_from_file_location("r226", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r226_retains_the_manual_visible_text_findings() -> None:
    report = _module().build()
    assert report["review"]["visible_rows_read"] == 86
    assert report["review"]["unverified_machine_state_claim_count"] == 2
    assert report["conclusion"]["candidate_verdict"] == "rejected"


def test_r226_published_audit_matches_builder() -> None:
    assert json.loads(ARTIFACT.read_text(encoding="utf-8")) == _module().build()
