"""BAXY Renew al máximo 9.4 (artifacts/renew/maximo/MAXIMO.md): the last answer of a turn streams, and its first
sentence is synthesized while the model still writes the rest, without sounding before the App publishes it."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from baxy_mind import voice_output
from baxy_mind.llm_server import LlmServer
from baxy_mind.voice_output import Speech

FIRST = "Listo, Spotify está abierto y sonando en tu PC. "
REST = "¿Quieres que suba el volumen?"


class _SseServer:
    """A llama-server's /v1/chat/completions that streams the given chunks; after `hold_after` chunks it waits for
    `go` (set by the test) before the rest, so what happens mid-stream can be seen."""

    def __init__(self, chunks: list[dict], hold_after: int | None = None) -> None:
        self.bodies: list[dict] = []
        self.go = threading.Event()
        self.held = False  # the rest was sent only after `go`
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                outer.bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for index, chunk in enumerate(chunks):
                    if index == hold_after:
                        outer.held = outer.go.wait(5)
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

            def log_message(self, *args) -> None:
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def server(self) -> LlmServer:
        server = LlmServer("model.gguf", "llama-server.exe")
        server.port = self.http.server_address[1]
        server._ready.set()
        return server

    def close(self) -> None:
        self.http.shutdown()


def _delta(text: str) -> dict:
    return {"choices": [{"index": 0, "finish_reason": None, "delta": {"content": text}}]}


def _chunks() -> list[dict]:
    # As llama-server b11609 streams a chat: the content's deltas, the finish chunk, then usage with the timings
    # (server-task.cpp, to_json_oaicompat_chat_stream).
    return [_delta("Listo, Spotify está "), _delta("abierto y sonando en tu PC. "), _delta("¿Quieres que suba "),
            _delta("el volumen?"), {"choices": [{"index": 0, "finish_reason": "stop", "delta": {}}]},
            {"choices": [], "usage": {"prompt_tokens": 40000, "completion_tokens": 20},
             "timings": {"prompt_n": 30, "predicted_n": 20}}]


def test_the_last_answer_streams_and_its_first_sentence_is_seen_before_the_rest_is_written() -> None:
    fake = _SseServer(_chunks(), hold_after=2)
    seen: list[tuple[str, bool]] = []

    def foresee(text: str, done: bool) -> bool:
        seen.append((text, done))
        if text.endswith(". "):
            fake.go.set()  # the first sentence closed: the rest may come
            return True
        return False

    try:
        reply = fake.server().chat({"messages": [], "tool_choice": "none"}, on_text=foresee)
    finally:
        fake.close()
    assert fake.held  # the first sentence reached the voice while the model still wrote the rest
    assert seen == [("Listo, Spotify está ", False), (FIRST, False)]  # taken: no more calls
    message = reply["choices"][0]["message"]
    assert message == {"role": "assistant", "content": FIRST + REST}
    assert reply["timings"] == {"prompt_n": 30, "predicted_n": 20}
    assert reply["usage"]["prompt_tokens"] == 40000
    body = fake.bodies[0]
    assert body["stream"] is True and body["stream_options"] == {"include_usage": True}
    assert body["id_slot"] == 0 and body["cache_prompt"] is True and body["tool_choice"] == "none"


def test_a_sentence_closed_only_by_the_end_of_the_stream_is_told_as_done() -> None:
    fake = _SseServer([_delta("Abrí "), _delta("Paint.")])
    seen: list[tuple[str, bool]] = []
    try:
        reply = fake.server().chat({"messages": []}, on_text=lambda text, done: seen.append((text, done)) or False)
    finally:
        fake.close()
    assert seen[-1] == ("Abrí Paint.", True)
    assert reply["choices"][0]["message"]["content"] == "Abrí Paint."


def test_a_voice_that_fails_mid_stream_never_fails_the_answer() -> None:
    fake = _SseServer(_chunks())

    def broken(text: str, done: bool) -> bool:
        raise RuntimeError("voice gone")

    try:
        reply = fake.server().chat({"messages": []}, on_text=broken)
    finally:
        fake.close()
    assert reply["choices"][0]["message"]["content"] == FIRST + REST


def test_an_error_in_the_stream_ends_the_request() -> None:
    fake = _SseServer([_delta("Listo"), {"error": {"code": 500, "message": "slot lost"}}])
    try:
        with pytest.raises(RuntimeError, match="slot lost"):
            fake.server().chat({"messages": []}, on_text=lambda text, done: False)
    finally:
        fake.close()


def test_only_the_last_answer_of_a_person_s_turn_streams_to_the_voice(tmp_path: Path) -> None:
    from test_mind_final import FakeServer, _call, _say

    class Server(FakeServer):
        def __init__(self, replies: list) -> None:
            super().__init__(replies)
            self.streamed: list[bool] = []

        def chat(self, body: dict, on_text=None) -> dict:
            self.streamed.append(on_text is not None)
            return super().chat(body)

    from baxy_mind.mind import Mind
    server = Server([_call("app_open", {"appId": "Paint"}), _call("app_open", {"appId": "Paint"}), _say("Abrí Paint.")])
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.call_tokens = [248058]
    mind.foresee = lambda text, done: True
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "completed"}))
    result = mind.continue_turn(3, json.dumps({"status": "completed"}), final=True)
    assert result["reply"] == "Abrí Paint."
    assert server.streamed == [False, False, True]
    assert server.bodies[-1]["tool_choice"] == "none"


# --- the voice: synthesized ahead, never sounded ahead -----------------------------------------------------------------

def _model_dir(tmp_path: Path) -> Path:
    for name in voice_output._MODEL_FILES:
        (tmp_path / name).write_bytes(b"")
    return tmp_path


def _voice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, synthesized: list[str], played: list[str]) -> Speech:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_start", lambda self: None)
    monkeypatch.setattr(voice_output, "spoken", lambda text: text)

    def synthesize(self: Speech, text: str, pause: bool = True) -> str:
        synthesized.append(text)
        return text

    monkeypatch.setattr(Speech, "_synthesize", synthesize)
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued, *rest: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda *spoken: None)
    deadline = time.monotonic() + 5
    while not speech.ready and time.monotonic() < deadline:
        time.sleep(0.01)
    return speech


def _until(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.1)


def test_a_first_sentence_seen_in_the_stream_is_synthesized_once_and_sounds_only_with_its_answer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synthesized: list[str] = []
    played: list[str] = []
    speech = _voice(tmp_path, monkeypatch, synthesized, played)
    assert not speech.foresee("Listo, Spotify está", False)
    assert speech.foresee(FIRST, False)  # closed by the space after its stop, before the next word is written
    assert speech.foresee(FIRST + "¿Quieres", False)  # already taken: not synthesized twice
    _until(lambda: synthesized)
    assert synthesized == [FIRST.strip()] and played == []  # ready, and silent until the App publishes it
    assert speech.speak(FIRST + REST)
    _until(lambda: len(played) == 2)
    assert played == [FIRST.strip(), REST]
    assert synthesized == [FIRST.strip(), REST]  # the first sentence was not synthesized again


def test_a_reply_that_starts_with_a_word_or_two_is_foreseen_whole_once_it_ends(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synthesized: list[str] = []
    played: list[str] = []
    speech = _voice(tmp_path, monkeypatch, synthesized, played)
    assert not speech.foresee("Listo. Spotify está abierto", False)  # one call with what follows (issue #30)
    assert speech.foresee("Listo. Spotify está abierto.", True)
    _until(lambda: synthesized)
    assert synthesized == ["Listo. Spotify está abierto."]
    assert speech.speak("Listo. Spotify está abierto.")
    _until(lambda: played)
    assert played == ["Listo. Spotify está abierto."] and len(synthesized) == 1


def test_an_answer_other_than_the_one_foreseen_is_synthesized_as_always(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synthesized: list[str] = []
    played: list[str] = []
    speech = _voice(tmp_path, monkeypatch, synthesized, played)
    assert speech.foresee(FIRST, True)
    _until(lambda: synthesized)
    assert speech.speak("Esa aplicación no está instalada.")
    _until(lambda: played)
    assert played == ["Esa aplicación no está instalada."]
