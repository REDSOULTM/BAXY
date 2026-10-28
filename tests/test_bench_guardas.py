"""The benches' second number (C62, scripts/renew/bench_guardas.py): the decision the person sees after the App's guards,
beside the first decision. The oracle here is a stand-in speaking the same JSON lines; the App's own is
tests/Baxy.GuardOracle."""
import sys
import json
import pathlib

import pytest

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "renew")]

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
        heard = request["heard"]
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
def oracle(tmp_path: pathlib.Path):
    script = tmp_path / "oracle.py"
    script.write_bytes(ORACLE.encode("utf-8"))
    launcher = tmp_path / "oracle.cmd"
    launcher.write_bytes(f'@"{sys.executable}" -I "{script}"\r\n'.encode("utf-8"))
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
    shown, went, refused, last, error = bench_guardas.seen(mind, "c1", _draft(), oracle, 3)
    assert shown == last == {"kind": "conversation", "reply": "¡Hola, Ana!"} and error is None
    assert went == [] and refused == ["channel_not_said"]
    assert "channel_not_said" in mind.given[0][0] and mind.given[0][1] is False
    expect = {"kind": "text"}
    assert bench_decision.judge(expect, _draft(), _draft()["arguments"]) is False  # the first decision, as before
    assert bench_decision.judge(expect, shown, None) is True  # the one seen


def test_a_call_that_goes_is_seen_as_it_would_run_and_the_decision_bench_stops_there(oracle) -> None:
    oracle.heard("¿qué hay en mi carpeta x?")
    mind = Mind()
    shown, went, refused, _, _ = bench_guardas.seen(
        mind, "c1", {"kind": "action", "operation": "filesystem.list", "arguments": {}}, oracle, 3)
    assert shown == {"kind": "action", "operation": "file.find", "arguments": {"folder": "home", "subdirectory": "x"}}
    assert went == ["file.find"] and refused == [] and mind.given == []


def test_refused_every_time_the_last_continuation_closes_the_turn(oracle) -> None:
    oracle.heard("escríbele a Ana")
    mind = Mind(_draft(), _draft(), {"kind": "clarify", "question": "¿Por dónde?"})
    shown, went, refused, _, _ = bench_guardas.seen(mind, "c1", _draft(), oracle, 3)
    assert shown["kind"] == "clarify" and refused == ["channel_not_said"] * 3
    assert [final for _, final in mind.given] == [False, False, True]  # MAX_CALLS spent: the App closes the turn


