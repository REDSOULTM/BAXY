from __future__ import annotations

import importlib.util
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/measure_situated_cut_b_r216.py"
OPENING_SEAL = "e3ce3a246bcfc5f4f624b9bfad4716e6c050ba829d9bc6287d2360463f3acd0b"


def test_r216_measures_r215_without_product_execution() -> None:
    spec = importlib.util.spec_from_file_location("r216", SOURCE)
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
    assert report["execution"] == {
        "product_started": False,
        "decider_invoked": False,
        "providers_enabled": False,
        "effects_executed": 0,
        "opened_v9": False,
        "voice_stt_wake_exercised": False,
    }


def test_r216_published_opening_matches_the_frozen_instrument() -> None:
    # The instrument still runs — that is the test above. The published opening
    # measured a catalogue that has since moved, so it is audited by its seal
    # (§7).
    artifact = ROOT / "artifacts/audit/situated_cut_b_r215_recogniser_reach_r216.json"
    assert_sealed(artifact, OPENING_SEAL)
