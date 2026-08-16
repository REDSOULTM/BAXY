from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_bge_reranker_r240.py"


def test_r240_freezes_r241_before_model_import() -> None:
    spec = importlib.util.spec_from_file_location("r240", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["candidate"]["device"] == "cuda_gpu_development_probe"
    assert report["development_population"]["r228_used"] is False
    assert report["constraints"]["opened_v9"] is False
    assert len(report["identities"]["runner_sha256"]) == 64
