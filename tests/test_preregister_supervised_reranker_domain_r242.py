from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_supervised_reranker_domain_r242.py"


def test_r242_seals_supervised_domain_probe_without_r228() -> None:
    spec = importlib.util.spec_from_file_location("r242", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["hypothesis"]["architecture"] == "supervised query-to-typed-family-document cross-encoder"
    assert report["training"]["no_r228"] is True
    assert report["constraints"]["opened_v9"] is False
    assert len(report["identities"]["runner_sha256"]) == 64
