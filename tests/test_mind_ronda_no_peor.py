"""Aid «check_no_worse», INT36B (b2m-off-09/11: the memory off and nothing read, «¿qué sabes de mí?» → «No tengo nada
guardado de ti», memory_off_empty twice, and the third answer «Tengo guardado que te gusta el café y que vives en
Madrid», unread_memory, was spoken as it was: the third answer is never checked again). When the last answer brings a
contradiction of a kind the one before it did not have and no call ran between them, the one before it is spoken: the
model's own words, as the rule «internal» already does."""
import json
import pathlib

from test_mente_ese7 import HELD_ENABLE, HELD_SAVE, SETTINGS
from test_mind_final import _mind, _say

ASKED = "¿Qué sabes de mí?"
FIRST = "No tengo nada guardado de ti."
SECOND = "No tengo información guardada sobre ti porque mi memoria está apagada."
INVENTED = "Tengo guardado que te gusta el café y que vives en Madrid."


def _off(tmp_path: pathlib.Path, replies: list):
    mind, server = _mind(tmp_path, replies)
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE], "memoryOff": True})
    return mind, server


def _rounds(tmp_path: pathlib.Path) -> list[dict]:
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row.get("stage") == "turn.check"]


def test_a_third_answer_with_a_new_kind_of_contradiction_is_not_spoken(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _off(tmp_path, [_say(FIRST), _say(SECOND), _say(INVENTED)])
    step = mind.decide("r1", ASKED)
    assert len(server.bodies) == 3, server.bodies
    assert step["reply"] == SECOND, step
    last = _rounds(tmp_path)[-1]
    assert last["round"] == 3 and "unread_memory" in last["worse"], last
    assert mind.conversation[-1] == {"role": "assistant", "content": SECOND}


def test_a_third_answer_with_the_same_contradiction_is_spoken_as_before(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    third = "No tengo nada guardado sobre ti ahora mismo."
    mind, _ = _off(tmp_path, [_say(FIRST), _say(SECOND), _say(third)])
    assert mind.decide("r1", ASKED)["reply"] == third


def test_a_third_answer_with_nothing_found_is_spoken(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    third = "Mi memoria está apagada: puede que tenga recuerdos tuyos de antes, pero no los puedo ver. ¿La enciendo?"
    mind, _ = _off(tmp_path, [_say(FIRST), _say(SECOND), _say(third)])
    assert mind.decide("r1", ASKED)["reply"] == third
