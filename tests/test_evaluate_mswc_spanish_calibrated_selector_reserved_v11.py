from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_calibrated_selector_reserved_v11.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_calibrated_selector_reserved_v11", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_candidates_uses_highest_probability_per_query() -> None:
    selected = MODULE.select_candidates(
        probabilities=np.asarray([0.2, 0.8, 0.7, 0.1]),
        query_ids=np.asarray([0, 0, 1, 1]),
        candidate_ids=np.asarray([4, 2, 3, 1]),
    )
    assert selected.tolist() == [2, 3]


def test_build_selector_dataset_matches_locked_feature_width() -> None:
    width = 41
    class_names = np.asarray([f"palabra-{index}" for index in range(width)])
    candidate_indexes = np.tile(np.arange(width), (2, 1))
    candidate_words = class_names[candidate_indexes]
    query_words = candidate_words[:, 0].copy()
    increasing = np.tile(np.linspace(-1.0, 1.0, width), (2, 1))
    decreasing = -increasing
    candidate_mask = np.zeros((2, width), dtype=bool)
    candidate_mask[:, :5] = True
    bundle = {
        "hyper_scores": increasing,
        "ctc_scores": decreasing,
        "candidate_indexes": candidate_indexes,
        "class_names": class_names,
        "candidate_words": candidate_words,
        "query_hashes": np.asarray(["a", "b"]),
        "query_words": query_words,
        "whisper_whole": increasing * 0.5,
        "whisper_token": decreasing * 0.5,
        "exact_candidate_match": np.zeros((2, width)),
        "forced_scores": increasing * 0.25,
        "candidate_mask": candidate_mask,
        "silence_prior": np.linspace(-20.0, -10.0, width),
    }

    dataset = MODULE.build_selector_dataset(bundle)

    assert dataset["features"].ndim == 2
    assert dataset["features"].shape[1] == 53
    assert len(dataset["query_ids"]) == len(dataset["candidate_ids"])
    assert np.isfinite(dataset["features"]).all()
