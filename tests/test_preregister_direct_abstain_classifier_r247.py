from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_direct_abstain_classifier_r247.py"


def test_r247_seals_an_explicit_abstain_class_and_fresh_split() -> None:
    spec = importlib.util.spec_from_file_location("r247", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert "explicit abstain class" in report["hypothesis"]["architecture"]
    assert report["development_evaluation"]["inside"] == 256
    assert report["development_evaluation"]["acceptance"]["outside_zero_candidates"] == 256
    assert report["constraints"]["r228_opened"] is False
    assert report["constraints"]["opened_v9"] is False
