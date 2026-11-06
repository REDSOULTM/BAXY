"""Asked what it remembers with the memory off (uso-83, 3/10; encargo A4): the memory call fails with memory_disabled and
the model asked in words whether to turn it on, instead of calling memory_enable (the call that asks the person), and
after their «sí» it sometimes said it had turned it on without calling it. The failure carries the one next that turns it
on and says it is not on until that call's own result says so; the aid turns on nothing."""
import json
import pathlib

from baxy_mind.mind import MEMORY_OFF_NOTE

from test_mind_final import _call, _mind, _say

OFF = json.dumps({"status": "failed", "error": "memory_disabled", "effectUncertain": False})


def _caps() -> dict:
    return {"capabilities": [{"name": "memory.recall", "description": "Recalls.", "risk": "read_only"},
                             {"name": "memory.enable", "description": "Enables.", "risk": "write"}]}


def _tool_texts(server) -> list[str]:
    return [m["content"] for m in server.bodies[-1]["messages"] if m.get("role") == "tool"]


def test_a_memory_call_that_failed_off_names_the_call_that_asks_the_person(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("memory_recall", {"query": "la persona"}), _say("Está apagada.")])
    mind.configure(_caps())
    mind.decide(1, "¿qué recuerdas de mí?")
    mind.continue_turn(2, OFF)
    told = _tool_texts(server)[-1]
    assert told.startswith(OFF + "\n")
    assert MEMORY_OFF_NOTE.format(enable="memory_enable") in told
    assert "no se lo preguntes tú antes en palabras" in told and "hasta que el resultado de memory_enable lo diga" in told


def test_the_failure_of_memory_enable_itself_and_other_failures_get_no_such_note(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("memory_enable", {}), _say("No pude.")])
    mind.configure(_caps())
    mind.decide(1, "activa la memoria")
    mind.continue_turn(2, OFF)
    assert "memory_enable {}" not in _tool_texts(server)[-1]
    mind, server = _mind(tmp_path, [_call("memory_recall", {"query": "x"}), _say("No pude.")])
    mind.configure(_caps())
    mind.decide(1, "¿qué recuerdas de mí?")
    mind.continue_turn(2, json.dumps({"status": "failed", "error": "memory_store_unavailable"}))
    assert "memory_enable" not in _tool_texts(server)[-1]


def test_without_the_aid_the_failure_is_as_it_was(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server = _mind(tmp_path, [_call("memory_recall", {"query": "la persona"}), _say("Está apagada.")])
    mind.configure(_caps())
    mind.decide(1, "¿qué recuerdas de mí?")
    mind.continue_turn(2, OFF)
    assert "memory_enable" not in _tool_texts(server)[-1]


def test_saying_the_memory_was_turned_on_without_the_call_that_does_it_is_flagged_and_the_question_is_not() -> None:
    # The second half of uso-83: after the «sí» the model said «la activé» with no memory_enable result. answer_check's
    # rules not_completed / no_call already read it (kind «encender», memory.* operations); this keeps them reading it.
    from baxy_mind.answer_check import check

    failed = {"op": "memory.recall", "tool": "memory_recall", "arguments": {}, "observation": OFF,
              "outcome": "falló (memory_disabled)", "completed": False, "read": True}
    calls = [("memory.recall", False, True)]
    for told in ("Listo, ya activé la memoria.", "He activado la memoria.", "Encendí la memoria, ya puedo recordar."):
        assert [f["rule"] for f in check(told, "sí", [failed], calls)] == ["no_call"]  # a read is no act of that kind
        assert [f["rule"] for f in check(told, "sí", [], calls)] == ["no_call"]
    assert check("La memoria está apagada, ¿quieres que la active?", "sí", [failed], calls) == []


def _asked_then(tmp_path: pathlib.Path, monkeypatch, question: dict):
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    from baxy_mind.mind import MEMORY_ON_OFFER_NOTE

    mind, server = _mind(tmp_path, [_call("memory_recall", {"query": "la persona"}), question,
                                    _call("memory_enable", {})])
    mind.configure(_caps())
    mind.decide(1, "¿qué recuerdas de mí?")
    mind.continue_turn(2, OFF)
    return mind, server, MEMORY_ON_OFFER_NOTE.format(enable="memory_enable")


def test_a_si_after_baxys_question_in_words_with_the_memory_off_carries_the_next_to_memory_enable(tmp_path: pathlib.Path,
                                                                                                 monkeypatch) -> None:
    mind, server, note = _asked_then(tmp_path, monkeypatch,
                                     _say("La memoria está apagada. ¿Quieres que la encienda?"))
    out = mind.decide(3, "sí")
    assert out["kind"] == "action" and out["operation"] == "memory.enable" and out["arguments"] == {}
    sent = [m["content"] for m in server.bodies[-1]["messages"] if m.get("role") == "user"]
    assert any(note in m for m in sent) and sent[-1] == "sí"


def test_a_si_to_another_question_or_after_the_note_was_used_carries_no_such_note(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Hola. ¿Quieres que busque música?"), _say("Vale.")])
    mind.configure(_caps())
    mind.decide(1, "hola")
    mind.decide(2, "sí")
    sent = [m["content"] for m in server.bodies[-1]["messages"] if m.get("role") == "user"]
    assert not any("memory_enable" in m for m in sent)
