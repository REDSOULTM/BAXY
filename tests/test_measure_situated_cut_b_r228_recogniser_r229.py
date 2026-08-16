from __future__ import annotations

import importlib.util
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "experiments/mind_router_spike/measure_situated_cut_b_r228_recogniser_r229.py"
)
OPENING_SEAL = "2b8917700bb444f9d13077d64f9f1d6ada97165a93c4f4ac2d5bba09b569e817"


def _module():
    spec = importlib.util.spec_from_file_location("r229", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r229_measures_r228_without_product_or_model_execution() -> None:
    report = _module().measure()
    assert report["population"] == {
        "rows": 93,
        "families": 31,
        "languages": {"en": 31, "es": 31, "spanglish": 31},
    }
    assert report["recogniser"]["overall"]["rows"] == 93
    assert report["execution"] == {
        "product_started": False,
        "model_started": False,
        "decider_invoked": False,
        "providers_enabled": False,
        "dispatch_invoked": False,
        "effects_executed": 0,
        "opened_v9": False,
        "voice_stt_wake_exercised": False,
    }


def test_r229_published_opening_matches_the_frozen_instrument() -> None:
    # The instrument still runs — that is the test above. The published opening
    # measured a catalogue that has since moved, so it is audited by its seal
    # (§7).
    artifact = ROOT / "artifacts/audit/situated_cut_b_r228_recogniser_reach_r229.json"
    assert_sealed(artifact, OPENING_SEAL)
