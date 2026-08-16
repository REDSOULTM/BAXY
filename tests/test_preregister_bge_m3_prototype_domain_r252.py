from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_bge_m3_prototype_domain_r252.py"


def test_r252_seals_exemplar_retrieval_and_separate_oos_boundary() -> None:
    spec = importlib.util.spec_from_file_location("r252", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert "separate class-balanced learned binary domain boundary" in report["hypothesis"]["architecture"]
    assert report["development_evaluation"]["outside"] == "CLINC oos_val 100"
    assert report["constraints"]["r228_opened"] is False
