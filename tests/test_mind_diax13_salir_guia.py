"""DIAX13 (the owner's F5, 16-11-2026, 1.5.4; REVX2 DX1-1): a guide of the routines that ends unsaved leaves in what the
model reads what happened, not its exchange, and never a question of BAXY from before it as the one just asked.

The owner, inside the guide of a new routine, asked four times for a new conversation and none was started: the model
read the guide's fixed questions as its own words and went on with the routine (DIAX1). DIAX1 cut the conversation back
to before the guide; when the last thing BAXY said there was an offer («¿Quieres que los borre?»), an «ok» to «no guardé
ninguna rutina» was read after that offer, with the note that it may answer it (REVX2's probe P1). Here the guide's
exchange is folded from its first question on: what the person said to open it stays, and so does the sentence the guide
ended with. «cancela» in more words than its closed form, with another request in them, leaves the guide for the model.
The phrases here are made up."""
from __future__ import annotations

import json
from pathlib import Path

from baxy_mind import mind as mind_module
from baxy_mind import routine_guide
from baxy_mind.mind import OFFERED_NOTE
from test_mind_final import _call, _say
from test_mind_routine_guide import _guide_mind
from test_mind_rut14_rutinas import _reading

OFFER = [{"role": "user", "content": "¿qué hay en la carpeta de descargas?"},
         {"role": "assistant", "content": "Hay cinco instaladores viejos. ¿Quieres que los borre?"}]
CANCELLED = routine_guide.TEXT["es"]["cancelled"]


def _texts(body: dict) -> list[str]:
    return [str(m.get("content") or "") for m in body["messages"]]


def _said_by_baxy(body: dict) -> list[str]:
    return [m["content"] for m in body["messages"] if m["role"] == "assistant" and m.get("content")]


def _more(server, answer: str) -> None:
    """The closed question of whether words that stop the routine ask for something else (Mind._asks_more)."""
    inner, server.more = server.ask_apart, []

    def ask_apart(body: dict, timeout: float = 60.0) -> dict:
        if body["messages"][0]["content"] == getattr(mind_module, "MORE_READ_SYSTEM", None):
            server.more.append(body)
            return {"choices": [{"message": {"content": answer}}]}
        return inner(body, timeout)

    server.ask_apart = ask_apart


def _to_the_order(mind) -> str:
    """A new routine of a word, by its closed answers, up to «¿Qué quieres que haga cuando la digas?»."""
    mind.decide(1, "crea una rutina")
    mind.decide(2, "con una palabra")
    asked = mind.decide(3, "lluvia")
    assert mind._guide.step == "order"
    return asked["reply"]


def test_an_ok_after_the_guide_was_cancelled_follows_its_end_and_no_offer_from_before(tmp_path: Path) -> None:
    # REVX2 P1: an offer of BAXY nobody answered, a guide opened instead and cancelled, and then «ok»
    mind, server = _guide_mind(tmp_path, [_say("Vale.")])
    mind.new_session(OFFER)
    asked = mind.decide(1, "crea una rutina")
    assert mind._guide is not None
    assert mind.decide(2, "cancela")["reply"] == CANCELLED and server.bodies == []
    mind.decide(3, "ok")
    texts = _texts(server.bodies[-1])
    assert asked["reply"] not in texts                                  # the guide's question is folded
    end = texts.index(CANCELLED)
    assert texts[end - 1] == "cancela"                                  # what ended it and what BAXY said then
    assert OFFERED_NOTE not in json.dumps(texts[end:], ensure_ascii=False)  # nothing says «ok» may answer a question
    assert _said_by_baxy(server.bodies[-1])[-1] == CANCELLED            # what they heard last is BAXY's last words
    assert texts[end - 2] == getattr(routine_guide, "ENDED_NOTE", "-") and texts[-1] == "ok"
    assert "crea una rutina" in texts and OFFER[1]["content"] in texts  # the words that set the offer aside stay


