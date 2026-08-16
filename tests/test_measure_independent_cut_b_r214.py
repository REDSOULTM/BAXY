from __future__ import annotations

import importlib.util
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/measure_independent_cut_b_r214.py"
OPENING_SEAL = "fec6591441f2d3e3a3713fab4d838790d2b1c42c8eea361b26e72909b6641cbb"


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
    # The instrument still runs — that is the test above. The published opening
    # also records the catalogue it measured, and the live catalogue has moved
    # since, so the artifact is audited by its seal (§7).
    artifact = (
        ROOT / "artifacts/audit/independent_cut_b_r213_recogniser_reach_r214.json"
    )
    assert_sealed(artifact, OPENING_SEAL)
