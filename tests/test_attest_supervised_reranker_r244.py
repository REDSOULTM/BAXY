from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_supervised_reranker_r244.py"


def test_r244_rejects_nonfinite_r243_without_opening_r228() -> None:
    spec = importlib.util.spec_from_file_location("r244", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["verdict"] == "rejected_invalid_nonfinite_training"
    assert "$.training.mean_loss" in report["nonfinite_fields"]
    assert report["constraints"]["r228_opened"] is False
