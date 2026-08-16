from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_hyperspotter_human_development_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_hyperspotter_human_development_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_score_metrics_preserve_fixed_and_group_disjoint_decisions() -> None:
    labels = np.asarray([1, 0, 1, 0, 1, 0])
    scores = np.asarray([0.9, 0.1, 0.8, 0.2, 0.7, 0.3])
    groups = np.asarray(["a", "a", "b", "b", "c", "c"])
    metrics = MODULE.score_metrics(
        labels=labels, scores=scores, groups=groups, fixed_threshold=0.5
    )
    assert metrics["auc"] == 1.0
    assert metrics["fixed_synthetic_threshold"]["positive_hits"] == 3
    assert metrics["fixed_synthetic_threshold"]["false_hits"] == 0
    assert metrics["human_global_zero_false_diagnostic"]["positive_hits"] == 3


def test_fusion_metrics_count_only_new_rescues() -> None:
    metrics = MODULE.fusion_metrics(
        labels=np.asarray([1, 1, 1, 0]),
        ctc_decisions=np.asarray([True, False, True, False]),
        hyper_decisions=np.asarray([True, True, False, False]),
    )
    assert metrics["fused_positive_hits"] == 3
    assert metrics["fused_false_hits"] == 0
    assert metrics["new_positive_rescues"] == 1
    assert metrics["positive_overlap"] == 1


def test_partition_fusion_metrics_are_aggregate_only() -> None:
    metrics = MODULE.partition_fusion_metrics(
        labels=np.asarray([1, 0, 1, 0]),
        ctc_decisions=np.asarray([True, False, False, False]),
        hyper_decisions=np.asarray([False, False, True, False]),
        partitions=np.asarray(["legacy", "legacy", "expanded", "expanded"]),
    )
    assert metrics["legacy"]["positive_records"] == 1
    assert metrics["legacy"]["ctc_positive_hits"] == 1
    assert metrics["expanded"]["hyper_positive_hits"] == 1
    assert metrics["expanded"]["fused_false_hits"] == 0
