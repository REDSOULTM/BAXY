"""Held-out: a read ahead that gave way (Yielded) to a request that does not use the model is read again once that
request is answered and nothing else waits (Mind.gave_way, __main__.main)."""
import json
import threading
import time
import urllib.error
from collections import defaultdict
from pathlib import Path

import pytest
from jinja2.sandbox import ImmutableSandboxedEnvironment

from baxy_mind.llm_server import Yielded
from baxy_mind.mind import CLOCK_MARK, Mind

WAIT_S = 2.0     # the longest a step of the fake App waits for the sidecar
SETTLE_S = 0.3   # time for the loop to reach its next wait after a reply

TEMPLATE = (Path(__file__).parent / "fixtures" / "qwen35_chat_template.jinja").read_text(encoding="utf-8")
TOOLS = [{"type": "function", "function": {"name": "ask_user", "description": "Ask the person.", "parameters": {
    "type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}}]


# ---- Mind.prefill -----------------------------------------------------------------------------------------------

def _raise(message: str) -> None:
    raise ValueError(message)


class TemplateServer:
    """The model server's double: the real chat template, canned replies and a read ahead that may raise."""

    context = 53248

    def __init__(self, replies: list) -> None:
        environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        environment.filters["tojson"] = lambda value, **_: json.dumps(value, ensure_ascii=False)
        environment.globals["raise_exception"] = _raise
        self._template = environment.from_string(TEMPLATE)
        self.replies = replies
        self.errors: list[Exception] = []
        self.prefilled: list[str] = []

    def _render(self, body: dict) -> str:
        messages = [{**m, "tool_calls": [{**c, "function": {**c["function"],
                                                           "arguments": json.loads(c["function"]["arguments"])}}
                                         for c in m["tool_calls"]]} if m.get("tool_calls") else m
                    for m in body["messages"]]
        return self._template.render(messages=messages, tools=body.get("tools"), add_generation_prompt=True,
                                     enable_thinking=False)

    def chat(self, body: dict, **_) -> dict:
        return self.replies.pop(0)

    def template(self, body: dict, timeout: float = 10.0) -> str:
        return self._render(body)

    def prefill(self, prompt: str, timeout: float = 60.0) -> dict:
        self.prefilled.append(prompt)
        if self.errors:
            raise self.errors.pop(0)
        return {"timings": {"prompt_n": 10, "prompt_ms": 1.0, "predicted_n": 1, "predicted_ms": 0.0}}

    def tokenize(self, text: str) -> list[int]:
        return [0] * (len(text) // 4)


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _mind_after_a_turn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Mind, TemplateServer]:
    monkeypatch.setattr(Mind, "_clock", lambda self: f"{CLOCK_MARK} miércoles 28/10/2026 21:10 hora local]")
    server = TemplateServer([_say("Hola, aquí estoy.")])
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.tools = json.loads(json.dumps(TOOLS))
    mind.call_tokens = [248058]
    mind.decide(1, "hola")
    return mind, server


def _warm_rows(tmp_path: Path) -> list[dict]:
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if r["stage"] == "warm.history"]


def test_a_read_after_a_turn_that_gives_way_says_so_and_is_kept_as_unclocked(tmp_path: Path,
                                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    mind, server = _mind_after_a_turn(tmp_path, monkeypatch)
    assert mind.gave_way is None
    server.errors.append(Yielded("a request waits"))
    assert mind.prefill() is False
    assert mind.gave_way is False
    row = _warm_rows(tmp_path)[-1]
    assert row.get("yielded") is True and "failure" not in row


def test_the_wake_s_read_that_gives_way_is_kept_as_clocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mind, server = _mind_after_a_turn(tmp_path, monkeypatch)
    server.errors.append(Yielded("a request waits"))
    assert mind.prefill(clock=True) is False
    assert mind.gave_way is True
    row = _warm_rows(tmp_path)[-1]
    assert row.get("yielded") is True and row.get("clock") is True and "failure" not in row


def test_any_later_read_forgets_that_one_gave_way(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mind, server = _mind_after_a_turn(tmp_path, monkeypatch)
    server.errors.append(Yielded("a request waits"))
    mind.prefill()
    assert mind.gave_way is False
    assert mind.prefill() is True  # read to its end
    assert mind.gave_way is None
    server.errors.append(Yielded("a request waits"))
    mind.prefill(clock=True)
    assert mind.gave_way is True
    monkeypatch.setenv("BAXY_RENEW_PREFILL", "0")  # a read that does not even start resets it too
    assert mind.prefill() is False
    assert mind.gave_way is None


@pytest.mark.parametrize("error", [urllib.error.URLError("refused")])
def test_a_read_that_fails_another_way_is_not_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   error: Exception) -> None:
    mind, server = _mind_after_a_turn(tmp_path, monkeypatch)
    server.errors.append(error)
    assert mind.prefill() is False
    assert mind.gave_way is None
    row = _warm_rows(tmp_path)[-1]
    assert row["failure"] == type(error).__name__ and not row.get("yielded")


def test_a_read_past_its_budget_is_kept_and_says_it_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # uso-124: what the slot read stays there, so another round goes on from it (mind.PREFILL_ROUNDS); until uso-124 it
    # was dropped like any failure, and on an RX 7600 the next decision read it and ended with nothing said.
    mind, server = _mind_after_a_turn(tmp_path, monkeypatch)
    server.errors.append(TimeoutError("spent"))
    assert mind.prefill() is False
    assert mind.gave_way is False
    row = _warm_rows(tmp_path)[-1]
    assert row["failure"] == "TimeoutError" and not row.get("yielded")


# ---- the sidecar's loop ------------------------------------------------------------------------------------------

def _sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcomes: list[str], steps: list[tuple]) -> list[str]:
    """Runs __main__.main() with fakes. ``outcomes``: what each Mind.prefill does in turn («read» to its end, «yield»
    once a request is queued, «fail» once a request is queued, without giving way); past the list, «read».
    «yield-all» gives way only once the step «queued» is reached. ``steps``: the App's messages as (flag to wait for,
    pause, message); the message «wake» is the voice hearing «Baxy». Returns what the loop did: each reply as «type:id» and each read ahead as «prefill:<clock>»."""
    from baxy_mind import __main__ as sidecar
    log: list[str] = []
    flags: defaultdict[str, threading.Event] = defaultdict(threading.Event)
    servers: list = []
    voices: list = []
    reads: list[bool] = []

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            servers.append(self)

        def start(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeMind:
        foresee = None
        tools = [{"type": "function"}]
        _beat = None
        _turn = None

        def __init__(self, *args) -> None:
            self.gave_way: bool | None = None

        def decide(self, request_id, text, pending, unsure=None, front=None, named=None):
            return {"type": "turn.result", "id": request_id}

        def new_session(self) -> None:
            pass

        def export_session(self) -> list:
            return []

        def prefill(self, clock: bool = False) -> bool:
            self.gave_way = None
            reads.append(clock)
            log.append(f"prefill:{clock}")
            outcome = outcomes.pop(0) if outcomes else "read"
            flags[f"prefill{len(reads)}"].set()
            if outcome == "read":
                return True
            until = time.monotonic() + WAIT_S
            while not servers[0].yields() and time.monotonic() < until:
                time.sleep(0.01)
            if outcome == "yield-all":
                flags["queued"].wait(WAIT_S)  # every request of the batch is queued before it gives way
            if outcome.startswith("yield") and servers[0].yields():
                self.gave_way = clock
            return False

    class FakeSpeech:
        failure = ""  # a voice that can speak (the hello offers voice.speak)
        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = FakeSpeech()
            self.on_wake = kwargs.get("on_wake")
            voices.append(self)

        def unsure(self, text: str) -> list:
            return []

        def stop(self) -> None:
            pass

    def read() -> dict | None:
        while True:
            after, pause, message = steps.pop(0)
            if after:
                flags[after].wait(WAIT_S)
            if pause:
                time.sleep(pause)
            if message == "wake":
                voices[0].on_wake()
                continue
            if message == "queued":  # read() runs again only once the message before is in the queue
                flags["queued"].set()
                continue
            return message

    def write(message: dict) -> None:
        if message.get("type") == "hello":
            return
        name = f"{message.get('type')}:{message.get('id')}"
        log.append(name)
        flags[f"wrote:{name}"].set()

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.delenv("BAXY_RENEW_WAKE_WARM", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", read)
    monkeypatch.setattr(sidecar.protocol, "write_message", write)
    assert sidecar.main() == 0
    return log


def _decide(request_id: int) -> dict:
    return {"type": "turn.decide", "id": request_id, "text": "hola"}


def _export(request_id: int) -> dict:
    return {"type": "session.export", "id": request_id}


def test_a_read_that_gave_way_to_the_export_after_a_turn_is_read_again(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    log = _sidecar(tmp_path, monkeypatch, ["yield"], [
        (None, 0, _decide(1)), ("prefill1", 0, _export(2)), ("prefill2", 0, None)])
    assert log == ["turn.result:1", "prefill:False", "session.exported:2", "prefill:False"]


def test_a_read_that_gave_way_to_a_new_session_is_read_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _sidecar(tmp_path, monkeypatch, ["yield"], [
        (None, 0, _decide(1)), ("prefill1", 0, {"type": "session.new", "id": 2}), ("prefill2", 0, None)])
    assert log == ["turn.result:1", "prefill:False", "session.ready:2", "prefill:False"]


def test_the_read_again_waits_until_every_queued_request_is_answered(tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    # The read gives way once three requests are queued; it is read again after all of them, not between them.
    log = _sidecar(tmp_path, monkeypatch, ["yield-all"], [
        (None, 0, _decide(1)), ("prefill1", 0, _export(2)), (None, 0, {"type": "session.new", "id": 3}),
        (None, 0, _export(4)), (None, 0, "queued"), ("prefill2", 0, None)])
    assert log == ["turn.result:1", "prefill:False", "session.exported:2", "session.ready:3", "session.exported:4",
                   "prefill:False"]


def test_a_read_that_gives_way_twice_is_read_until_it_ends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _sidecar(tmp_path, monkeypatch, ["yield", "yield", "read"], [
        (None, 0, _decide(1)), ("prefill1", 0, _export(2)), ("prefill2", 0, _export(3)), ("prefill3", 0, None)])
    assert log == ["turn.result:1", "prefill:False", "session.exported:2", "prefill:False", "session.exported:3",
                   "prefill:False"]


def test_the_wake_s_read_that_gave_way_is_read_again_with_its_clock(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    log = _sidecar(tmp_path, monkeypatch, ["yield"], [
        (None, 0, "wake"), ("prefill1", 0, _export(1)), ("prefill2", 0, None)])
    assert log == ["prefill:True", "session.exported:1", "prefill:True"]


def test_a_read_that_did_not_give_way_is_not_read_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _sidecar(tmp_path, monkeypatch, ["read"], [
        (None, 0, _decide(1)), ("prefill1", 0, _export(2)), ("wrote:session.exported:2", SETTLE_S, None)])
    assert log == ["turn.result:1", "prefill:False", "session.exported:2"]


def test_a_read_that_failed_another_way_is_not_read_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _sidecar(tmp_path, monkeypatch, ["fail"], [
        (None, 0, _decide(1)), ("prefill1", 0, _export(2)), ("wrote:session.exported:2", SETTLE_S, None)])
    assert log == ["turn.result:1", "prefill:False", "session.exported:2"]


def test_a_read_again_that_ends_is_not_read_a_third_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _sidecar(tmp_path, monkeypatch, ["yield", "read"], [
        (None, 0, _decide(1)), ("prefill1", 0, _export(2)), ("prefill2", SETTLE_S, _export(3)),
        ("wrote:session.exported:3", SETTLE_S, None)])
    assert log == ["turn.result:1", "prefill:False", "session.exported:2", "prefill:False", "session.exported:3"]


def test_a_read_that_gave_way_to_a_turn_is_left_to_that_turn_s_own_read(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    # Not read again before the turn is answered; the turn's own read after it is the only one.
    log = _sidecar(tmp_path, monkeypatch, ["yield", "read"], [
        (None, 0, _decide(1)), ("prefill1", 0, _decide(2)), ("prefill2", SETTLE_S, None)])
    assert log == ["turn.result:1", "prefill:False", "turn.result:2", "prefill:False"]
