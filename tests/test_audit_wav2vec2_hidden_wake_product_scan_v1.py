from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_wav2vec2_hidden_wake_product_scan_v1.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location(
    "audit_wav2vec2_hidden_wake_product_scan_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_target_sample_in_capture_accounts_for_leading_preroll() -> None:
    sample = MODULE.target_sample_in_capture(
        target_onset_seconds=1.0,
        hit_end_seconds=0.88,
        pre_roll_samples=79_872,
    )
    assert sample == 81_792


def test_sliding_vectors_cover_hidden_sequence() -> None:
    hidden = np.arange(12, dtype=np.float32).reshape(6, 2)
    vectors, starts = MODULE.sliding_vectors(
        hidden, duration_seconds=0.05, pooling="mean"
    )
    assert vectors.shape[1] == 2
    assert len(vectors) == len(starts)
    assert starts[0] > 0.0


def test_held_out_product_scores_scan_all_views() -> None:
    aligned = np.asarray(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]],
        dtype=np.float64,
    )
    views = [
        [(0, np.asarray([row, row]), np.asarray([0.0, 0.1]))]
        for row in aligned
    ]
    labels = np.asarray([1, 1, 0, 0])
    scores, locations = MODULE.held_out_product_scores(
        aligned, views, labels, ["p1", "p2", "n1", "n2"]
    )
    assert scores.shape == (4,)
    assert all("view_start_sample" in item for item in locations)
