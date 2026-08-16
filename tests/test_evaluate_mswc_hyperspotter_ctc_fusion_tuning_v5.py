from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_hyperspotter_ctc_fusion_tuning_v5.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_hyperspotter_ctc_fusion_tuning_v5", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_global_standardize_has_zero_mean_and_unit_deviation() -> None:
    standardized = MODULE.global_standardize(
        np.asarray([[1.0, 2.0], [4.0, 8.0]], dtype=np.float64)
    )
    assert abs(float(standardized.mean())) < 1e-12
    assert abs(float(standardized.std()) - 1.0) < 1e-12


def test_row_rank_scores_preserve_candidate_order() -> None:
    ranked = MODULE.row_rank_scores(
        np.asarray([[3.0, 1.0, 2.0], [-1.0, 5.0, 0.0]], dtype=np.float64)
    )
    assert ranked.tolist() == [[1.0, 0.0, 0.5], [0.0, 1.0, 0.5]]


def test_write_score_cache_preserves_alignment(tmp_path: Path) -> None:
    path = tmp_path / "scores.npz"
    MODULE.write_score_cache(
        path=path,
        hyper_scores=np.asarray([[3.0, 1.0], [2.0, 4.0]]),
        ctc_scores=np.asarray([[0.5, 0.1], [0.2, 0.8]]),
        candidates=np.asarray([[0, 1], [1, 0]]),
        query_audio_sha256=["a" * 64, "b" * 64],
        query_words=["casa", "mundo"],
        class_names=["casa", "mundo"],
    )
    with np.load(path) as cache:
        assert cache["schema"].tolist() == [
            "baxy.mswc-hyperspotter-ctc-score-cache.v1"
        ]
        assert cache["candidate_indexes"].tolist() == [[0, 1], [1, 0]]
