from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/measure_independent_cut_b_r214.py"


def test_r214_measures_recogniser_reach_without_starting_the_product() -> None:
    spec = importlib.util.spec_from_file_location("r214", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.measure()

    assert report["population"] == {
        "rows": 93,
        "families": 31,
        "languages": {"en": 31, "es": 31, "spanglish": 31},
    }
    assert report["recogniser"]["overall"]["rows"] == 93
    assert report["recogniser"]["overall"]["rows"] == sum(
        report["recogniser"]["overall"][key]
        for key in ("expected", "other", "unresolved")
    )
    assert report["execution"] == {
        "product_started": False,
        "decider_invoked": False,
        "providers_enabled": False,
        "effects_executed": 0,
        "opened_v9": False,
        "voice_stt_wake_exercised": False,
    }


def test_r214_published_opening_matches_the_frozen_instrument() -> None:
    spec = importlib.util.spec_from_file_location("r214_artifact", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    artifact = (
        ROOT / "artifacts/audit/independent_cut_b_r213_recogniser_reach_r214.json"
    )
    assert json.loads(artifact.read_text(encoding="utf-8")) == module.measure()
