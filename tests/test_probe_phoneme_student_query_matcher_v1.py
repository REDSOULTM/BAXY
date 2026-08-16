from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "voice_latency"))

from phoneme_student_vocabulary_v2 import CATEGORY_NAMES  # noqa: E402
from probe_phoneme_student_query_matcher_v1 import (  # noqa: E402
    aggregate_human_clip_scores,
    monotonic_sequence_score,
    query_features,
)


def test_monotonic_sequence_score_rewards_ordered_phonemes() -> None:
    sequence = tuple(CATEGORY_NAMES.index(name) for name in ("B", "A", "K"))
    ordered = np.full((1, 6, len(CATEGORY_NAMES)), -10.0, dtype=np.float32)
    reversed_values = ordered.copy()
    for frame, token in zip((1, 3, 5), sequence, strict=True):
        ordered[0, frame, token] = 0.0
    for frame, token in zip((1, 3, 5), reversed(sequence), strict=True):
        reversed_values[0, frame, token] = 0.0

    ordered_score = monotonic_sequence_score(ordered, sequence)[0]
    reversed_score = monotonic_sequence_score(reversed_values, sequence)[0]

    assert ordered_score == pytest.approx(0.0)
    assert ordered_score > reversed_score


def test_query_features_have_stable_finite_contract() -> None:
    values = np.full(
        (2, 12, len(CATEGORY_NAMES)),
        1.0 / len(CATEGORY_NAMES),
        dtype=np.float32,
    )

    features, names = query_features(values)

    assert features.shape == (2, 117)
    assert len(names) == features.shape[1]
    assert np.isfinite(features).all()


def test_human_scores_aggregate_target_windows_per_clip() -> None:
    records = []
    scores = []
    for index in range(14):
        path = f"positive_{index}.wav"
        records.extend(
            (
                {"relative_path": path, "clip_label": "positive", "label": 0},
                {"relative_path": path, "clip_label": "positive", "label": 1},
            )
        )
        scores.extend((0.99, 0.75))
    for index in range(4):
        records.append(
            {
                "relative_path": f"negative_{index}.wav",
                "clip_label": "hard_negative",
                "label": 0,
            }
        )
        scores.append(0.25)

    positive, negative, clips = aggregate_human_clip_scores(
        np.asarray(scores), records
    )

    assert positive.tolist() == pytest.approx([0.75] * 14)
    assert negative.tolist() == pytest.approx([0.25] * 4)
    assert len(clips) == 18
