from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "voice_latency"))

from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    search_anchored_category_probabilities,
    search_category_probabilities,
    score_category_probabilities,
)
from phoneme_student_vocabulary_v2 import CATEGORY_NAMES  # noqa: E402


def _path_probabilities(categories: list[str]) -> np.ndarray:
    ids = {name: index for index, name in enumerate(CATEGORY_NAMES)}
    frame_categories = ["blank"]
    for category in categories:
        frame_categories.extend((category, "blank"))
    values = np.full((len(frame_categories), len(CATEGORY_NAMES)), 1e-5)
    for frame, category in enumerate(frame_categories):
        values[frame, ids[category]] = 1.0
    return values / values.sum(axis=1, keepdims=True)


def test_exact_baxy_path_is_located_and_scored() -> None:
    result = score_category_probabilities(
        _path_probabilities(["B", "AE", "K", "S", "IH"]),
        context_frames=0,
    )

    assert result["greedy_target_span_count"] == 1
    assert result["best_verifier"] is not None
    assert result["best_verifier"]["margin"] > 0


def test_boxing_prefix_is_not_a_permitted_target_path() -> None:
    result = score_category_probabilities(
        _path_probabilities(["B", "A", "K", "S", "IH", "other"]),
        context_frames=0,
    )

    assert result["greedy_target_span_count"] == 0
    assert result["best_verifier"] is None


def test_multiword_veto_removes_an_exact_acoustic_locator() -> None:
    result = score_category_probabilities(
        _path_probabilities(["B", "A", "K", "S", "I"]),
        veto_spans=((1, 10),),
        context_frames=0,
    )

    assert result["greedy_target_span_count"] == 1
    assert result["locators"][0]["multiword_non_target_veto"] is True
    assert result["best_verifier"] is None


def test_qbt_search_finds_target_without_an_exact_greedy_locator() -> None:
    values = _path_probabilities(["B", "A", "K", "S", "I"])
    ids = {name: index for index, name in enumerate(CATEGORY_NAMES)}
    values[1, ids["B"]] = 0.45
    values[1, ids["other"]] = 0.55
    values[1] /= values[1].sum()

    exact = score_category_probabilities(values, context_frames=0)
    searched = search_category_probabilities(values, span_frames=(len(values),))

    assert exact["best_verifier"] is None
    assert searched["best_verifier"]["margin"] > 0


def test_qbt_search_prefers_vaxi_confusable() -> None:
    searched = search_category_probabilities(
        _path_probabilities(["V", "A", "K", "S", "I"]),
        span_frames=(11,),
    )

    assert searched["best_verifier"]["margin"] < 0


def test_anchored_qbt_tolerates_an_internal_greedy_insertion() -> None:
    values = _path_probabilities(["B", "A", "other", "K", "S", "I"])
    exact = score_category_probabilities(values, context_frames=0)
    searched = search_anchored_category_probabilities(
        values, minimum_span_frames=8, maximum_span_frames=20, context_frames=0
    )

    assert exact["best_verifier"] is None
    assert searched["best_verifier"]["margin"] > 0


def test_anchored_qbt_does_not_invent_a_b_anchor_for_vaxi() -> None:
    searched = search_anchored_category_probabilities(
        _path_probabilities(["V", "A", "K", "S", "I"]),
        minimum_span_frames=8,
        maximum_span_frames=20,
        context_frames=0,
    )

    assert searched["best_verifier"] is None
