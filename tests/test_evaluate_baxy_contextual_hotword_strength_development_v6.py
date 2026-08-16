from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_contextual_hotword_strength_development_v6.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_contextual_hotword_strength_development_v6", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_retain_complete_recall_orders_numeric_scores() -> None:
    summaries = {
        "5.0": {"positiveHits": 4, "positiveTotal": 4, "falseHits": 0},
        "2.0": {"positiveHits": 3, "positiveTotal": 4, "falseHits": 0},
        "3.0": {"positiveHits": 4, "positiveTotal": 4, "falseHits": 0},
        "1.0": {"positiveHits": 4, "positiveTotal": 4, "falseHits": 1},
    }
    assert sorted(MODULE.retain_complete_recall(summaries)) == [3.0, 5.0]


def test_retain_complete_recall_rejects_incomplete_total() -> None:
    summaries = {
        "4.0": {"positiveHits": 4, "positiveTotal": 5, "falseHits": 0}
    }
    assert MODULE.retain_complete_recall(summaries) == []