def test_another_request_leaves_the_guide_and_no_question_before_it_is_the_one_asked(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("No guardé la rutina. Son las diez.")])
    _reading(server, [{"x": "other"}])
    mind.new_session(OFFER)
    asked = mind.decide(1, "crea una rutina")
    mind.decide(2, "mejor dime qué hora es ahora")
    texts = _texts(server.bodies[-1])
    assert mind._guide is None and asked["reply"] not in texts
    assert routine_guide.LEFT_NOTE in texts[-2] and OFFERED_NOTE not in texts[-2]
    assert texts[-1] == "mejor dime qué hora es ahora"
    assert [m["content"] for m in mind.conversation if m.get("role") == "assistant"][-1] == "No guardé la rutina. Son las diez."


def test_a_cancel_in_more_words_with_another_request_leaves_it_to_the_model(tmp_path: Path) -> None:
    # DIAX1's held-out: «Cancela eso. Oye, ¿qué hora es?» → «Listo, lo dejo…» and the request lost
    mind, server = _guide_mind(tmp_path, [_say("No la guardé. Son las diez.")])
    _reading(server, [{"k": "word", "t": "dime qué hora es", "x": "cancel"}])
    _more(server, "otra")
    asked = _to_the_order(mind)
    told = mind.decide(4, "ya no, cancela eso y dime qué hora es")
    assert told["reply"] == "No la guardé. Son las diez." and mind._guide is None and len(server.more) == 1
    texts = _texts(server.bodies[-1])
    assert getattr(routine_guide, "CANCEL_LEFT_NOTE", "-") in texts[-2] and asked not in texts


def test_a_cancel_in_more_words_that_asks_nothing_else_ends_the_guide_in_its_words_and_fills_nothing(
        tmp_path: Path) -> None:
    # DIAX1's held-out hc02: «olvídalo, abre una conversación nueva» at «¿Qué quieres que haga…?» was kept as the order
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [{"k": "word", "t": "abre una conversación nueva", "x": "cancel"}])
    _more(server, "nada")
    _to_the_order(mind)
    told = mind.decide(4, "no, olvídalo, abre una conversación nueva")
    assert told["reply"] == CANCELLED and mind._guide is None and server.bodies == []


def test_a_guide_left_by_its_silence_is_folded_too(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_say("Son las diez.")])
    mind.new_session(OFFER)
    asked = mind.decide(1, "crea una rutina")
    mind._guide_at -= 10_000   # GUIDE_SILENCE_S long past
    mind.decide(2, "¿qué hora es?")
    texts = _texts(server.bodies[-1])
    assert asked["reply"] not in texts and routine_guide.SILENT_NOTE in texts[-2] and OFFERED_NOTE not in texts[-2]


def test_a_deletion_left_by_another_request_is_folded_and_its_question_not_answered(tmp_path: Path) -> None:
    routine = {"id": "r-00000a", "name": "cine", "trigger": {"phrase": "cine"}, "active": True, "steps": [],
               "order": "pausa la música"}
    mind, server = _guide_mind(tmp_path, [_say("No la borré. Abro la calculadora.")], [routine])
    asked = mind.decide(1, "borra todas mis rutinas")
    assert mind._guide is not None and asked["reply"].endswith("?")
    mind.decide(2, "abre la calculadora por favor ahora")
    texts = _texts(server.bodies[-1])
    assert mind._guide is None and asked["reply"] not in texts
    assert routine_guide.LEFT_NOTES["delete"] in texts[-2] and OFFERED_NOTE not in texts[-2]


