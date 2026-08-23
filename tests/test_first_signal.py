"""Goal 08: estimate, formulate, cadence, and honesty correction on shipped units."""

from __future__ import annotations

from baxy_mind.first_signal import (
    KIND_MILESTONE,
    MILESTONE_DUE_SECONDS,
    PATH_CLOSED_CONVERSATION,
    PATH_MODEL,
    PATH_RECOGNIZER,
    SILENCE_BUDGET_SECONDS,
    formulate_progress,
    should_emit_early,
    should_emit_milestone,
    turn_signal_payload,
    visible_after_verification,
)
from baxy_mind.llm import compose_visible_defect, visible_reply_is_a_fixed_stall

_ACTING_FACTS = {
    "situation": '{"kind":"status","cause":"acting","polarity":"success"}'
}


def _acting_defect(text: str, user_text: str) -> str:
    return compose_visible_defect(text, "status", user_text, _ACTING_FACTS)


def test_predicted_fast_recognizer_emits_no_early_signal() -> None:
    assert should_emit_early(PATH_RECOGNIZER) is False
    assert should_emit_early(PATH_CLOSED_CONVERSATION) is False


def test_predicted_slow_model_path_emits_early_signal() -> None:
    assert should_emit_early(PATH_MODEL) is True
    assert should_emit_early(PATH_RECOGNIZER, step_count=3) is True


def test_formulated_progress_is_not_a_stall_and_varies_by_turn() -> None:
    spanish = "Explicame en dos frases que es la fotosintesis."
    english = "Tell me something odd about walnut trees."
    first = formulate_progress(spanish)
    second = formulate_progress(english)
    assert first != second
    assert not visible_reply_is_a_fixed_stall(first)
    assert not visible_reply_is_a_fixed_stall(second)
    assert _acting_defect(first, spanish) == ""
    assert _acting_defect(second, english) == ""
    assert "Listo" not in first
    assert "Listo" not in second


def test_early_signal_never_asserts_a_result() -> None:
    text = formulate_progress("Abre Spotify y pon la biblioteca.")
    defect = _acting_defect(text, "Abre Spotify y pon la biblioteca.")
    assert defect == ""
    assert not text.casefold().startswith("listo")
    payload = turn_signal_payload("req-1", text)
    assert payload["asserted_result"] is False
    assert payload["type"] == "turn.signal"
    assert payload["text"] == text


def test_verification_denial_replaces_the_in_progress_signal() -> None:
    in_progress = formulate_progress("Silencia el audio del computador.")
    correction = "No pude: el audio no responde."
    visible = visible_after_verification(in_progress, correction)
    assert visible == correction
    assert visible != in_progress
    assert "Listo" not in visible


def test_milestone_fires_only_after_a_gap_strictly_over_three_seconds() -> None:
    started = 10.0
    assert should_emit_milestone(started, started + SILENCE_BUDGET_SECONDS) is False
    assert should_emit_milestone(started, started + SILENCE_BUDGET_SECONDS + 0.01) is True
    assert MILESTONE_DUE_SECONDS == SILENCE_BUDGET_SECONDS + 0.01
    assert should_emit_milestone(started, started + MILESTONE_DUE_SECONDS) is True
    pulse_only = 0.0
    while pulse_only <= SILENCE_BUDGET_SECONDS:
        pulse_only += 1.0
    assert pulse_only == 4.0
    assert MILESTONE_DUE_SECONDS < pulse_only
    assert should_emit_milestone(None, started + 10.0) is False
    spanish = formulate_progress(
        "Abre Steam y ve a la biblioteca",
        kind=KIND_MILESTONE,
        step=2,
        total=3,
    )
    english = formulate_progress(
        "Open Steam and go to the library",
        kind=KIND_MILESTONE,
        step=2,
        total=3,
    )
    assert spanish != english
    assert _acting_defect(spanish, "Abre Steam y ve a la biblioteca") == ""
    assert _acting_defect(english, "Open Steam and go to the library") == ""
    assert not spanish.casefold().startswith("listo")
    assert not english.casefold().startswith("listo")
