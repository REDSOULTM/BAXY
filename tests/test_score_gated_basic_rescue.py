from __future__ import annotations

import math

import pytest

from experiments.wake_validation.evaluate_score_gated_basic_rescue_v1 import (
    score_gated_basic_match,
)


@pytest.mark.parametrize(
    ("text", "score", "expected"),
    [
        ("Basic", 4.0, True),
        ("basic lower the screen brightness", 4.1, True),
        ("Basic word and longer mañana", 4.8, True),
        ("this is basic", 6.0, False),
        ("Baxy open settings", 6.0, False),
        ("basic", 3.999, False),
        ("basic", None, False),
        ("basic", math.inf, False),
        ("basic", math.nan, False),
    ],
)
def test_score_gated_basic_match_is_leading_and_bounded_by_frozen_score(
    text: str,
    score: float | None,
    expected: bool,
) -> None:
    assert (
        score_gated_basic_match(
            (text,),
            verifier_score=score,
            score_gte=4.0,
        )
        is expected
    )


def test_score_gated_basic_match_checks_all_speed_views() -> None:
    assert score_gated_basic_match(
        ("", "Basic take a screenshot"),
        verifier_score=4.0,
        score_gte=4.0,
    )


def test_score_gated_basic_match_rejects_an_invalid_gate() -> None:
    assert not score_gated_basic_match(
        ("basic",),
        verifier_score=5.0,
        score_gte=math.inf,
    )
