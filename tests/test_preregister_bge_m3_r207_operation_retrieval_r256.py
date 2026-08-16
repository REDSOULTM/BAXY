from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_bge_m3_r207_operation_retrieval_r256.py"


def test_r256_seals_operation_retrieval_without_an_oos_gate() -> None:
    spec = importlib.util.spec_from_file_location("r256", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["selection"]["overlap_rule"].startswith("no normalized query")
    assert report["development_evaluation"]["inside"] == 256
    assert report["constraints"]["r228_opened"] is False
    assert report["constraints"]["clinc_opened"] is False
