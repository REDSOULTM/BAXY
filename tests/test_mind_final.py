"""When a turn of the mind (src/baxy_mind/mind.py) answers in words after its calls: the prompt of the turn grew past the
context (llama-server's HTTP 400) or the model wrote nothing after a call (FT/proveedores goal, e2e E022)."""
import io
import json
import urllib.error
from pathlib import Path

from baxy_mind.mind import SHRUNK_CHARS, Mind


class FakeServer:
    context = 49152

    def __init__(self, replies: list) -> None:
        self.replies = replies
        self.bodies: list[dict] = []

    def chat(self, body: dict) -> dict:
        self.bodies.append(json.loads(json.dumps(body)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def tokenize(self, text: str) -> list[int]:
        return [0] * (len(text) // 4)


def _call(name: str, arguments: dict) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]}


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _overflow() -> urllib.error.HTTPError:
    body = b'{"error":{"code":400,"type":"exceed_context_size_error"}}'
    return urllib.error.HTTPError("http://127.0.0.1/v1/chat/completions", 400, "Bad Request", {}, io.BytesIO(body))


def _mind(tmp_path: Path, replies: list) -> tuple[Mind, FakeServer]:
    server = FakeServer(replies)
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.call_tokens = [248058]  # set at warm-up from the server's vocabulary: the token that opens a call
    return mind, server


def test_a_turn_past_the_context_cuts_its_earlier_results_and_answers_in_words(tmp_path: Path) -> None:
    page = {"url": "https://example.org/rfc"}
    mind, server = _mind(tmp_path, [_call("web_fetch", page), _call("web_fetch", page), _overflow(),
                                    _say("La página no dice el código.")])
    assert mind.decide(1, "lee la página")["kind"] == "action"
    assert mind.continue_turn(2, json.dumps({"status": "completed", "text": "a" * 6000}))["kind"] == "action"
    result = mind.continue_turn(3, json.dumps({"status": "completed", "text": "b" * 6000}))
    assert result["reply"] == "La página no dice el código."
    last = server.bodies[-1]
    assert last["tool_choice"] == "none"
    tools = [m["content"] for m in last["messages"] if m["role"] == "tool"]
    assert len(tools[0]) < SHRUNK_CHARS + 200 and "Resultado recortado" in tools[0]
    assert "b" * 6000 in tools[1]


def test_an_overflow_with_nothing_to_cut_is_not_hidden(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_overflow()])
    try:
        mind.decide(1, "hola")
    except urllib.error.HTTPError:
        return
    raise AssertionError("the refused prompt must reach the App as a failed turn")


def test_nothing_written_after_a_call_is_answered_in_words(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("audio_volume", {"level": 30}), _say(""), _say("Puse el volumen al 30.")])
    mind.decide(1, "pon el volumen al 30")
    result = mind.continue_turn(2, json.dumps({"status": "completed", "verified": True}))
    assert result["reply"] == "Puse el volumen al 30."
    assert server.bodies[-1]["tool_choice"] == "none"
