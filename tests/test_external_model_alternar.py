"""MODX1 (MOD2 §4): a model whose own chat template refuses two turns of the same speaker in a row (Ministral 3: «After the
optional system message, conversation roles must alternate user and assistant roles except for tool calls and results», a
500 from Ollama 0.40.16 and from llama-server b11609 to every turn of BAXY's, measured in the App on 16-11-2026) gets the
mind's conversation with those turns joined, in their order, once the server refused it; nothing else changes."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from baxy_mind import external_model as traductor

# The mind's conversation as the proxy saw it in the App (roles and shape; the words are made up): its clock note and the
# person's words, two user turns.
CLOCK = {"role": "user", "content": "[Reloj: 10:00 hora local; turno nuevo: aún no se ejecutó ninguna herramienta]"}
ASKED = {"role": "user", "content": "¿Qué hora es en Lima?"}
SYSTEM = {"role": "system", "content": "Eres BAXY."}


def alternates(messages: list[dict]) -> bool:
    """Ministral 3's own check (its template, lines 41-50): user and assistant-in-words turns alternate, starting with the
    person; calls and results do not count."""
    loop = messages[1:] if messages and messages[0]["role"] == "system" else messages
    index = 0
    for message in loop:
        if message["role"] == "user" or (message["role"] == "assistant" and not message.get("tool_calls")):
            if (message["role"] == "user") != (index % 2 == 0):
                return False
            index += 1
    return True


class Strict(BaseHTTPRequestHandler):
    seen: list[dict] = []

    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Strict.seen.append(body)
        if not alternates(body["messages"]):
            status, answer = 500, {"error": {"code": 500, "message": "Jinja Exception: After the optional system message, "
                                             "conversation roles must alternate user and assistant roles"}}
        else:
            status, answer = 200, {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Son las 8."}}],
                                   "usage": {"prompt_tokens": 10, "completion_tokens": 3}}
        data = json.dumps(answer).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def strict():
    Strict.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Strict)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_two_turns_of_the_person_become_one_in_their_order():
    assert traductor.alternated([SYSTEM, CLOCK, ASKED]) == [SYSTEM, {"role": "user", "content": CLOCK["content"] + "\n\n" + ASKED["content"]}]


def test_a_turn_after_a_calls_result_joins_that_result_and_nothing_moves():
    call = {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "system__time", "arguments": "{}"}}]}
    result = {"role": "tool", "tool_call_id": "c1", "content": '{"time":"10:00"}'}
    note = {"role": "user", "content": "[Nota interna: contesta ahora en palabras]"}
    out = traductor.alternated([SYSTEM, ASKED, call, result, note])
    assert [m["role"] for m in out] == ["system", "user", "assistant", "tool"]
    assert out[3]["content"] == result["content"] + "\n\n" + note["content"]
    assert alternates(out)


def test_a_conversation_that_already_alternates_is_left_as_it_is():
    reply = {"role": "assistant", "content": "Son las 10."}
    conversation = [SYSTEM, ASKED, reply, CLOCK]
    assert traductor.alternated(conversation) == conversation


def test_parts_with_an_image_are_kept_as_parts():
    image = {"role": "user", "content": [{"type": "text", "text": "Mira esto"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]}
    out = traductor.alternated([CLOCK, image])
    assert len(out) == 1 and out[0]["content"][0] == {"type": "text", "text": CLOCK["content"]}
    assert out[0]["content"][-1]["type"] == "image_url"


def test_the_server_that_refuses_turns_in_a_row_is_answered_and_learned_once(strict, tmp_path, capsys):
    backend = traductor.Compatible(strict + "/v1", "", "ministral", "compatible")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "ministral", backend)
    first = translator.ask({"messages": [SYSTEM, CLOCK, ASKED], "max_tokens": 64}, lambda _text: None)
    second = translator.ask({"messages": [SYSTEM, CLOCK, ASKED], "max_tokens": 64}, lambda _text: None)
    assert first["choices"][0]["message"]["content"] == second["choices"][0]["message"]["content"] == "Son las 8."
    # One refusal, then joined: the retry and every later request.
    assert [alternates(body["messages"]) for body in Strict.seen] == [False, True, True]
    assert capsys.readouterr().out.count("no admite dos turnos seguidos") == 1


def test_any_other_refusal_is_not_asked_again(strict, tmp_path):
    backend = traductor.Compatible(strict + "/v1", "", "ministral", "compatible")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "ministral", backend)
    # A server that fell for a conversation with nothing in a row: its 500 is its own, sent once, as before.
    Strict.seen = []
    original = Strict.do_POST

    def falls(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        Strict.seen.append({})
        self.send_response(500)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    Strict.do_POST = falls
    try:
        with pytest.raises(traductor.UpstreamError):
            translator.ask({"messages": [SYSTEM, ASKED], "max_tokens": 64}, lambda _text: None)
        with pytest.raises(traductor.UpstreamError):
            translator.ask({"messages": [SYSTEM, CLOCK, ASKED], "max_tokens": 64}, lambda _text: None)
    finally:
        Strict.do_POST = original
    # 1 for the first; 2 for the second (the joined retry also fell), and it is not learned.
    assert len(Strict.seen) == 3 and backend.alternate is False


def test_ollamas_request_joins_them_too_once_learned(monkeypatch):
    monkeypatch.setattr(traductor, "_show", lambda url, model: {"capabilities": ["tools", "completion"]})
    backend = traductor.Ollama("http://127.0.0.1:9", "ministral")
    plain = backend.to_request({"messages": [SYSTEM, CLOCK, ASKED], "tool_choice": "none", "max_tokens": 24})["messages"]
    backend.alternate = True
    joined = backend.to_request({"messages": [SYSTEM, CLOCK, ASKED], "tool_choice": "none", "max_tokens": 24})["messages"]
    assert [m["role"] for m in plain] == ["system", "user", "user", "user"]
    assert [m["role"] for m in joined] == ["system", "user"]
    assert joined[1]["content"].endswith("Answer in words now. Call no tool.")
