from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_wake_scaf_human_localization_oracle_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_wake_scaf_human_localization_oracle_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_oracle_query_kind_never_aligns_unannotated_negatives() -> None:
    assert MODULE.oracle_query_kind(
        {"label": "positive", "target_onset_seconds": 1.0}
    ) == "ground_truth_aligned_positive"
    assert MODULE.oracle_query_kind(
        {"label": "negative", "target_onset_seconds": 1.0}
    ) == "ground_truth_aligned_hard_negative"
    assert MODULE.oracle_query_kind(
        {"label": "negative", "target_onset_seconds": None}
    ) == "all_sliding_windows_matched_negative"
