"""v3 r22 revisión (bloqueante 4): app.close that the application answered with a dialog of its own comes back as
close_prompted (WindowControlErrorCodes.ClosePrompted). The final says that fact, never the code («close prompted»),
the same defect the owner rejected in H0714."""

from __future__ import annotations

from baxy_mind import operation_floor
from baxy_mind import compose_situation


def test_the_prompted_close_has_a_cause_fact() -> None:
    assert compose_situation._has_cause_fact("close_prompted")
    said = compose_situation._cause_in_prose("close_prompted", "es")
    assert said != "close prompted"
    assert "close prompted" not in said
    assert "still open" in said and "question" in said


def test_the_prompted_close_floor_says_the_window_stayed_and_was_not_answered() -> None:
    spanish, english = operation_floor.failure_sentences()["close_prompted"]
    assert "sigue abierta" in spanish and "no le contesté" in spanish
    assert "still open" in english and "didn't answer" in english
    assert "close_prompted" not in spanish and "close prompted" not in english


def test_an_unknown_close_code_still_has_no_fact() -> None:
    # Contracaso: only the code the Core sends is a fact; a code of no fact is not given one by this entry.
    assert not compose_situation._has_cause_fact("close_prompted_extra")
