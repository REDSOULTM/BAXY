from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_head_only_reranker_domain_r245.py"


def test_r245_uses_fresh_split_and_finite_gate() -> None:
    spec = importlib.util.spec_from_file_location("r245", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["development_evaluation"]["finite_scores_required"] is True
    assert report["development_evaluation"]["inside"] == 256
    assert report["constraints"]["r228_opened"] is False
