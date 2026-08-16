from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_wav2vec2_hidden_wake_expanded_development_v1.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location(
    "audit_wav2vec2_hidden_wake_expanded_development_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_canonical_group_merges_known_same_speaker() -> None:
    record = {"source_id": "Axgc6aHutvw", "speaker_group": "different_name"}
    assert MODULE.canonical_group(record) == "jesus_marcos"


def test_held_out_scores_support_multiple_negative_windows() -> None:
    queries = [
        np.asarray([[1.0, 0.0]]),
        np.asarray([[0.9, 0.1]]),
        np.asarray([[0.0, 1.0], [0.1, 0.9]]),
        np.asarray([[0.2, 0.8], [0.0, 1.0]]),
    ]
    labels = np.asarray([1, 1, 0, 0])
    scores = MODULE.held_out_scores(queries, labels, ["p1", "p2", "n1", "n2"])
    assert scores.shape == (4,)
    assert np.all(np.isfinite(scores))


def test_category_metrics_keeps_negative_types_separate() -> None:
    records = [
        {"label": "positive"},
        {"label": "hard_negative"},
        {"label": "matched_negative"},
    ]
    metrics = MODULE.category_metrics(np.asarray([1.0, -1.0, 0.5]), records, 0.0)
    assert metrics["positive"]["accepted"] == 1
    assert metrics["hard_negative"]["accepted"] == 0
    assert metrics["matched_negative"]["accepted"] == 1
