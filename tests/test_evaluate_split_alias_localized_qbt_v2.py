from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "wake_validation"))

from evaluate_split_alias_localized_qbt_v2 import (  # noqa: E402
    DECISION_MARGIN,
    leading_word_locator_seconds,
    locator_frames,
    qbt_accepts,
    summarize,
)


def _record(audio: str, label: str, accepted: bool) -> dict[str, object]:
    return {
        "corpus": "endpoint_confusable",
        "label": label,
        "audioSha256": audio,
        "guardAccepted": accepted,
    }


def test_leading_two_word_locator_covers_all_subword_tokens() -> None:
    start, end = leading_word_locator_seconds(
        [" V", "as", " y", " mu", "ést"],
        [0.08, 0.32, 0.56, 0.72, 0.88],
        [0.24, 0.24, 0.16, 0.16, 0.16],
        speed_factor=1.0,
    )

    assert start == pytest.approx(0.08)
    assert end == pytest.approx(0.72)


def test_speed_factor_maps_retry_timestamps_back_to_original_audio() -> None:
    start, end = leading_word_locator_seconds(
        [" V", "as", " y", " next"],
        [0.16, 0.40, 0.56, 0.88],
        [0.24, 0.16, 0.16, 0.16],
        speed_factor=0.85,
    )

    assert start == pytest.approx(0.136)
    assert end == pytest.approx(0.612)


def test_locator_frames_rounds_outward() -> None:
    assert locator_frames(0.081, 0.719) == (4, 36)


def test_qbt_uses_the_published_half_point_margin() -> None:
    assert qbt_accepts(DECISION_MARGIN)
    assert not qbt_accepts(DECISION_MARGIN - 1e-6)
    assert not qbt_accepts(None)


def test_gate_requires_all_positives_and_zero_negatives() -> None:
    metrics = summarize(
        [_record("p", "positive", True), _record("n", "negative", False)],
        current_confusable_positive_hashes=frozenset({"p"}),
        current_confusable_negative_hashes=frozenset({"n"}),
    )

    assert metrics["developmentGatePassed"] is True