def test_a_saved_routine_keeps_its_exchange(tmp_path: Path) -> None:
    # control: what the guide made and saved stays as it was said (RUT10)
    mind, server = _guide_mind(tmp_path, [_say("De nada.")])
    _reading(server, [{"k": "word", "t": "pauses la música", "x": "answer"}])
    asked = _to_the_order(mind)
    assert mind.decide(4, "que pauses la música")["reply"].endswith("¿La guardo?")
    assert mind.decide(5, "sí")["operation"] == "baxy.routines"
    routine = {"id": "r-00000a", "name": "lluvia", "trigger": {"phrase": "lluvia"}, "active": True, "steps": [],
               "order": "que pauses la música"}
    saved = mind.continue_turn(5, json.dumps({"status": "completed", "verification": "readback",
                                              "observed": {"routine": routine, "saved": True}}))
    assert saved["reply"].startswith("Guardada.")
    mind.decide(6, "gracias")
    texts = _texts(server.bodies[-1])
    assert asked in texts and getattr(routine_guide, "ENDED_NOTE", "-") not in texts


def test_a_call_that_ran_in_the_turn_that_opened_the_guide_stays(tmp_path: Path) -> None:
    # REVX2 DX1-2: «pausa la música y hazme una rutina» paused it; leaving the guide must not take that away
    mind, server = _guide_mind(tmp_path, [_call("media_control", {"action": "pause"}), _call("baxy_routines", {}),
                                          _say("No la guardé. Son las diez.")])
    _reading(server, [{"x": "answer"}, {"x": "other"}])
    assert mind.decide(1, "pausa la música y hazme una rutina")["operation"] == "media.control"
    asked = mind.continue_turn(1, json.dumps({"status": "completed", "verification": "readback",
                                              "observed": {"state": "paused"}}))
    assert mind._guide is not None and asked["kind"] == "conversation"
    mind.decide(2, "mejor dime qué hora es ahora")
    texts = _texts(server.bodies[-1])
    assert "pausa la música y hazme una rutina" in texts and asked["reply"] not in texts
    calls = [c["function"]["name"] for m in server.bodies[-1]["messages"] for c in m.get("tool_calls") or []]
    assert "media_control" in calls and routine_guide.LEFT_NOTE in texts[-2]


def test_with_no_question_of_baxy_before_it_the_turn_that_opened_the_guide_goes_too(tmp_path: Path) -> None:
    # the owner's F5: with the words that opened it still there the 4B said «Nuevo chat iniciado» with no call
    mind, server = _guide_mind(tmp_path, [_say("Son las diez."), _say("Vale.")])
    mind.decide(1, "¿qué hora es?")
    mind.decide(2, "crea una rutina")
    mind.decide(3, "cancela")
    mind.decide(4, "empieza otra conversación")
    texts = _texts(server.bodies[-1])
    assert "crea una rutina" not in texts and "cancela" not in texts and "Son las diez." in texts
    assert texts[texts.index(CANCELLED) - 1] == getattr(routine_guide, "ENDED_NOTE", "-")


def test_a_late_yes_after_the_guide_fell_silent_does_not_follow_an_offer_from_before_it(tmp_path: Path) -> None:
    # REVX2 D13-1 (DIAX13B): dropped by its silence at «¿La guardo?», no sentence of BAXY followed the fold, so the offer
    # before the guide was again the last thing BAXY said and a late «sí» was read right after it
    mind, server = _guide_mind(tmp_path, [_say("No hay nada que guardar.")])
    _reading(server, [{"k": "word", "t": "abre el bloc de notas", "x": "answer"}])
    mind.new_session(OFFER)
    _to_the_order(mind)
    assert mind.decide(4, "abre el bloc de notas")["reply"].endswith("¿La guardo?")
    mind._guide_at -= 10_000   # GUIDE_SILENCE_S long past
    mind.decide(5, "sí")
    texts = _texts(server.bodies[-1])
    last = _said_by_baxy(server.bodies[-1])[-1]
    assert last != OFFER[1]["content"] and "?" not in last                     # BAXY's last words ask nothing
    assert texts.index(last) > texts.index(routine_guide.ENDED_NOTE)           # and follow the fold
    assert OFFERED_NOTE not in json.dumps(texts[texts.index(last):], ensure_ascii=False)
    assert routine_guide.SILENT_NOTE in texts[-2] and texts[-1] == "sí"
