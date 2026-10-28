"""The benches' second number (C62, scripts/renew/bench_guardas.py): the decision the person sees after the App's guards,
beside the first decision. The oracle here is a stand-in speaking the same JSON lines; the App's own is
tests/Baxy.GuardOracle."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_decision
import bench_guardas

# A stand-in oracle: refuses message.draft by «whatsapp» unless the words heard say it, routes filesystem.list into
# file.find, and dies on {"call": "die"}.
ORACLE = r'''
import json, sys
heard = ""
for line in sys.stdin:
    request = json.loads(line)
    answer = {}
    if "heard" in request:
        heard = request["heard"] + ("|answering" if request.get("answering") else "")
        answer = {"heard": heard}
    elif request.get("call") == "die":
        sys.exit(3)
    elif request.get("call") == "message.draft" and "whatsapp" not in heard:
        answer = {"refused": json.dumps({"status": "rejected", "error": "channel_not_said", "next": "words"})}
    elif request.get("call") == "filesystem.list":
        answer = {"operation": "file.find", "arguments": {"folder": "home", "subdirectory": "x"}, "note": "routed"}
    elif "call" in request:
        answer = {"operation": request["call"], "arguments": request["arguments"], "note": None}
    print(json.dumps(answer), flush=True)
'''


@pytest.fixture
def oracle(tmp_path: Path):
    script = tmp_path / "oracle.py"
    script.write_text(ORACLE, encoding="utf-8")
    launcher = tmp_path / "oracle.cmd"
    launcher.write_text(f'@"{sys.executable}" -I "{script}"\r\n', encoding="utf-8")
    guards = bench_guardas.Guards(str(launcher))
    yield guards
    guards.close()


class Mind:
    """Answers each result with the next of `replies`, keeping what it was given."""

    def __init__(self, *replies: dict) -> None:
        self.replies, self.given = list(replies), []

    def continue_turn(self, request_id, observation: str, final: bool = False) -> dict:
        self.given.append((observation, final))
        return self.replies.pop(0)


def _draft(channel: str = "whatsapp") -> dict:
    return {"kind": "action", "operation": "message.draft", "arguments": {"channel": channel, "recipient": "Ana"}}


def test_a_refused_call_goes_back_to_the_model_and_its_words_are_what_the_person_sees(oracle) -> None:
    oracle.heard("saluda a Ana, que está aquí")
    mind = Mind({"kind": "conversation", "reply": "¡Hola, Ana!"})
    shown, went, refused, last = bench_guardas.seen(mind, "c1", _draft(), oracle, 3)
    assert shown == last == {"kind": "conversation", "reply": "¡Hola, Ana!"}
    assert went == [] and refused == ["channel_not_said"]
    assert "channel_not_said" in mind.given[0][0] and mind.given[0][1] is False
    expect = {"kind": "text"}
    assert bench_decision.judge(expect, _draft(), _draft()["arguments"]) is False  # the first decision, as before
    assert bench_decision.judge(expect, shown, None) is True  # the one seen


def test_a_call_that_goes_is_seen_as_it_would_run_and_the_decision_bench_stops_there(oracle) -> None:
    oracle.heard("¿qué hay en mi carpeta x?")
    mind = Mind()
    shown, went, refused, _ = bench_guardas.seen(
        mind, "c1", {"kind": "action", "operation": "filesystem.list", "arguments": {}}, oracle, 3)
    assert shown == {"kind": "action", "operation": "file.find", "arguments": {"folder": "home", "subdirectory": "x"}}
    assert went == ["file.find"] and refused == [] and mind.given == []


def test_refused_every_time_the_last_continuation_closes_the_turn(oracle) -> None:
    oracle.heard("escríbele a Ana")
    mind = Mind(_draft(), _draft(), {"kind": "clarify", "question": "¿Por dónde?"})
    shown, went, refused, _ = bench_guardas.seen(mind, "c1", _draft(), oracle, 3)
    assert shown["kind"] == "clarify" and refused == ["channel_not_said"] * 3
    assert [final for _, final in mind.given] == [False, False, True]  # MAX_CALLS spent: the App closes the turn


def test_the_session_bench_gives_each_call_that_goes_its_result_and_tells_the_guards(oracle) -> None:
    oracle.heard("escríbele a Ana por whatsapp")
    mind = Mind({"kind": "conversation", "reply": "Listo."})
    shown, went, _, last = bench_guardas.seen(mind, "c1", _draft(), oracle, 3,
                                              lambda op, arguments, index: json.dumps({"status": "completed"}))
    assert shown["operation"] == "message.draft" and went == ["message.draft"] and last["reply"] == "Listo."
    assert mind.given == [('{"status": "completed"}', False)]


def test_a_case_is_heard_with_its_earlier_words_and_an_answer_to_what_waits(oracle, monkeypatch) -> None:
    sent = []
    monkeypatch.setattr(oracle, "_ask", lambda request: sent.append(request) or {})
    bench_decision.hear(oracle, {"text": "sí", "pending": {"operation": "x"}, "history": [
        {"role": "user", "content": "por whatsapp"}, {"role": "assistant", "content": "¿Le escribo?"}]})
    assert sent == [{"reset": True}, {"heard": "por whatsapp", "answering": False}, {"heard": "sí", "answering": True}]


def test_an_oracle_that_died_stops_the_run(oracle) -> None:
    with pytest.raises(RuntimeError, match="guard oracle exited"):
        oracle.call("die", {})


def test_the_summary_says_both_numbers_and_which_oracle_judged(tmp_path: Path) -> None:
    exe = tmp_path / "oracle.exe"
    exe.write_bytes(b"x")
    rows = [{"ok": False, "ok_seen": True, "refused": ["channel_not_said"]}, {"ok": True, "ok_seen": True, "refused": []}]
    summary = bench_guardas.seen_summary(rows, str(exe))
    assert summary["ok_seen"] == 2 and summary["accuracy_seen"] == 1.0 and summary["refused"] == 1
    assert summary["guardas"]["path"] == str(exe) and len(summary["guardas"]["sha256"]) == 64
    assert bench_guardas.seen_summary(rows, None) == {}  # without the oracle, the summary is as before
