"""Encargo 119 (F10): «qué dice esto» with a window open ended in «¿Qué quieres que lea?». The window in front is told only on
a question about to be asked, so no other decision reads it (the note of encargo 46, always written, failed the gate)."""
import json
from pathlib import Path
from types import SimpleNamespace

from baxy_mind.early import Anticipation
from baxy_mind.mind import FRONT_NOT_ASKED, NAMED_NOTE
from test_mind_final import _call, _mind, _say

FRONT = {"title": "Visor de prueba - aviso.png", "process": "visorprueba"}
ASK = {"question": "¿Qué quieres que lea?"}


def test_a_first_question_is_not_asked_and_the_model_reads_the_window_in_front(tmp_path: Path) -> None:
    look = _call("input_visible_controls", {"includeText": True})
    mind, server = _mind(tmp_path, [_call("ask_user", ASK), look])
    result = mind.decide(1, "qué dice esto", None, None, FRONT)
    told = json.loads(server.bodies[1]["messages"][-1]["content"])
    assert told == {"status": "not_run", "reason": FRONT_NOT_ASKED.format(window="«Visor de prueba - aviso.png» (visorprueba)")}
    assert result["kind"] == "action"


def test_the_model_may_still_ask_and_then_it_is_asked_once(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("ask_user", ASK), _call("ask_user", {"question": "¿A quién se lo mando?"})])
    result = mind.decide(1, "mándale eso", None, None, FRONT)
    assert result["kind"] == "clarify" and result["question"] == "¿A quién se lo mando?"
    assert len(server.bodies) == 2


def test_no_decision_but_a_question_reads_the_window(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("Hola.")])
    assert mind.decide(1, "hola", None, None, FRONT)["reply"] == "Hola."
    assert "Visor de prueba" not in json.dumps(server.bodies[0]["messages"], ensure_ascii=False)


def test_with_no_window_told_the_question_is_asked(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("ask_user", ASK)])
    assert mind.decide(1, "qué dice esto")["kind"] == "clarify"
    assert len(server.bodies) == 1


def test_a_question_while_a_call_waits_for_the_yes_is_asked(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("ask_user", ASK)])
    pending = {"operation": "file.delete", "arguments": {"path": "x.txt"}}
    assert mind.decide(1, "cuál era", pending, None, FRONT)["kind"] == "clarify"
    assert len(server.bodies) == 1


def test_a_long_title_is_cut_saying_so(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("ask_user", ASK), _say("Listo.")])
    mind.decide(1, "qué dice esto", None, None, {"title": "x" * 300})
    told = json.loads(server.bodies[1]["messages"][-1]["content"])["reason"]
    assert "«" + "x" * 200 + "…»" in told


def test_the_windows_the_words_name_are_a_note_after_the_clock_and_never_in_the_persons_message(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("Listo."), _say("Hola.")])
    mind.decide(1, "cuánto saldo me queda en Vaporeta", None, None, None, [{"title": "Vaporeta", "process": "vaporeta"}])
    messages = server.bodies[0]["messages"]
    assert messages[-1] == {"role": "user", "content": "cuánto saldo me queda en Vaporeta"}
    assert messages[-2]["content"] == NAMED_NOTE.format(windows="«Vaporeta» (vaporeta)")
    mind.decide(2, "hola")
    assert all("ventanas abiertas" not in str(m.get("content")) for m in server.bodies[1]["messages"][-3:])


def test_an_early_decision_made_without_the_note_is_decided_again() -> None:
    anticipation, put_back = _anticipation({"kind": "action"})
    message = {"type": "turn.decide", "id": 7, "text": "qué dice esto", "named": [{"title": "Vaporeta"}]}
    assert anticipation.settle("turn.decide", message, 0.05) is None
    assert put_back == ["named"]


def _anticipation(result: dict) -> tuple[Anticipation, list[str]]:
    put_back: list[str] = []
    anticipation = object.__new__(Anticipation)
    anticipation.mind = SimpleNamespace(_clock_time=lambda: "minute", foresee=None, _write_row=lambda row: None)
    anticipation._back = lambda held, reason, reread=True: put_back.append(reason)
    anticipation._discarded, anticipation._missed = 0, None
    anticipation._held = {"text": "qué dice esto", "clock": "minute", "result": result, "rows": [], "foreseen": [],
                          "started": 0.0, "ended": 0.1}
    return anticipation, put_back


def test_an_early_question_is_decided_again_when_the_app_tells_the_window() -> None:
    anticipation, put_back = _anticipation({"kind": "clarify"})
    message = {"type": "turn.decide", "id": 7, "text": "qué dice esto", "front": FRONT}
    assert anticipation.settle("turn.decide", message, 0.05) is None
    assert put_back == ["front"]


def test_an_early_decision_that_asks_nothing_is_used_whatever_the_window() -> None:
    anticipation, put_back = _anticipation({"kind": "action"})
    message = {"type": "turn.decide", "id": 7, "text": "qué dice esto", "front": FRONT}
    assert anticipation.settle("turn.decide", message, 0.05) == {"kind": "action", "id": 7}
    assert put_back == []


def test_the_apps_decision_reaches_the_mind_with_the_window_in_front(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("ask_user", ASK), _say("Listo.")])
    Anticipation(mind, warm=False).decide(1, "qué dice esto", None, None, FRONT)
    assert "Visor de prueba" in server.bodies[1]["messages"][-1]["content"]
