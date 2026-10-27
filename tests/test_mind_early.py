"""BAXY Renew al máximo, palancas 2 y 5 (src/baxy_mind/early.py): a decision made while the voice waits for the end of
the request is used only when it is the one the App's request would make, and one put back leaves the mind, its trace
and the slot exactly as they were, as if it never ran. The double (test_mind_prefill.SlotServer) renders prompts with
the model's own chat template and keeps one slot as llama-server does."""
import copy
import json
import threading
import time
from pathlib import Path

import pytest

from baxy_mind import early
from baxy_mind.early import SHARED, Anticipation, set_aside
from baxy_mind.mind import CLOCK_MARK, UNSURE_NOTE, Mind
from test_mind_prefill import TOOLS, SlotServer, _call, _say

MINUTE = "jueves 22/10/2026 18:30 hora local, UTC-03:00"


class Server(SlotServer):
    """The double with LlmServer.resident: the text a prefill left in the slot, until any other call uses it."""

    REQUEST_SECONDS = 24.0

    def __init__(self, replies: list, delay: float = 0.0) -> None:
        super().__init__(replies)
        self.resident: str | None = None
        self.delay = delay
        self.on_chat = None

    def chat(self, body: dict, **kwargs) -> dict:
        self.resident = None
        if self.on_chat is not None:
            self.on_chat(len(self.bodies))
        if self.delay:
            time.sleep(self.delay)
        return super().chat(body, **kwargs)

    def prefill(self, prompt: str, timeout: float = 60.0) -> dict:
        if prompt == self.resident:
            return {"resident": True}
        reply = super().prefill(prompt, timeout)
        self.resident = prompt
        return reply


def _mind(path: Path, replies: list, monkeypatch: pytest.MonkeyPatch, delay: float = 0.0) -> tuple[Mind, Server]:
    monkeypatch.setattr(Mind, "_clock_time", staticmethod(lambda: MINUTE))
    server = Server(replies, delay)
    path.mkdir(parents=True, exist_ok=True)
    mind = Mind(server, path / "turns.jsonl")  # type: ignore[arg-type]
    mind.tools = json.loads(json.dumps(TOOLS))
    mind.call_tokens = [248058]
    return mind, server


def _before(mind: Mind) -> None:
    """A turn that opened Paint and ended in words, read ahead as the sidecar does after it."""
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "readback", "observed": {
        "appId": "Paint", "foreground": True}}))
    assert mind.prefill() is True


def _replies(*after: dict) -> list:
    return [_call("app_open", {"appId": "Paint", "foreground": True}), _say("Abrí Paint."), *after]


def _rows(path: Path) -> list[dict]:
    trace = path / "turns.jsonl"
    return [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()] if trace.exists() else []


def _plain(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in ("t", "ms", "early")}


def _state(mind: Mind) -> str:
    """Everything of the mind an early decision could change, as text (the shared references aside, but the tools)."""
    kept = set_aside(mind)
    kept.update({k: copy.deepcopy(getattr(mind, k)) for k in ("tools", "names", "wire_to_op", "risk", "effects",
                                                             "constants")})
    return json.dumps(kept, ensure_ascii=False, sort_keys=True, default=str)


