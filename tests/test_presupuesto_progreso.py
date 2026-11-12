"""Uso-124 (RX 7600 on Vulkan, ~100 tokens/s): a turn with a web.search and web.fetch results of 8 kB ran out the fixed
24 s of a request (LlmServer.REQUEST_SECONDS) while the server was still reading, and ended with nothing said
(decision_unavailable_after_call). A request now lasts while the server advances, up to a ceiling; a server that does
not advance fails as it did. Times are scaled down: a window of 0.5 s stands for REQUEST_SECONDS."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from baxy_mind.llm_server import LlmServer

TOTAL = 2850
REPLY = {"choices": [{"finish_reason": "stop", "index": 0, "message": {"role": "assistant", "content": "Argentina"}}],
         "usage": {"prompt_tokens": TOTAL, "completion_tokens": 3}, "object": "chat.completion"}


def _sse(chunk: dict) -> bytes:
    return f"data: {json.dumps(chunk)}\n\n".encode("utf-8")


def _progress(processed: int) -> bytes:
    # As b11609 streams a chat's prompt progress (server-task.cpp:1125-1153): a role delta carrying prompt_progress.
    return _sse({"choices": [{"index": 0, "finish_reason": None, "delta": {"role": "assistant", "content": None}}],
                 "prompt_progress": {"total": TOTAL, "cache": 0, "processed": processed, "time_ms": 0}})


END = [_sse({"choices": [{"index": 0, "finish_reason": None, "delta": {"content": "Argentina"}}]}),
       _sse({"choices": [{"index": 0, "finish_reason": "stop", "delta": {}}], "usage": REPLY["usage"]}),
       b"data: [DONE]\n\n"]


class _Llama:
    """A llama-server: streams ``events`` (seconds to wait first, bytes) when asked to stream, else answers one reply
    ``answer_after`` seconds later with nothing before it, while its /slots counts as ``slots(elapsed)`` says."""

    def __init__(self, events=(), answer_after: float = 0.0, slots=None) -> None:
        self.bodies: list[bytes] = []
        self.looks = 0
        self.closed = threading.Event()
        self.started = time.monotonic()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802 - http.server's name
                outer.looks += 1
                if self.path != "/slots" or slots is None:
                    self.send_error(404)
                    return
                data = json.dumps(slots(time.monotonic() - outer.started)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
                self.close_connection = True

            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                outer.bodies.append(raw)
                outer.started = time.monotonic()
                self.close_connection = True
                try:
                    if json.loads(raw).get("stream"):
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Connection", "close")
                        self.end_headers()
                        for wait, data in events:
                            if outer.closed.wait(wait):
                                return
                            self.wfile.write(data)
                            self.wfile.flush()
                        return
                    if outer.closed.wait(answer_after):
                        return
                    data = json.dumps(REPLY).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass  # the mind closed the connection

            def log_message(self, *args) -> None:
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http.daemon_threads = True
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def server(self) -> LlmServer:
        server = LlmServer("model.gguf", "llama-server.exe")
        server.port = self.http.server_address[1]
        server._ready.set()
        server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
        server.advanced = lambda: None  # a person's turn
        return server

    def close(self) -> None:
        self.closed.set()
        self.http.shutdown()


@pytest.fixture
def scaled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LlmServer, "REQUEST_SECONDS", 0.5)
    monkeypatch.setattr(LlmServer, "REQUEST_CEILING_S", 30.0, raising=False)
    monkeypatch.setattr(LlmServer, "SLOTS_EVERY_S", 0.05, raising=False)
    monkeypatch.setattr(LlmServer, "ADVANCE_TOLD_EVERY_S", 0.0, raising=False)


BODY = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "¿quién ganó?"}],
        "tools": [], "max_tokens": 768, "temperature": 0.0, "seed": 0}
DOUBTED = {**BODY, "logprobs": True, "top_logprobs": 10}


def _reading(step: float, until: float | None = None):
    """/slots of a server that takes one more batch every ``step`` seconds, and none past ``until``."""
    def slots(elapsed: float) -> list[dict]:
        moved = min(elapsed, until) if until is not None else elapsed
        return [{"id": 0, "id_task": 7, "is_processing": True, "n_prompt_tokens": 512 * int(moved / step),
                 "next_token": [{"n_decoded": 0}]}]
    return slots


def _fails(call) -> float:
    """How long ``call`` took to end its request with a TimeoutError."""
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        call()
    return time.monotonic() - started


def _told(server: LlmServer) -> list[int]:
    told: list[int] = []
    server.advanced = lambda: told.append(1)
    return told


# The three servers, streaming (a person's turn after a call, with the voice's look-ahead).

def test_a_stream_that_keeps_reading_is_waited_for_far_past_the_window(scaled) -> None:
    fake = _Llama([(0.0, _progress(0))] + [(0.2, _progress(TOTAL * step // 12)) for step in range(1, 13)]
                  + [(0.0, data) for data in END])
    server = fake.server()
    told = _told(server)
    started = time.monotonic()
    try:
        reply = server.chat(BODY, on_text=lambda _text, _done: True)
        elapsed = time.monotonic() - started
    finally:
        fake.close()
    assert elapsed > 2.0  # 2.4 s of reading: about five windows
    assert reply["choices"][0]["message"]["content"] == "Argentina"
    assert len(told) >= 13  # the App's own window starts again with each advance


def test_a_stream_of_a_hung_server_fails_at_the_window(scaled) -> None:
    fake = _Llama([(5.0, _progress(0))])
    try:
        elapsed = _fails(lambda: fake.server().chat(BODY, on_text=lambda _text, _done: True))
    finally:
        fake.close()
    assert 0.4 <= elapsed < 1.2


def test_a_stream_that_stops_advancing_fails_one_window_after_its_last_advance(scaled) -> None:
    fake = _Llama([(0.0, _progress(0)), (0.3, _progress(512)), (0.3, _progress(1024)), (5.0, _progress(1536))])
    try:
        elapsed = _fails(lambda: fake.server().chat(BODY, on_text=lambda _text, _done: True))
    finally:
        fake.close()
    assert 1.0 <= elapsed < 1.7


def test_a_stream_that_only_pings_is_not_advancing(scaled) -> None:
    # b11609 sends an SSE comment every 30 s while a stream is silent (sse_ping_interval, server-task.h:58).
    fake = _Llama([(0.0, _progress(0))] + [(0.1, b": ping\n\n")] * 40)
    try:
        elapsed = _fails(lambda: fake.server().chat(BODY, on_text=lambda _text, _done: True))
    finally:
        fake.close()
    assert elapsed < 1.5


def test_a_long_answer_still_being_written_is_an_advance(scaled) -> None:
    written = [_sse({"choices": [{"index": 0, "finish_reason": None, "delta": {"content": "palabra "}}]})]
    fake = _Llama([(0.0, _progress(TOTAL))] + [(0.1, written[0])] * 15 + [(0.0, data) for data in END])
    started = time.monotonic()
    try:
        fake.server().chat(BODY, on_text=lambda _text, _done: True)
        elapsed = time.monotonic() - started
    finally:
        fake.close()
    assert elapsed > 1.2


def test_a_stream_past_the_ceiling_fails_even_while_it_advances(scaled, monkeypatch) -> None:
    monkeypatch.setattr(LlmServer, "REQUEST_CEILING_S", 1.0, raising=False)
    fake = _Llama([(0.1, _progress(step)) for step in range(60)] + [(0.0, data) for data in END])
    try:
        elapsed = _fails(lambda: fake.server().chat(BODY, on_text=lambda _text, _done: True))
    finally:
        fake.close()
    assert 0.9 <= elapsed < 1.7



# Revisión PCR1, A3: the socket of a stream waited a whole window for its next line however little was left of the
# request, and the RX 7600 tells its progress once a batch (~12 s): the mind could give up up to 24 s past its ceiling,
# after the App. It waits only what is left now.
def test_a_stream_ends_at_its_ceiling_not_at_the_next_line_after_it(scaled, monkeypatch) -> None:
    monkeypatch.setattr(LlmServer, "REQUEST_SECONDS", 1.0)
    monkeypatch.setattr(LlmServer, "REQUEST_CEILING_S", 2.0, raising=False)
    fake = _Llama([(0.0, _progress(0))] + [(0.9, _progress(512 * step)) for step in range(1, 6)]
                  + [(0.0, data) for data in END])
    try:
        elapsed = _fails(lambda: fake.server().chat(BODY, on_text=lambda _text, _done: True))
    finally:
        fake.close()
    assert 1.9 <= elapsed < 2.4  # the line after the ceiling comes at 2.7 s


# Revisión PCR1, A2: the RX 7600's first decision of a turn read 7,369 tokens past what its server kept (m4-cand-p0-n);
# at 50 tokens/s, the speed the 120 s ceiling was laid out for, that is 147 s, and the turn would end with nothing said
# after two minutes. The ceiling is now what the context leaves past the kept prefix, read at the slowest the window
# lets a server go on (a batch a window), with the answer: a read that long, that slow, is waited for. Scaled 1:48.
def test_a_read_of_all_the_context_leaves_is_waited_for_at_the_slowest_the_window_lets_it_go_on(monkeypatch) -> None:
    monkeypatch.setattr(LlmServer, "REQUEST_SECONDS", 0.5)
    monkeypatch.setattr(LlmServer, "REQUEST_CEILING_S", 2.5, raising=False)
    monkeypatch.setattr(LlmServer, "ANSWER_S", 1.25, raising=False)
    monkeypatch.setattr(LlmServer, "ADVANCE_TOLD_EVERY_S", 0.0, raising=False)
    read, kept = 7369, 45361
    fake = _Llama([(0.0, _progress(0))] + [(0.45, _progress(min(1024 * step, read))) for step in range(1, 9)]
                  + [(0.0, data) for data in END])
    server = fake.server()
    server.backend, server.context, server.kept = "vulkan", kept + read, kept
    server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
    started = time.monotonic()
    try:
        reply = server.chat(BODY, on_text=lambda _text, _done: True)
        elapsed = time.monotonic() - started
    finally:
        fake.close()
    assert elapsed > 3.0  # past the 2.5 s it had
    assert reply["choices"][0]["message"]["content"] == "Argentina"

# The three servers, not streaming: the decision whose token probabilities are read (LlmServer.chat), told by /slots.

def test_a_decision_that_keeps_reading_is_waited_for_far_past_the_window(scaled) -> None:
    fake = _Llama(answer_after=2.0, slots=_reading(0.2))
    server = fake.server()
    told = _told(server)
    started = time.monotonic()
    try:
        reply = server.chat(DOUBTED)
        elapsed = time.monotonic() - started
    finally:
        fake.close()
    assert elapsed > 1.9
    assert reply["choices"][0]["message"]["content"] == "Argentina"
    assert told  # the App's window starts again too


def test_a_decision_of_a_hung_server_fails_at_the_window(scaled) -> None:
    # /slots answers (b11609 answers it while it decodes), and nothing moves.
    fake = _Llama(answer_after=5.0, slots=_reading(0.1, until=0.0))
    try:
        elapsed = _fails(lambda: fake.server().chat(DOUBTED))
    finally:
        fake.close()
    assert 0.4 <= elapsed < 1.0


def test_a_decision_of_a_server_with_no_slots_endpoint_fails_at_the_window(scaled) -> None:
    fake = _Llama(answer_after=5.0)
    try:
        elapsed = _fails(lambda: fake.server().chat(DOUBTED))
    finally:
        fake.close()
    assert 0.4 <= elapsed < 1.0


def test_a_decision_that_stops_advancing_fails_one_window_after_its_last_advance(scaled) -> None:
    fake = _Llama(answer_after=5.0, slots=_reading(0.2, until=0.8))
    try:
        elapsed = _fails(lambda: fake.server().chat(DOUBTED))
    finally:
        fake.close()
    assert 1.1 <= elapsed < 1.9


def test_a_decision_past_the_ceiling_fails_even_while_it_advances(scaled, monkeypatch) -> None:
    monkeypatch.setattr(LlmServer, "REQUEST_CEILING_S", 1.0, raising=False)
    fake = _Llama(answer_after=5.0, slots=_reading(0.05))
    try:
        elapsed = _fails(lambda: fake.server().chat(DOUBTED))
    finally:
        fake.close()
    assert 0.9 <= elapsed < 1.5


def test_another_slot_moving_is_not_this_mind_advancing(scaled) -> None:
    # A shared server of several slots (measurement): only this mind's slot counts.
    def slots(elapsed: float) -> list[dict]:
        return [{"id": 0, "id_task": 1, "n_prompt_tokens": 7, "next_token": [{"n_decoded": 0}]},
                {"id": 1, "id_task": 2, "n_prompt_tokens": int(elapsed * 1000), "next_token": [{"n_decoded": 0}]}]
    fake = _Llama(answer_after=5.0, slots=slots)
    try:
        elapsed = _fails(lambda: fake.server().chat(DOUBTED))
    finally:
        fake.close()
    assert elapsed < 1.0


# What the model reads and writes does not change.

def test_a_decision_sends_the_same_bytes_it_sent() -> None:
    fake = _Llama(answer_after=0.0, slots=_reading(1.0))
    server = fake.server()
    try:
        server.chat(DOUBTED)
    finally:
        fake.close()
    assert fake.bodies == [json.dumps({**DOUBTED, "id_slot": 0, "cache_prompt": True}).encode("utf-8")]


def test_a_stream_only_adds_that_the_server_tells_its_progress() -> None:
    fake = _Llama([(0.0, data) for data in END])
    server = fake.server()
    try:
        server.chat(BODY, on_text=lambda _text, _done: True)
    finally:
        fake.close()
    sent = json.loads(fake.bodies[0])
    assert sent.pop("return_progress") is True
    assert sent == {**BODY, "stream": True, "stream_options": {"include_usage": True}, "id_slot": 0,
                    "cache_prompt": True}


def test_the_stream_and_the_plain_reply_say_the_same(scaled) -> None:
    fake = _Llama([(0.0, _progress(0)), (0.05, _progress(TOTAL))] + [(0.0, data) for data in END])
    server = fake.server()
    try:
        message = server.chat(BODY, on_text=lambda _text, _done: True)["choices"][0]
    finally:
        fake.close()
    assert message["message"] == {"role": "assistant", "content": "Argentina"}
    assert message["finish_reason"] == "stop"


# What stays as it was.

def test_a_quick_decision_never_asks_for_slots() -> None:
    fake = _Llama(answer_after=0.05, slots=_reading(1.0))
    server = fake.server()
    try:
        server.chat(DOUBTED)
    finally:
        fake.close()
    assert fake.looks == 0


def test_a_notice_keeps_its_own_short_time(scaled) -> None:
    # Mind.notice_of: the result of the call it speaks of may come meanwhile.
    fake = _Llama(answer_after=5.0, slots=_reading(0.05))
    try:
        elapsed = _fails(lambda: fake.server().chat(BODY, timeout=0.3))
    finally:
        fake.close()
    assert elapsed < 0.8


def test_with_no_budget_a_chat_is_not_watched() -> None:
    # The warm-up and a kept session's load have no budget (``deadline`` None).
    fake = _Llama(answer_after=0.05, slots=_reading(1.0))
    server = fake.server()
    server.deadline, server.advanced = None, None
    try:
        assert server.chat(BODY)["choices"][0]["message"]["content"] == "Argentina"
    finally:
        fake.close()
    assert fake.looks == 0


def test_a_heartbeat_keeps_its_fixed_budget_however_the_server_advances(scaled) -> None:
    # Nobody asked for it, and the person's next words wait for it to end.
    fake = _Llama(answer_after=5.0, slots=_reading(0.05))
    server = fake.server()
    server.advanced = None
    try:
        elapsed = _fails(lambda: server.chat(BODY))
    finally:
        fake.close()
    assert elapsed < 0.9


def test_a_heartbeats_stream_does_not_ask_for_progress() -> None:
    fake = _Llama([(0.0, data) for data in END])
    server = fake.server()
    server.advanced = None
    try:
        server.chat(BODY, on_text=lambda _text, _done: True)
    finally:
        fake.close()
    assert "return_progress" not in json.loads(fake.bodies[0])


def test_a_server_error_is_asked_again_within_the_budget(scaled, monkeypatch) -> None:
    # Uso real 2026-11-03 (F4): SERVER_ERROR_RETRIES holds for a decision told by /slots as well.
    answers = [500, 200]
    outer: list[bytes] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802 - http.server's name
            outer.append(self.rfile.read(int(self.headers["Content-Length"])))
            code = answers.pop(0)
            data = json.dumps(REPLY).encode("utf-8") if code == 200 else b'{"error":"x"}'
            self.send_response(code)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def log_message(self, *args) -> None:
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    monkeypatch.setattr(LlmServer, "SERVER_ERROR_PAUSE_S", 0.01)
    server = LlmServer("model.gguf", "llama-server.exe")
    server.port = http.server_address[1]
    server._ready.set()
    server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
    server.advanced = lambda: None
    try:
        assert server.chat(DOUBTED)["choices"][0]["message"]["content"] == "Argentina"
    finally:
        http.shutdown()
    assert len(outer) == 2


def test_a_refusal_still_reaches_the_mind_as_an_http_error(scaled) -> None:
    # Mind._next makes room when llama-server refuses a prompt past its context (HTTP 400).
    import urllib.error

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802 - http.server's name
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(400)
            self.send_header("Content-Length", "2")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"{}")
            self.close_connection = True

        def log_message(self, *args) -> None:
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    server = LlmServer("model.gguf", "llama-server.exe")
    server.port = http.server_address[1]
    server._ready.set()
    server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
    server.advanced = lambda: None
    try:
        with pytest.raises(urllib.error.HTTPError) as refused:
            server.chat(DOUBTED)
    finally:
        http.shutdown()
    assert refused.value.code == 400


# The App is told, and its window for that request starts again.

def test_each_advance_of_a_turn_tells_the_app_of_that_request(tmp_path, monkeypatch) -> None:
    from baxy_mind import __main__ as sidecar
    from baxy_mind.mind import Mind
    from test_mind_early import Server
    from test_mind_prefill import TOOLS, _say

    server = Server([_say("Hola.")])
    written: list[dict] = []
    told_at: list[int] = []

    def advancing(_nth: int) -> None:
        told_at.append(len(written))
        server.advanced()

    server.on_chat = advancing

    class ReadyMind(Mind):
        def __init__(self, _server, trace, system_one=None) -> None:
            super().__init__(server, trace, system_one)  # type: ignore[arg-type]
            self.tools = json.loads(json.dumps(TOOLS))
            self.call_tokens = [248058]

    class FakeSpeech:
        failure = ""

        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, write, spoken, on_early=None, early_s=0.0, on_wake=None) -> None:
            self.speech = FakeSpeech()

        def unsure(self, text: str) -> list:
            return []

        def stop(self) -> None:
            pass

    feed = iter([{"type": "turn.decide", "id": "r7", "text": "hola"}, None])
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(Server, "start", lambda self: None, raising=False)
    monkeypatch.setattr(Server, "close", lambda self: None, raising=False)
    monkeypatch.setattr(Server, "name", "model.gguf", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", type("Factory", (), {"REQUEST_SECONDS": 24.0,
                                                                   "__new__": lambda cls, *a, **k: server}))
    monkeypatch.setattr(sidecar, "Mind", ReadyMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: next(feed))
    monkeypatch.setattr(sidecar.protocol, "write_message", written.append)
    assert sidecar.main() == 0
    assert told_at
    assert {"type": "progress", "id": "r7"} in written
    assert written.index({"type": "progress", "id": "r7"}) < next(
        at for at, message in enumerate(written) if message.get("type") == "turn.result")



# Revisión PCR1, A3: the App's window and ceiling count from when it sent a request; the mind's counted from when it took
# it from its queue, behind whatever went first, and it could give up after the App. They count from when it arrived.
def test_a_request_s_time_counts_from_when_it_arrived_not_from_when_its_turn_came(tmp_path, monkeypatch) -> None:
    from baxy_mind import __main__ as sidecar
    from baxy_mind.mind import Mind
    from test_mind_early import Server
    from test_mind_prefill import TOOLS, _say

    server = Server([_say("Hola.")] * 6)
    left: dict[float, float] = {}  # each request's deadline, and what was left of it at its first call to the model

    def deciding(_nth: int) -> None:
        if server.deadline not in left:
            left[server.deadline] = server.deadline - time.monotonic()
            if len(left) == 1:
                time.sleep(0.5)  # the first request keeps the second waiting

    server.on_chat = deciding

    class ReadyMind(Mind):
        def __init__(self, _server, trace, system_one=None) -> None:
            super().__init__(server, trace, system_one)  # type: ignore[arg-type]
            self.tools = json.loads(json.dumps(TOOLS))
            self.call_tokens = [248058]

    class FakeSpeech:
        failure = ""

        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, write, spoken, on_early=None, early_s=0.0, on_wake=None) -> None:
            self.speech = FakeSpeech()

        def unsure(self, text: str) -> list:
            return []

        def stop(self) -> None:
            pass

    feed = iter([{"type": "turn.decide", "id": "r6", "text": "hola"},
                 {"type": "turn.decide", "id": "r7", "text": "hola"}, None])
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(Server, "start", lambda self: None, raising=False)
    monkeypatch.setattr(Server, "close", lambda self: None, raising=False)
    monkeypatch.setattr(Server, "name", "model.gguf", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", type("Factory", (), {"REQUEST_SECONDS": 24.0,
                                                                   "__new__": lambda cls, *a, **k: server}))
    monkeypatch.setattr(sidecar, "Mind", ReadyMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: next(feed))
    monkeypatch.setattr(sidecar.protocol, "write_message", lambda message: None)
    assert sidecar.main() == 0
    first, second = left.values()
    assert first > 23.5
    assert second < 24.0 - 0.4  # it waited 0.5 s behind the first

# A notice's budget: what it costs on this machine, never less than the 1.5 s it had.

def _noticed(tmp_path, timings: dict | None) -> float:
    from test_mind_final import _call, _mind, _say

    decision = _call("web_search", {"query": "vuelos a Lima"})
    if timings is not None:
        decision["timings"] = timings
    mind, server = _mind(tmp_path, [decision, _say("Busco vuelos a Lima.")])
    assert mind.decide(1, "busca vuelos a Lima")["kind"] == "action"
    asked: list[float] = []
    chat = server.chat

    def timed(body: dict, **named) -> dict:
        asked.append(named["timeout"])
        return chat(body, **named)

    server.chat = timed
    assert mind.notice_of() == "Busco vuelos a Lima."
    return asked[0]


def test_on_a_slow_server_a_notice_has_the_time_it_takes(tmp_path) -> None:
    # As the RX 7600 read and wrote it: every notice took 3.0 to 3.5 s against 1.5 s.
    slow = {"prompt_n": 106, "prompt_ms": 2600.0, "predicted_n": 38, "predicted_ms": 2200.0}
    assert 3.5 < _noticed(tmp_path, slow) < 6.0


def test_on_a_fast_server_a_notice_keeps_its_time(tmp_path) -> None:
    # As an NVIDIA GPU does: ~1,400 tokens/s of reading, ~36 of writing.
    fast = {"prompt_n": 106, "prompt_ms": 150.0, "predicted_n": 38, "predicted_ms": 1050.0}
    assert _noticed(tmp_path, fast) == 1.5


def test_the_mind_says_whether_its_notices_are_slow(tmp_path) -> None:
    from test_mind_final import _call, _mind

    def after(timings: dict) -> bool:
        decision = _call("web_search", {"query": "vuelos a Lima"})
        decision["timings"] = timings
        mind, _ = _mind(tmp_path, [decision])
        assert mind.decide(1, "busca vuelos a Lima")["kind"] == "action"
        return mind.notices_are_slow

    assert after({"prompt_n": 106, "prompt_ms": 2600.0, "predicted_n": 38, "predicted_ms": 2200.0}) is True
    assert after({"prompt_n": 106, "prompt_ms": 150.0, "predicted_n": 38, "predicted_ms": 1050.0}) is False


def test_a_notice_never_waits_past_its_limit(tmp_path) -> None:
    stuck = {"prompt_n": 106, "prompt_ms": 40000.0, "predicted_n": 38, "predicted_ms": 40000.0}
    assert _noticed(tmp_path, stuck) == 6.0


def test_a_server_that_says_no_timings_gives_a_notice_what_its_decisions_take(tmp_path) -> None:
    # Pedido del dueño 2026-11-08: «apenas cambio el modelo… ya no me habla hasta completar la misión». The translator (an API,
    # Ollama) says no llama-server timings, and the notice kept 1.5 s however long a request took there.
    import time

    from test_mind_final import _call, _mind, _say

    mind, server = _mind(tmp_path, [_call("web_search", {"query": "vuelos a Lima"}), _say("Busco vuelos a Lima.")])
    chat = server.chat

    def slow(body: dict, **named) -> dict:
        time.sleep(2.6)
        reply = chat(body, **named)
        server.took_s = 2.6  # as LlmServer.chat reads it
        return reply

    server.chat = slow
    assert mind.decide(1, "busca vuelos a Lima")["kind"] == "action"
    asked: list[float] = []

    def timed(body: dict, **named) -> dict:
        asked.append(named["timeout"])
        return chat(body, **named)

    server.chat = timed
    assert mind.notice_of() == "Busco vuelos a Lima."
    assert 2.6 * 1.25 <= asked[0] <= 6.0
    assert mind.notices_are_slow


def test_a_long_read_or_no_timings_says_nothing_of_a_notice(tmp_path) -> None:
    assert _noticed(tmp_path, None) == 1.5
    assert _noticed(tmp_path, {"prompt_n": 2850, "prompt_ms": 29000.0, "predicted_n": 30, "predicted_ms": 1700.0}) == 1.5
