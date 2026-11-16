"""MOD4: through Ollama or an API no grammar holds a closed question's answer to the word alone, and «Now.» or
{"answer": "now"} came back unread: their «sí» was asked again. The word is read by its shape (closed_word): its case, the
marks, quotes and spaces around it, a JSON that holds it. Only a reply that is one of the values reads as that value; a
yes that is not exactly the confirming value never runs what waits."""
import json

import pytest

from baxy_mind.mind import AGREEMENT_ANSWER_KINDS, RING_READ_KINDS, THEIR_ANSWER_KINDS, closed_word
from test_mind_final import _call, _say
from test_mind_su_si import PENDING, _asked_mind


@pytest.mark.parametrize("read, word", [
    ("now", "now"), ("Now.", "now"), ("NOW", "now"), ('"now"', "now"), ("  now\n", "now"), ("«now»", "now"),
    ('{"answer": "now"}', "now"), ('{"respuesta":"Now."}', "now"), ('```json\n{"answer": "later"}\n```', "later"),
    ("**maybe**", "maybe"), ("`yours`", "yours"), ('"No."', "no"),
])
def test_a_value_in_any_wrapping_is_that_value(read, word) -> None:
    assert closed_word(read, THEIR_ANSWER_KINDS) == word


@pytest.mark.parametrize("read", [
    "", "yes", "Yes.", "sí", "Sí, claro", "yes please", "now please", "now, sure", "not now", "no now", "nowadays", "n o w",
    '{"answer": "now", "why": "they said so"}', '["now"]', '{"answer": ["now"]}', '{"respuesta":"sí"}', "{now}", "dale",
    "<think>now</think>", "</think>now", "<think>x</think>\nLater.",
])
def test_anything_else_is_not_read(read) -> None:
    assert closed_word(read, THEIR_ANSWER_KINDS) is None


def test_every_closed_list_is_read_the_same_way() -> None:
    assert closed_word("Accept!", AGREEMENT_ANSWER_KINDS) == "accept"
    assert closed_word("I accept", AGREEMENT_ANSWER_KINDS) is None
    assert closed_word("¡Parar!", RING_READ_KINDS) == "parar"
    assert closed_word("stop", RING_READ_KINDS) is None
    assert closed_word("Yes.", ("yes", "no")) == "yes" and closed_word("Yeah.", ("yes", "no")) is None


@pytest.mark.parametrize("verdict", ["Now.", '{"answer": "now"}', " NOW "])
def test_their_yes_in_the_shape_an_api_gives_answers_the_waiting_call(tmp_path, verdict) -> None:
    mind, _, _ = _asked_mind(tmp_path, [], verdict)
    result = mind.decide(3, "dale nomás", PENDING)
    assert (result["operation"], result["arguments"]) == ("confirmation.answer", {"answer": "yes"})
    assert result.get("theirYes") is True


@pytest.mark.parametrize("verdict", ["Yes.", "sí", "Sí, claro", "yes please", "now please", "", '{"respuesta":"sí"}',
                                     '{"answer": "now", "note": "x"}', "ok"])
def test_a_reply_that_is_not_exactly_a_value_confirms_nothing(tmp_path, verdict) -> None:
    mind, _, _ = _asked_mind(tmp_path, [_call("confirm_pending", {"answer": "yes"}),
                                     _say("¿La enciendo entonces?")], verdict)
    result = mind.decide(3, "puede ser", PENDING)
    assert result["operation"] == "confirmation.answer" and result["arguments"] == {"answer": "unclear"}
    assert not result.get("theirYes")
    said = mind.continue_turn(4, json.dumps({"status": "needs_confirmation", "operation": "baxy.settings.set"}))
    assert said["operation"] is None

