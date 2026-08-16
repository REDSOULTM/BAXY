from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_wake_verifier_product_capture_development_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_wake_verifier_product_capture_development_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_summary_requires_every_positive_and_zero_negative_false() -> None:
    records = [
        {"label": "positive", "detected": True},
        {"label": "positive", "detected": True},
        {"label": "hard_negative", "detected": False},
    ]
    assert MODULE.summarize(records) == {
        "positive_accepted": 2,
        "positive_total": 2,
        "hard_negative_false_accepts": 0,
        "hard_negative_total": 1,
        "gate_passed": True,
    }
