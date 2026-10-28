"""Noche P0.2 (BAXY más torpe con cada mensaje): a long result of a turn before the newest closed one reaches the model as
its turn's facts (src/baxy_mind/mind.py, Mind._age_bodies), by its size and its age only; the newest closed turn and the
short results keep their bodies, and the read ahead (Mind.prefill) reads the history as the next decision sends it."""
import json
import pytest

from baxy_mind.mind import COMPACTED, OLD_BODY_CHARS, TURN_FACTS
from test_mind_prefill import _mind as _slot_mind
from test_mind_w5_mem import Session


def _body(size: int) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": {"text": "x" * size}})


def _results(session: Session) -> list[str]:
    sent = session.server.bodies[-1]["messages"]
    return [message["content"] for message in sent if message["role"] == "tool"]


def test_a_long_result_of_an_older_turn_travels_as_its_facts(tmp_path) -> None:
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS * 3), _body(50), reply="Hecho 1.")
    session.say("pedido 2", _body(OLD_BODY_CHARS * 3), reply="Hecho 2.")
    session.say("pedido 3", reply="Hecho 3.")
    old_long, old_short, newest = _results(session)
    assert old_long.startswith(COMPACTED) and TURN_FACTS in old_long
    assert not old_short.startswith(COMPACTED) and "x" * 50 in old_short
    assert not newest.startswith(COMPACTED) and "x" * OLD_BODY_CHARS * 3 in newest


def test_a_result_under_the_bound_keeps_its_body(tmp_path) -> None:
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS - 200), reply="Hecho 1.")
    session.say("pedido 2", reply="Hecho 2.")
    session.say("pedido 3", reply="Hecho 3.")
    assert not _results(session)[0].startswith(COMPACTED)


def test_with_the_aid_off_every_body_travels_as_it_came(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS * 3), reply="Hecho 1.")
    session.say("pedido 2", reply="Hecho 2.")
    session.say("pedido 3", reply="Hecho 3.")
    assert not _results(session)[0].startswith(COMPACTED)


def test_the_history_already_sent_is_rewritten_once_a_turn_and_only_when_a_turn_begins(tmp_path) -> None:
    session = Session(tmp_path)
    for turn in range(1, 6):
        session.say(f"pedido {turn}", _body(OLD_BODY_CHARS * 3), reply=f"Hecho {turn}.")
    assert session.rewrites == [3, 4, 5]


def test_a_short_reference_of_a_body_left_out_is_not_kept(tmp_path) -> None:
    session = Session(tmp_path)
    address = "https://example.com/" + "a" * 200
    session.say("pedido 1", json.dumps({"status": "completed", "observed": {"url": address, "text": "x" * 3000}}),
                reply="Hecho 1.")
    session.say("pedido 2", _body(50), reply="Hecho 2.")
    assert session.mind._refs
    session.say("pedido 3", reply="Hecho 3.")
    assert session.mind._refs == {}


def _call(n: int) -> dict:
    call = {"name": "app_open", "arguments": json.dumps({"appId": "Paint"})}
    return {"choices": [{"message": {"content": "", "tool_calls": [{"id": f"c{n}", "type": "function", "function": call}]}}]}


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def test_the_read_ahead_reads_the_history_as_the_next_decision_sends_it(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = [_call(1), _say("Hecho 1."), _call(2), _say("Hecho 2."), _say("Sí.")]
    mind, server = _slot_mind(tmp_path, replies, monkeypatch)
    for turn in (1, 2):
        mind.decide(turn, f"pedido {turn}")
        mind.continue_turn(turn, _body(OLD_BODY_CHARS * 3))
        assert mind.prefill() is True
    mind.decide(3, "pedido 3")
    # The older turn's body left the conversation in the read ahead, not in the decision: it reads only its own words.
    assert server.prompts[-1].startswith(server.prefilled[-1])
    assert server.prefilled[-1].count("x" * OLD_BODY_CHARS * 3) == 1


def test_a_turn_without_results_ages_no_body(tmp_path) -> None:
    # Revisión de PC-R1-W2: a question answered in words between the reading and the next question aged the reading,
    # so the third turn of a chain about one reading had lost its body though nothing new was read in the second.
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS * 3), reply="Hecho 1.")
    session.say("pedido 2", reply="Hecho 2.")
    session.say("pedido 3", reply="Hecho 3.")
    assert "x" * OLD_BODY_CHARS * 3 in _results(session)[0]


def test_a_question_and_its_answer_in_words_age_no_body(tmp_path) -> None:
    # The same with two turns in words: BAXY asks which one is meant and the person answers.
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS * 3), reply="Hecho 1.")
    session.say("pedido 2", reply="¿Cuál de los dos?")
    session.say("el primero", reply="Hecho 2.")
    session.say("pedido 3", reply="Hecho 3.")
    assert "x" * OLD_BODY_CHARS * 3 in _results(session)[0]


def test_the_body_ages_once_a_newer_turn_has_results(tmp_path) -> None:
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS * 3), reply="Hecho 1.")
    session.say("pedido 2", reply="Hecho 2.")
    session.say("pedido 3", _body(50), reply="Hecho 3.")
    session.say("pedido 4", reply="Hecho 4.")
    old, newest = _results(session)
    assert old.startswith(COMPACTED) and "x" * 50 in newest


def test_a_result_just_over_the_bound_is_left_out_with_every_aid_on(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The bound counts the result as the conversation keeps it, after «result_dedup» and the rest of the aids.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS + 50), reply="Hecho 1.")
    session.say("pedido 2", _body(50), reply="Hecho 2.")
    session.say("pedido 3", reply="Hecho 3.")
    assert _results(session)[0].startswith(COMPACTED)


def test_a_question_asked_with_ask_user_and_its_answer_age_no_body(tmp_path) -> None:
    # Hallazgo del revisor de pruebas: the answer to ask_user is a tool message, with no line of the turn's facts.
    from test_mind_w5_mem import _call as _tool
    session = Session(tmp_path)
    session.say("pedido 1", _body(OLD_BODY_CHARS * 3), reply="Hecho 1.")
    session.server.replies += [_tool("ask_user", {"question": "¿Cuál de los dos?"}), _say("Hecho 2.")]
    assert session.mind.decide("p2", "pedido 2")["kind"] == "clarify"
    session.mind.decide("p2b", "el primero")
    session.say("pedido 3", reply="Hecho 3.")
    assert "x" * OLD_BODY_CHARS * 3 in _results(session)[0]
