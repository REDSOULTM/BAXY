from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "select_mswc_spanish_qbye_metric_candidate_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "select_mswc_spanish_qbye_metric_candidate_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_tuning_rank_prioritizes_top1_then_auc_then_eer() -> None:
    report = {
        "selected": {
            "open_keyword_tuning": {
                "top1_accuracy": 0.91,
                "pair_auc": 0.995,
                "equal_error_rate": 0.04,
            }
        }
    }
    assert MODULE.tuning_rank(report) == (0.91, 0.995, -0.04)