def test_a_used_early_decision_is_the_decision_the_request_would_make(tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    control, plain = _mind(tmp_path / "control", _replies(_say("Sí, Paint está abierto.")), monkeypatch)
    _before(control)
    expected = control.decide(3, "¿ya lo abriste?")

    mind, server = _mind(tmp_path / "early", _replies(_say("Sí, Paint está abierto.")), monkeypatch)
    _before(mind)
    told: list = []
    mind.foresee = lambda text, done: told.append((text, done)) or True
    anticipation = Anticipation(mind)
    rows_before = _rows(tmp_path / "early")
    assert anticipation.speculate(1, "¿ya lo abriste?") is True
    # Decided, and nothing of it is out: no trace row, nothing told to the voice's look-ahead.
    assert len(server.bodies) == len(plain.bodies) and _rows(tmp_path / "early") == rows_before and told == []
    used = anticipation.settle("turn.decide", {"type": "turn.decide", "id": 3, "text": "¿ya lo abriste?"},
                               time.perf_counter())
    assert used == expected
    # The model got the same bodies and read the same text; the conversation and every row are the same.
    assert server.bodies == plain.bodies and server.prompts == plain.prompts and server.read == plain.read
    assert mind.conversation == control.conversation and _state(mind) == _state(control)
    rows, control_rows = _rows(tmp_path / "early"), _rows(tmp_path / "control")
    assert [_plain(r) for r in rows] == [_plain(r) for r in control_rows]
    assert rows[-1]["early"]["hit"] is True and rows[-1]["early"]["saved_ms"] >= 0
    # Its words reach the voice's look-ahead once it is used, as an answer that came whole does.
    assert told == [("Sí, Paint está abierto.", True)]


@pytest.mark.parametrize("how", ["cancelled", "expired", "request", "superseded"])
def test_a_decision_put_back_leaves_the_mind_the_trace_and_the_slot_as_if_it_never_ran(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    control, plain = _mind(tmp_path / "control", _replies(_say("Listo, abro Spotify.")), monkeypatch)
    _before(control)
    mind, server = _mind(tmp_path / "early", _replies(_say("Sí, Paint está abierto."), _say("Listo, abro Spotify.")),
                         monkeypatch)
    _before(mind)
    told: list = []
    mind.foresee = lambda text, done: told.append((text, done)) or True
    state, slot, resident, trace = _state(mind), server.slot, server.resident, _rows(tmp_path / "early")
    anticipation = Anticipation(mind, hold_s=0.0 if how == "expired" else 5.0)
    assert anticipation.speculate(1, "¿ya lo abriste?") is True
    assert server.slot != slot and mind.conversation != control.conversation  # it did decide, in the slot
    if how == "cancelled":
        anticipation.cancel(1)
        anticipation.drop("cancelled", 1)
    elif how == "expired":
        anticipation.expire()
    elif how == "request":
        assert anticipation.settle("session.export", {"type": "session.export", "id": 9}, time.perf_counter()) is None
    else:
        monkeypatch.setattr(anticipation, "idle", lambda: False)  # the next one is not made: only the put back shows
        assert anticipation.speculate(2, "¿ya lo abriste? y Spotify") is False
    # As if it never ran: the mind's state, the trace, the voice's look-ahead, and the slot holds the read ahead again.
    assert _state(mind) == state and _rows(tmp_path / "early") == trace and told == []
    assert server.slot == slot and server.resident == resident
    assert mind._turned is True  # the one fact kept: the slot read a person's words, so the warm-up never saves it
    # The next request is decided as it would have been: the same body, the same text read, the same row.
    real = anticipation.decide(3, "abre spotify", None)
    expected = control.decide(3, "abre spotify")
    assert real == expected
    assert server.bodies[-1] == plain.bodies[-1] and server.read[-1] == plain.read[-1]
    rows, control_rows = _rows(tmp_path / "early"), _rows(tmp_path / "control")
    assert [_plain(r) for r in rows] == [_plain(r) for r in control_rows]
    assert rows[-1]["early"] == {"hit": False, "reason": how, "discarded": 1}


def test_a_cancel_while_it_decides_stops_it_before_its_next_call(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    # A call written as text is a failed call: the model is asked again for words. The person goes on speaking while
    # the first call runs, so the second is never made.
    mind, server = _mind(tmp_path, _replies(_say("<tool_call>\n<function=app_open>"), _say("No pude.")), monkeypatch)
    _before(mind)
    state, slot, trace = _state(mind), server.slot, _rows(tmp_path)
    anticipation = Anticipation(mind)
    calls_before = len(server.bodies)
    server.on_chat = lambda n: anticipation.cancel(1) if n == calls_before else None
    assert anticipation.speculate(1, "¿ya lo abriste?") is False
    assert len(server.bodies) == calls_before + 1  # the call in flight ends; no other is made
    assert _state(mind) == state and _rows(tmp_path) == trace and server.slot == slot
    assert anticipation.speculate(1, "¿ya lo abriste?") is False  # a transcript taken back is never decided again


@pytest.mark.parametrize("change", ["text", "pending", "clock"])
def test_a_request_that_differs_is_decided_as_always(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                    change: str) -> None:
    pending = {"operation": "app.close", "arguments": {"appId": "Paint"}} if change == "pending" else None
    text = "¿ya lo cerraste?" if change == "text" else "¿ya lo abriste?"
    control, plain = _mind(tmp_path / "control", _replies(_say("No lo he mirado.")), monkeypatch)
    _before(control)
    mind, server = _mind(tmp_path / "early", _replies(_say("Todavía no lo miro."), _say("No lo he mirado.")),
                         monkeypatch)
    _before(mind)
    anticipation = Anticipation(mind)
    assert anticipation.speculate(1, "¿ya lo abriste?") is True
    if change == "clock":
        monkeypatch.setattr(Mind, "_clock_time", staticmethod(lambda: MINUTE.replace("18:30", "18:31")))
    message = {"type": "turn.decide", "id": 3, "text": text, **({"pendingConfirmation": pending} if pending else {})}
    assert anticipation.settle("turn.decide", message, time.perf_counter()) is None
    real = anticipation.decide(3, text, pending)
    assert real == control.decide(3, text, pending)
    assert server.bodies[-1] == plain.bodies[-1]
    rows = _rows(tmp_path / "early")
    assert [_plain(r) for r in rows] == [_plain(r) for r in _rows(tmp_path / "control")]
    assert rows[-1]["early"] == {"hit": False, "reason": change, "discarded": 1}


def test_nothing_is_decided_early_while_a_call_waits_or_a_heartbeat_is_open(tmp_path: Path,
                                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"})], monkeypatch)
    mind.decide(1, "abre paint")  # its call waits for the App's result
    anticipation = Anticipation(mind)
    calls, state = len(server.bodies), _state(mind)
    assert anticipation.speculate(1, "¿ya?") is False and _state(mind) == state
    mind._turn, mind._beat = None, {"conv": [], "queue": []}
    assert anticipation.speculate(2, "¿ya?") is False
    assert anticipation.wake() is False
    assert len(server.bodies) == calls and server.prefilled == []


def test_a_question_of_the_model_may_be_answered_early(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = [_call("ask_user", {"question": "¿Cuál?"}), _call("app_open", {"appId": "Paint"})]
    control, plain = _mind(tmp_path / "control", json.loads(json.dumps(replies)), monkeypatch)
    control.decide(1, "abre eso")
    mind, server = _mind(tmp_path / "early", json.loads(json.dumps(replies)), monkeypatch)
    mind.decide(1, "abre eso")
    anticipation = Anticipation(mind)
    assert anticipation.speculate(1, "paint") is True
    used = anticipation.settle("turn.decide", {"type": "turn.decide", "id": 2, "text": "paint"}, time.perf_counter())
    assert used == control.decide(2, "paint") and server.bodies == plain.bodies
    assert _state(mind) == _state(control)


def test_the_early_decision_hides_the_wait_measured_on_a_synthetic_clock(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    # The model decides in DECIDE s. The voice tells the words EARLY_SILENCE_S into the silence and the App asks
    # AHEAD s later (END_SILENCE_S − EARLY_SILENCE_S and the final decoding): the reply is ready DECIDE − AHEAD after
    # the request instead of DECIDE. Scaled down tenfold so the test is fast.
    decide, ahead = 0.10, 0.07
    control, _ = _mind(tmp_path / "control", _replies(_say("Sí.")), monkeypatch, delay=0.0)
    _before(control)
    control.server.delay = decide
    began = time.perf_counter()
    control.decide(3, "¿ya lo abriste?")
    plain_latency = time.perf_counter() - began

    mind, server = _mind(tmp_path / "early", _replies(_say("Sí.")), monkeypatch)
    _before(mind)
    server.delay = decide
    anticipation = Anticipation(mind)
    asked = {}

    def request() -> None:
        time.sleep(ahead)
        asked["at"] = time.perf_counter()

    app = threading.Thread(target=request)
    began = time.perf_counter()
    app.start()
    anticipation.speculate(1, "¿ya lo abriste?")
    app.join()
    anticipation.settle("turn.decide", {"type": "turn.decide", "id": 3, "text": "¿ya lo abriste?"}, asked["at"])
    early_latency = time.perf_counter() - asked["at"]
    # Without it the request waits the whole decision; with it, only what was left of it.
    assert plain_latency >= decide and early_latency <= plain_latency - ahead + 0.02
    row = _rows(tmp_path / "early")[-1]["early"]
    assert row["hit"] is True and ahead * 1000 - 5 <= row["ahead_ms"] <= ahead * 1000 + 30
    assert row["saved_ms"] == row["ahead_ms"] and 0 < row["waited_ms"] <= (decide - ahead) * 1000 + 30


def test_hearing_the_wake_word_reads_the_next_turns_clock_ahead_and_the_prompt_does_not_change(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control, plain = _mind(tmp_path / "control", _replies(_say("Sí.")), monkeypatch)
    _before(control)
    control.decide(3, "¿ya lo abriste?")
    mind, server = _mind(tmp_path / "warm", _replies(_say("Sí.")), monkeypatch)
    _before(mind)
    anticipation = Anticipation(mind)
    assert anticipation.wake() is True
    warmed = server.prefilled[-1]
    assert warmed.endswith(f"<|im_start|>user\n{mind._clock()}<|im_end|>\n") and MINUTE in warmed
    assert mind._clock().startswith(CLOCK_MARK)
    reads = len(server.read)
    assert anticipation.wake() is True and len(server.read) == reads  # the same text again is not sent
    mind.decide(3, "¿ya lo abriste?")
    # The same prompt; the decision read only the person's words.
    assert server.bodies == plain.bodies and server.prompts[-1].startswith(warmed)
    assert server.read[-1] == len(server.prompts[-1]) - len(warmed) < plain.read[-1]
    rows = [r for r in _rows(tmp_path / "warm") if r["stage"] == "warm.history"]
    assert rows[-1]["clock"] is True and "text" not in rows[-1]


def test_the_wake_warm_and_the_early_decision_have_their_switches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_RENEW_EARLY", raising=False)
    monkeypatch.delenv("BAXY_RENEW_WAKE_WARM", raising=False)
    assert early.early_silence() == early.EARLY_SILENCE_S and early.wake_warm() is True
    for setting, expected in (("0", None), ("1", 0.2), ("0.35", 0.35), ("0.9", 0.2), ("x", 0.2)):
        monkeypatch.setenv("BAXY_RENEW_EARLY", setting)
        assert early.early_silence() == expected
    monkeypatch.setenv("BAXY_RENEW_WAKE_WARM", "0")
    assert early.wake_warm() is False


def test_shared_attributes_are_the_ones_a_decision_never_writes() -> None:
    # Every attribute a Mind has is either set aside or shared; a new one is set aside by default.
    mind = Mind(Server([]), Path("unused.jsonl"))  # type: ignore[arg-type]
    assert {"conversation", "_turn", "_beat", "_ids", "_ran", "_tokens", "_refs"} <= set(set_aside(mind))
    assert SHARED >= {"server", "system_one", "foresee", "_turned", "_holding"}


@pytest.mark.parametrize("unsure", [[], [("hola", 0.3)]])
def test_the_sidecar_answers_the_app_with_the_decision_made_early_unless_the_ear_was_unsure(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsure: list) -> None:
    from baxy_mind import __main__ as sidecar
    server = Server([_say("Hola, ¿qué necesitas?"), _say("¿Me lo repites?")])
    asked: list[str] = []
    written: list[dict] = []
    voice: dict = {}

    class EarlyMind(Mind):
        def __init__(self, _server, trace, system_one=None) -> None:
            super().__init__(server, trace, system_one)  # type: ignore[arg-type]
            self.tools = json.loads(json.dumps(TOOLS))
            self.call_tokens = [248058]

    class FakeSpeech:
        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, write, spoken, on_early=None, early_s=0.0, on_wake=None) -> None:
            voice.update(on_early=on_early, early_s=early_s, on_wake=on_wake)
            self.speech = FakeSpeech()

        def unsure(self, text: str) -> list:
            asked.append(text)
            return unsure

        def stop(self) -> None:
            pass

    def incoming():
        # The voice heard «hola» early, then the App asks for it: the loop decides on the first and answers the second.
        voice["on_early"](1, "hola")
        yield {"type": "turn.decide", "id": "r1", "text": "hola"}
        yield None

    feed = incoming()
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.delenv("BAXY_RENEW_EARLY", raising=False)
    monkeypatch.setattr(Mind, "_clock_time", staticmethod(lambda: MINUTE))
    monkeypatch.setattr(Server, "start", lambda self: None, raising=False)
    monkeypatch.setattr(Server, "close", lambda self: None, raising=False)
    monkeypatch.setattr(Server, "name", "model.gguf", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")  # the server is a fake
    monkeypatch.setattr(sidecar, "LlmServer", type("Factory", (), {"REQUEST_SECONDS": 24.0,
                                                                   "__new__": lambda cls, *a, **k: server}))
    monkeypatch.setattr(sidecar, "Mind", EarlyMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: next(feed))
    monkeypatch.setattr(sidecar.protocol, "write_message", written.append)
    assert sidecar.main() == 0
    assert voice["early_s"] == early.EARLY_SILENCE_S and voice["on_wake"] is not None
    replies = [m for m in written if m.get("type") == "turn.result"]
    assert asked == ["hola"]
    rows = _rows(tmp_path / "BAXY" / "renew")
    if not unsure:
        assert replies == [{"type": "turn.result", "id": "r1", "kind": "conversation", "operation": None,
                            "arguments": None, "question": "", "reply": "Hola, ¿qué necesitas?"}]
        assert len(server.bodies) == 1  # decided once, early
        assert [r["stage"] for r in rows] == ["turn.decide", "warm.history"] and rows[0]["early"]["hit"] is True
        return
    # The early decision did not read the note: it is put back, and the request decides with it.
    assert [m["reply"] for m in replies] == ["¿Me lo repites?"] and replies[0]["id"] == "r1"
    messages = server.bodies[1]["messages"]
    assert messages[-1] == {"role": "user", "content": "hola"}
    assert messages[-2]["content"].endswith(UNSURE_NOTE.format(words="«hola» (30 %)"))
    assert [m["content"] for m in messages if m["role"] == "user"].count("hola") == 1
    assert rows[0]["stage"] == "turn.decide" and rows[0]["early"]["hit"] is False
    assert rows[0]["early"]["reason"] == "unsure"
