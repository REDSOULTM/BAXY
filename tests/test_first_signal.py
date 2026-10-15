"""Goal 08: which turns announce an early first signal (the rest of the first-signal prose is formulated by
the model; the retired in-progress formulator and milestone cadence went in the 2026-10-06 code audit)."""

from __future__ import annotations

from baxy_mind.first_signal import (
    PATH_CLOSED_CONVERSATION,
    PATH_MODEL,
    PATH_RECOGNIZER,
    should_emit_early,
)


def test_predicted_fast_recognizer_emits_no_early_signal() -> None:
    assert should_emit_early(PATH_RECOGNIZER) is False
    assert should_emit_early(PATH_CLOSED_CONVERSATION) is False


def test_predicted_slow_model_path_emits_early_signal() -> None:
    assert should_emit_early(PATH_MODEL) is True
    assert should_emit_early(PATH_RECOGNIZER, step_count=3) is True
