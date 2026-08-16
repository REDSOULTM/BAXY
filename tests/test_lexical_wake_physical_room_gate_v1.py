from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "run_lexical_wake_physical_room_gate_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_lexical_wake_gate", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_exact_and_protocol_policies_are_reported_separately() -> None:
    gate = _module()

    assert gate.match_policies("Baxy abre Spotify") == {
        "exactBaxy": True,
        "baxyBaxiProtocol": True,
    }
    assert gate.match_policies("Baxi abre Spotify") == {
        "exactBaxy": False,
        "baxyBaxiProtocol": True,
    }


def test_lexical_policy_rejects_non_prefix_and_confusable_words() -> None:
    gate = _module()

    assert gate.match_policies("abre Baxy en el navegador") == {
        "exactBaxy": False,
        "baxyBaxiProtocol": False,
    }
    assert gate.match_policies("Taxi, abre Spotify") == {
        "exactBaxy": False,
        "baxyBaxiProtocol": False,
    }
