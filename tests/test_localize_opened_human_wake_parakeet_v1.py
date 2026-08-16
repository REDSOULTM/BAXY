from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "localize_opened_human_wake_parakeet_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_opened_localizer", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_locates_split_baxy_token_span() -> None:
    gate = _module()

    spans = gate.locate_alias_spans(
        [" viene", " de", " ", "ba", "x", "y", "."],
        [0.0, 0.2, 0.4, 0.48, 0.56, 0.64, 0.72],
        [0.1] * 7,
    )

    assert spans == [(0.48, 0.74, "baxy")]


def test_rejects_mismatched_token_timings() -> None:
    gate = _module()

    try:
        gate.locate_alias_spans([" baxy"], [0.1], [])
    except ValueError as error:
        assert str(error) == "opened_wake_localizer_token_timing_mismatch"
    else:
        raise AssertionError("mismatched token timing must fail closed")
