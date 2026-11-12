"""RUT10: «Pauso lo que está sonando y le doy play…» with no media_control in the turn (RUT8's bench, «pausa o
reproduce» said directly) is a claim of an act, as «pausé» is; an offer or a question in the present is not."""
import json

import pytest

from baxy_mind import answer_check

READ = {"op": "media.status", "tool": "media_status", "arguments": {}, "completed": True, "read": True,
        "observation": json.dumps({"status": "completed", "verification": "read",
                                   "observed": {"title": "Documental", "playbackStatus": "playing"}}),
        "outcome": "completed"}
TOGGLED = {"op": "media.control", "tool": "media_control", "arguments": {"action": "toggle"}, "completed": True,
           "read": False, "outcome": "completed",
           "observation": json.dumps({"status": "completed", "verification": "readback", "observed": {
               "commandSent": "toggle", "previousPlaybackStatus": "playing", "playbackStatus": "paused"}})}


def _rules(answer: str, receipts: list, session: list) -> list[str]:
    return [f["rule"] for f in answer_check.check(answer, "ponle pausa o dale play a lo que esté sonando", receipts, session)]


@pytest.mark.parametrize(("answer", "receipts", "session"), [
    ("Pauso lo que está sonando y le doy play para que continúe.", [], []),
    ("Pauso.", [], []),
    ("Pauso lo que está sonando ahora mismo. ¿Quieres que lo vuelva a poner?", [], []),
    ("Está sonando un documental de volcanes, y le doy play para que siga reproduciéndose.", [READ],
     [("media.status", True, True)]),
])
def test_the_present_told_as_done_with_no_call_of_its_kind_is_found(answer: str, receipts: list, session: list) -> None:
    assert _rules(answer, receipts, session) == ["no_call"]


@pytest.mark.parametrize(("answer", "receipts", "session"), [
    ("¿Lo pauso?", [], []),
    ("Si quieres, lo pauso.", [], []),
    ("No pauso nada sin que me lo digas.", [], []),
    ("¿Quieres que le doy play?", [], []),
    ("Pausé lo que estaba sonando.", [TOGGLED], [("media.control", True, False)]),
    ("Pauso lo que está sonando: ya quedó en pausa.", [TOGGLED], [("media.control", True, False)]),
    ("Dime «pauso» y lo pauso.", [], None),
])
def test_an_offer_a_question_or_a_call_that_did_it_is_not_found(answer: str, receipts: list, session: list) -> None:
    assert "no_call" not in _rules(answer, receipts, session) and "not_completed" not in _rules(answer, receipts, session)
