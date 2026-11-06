"""Encargo 11: the mind's server slot (BAXY_MIND_SLOT, measurement only). Several minds share one remote llama-server,
each on its own slot: every request, the slot's save and restore and the prefix kept between starts go to that slot."""
import http.server
import json
import threading
from pathlib import Path

import pytest

from baxy_mind.llm_server import LlmServer


class _Fake:
    """A llama-server of ``total_slots`` slots that records the slot each request asks for."""

    def __init__(self, folder: Path, total_slots: int = 4) -> None:
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.asked: list[tuple[str, object]] = []  # (path, the body's id_slot)
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def _answer(self, payload: dict, stream: bool = False) -> None:
                data = (f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n" if stream else json.dumps(payload)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if stream else "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802 - http.server's name
                self._answer({"total_slots": total_slots, "build_info": "b11609"})

            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.asked.append((self.path, body.get("id_slot")))
                if self.path.startswith("/slots/"):
                    state = fake.folder / body["filename"]
                    if "action=save" in self.path:
                        state.write_bytes(b"state")
                        return self._answer({"n_saved": 10})
                    return self._answer({"n_restored": 10})
                if self.path == "/completion":
                    return self._answer({"content": "open"})
                message: dict[str, object] = {"role": "assistant", "content": "Listo."}
                if body.get("tool_choice") == "required":
                    message["tool_calls"] = [{"type": "function", "function": {"name": "app_open",
                                                                               "arguments": "{}"}}]
                if body.get("stream"):
                    return self._answer({"choices": [{"index": 0, "delta": {"content": "Listo."},
                                                      "finish_reason": "stop"}]}, stream=True)
                return self._answer({"choices": [{"index": 0, "message": message, "finish_reason": "stop"}]})

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]


def _remote(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake: _Fake, slot: str | None) -> LlmServer:
    monkeypatch.setenv("BAXY_MIND_LLAMA_REMOTE", str(fake.port))
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(fake.folder))
    if slot is None:
        monkeypatch.delenv("BAXY_MIND_SLOT", raising=False)
    else:
        monkeypatch.setenv("BAXY_MIND_SLOT", slot)
    server = LlmServer(str(tmp_path / "model.gguf"), "llama-server.exe")
    server.start()
    return server


def _every_call(server: LlmServer) -> None:
    body = {"messages": [{"role": "user", "content": "hola"}]}
    server.chat(body, timeout=10)
    server.chat(body, timeout=10, on_text=lambda text, done: False)
    server.complete_name("prompt", "<tool_call>\n<function=", timeout=10)
    server.prefill("prompt", timeout=10)
    assert server.fill_call(body, "app_open", timeout=10) is not None
    assert server.save_prefix("k", {"prefix_tokens": 10})
    assert server.restore_prefix("k") == {"prefix_tokens": 10}


@pytest.mark.parametrize(("slot", "expected"), [(None, 0), ("", 0), ("3", 3)])
def test_every_call_of_the_mind_goes_to_its_configured_slot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                             slot: str | None, expected: int) -> None:
    fake = _Fake(tmp_path / "slots")
    try:
        server = _remote(monkeypatch, tmp_path, fake, slot)
        server.wait_ready(10)
        _every_call(server)
    finally:
        fake.httpd.shutdown()
    requests = [(path, id_slot) for path, id_slot in fake.asked if not path.startswith("/slots/")]
    assert [path for path, _ in requests] == ["/v1/chat/completions"] * 2 + ["/completion"] * 2 + [
        "/v1/chat/completions"]
    assert {id_slot for _, id_slot in requests} == {expected}
    assert [path for path, _ in fake.asked if path.startswith("/slots/")] == [
        f"/slots/{expected}?action=save", f"/slots/{expected}?action=restore"]


def test_a_slot_the_remote_server_does_not_have_fails_the_start_with_its_cause(monkeypatch: pytest.MonkeyPatch,
                                                                               tmp_path: Path) -> None:
    # llama-server takes id_slot modulo its slots (server-context.cpp:1663 at b11609): slot 4 on a server of 4 would
    # be slot 0, another mind's, in silence.
    fake = _Fake(tmp_path / "slots", total_slots=4)
    try:
        server = _remote(monkeypatch, tmp_path, fake, "4")
        with pytest.raises(RuntimeError, match="BAXY_MIND_SLOT 4.*4 slots"):
            server.wait_ready(10)
    finally:
        fake.httpd.shutdown()


@pytest.mark.parametrize("slot", ["uno", "-1"])
def test_a_slot_that_is_not_a_slot_number_fails_with_its_cause(monkeypatch: pytest.MonkeyPatch, slot: str) -> None:
    monkeypatch.delenv("BAXY_MIND_LLAMA_REMOTE", raising=False)
    monkeypatch.setenv("BAXY_MIND_SLOT", slot)
    with pytest.raises(RuntimeError, match="BAXY_MIND_SLOT"):
        LlmServer("model.gguf", "llama-server.exe")


def test_another_slot_needs_a_shared_remote_server(monkeypatch: pytest.MonkeyPatch) -> None:
    # The mind's own server is started with one slot (-np 1).
    monkeypatch.delenv("BAXY_MIND_LLAMA_REMOTE", raising=False)
    monkeypatch.setenv("BAXY_MIND_SLOT", "2")
    with pytest.raises(RuntimeError, match="BAXY_MIND_LLAMA_REMOTE"):
        LlmServer("model.gguf", "llama-server.exe")
