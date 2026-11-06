"""The model server's failures (uso real 2026-11-03, F4): an HTTP 5xx of llama-server is asked again once within the
request's budget (src/baxy_mind/llm_server.py, LlmServer._open), and each start keeps the last run's log beside the
new one (.1) instead of writing over it."""
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
from pathlib import Path

import pytest

from baxy_mind import llm_server


def _error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://127.0.0.1/v1/chat/completions", code, "error", {}, io.BytesIO(b"{}"))


def _server(monkeypatch, answers: list, calls: list, pauses: list) -> llm_server.LlmServer:
    def urlopen(request, timeout):
        calls.append(timeout)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(json.dumps(answer).encode("utf-8"))

    monkeypatch.setattr(llm_server.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm_server.time, "sleep", pauses.append)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server._ready.set()
    return server


REPLY = {"tokens": [1, 2], "prompt": "p", "choices": [{"message": {"content": "Hola."}}]}
CALLS = [lambda s: s.chat({"messages": []}), lambda s: s.tokenize("hola"),
         lambda s: s.template({"messages": [], "tools": [], "chat_template_kwargs": {}})]


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("code", [500, 503])
def test_a_server_error_is_asked_again_once_after_a_pause(monkeypatch, call, code: int) -> None:
    calls: list = []
    pauses: list = []
    server = _server(monkeypatch, [_error(code), REPLY], calls, pauses)
    call(server)
    assert len(calls) == 2
    assert pauses == [llm_server.LlmServer.SERVER_ERROR_PAUSE_S]


def test_a_server_error_that_stays_is_raised_after_the_retry(monkeypatch) -> None:
    calls: list = []
    pauses: list = []
    server = _server(monkeypatch, [_error(500), _error(500), REPLY], calls, pauses)
    with pytest.raises(urllib.error.HTTPError) as raised:
        server.chat({"messages": []})
    assert raised.value.code == 500
    assert len(calls) == 1 + llm_server.LlmServer.SERVER_ERROR_RETRIES


@pytest.mark.parametrize("code", [400, 404])
def test_a_client_error_is_never_asked_again(monkeypatch, code: int) -> None:
    # A 400 is a prompt past the context (Mind._next makes room): the same request would be refused the same way.
    calls: list = []
    pauses: list = []
    server = _server(monkeypatch, [_error(code), REPLY], calls, pauses)
    with pytest.raises(urllib.error.HTTPError):
        server.chat({"messages": []})
    assert len(calls) == 1 and pauses == []


def test_the_retry_and_its_pause_stay_within_the_requests_budget(monkeypatch) -> None:
    calls: list = []
    pauses: list = []
    server = _server(monkeypatch, [_error(500), REPLY], calls, pauses)
    server.deadline = time.monotonic() + 0.2
    server.chat({"messages": []})
    # the pause asked is 0.5 s; the clock's float leaves a hair over 0.2
    assert len(calls) == 2 and all(t < 0.21 for t in calls) and pauses and all(p < 0.21 for p in pauses)


def test_a_spent_budget_ends_the_request_instead_of_the_retry(monkeypatch) -> None:
    calls: list = []
    server = _server(monkeypatch, [_error(500), REPLY], calls, [])
    monkeypatch.setattr(llm_server.time, "sleep", lambda _: setattr(server, "deadline", time.monotonic() - 1))
    server.deadline = time.monotonic() + 5
    with pytest.raises(TimeoutError):
        server.chat({"messages": []})
    assert len(calls) == 1


class _Process:
    def __init__(self, *args, **kwargs) -> None:
        kwargs["stdout"].write("run 2\n")

    def poll(self) -> int | None:
        return None


