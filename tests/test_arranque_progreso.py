"""Uso 84 (AMD RX 7600 on Vulkan, 2026-11-04): a cold start read its 45,240-token prefix in 167.5 s against fixed
budgets of 180 s (the App's conductor) and 600 s (the mind). The warm-up is waited for while llama-server advances
through the prompt (its own progress, return_progress at b11609), and fails only when it stops advancing or past a
high ceiling. The times here are scaled down: a stall window of 0.5 s stands for PREFIX_STALL_S."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from baxy_mind.llm_server import LlmServer

TOTAL = 45240


def _progress(processed: int) -> bytes:
    # As b11609 streams a chat's prompt progress (server-task.cpp:1125-1153): a role delta carrying prompt_progress.
    chunk = {"choices": [{"index": 0, "finish_reason": None, "delta": {"role": "assistant", "content": None}}],
             "prompt_progress": {"total": TOTAL, "cache": 0, "processed": processed, "time_ms": 0}}
    return f"data: {json.dumps(chunk)}\n\n".encode("utf-8")


END = [f"data: {json.dumps(chunk)}\n\n".encode("utf-8") for chunk in (
    {"choices": [{"index": 0, "finish_reason": "length", "delta": {"content": "H"}}]},
    {"choices": [], "usage": {"prompt_tokens": TOTAL, "completion_tokens": 1}})] + [b"data: [DONE]\n\n"]


class _Llama:
    """A llama-server's /v1/chat/completions that streams `events`, each (seconds to wait first, bytes)."""

    def __init__(self, events: list[tuple[float, bytes]]) -> None:
        self.bodies: list[dict] = []
        self.closed = threading.Event()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                outer.bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    for wait, data in events:
                        if outer.closed.wait(wait):
                            return
                        self.wfile.write(data)
                        self.wfile.flush()
                except OSError:
                    pass  # the mind closed the connection

            def log_message(self, *args) -> None:
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        serve = self.http.serve_forever
        threading.Thread(target=serve, daemon=True).start()

    def server(self) -> LlmServer:
        server = LlmServer("model.gguf", "llama-server.exe")
        server.port = self.http.server_address[1]
        server._ready.set()
        return server

    def close(self) -> None:
        self.closed.set()
        self.http.shutdown()


@pytest.fixture
def scaled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LlmServer, "PREFIX_STALL_S", 0.5)
    monkeypatch.setattr(LlmServer, "PREFIX_CEILING_S", 30.0)


WARM = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "hola"}], "max_tokens": 1}


def test_a_cold_start_that_keeps_advancing_is_waited_for_far_past_the_stall_window(scaled) -> None:
    # 2.4 s of reading (about five stall windows: 200 s against a budget of 40 s), one batch every 0.15 s.
    steps = 16
    fake = _Llama([(0.0, _progress(0))] + [(0.15, _progress(TOTAL * step // steps)) for step in range(1, steps + 1)]
                  + [(0.0, data) for data in END])
    told: list[tuple[int, int]] = []
    started = time.monotonic()
    try:
        reply = fake.server().read_prefix(WARM, lambda done, total: told.append((done, total)))
    finally:
        fake.close()
    assert time.monotonic() - started > 2.0
    assert reply["usage"]["prompt_tokens"] == TOTAL
    assert fake.bodies[0]["stream"] is True and fake.bodies[0]["return_progress"] is True
    assert [done for done, _ in told] == [TOTAL * step // steps for step in range(steps + 1)]
    assert {total for _, total in told} == {TOTAL}


def test_a_server_that_goes_silent_mid_prompt_fails_at_the_stall_window(scaled) -> None:
    fake = _Llama([(0.0, _progress(0)), (0.1, _progress(2048)), (5.0, _progress(4096))] + [(0.0, d) for d in END])
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            fake.server().read_prefix(WARM)
    finally:
        fake.close()
    assert time.monotonic() - started < 2.0


def test_a_server_that_only_pings_without_advancing_fails_at_the_stall_window(scaled) -> None:
    # b11609 sends an SSE comment every 30 s while a stream is silent (sse_ping_interval): alive, but reading nothing.
    pings = [(0.1, b": ping\n\n")] * 40
    fake = _Llama([(0.0, _progress(0)), (0.1, _progress(2048))] + pings + [(0.0, d) for d in END])
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            fake.server().read_prefix(WARM)
    finally:
        fake.close()
    assert time.monotonic() - started < 2.0


def test_a_prompt_read_past_the_ceiling_fails_even_while_it_advances(scaled, monkeypatch) -> None:
    monkeypatch.setattr(LlmServer, "PREFIX_CEILING_S", 1.0)
    fake = _Llama([(0.1, _progress(step)) for step in range(60)] + [(0.0, d) for d in END])
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            fake.server().read_prefix(WARM)
    finally:
        fake.close()
    assert 1.0 <= time.monotonic() - started < 2.5


def test_the_warm_up_reads_the_prefix_by_progress_and_tells_each_advance(tmp_path) -> None:
    from baxy_mind.mind import Mind

    class Server(LlmServer):
        def __init__(self) -> None:
            super().__init__("model.gguf", "llama-server.exe")
            self.read: list[dict] = []

        def tokenize(self, text: str) -> list[int]:
            return [248058]

        def prefix_key(self, warm) -> str:
            return "key"

        def restore_prefix(self, key: str) -> None:
            return None

        def save_prefix(self, key: str, facts: dict) -> bool:
            return True

        def read_prefix(self, body: dict, on_progress=None) -> dict:
            self.read.append(body)
            on_progress(2048, TOTAL)
            return {"choices": [{"message": {"content": "H"}}], "usage": {"prompt_tokens": TOTAL}}

    server = Server()
    mind = Mind(server, tmp_path / "turns.jsonl")
    mind.tools = []
    told: list[tuple[int, int]] = []
    mind.warm(lambda done, total: told.append((done, total)))
    assert told == [(2048, TOTAL)] and mind.prefix_tokens == TOTAL and len(server.read) == 1
