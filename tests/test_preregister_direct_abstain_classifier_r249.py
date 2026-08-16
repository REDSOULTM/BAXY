from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_direct_abstain_classifier_r249.py"


def test_r249_uses_the_available_fresh_oos_rows_with_weighted_loss() -> None:
    spec = importlib.util.spec_from_file_location("r249", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["training"]["inverse_frequency_class_weighted_loss"] is True
    assert report["development_evaluation"]["acceptance"]["inside_family_mismatches"] == 0
    assert report["constraints"]["r228_opened"] is False