def test_each_start_keeps_the_last_runs_log(monkeypatch, tmp_path: Path) -> None:
    # Relaunched at 17:05, 17:19 and 18:14, the log of the run with the 500 (14:47) was written over.
    folder = tmp_path / "BAXY" / "renew"
    folder.mkdir(parents=True)
    (folder / "llama-server.log").write_text("run 1: the 500\n", encoding="utf-8")
    (folder / "llama-server.log.1").write_text("run 0\n", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(tmp_path / "slots"))
    monkeypatch.setattr(llm_server.subprocess, "Popen", _Process)
    monkeypatch.setattr(llm_server.threading.Thread, "start", lambda self: None)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server.start()
    assert (folder / "llama-server.log.1").read_text(encoding="utf-8") == "run 1: the 500\n"
    assert (folder / "llama-server.log").read_text(encoding="utf-8") == "run 2\n"
    # «olvida todo» (trace.forget) takes the kept log too: a server error may quote the model's words.
    assert server.forget_log() is True
    assert not (folder / "llama-server.log.1").exists()


# hub/modelo-local widened this default for a slow model behind the translator: BAXY's own model must keep its 120 s, and the App
# gives it BAXY_MIND_TURN_SECONDS only with another model chosen.
@pytest.mark.parametrize(("turn", "seconds"), [(None, 120.0), ("30", 120.0), ("90", 120.0), ("300", 294.0)])
def test_a_chats_time_is_the_same_for_the_own_model_and_only_a_longer_turn_moves_it(turn, seconds):
    environment = {k: v for k, v in os.environ.items() if k != "BAXY_MIND_TURN_SECONDS"}
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    if turn:
        environment["BAXY_MIND_TURN_SECONDS"] = turn
    read = "import inspect; from baxy_mind.llm_server import LlmServer; print(inspect.signature(LlmServer.chat).parameters['timeout'].default)"
    answer = subprocess.run([sys.executable, "-c", read], env=environment, capture_output=True, text=True, check=True, timeout=120)
    assert float(answer.stdout) == seconds


# int-staging-1: hub/i6-l4-arreglos put a ceiling of 120 s on a request until the warm-up says what the server keeps; a
# model on this PC behind the translator waits 294 s without an advance, and the ceiling must not end that window first.
@pytest.mark.parametrize(("turn", "window", "ceiling"), [(None, 24.0, 120.0), ("90", 84.0, 120.0), ("300", 294.0, 294.0)])
def test_a_requests_ceiling_is_never_shorter_than_its_window(turn, window, ceiling):
    environment = {k: v for k, v in os.environ.items() if k != "BAXY_MIND_TURN_SECONDS"}
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    if turn:
        environment["BAXY_MIND_TURN_SECONDS"] = turn
    read = ("from baxy_mind.llm_server import LlmServer; s = LlmServer('model.gguf', 'llama-server.exe'); "
            "print(LlmServer.REQUEST_SECONDS, s.ceiling_s)")
    answer = subprocess.run([sys.executable, "-c", read], env=environment, capture_output=True, text=True, check=True, timeout=120)
    assert [float(x) for x in answer.stdout.split()] == [window, ceiling]


# int-staging-1 (revisión a ciegas de la fusión): behind an API the window is 84 s and the context 200,000, and the ceiling
# the warm-up gave came to ~8,100 s, past the 45 min the App takes from catalog.ready: the App kept its 126 s and the mind
# went on after it. The own model's ceilings stay what they were (468 s on the RX 7600).
@pytest.mark.parametrize(("window", "context", "kept", "backend", "ceiling"), [
    (84.0, 200_000, 20_000, "cuda", 2694.0), (24.0, 61_440, 45_361, "vulkan", 468.0), (24.0, 53_248, 1, "cpu", 708.0)])
def test_a_requests_ceiling_is_never_past_what_the_app_takes(monkeypatch, window, context, kept, backend, ceiling):
    monkeypatch.setattr(llm_server.LlmServer, "REQUEST_SECONDS", window)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe", context=context)
    monkeypatch.setattr(server, "backend", backend, raising=False)
    server.kept = kept
    assert server.ceiling_s == ceiling
    assert server.ceiling_s + 6 <= 45 * 60
