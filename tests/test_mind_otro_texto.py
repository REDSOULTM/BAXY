"""Noche NB r1, hallazgo 5 (sesión larga, T2-bloc y T5-bloc): a text written beside text the field already held was told
only «escribí», and a window number that is no window was told «no encontré el campo de texto». The typed facts of the
receipt (otherTextInField, windowFound) are said in the facts line the model reads."""

import json

from baxy_mind.mind import OTHER_TEXT, WINDOW_NOT_FOUND, _deduplicated, _outcome


def _typed(other: bool) -> str:
    return json.dumps({"status": "completed", "verification": "readback",
                       "observed": {"ok": True, "readBack": True, "otherTextInField": other}})


def test_a_text_written_beside_other_text_says_so_in_the_facts_line() -> None:
    assert OTHER_TEXT in _outcome(_typed(True))
    assert OTHER_TEXT not in _outcome(_typed(False))


def test_the_facts_line_and_the_result_say_it_once() -> None:
    told = _outcome(_typed(True))
    assert "otherTextInField" not in _deduplicated(_typed(True), told)
    assert json.loads(_deduplicated(_typed(False), _outcome(_typed(False))))["observed"]["otherTextInField"] is False


def test_a_window_not_found_is_told_apart_from_a_field_not_found() -> None:
    gone = {"status": "failed", "error": "input_window_not_found", "observed": {"window": 125, "windowFound": False}}
    field = {"status": "failed", "error": "input_field_not_found"}
    assert _outcome(json.dumps(gone)) == "falló (input_window_not_found)" + WINDOW_NOT_FOUND
    assert WINDOW_NOT_FOUND not in _outcome(json.dumps(field))
    told = _deduplicated(json.dumps(gone), _outcome(json.dumps(gone)))
    assert json.loads(told)["observed"] == {"window": 125}