def test_the_session_bench_gives_each_call_that_goes_its_result_and_tells_the_guards(oracle) -> None:
    oracle.heard("escríbele a Ana por whatsapp")
    mind = Mind({"kind": "conversation", "reply": "Listo."})
    shown, went, _, last, _ = bench_guardas.seen(mind, "c1", _draft(), oracle, 3,
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
    with pytest.raises(bench_guardas.GuardOracleError, match="guard oracle answered ''"):
        oracle.call("die", {})


def test_the_summary_says_both_numbers_and_which_oracle_judged(oracle) -> None:
    rows = [{"id": "a", "ok": False, "ok_seen": True, "refused": ["channel_not_said"]},
            {"id": "b", "ok": True, "ok_seen": False, "refused": [], "seen_error": "TimeoutError()"}]
    summary = bench_guardas.seen_summary(rows, oracle)
    assert summary["ok_seen"] == 1 and summary["accuracy_seen"] == 0.5 and summary["refused"] == 1
    assert summary["seen_errors"] == ["b"]
    assert summary["guardas"]["path"].endswith("oracle.cmd") and len(summary["guardas"]["oracle.cmd"]) == 64
    assert bench_guardas.seen_summary(rows, None) == {}  # without the oracle, the summary is as before


def test_an_answer_out_of_the_protocol_stops_the_run(oracle, monkeypatch) -> None:
    for wrong in ({"error": "unknown"}, {}, {"operation": "x"}, {"refused": "r", "operation": "x", "arguments": {}}):
        monkeypatch.setattr(oracle, "_ask", lambda request, wrong=wrong: wrong)
        with pytest.raises(bench_guardas.GuardOracleError):
            oracle.call("message.draft", {})
    monkeypatch.setattr(oracle, "_ask", lambda request: {"error": "unknown request"})
    with pytest.raises(bench_guardas.GuardOracleError):
        oracle.heard("hola")  # a state request not taken is not a state the oracle holds


def test_a_doubted_call_is_held_before_the_guards_and_seen_as_it_was(oracle, monkeypatch) -> None:
    monkeypatch.setattr(oracle, "call", lambda *a: pytest.fail("a doubted call went to the guards"))
    held = {**_draft(), "unsure": True}
    assert bench_guardas.seen(Mind(), "c1", held, oracle, 3).shown == held


def test_the_minds_failure_after_a_refusal_ends_the_seen_decision_only(oracle) -> None:
    class Down(Mind):
        def continue_turn(self, request_id, observation: str, final: bool = False) -> dict:
            raise TimeoutError("server")

    oracle.heard("saluda a Ana")
    after = bench_guardas.seen(Down(), "c1", _draft(), oracle, 3)
    assert after.shown == {"kind": "error"} and "TimeoutError" in after.error and after.refused == ["channel_not_said"]


def test_the_persons_words_leave_out_baxys_notes_and_keep_their_answers() -> None:
    conversation = [{"role": "user", "content": "[En este turno: carpeta Viajes]"}, {"role": "user", "content": "hola"},
                    {"role": "assistant", "tool_calls": [
                        {"id": "q1", "function": {"name": "ask_user", "arguments": "{}"}}], "content": ""},
                    {"role": "tool", "tool_call_id": "q1", "content": "por whatsapp"},
                    {"role": "tool", "tool_call_id": "c9", "content": "{\"status\": \"completed\"}"},
                    {"role": "role-state", "refs": {}}]
    assert bench_guardas.person_words(conversation) == ["hola", "por whatsapp"]


def test_the_oracle_is_given_by_its_full_path_never_by_a_name_looked_up() -> None:
    with pytest.raises(bench_guardas.GuardOracleError, match="no guard oracle"):
        bench_guardas.Guards("Baxy.GuardOracle.exe")


class _Server:
    made: list = []

    def __init__(self, gguf, server, **options):
        self.closed = False
        self._process = type("P", (), {"pid": 4242})()
        _Server.made.append(self)

    def start(self):
        pass

    def wait_ready(self, timeout):
        pass

    def close(self):
        self.closed = True


class _Mind:
    """Drafts by WhatsApp for «saluda…», calls «die» for «muere», and greets in words after a result."""

    def __init__(self, server, trace, system_one=None):
        pass

    def configure(self, catalog):
        pass

    def warm(self):
        pass

    def new_session(self, history):
        pass

    def decide(self, case_id, text, pending=None, unsure=None):
        if text == "muere":
            return {"kind": "action", "operation": "die", "arguments": {}}
        return _draft()

    def continue_turn(self, request_id, observation, final=False):
        return {"kind": "conversation", "reply": "¡Hola, Ana!"}


def _main(tmp_path, monkeypatch, launcher, cases):
    import types
    _Server.made.clear()
    package = types.ModuleType("baxy_mind")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "baxy_mind", package)
    monkeypatch.setitem(sys.modules, "baxy_mind.llm_server", types.SimpleNamespace(LlmServer=_Server))
    monkeypatch.setitem(sys.modules, "baxy_mind.mind", types.SimpleNamespace(Mind=_Mind))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(bench_decision, "BANKS", tmp_path)
    monkeypatch.setattr(bench_decision, "gpu_used_mib", lambda: None)
    monkeypatch.setattr(bench_decision, "resources", lambda *a: {})
    monkeypatch.setattr(bench_decision, "run_record", lambda *a: {})
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path / "datos"))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    catalog, given = tmp_path / "catalog.json", tmp_path / "cases.json"
    catalog.write_bytes(json.dumps({"capabilities": []}).encode("utf-8"))
    given.write_bytes(json.dumps(cases).encode("utf-8"))
    monkeypatch.setattr(sys, "argv", ["bench_decision.py", "g", "--cases", str(given), "--catalog", str(catalog),
                                      "--guardas", launcher])
    bench_decision.main()
    return [json.loads(line) for line in (tmp_path / "runs" / "g.jsonl").read_bytes().decode("utf-8").splitlines()]


def test_the_decision_bench_writes_both_numbers_with_the_guards(tmp_path, monkeypatch, oracle) -> None:
    launcher = oracle.identity["path"]
    oracle.close()
    lines = _main(tmp_path, monkeypatch, launcher, [
        {"id": "S1", "text": "saluda a Ana, que está aquí", "expect": {"kind": "text"}},
        {"id": "S2", "text": "escríbele a Ana por whatsapp", "expect": {"kind": "call", "op": "message.draft"}}])
    summary, first, second = lines[0]["summary"], lines[1], lines[2]
    assert (summary["ok"], summary["ok_seen"], summary["n"], summary["refused"]) == (1, 2, 2, 1)
    assert first["ok"] is False and first["ok_seen"] is True and first["refused"] == ["channel_not_said"]
    assert first["operation"] == "message.draft" and first["seen_kind"] == "conversation"  # the first decision kept
    assert second["ok"] is True and second["ok_seen"] is True and second["seen_operation"] == "message.draft"
    assert _Server.made[-1].closed


def test_the_decision_bench_stops_when_the_oracle_dies_and_closes_the_server(tmp_path, monkeypatch, oracle) -> None:
    launcher = oracle.identity["path"]
    oracle.close()
    with pytest.raises(bench_guardas.GuardOracleError):
        _main(tmp_path, monkeypatch, launcher, [{"id": "D1", "text": "muere", "expect": {"kind": "text"}}])
    assert _Server.made[-1].closed and not (tmp_path / "runs" / "g.jsonl").exists()
