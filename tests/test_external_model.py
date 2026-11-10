"""The translator against a stand-in for the Messages API (the real SDK, real SSE) and the real mind against both."""

from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

anthropic = pytest.importorskip("anthropic")

from baxy_mind import external_model as traductor  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MIND_PYTHON = Path(os.environ.get("LOCALAPPDATA", "")) / "BAXYRuntime" / "python" / "mind-runtime-v1" / "Scripts" / "python.exe"
USAGE = {"input_tokens": 100, "output_tokens": 0, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 10}


class Upstream:
    """Answers POST /v1/messages from a list of blocks, as the API streams them, and keeps what it was sent."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        self.answers: list[dict] = []
        self.usage = USAGE
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                outer.headers.append(dict(self.headers))
                answer = outer.answers.pop(0) if outer.answers else {"blocks": [{"type": "text", "text": "ok"}]}
                if "status" in answer:
                    data = json.dumps({"type": "error", "error": {"type": answer.get("type", "invalid_request_error"), "message": answer["message"]}}).encode()
                    self.send_response(answer["status"])
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()

                def event(kind, value):
                    self.wfile.write(f"event: {kind}\ndata: {json.dumps({'type': kind, **value})}\n\n".encode())

                event("message_start", {"message": {
                    "id": "msg_1", "type": "message", "role": "assistant", "model": traductor.MODEL, "content": [],
                    "stop_reason": None, "stop_sequence": None, "usage": outer.usage}})
                stop = "end_turn"
                for index, block in enumerate(answer["blocks"]):
                    if block["type"] == "text":
                        event("content_block_start", {"index": index, "content_block": {"type": "text", "text": ""}})
                        event("content_block_delta", {"index": index, "delta": {"type": "text_delta", "text": block["text"]}})
                    elif block["type"] == "thinking":
                        event("content_block_start", {"index": index, "content_block": {"type": "thinking", "thinking": "", "signature": ""}})
                        event("content_block_delta", {"index": index, "delta": {"type": "signature_delta", "signature": "firma"}})
                    else:
                        stop = "tool_use"
                        # «file*»: the tool of that name the mind offered in this request.
                        name = block["name"] if not block["name"].endswith("*") else next(
                            t["name"] for t in body["tools"] if t["name"].startswith(block["name"][:-1]))
                        event("content_block_start", {"index": index, "content_block": {
                            "type": "tool_use", "id": block["id"], "name": name, "input": {}}})
                        event("content_block_delta", {"index": index, "delta": {
                            "type": "input_json_delta", "partial_json": block.get("raw") or json.dumps(block["input"])}})
                    event("content_block_stop", {"index": index})
                event("message_delta", {"delta": {"stop_reason": answer.get("stop", stop), "stop_sequence": None},
                                        "usage": {"output_tokens": 50}})
                event("message_stop", {})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def stack(tmp_path):
    upstream = Upstream()
    spend = traductor.Spend(tmp_path / "gasto.jsonl", 3.0)
    client = anthropic.Anthropic(api_key="sk-prueba", base_url=upstream.url, max_retries=0)
    server = traductor.serve(traductor.Translator(client, spend, "medium"), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield upstream, f"http://127.0.0.1:{server.server_address[1]}", spend
    server.shutdown()
    upstream.server.shutdown()


def post(url, path, body):
    request = urllib.request.Request(url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as reply:
        return reply.read()


TOOL = {"type": "function", "function": {"name": "file.find", "description": "Busca.", "parameters": {
    "type": "object", "properties": {"query": {"type": "string"}}}}}


@pytest.mark.parametrize("headers", [
    {"Origin": "https://una-pagina.invalid"},
    {"Origin": "null"},
    {"Host": "una-pagina.invalid"},
])
def test_a_web_page_cannot_spend_the_key_through_the_local_port(stack, headers):
    upstream, url, _ = stack
    # Text/plain is what a page may send without asking first.
    request = urllib.request.Request(url + "/v1/chat/completions", headers={"Content-Type": "text/plain", **headers}, data=json.dumps({
        "messages": [{"role": "user", "content": "hola"}], "max_tokens": 10}).encode())

    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(request, timeout=30)

    assert refused.value.code == 403
    assert upstream.requests == []


def test_baxys_own_calls_still_get_through(stack):
    upstream, url, _ = stack

    post(url, "/v1/chat/completions", {"messages": [{"role": "user", "content": "hola"}], "max_tokens": 10})

    assert len(upstream.requests) == 1


def test_a_decision_becomes_a_messages_request_with_nothing_this_model_refuses(stack):
    upstream, url, _ = stack
    post(url, "/v1/chat/completions", {
        "messages": [{"role": "system", "content": "Eres BAXY"}, {"role": "user", "content": "hola"}],
        "tools": [TOOL], "max_tokens": 768, "temperature": 0.2, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "seed": 0,
        "logprobs": True, "top_logprobs": 10, "parallel_tool_calls": True, "id_slot": 0, "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": False}})
    sent = upstream.requests[0]
    assert not {"temperature", "top_p", "top_k", "min_p", "seed", "logprobs", "thinking", "id_slot"} & set(sent)
    assert sent["model"] == "claude-opus-5-5"
    assert sent["max_tokens"] == traductor.MIN_MAX_TOKENS
    assert sent["system"] == [{"type": "text", "text": "Eres BAXY"}]
    assert sent["tools"][0]["input_schema"]["properties"] == {"query": {"type": "string"}}
    assert sent["output_config"] == {"effort": "medium"}
    assert sent["cache_control"] == {"type": "ephemeral"}
    assert sent["fallbacks"] == "default"
    assert traductor.FALLBACK_BETA in upstream.headers[0].get("anthropic-beta", upstream.headers[0].get("Anthropic-Beta", ""))


def test_the_results_of_one_step_go_together_and_a_tool_with_a_dot_keeps_its_name(stack):
    upstream, url, _ = stack
    upstream.answers.append({"blocks": [{"type": "thinking"}, {"type": "text", "text": "Busco."},
                                        {"type": "tool_use", "id": "toolu_2", "name": "file__find", "input": {"query": "a"}}]})
    reply = json.loads(post(url, "/v1/chat/completions", {
        "tools": [TOOL], "max_tokens": 768, "messages": [
            {"role": "user", "content": "busca"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call:1", "type": "function", "function": {"name": "file.find", "arguments": "{\"query\":\"x\"}"}},
                {"id": "call:2", "type": "function", "function": {"name": "file.find", "arguments": "{\"query\":\"y\"}"}}]},
            {"role": "tool", "tool_call_id": "call:1", "content": "uno"},
            {"role": "tool", "tool_call_id": "call:2", "content": "dos"}]}))
    turns = upstream.requests[0]["messages"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user"]
    assert [b["tool_use_id"] for b in turns[2]["content"]] == ["call_1", "call_2"]
    assert turns[1]["content"][0] == {"type": "tool_use", "id": "call_1", "name": "file__find", "input": {"query": "x"}}
    choice = reply["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["content"] == "Busco."
    assert choice["message"]["tool_calls"][0]["function"] == {"name": "file.find", "arguments": "{\"query\": \"a\"}"}
    assert reply["usage"] == {"prompt_tokens": 1110, "completion_tokens": 50}


def test_a_fill_call_asks_in_words_because_prefill_and_forced_tools_are_refused(stack):
    upstream, url, _ = stack
    post(url, "/v1/chat/completions", {
        "tools": [TOOL], "tool_choice": "required", "max_tokens": 300, "messages": [
            {"role": "user", "content": "busca"},
            {"role": "assistant", "content": "<tool_call>\n<function=file.find>\n"}]})
    sent = upstream.requests[0]
    assert "tool_choice" not in sent
    assert sent["messages"][-1] == {"role": "system", "content": "Call the tool file__find now, with the arguments this conversation gives."}


def test_words_only_and_images_reach_the_api_as_it_takes_them(stack):
    upstream, url, _ = stack
    post(url, "/v1/chat/completions", {
        "tools": [TOOL], "tool_choice": "none", "max_tokens": 768, "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}, {"type": "text", "text": "¿qué ves?"}]}]})
    sent = upstream.requests[0]
    assert sent["tool_choice"] == {"type": "none"}
    assert sent["messages"][0]["content"][0] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}}


def test_the_warm_up_and_what_only_llama_server_has_cost_nothing(stack):
    upstream, url, spend = stack
    warm = post(url, "/v1/chat/completions", {"stream": True, "max_tokens": 1, "tools": [TOOL],
                                              "messages": [{"role": "user", "content": "hola"}]}).decode()
    assert "\"usage\"" in warm and "[DONE]" in warm
    assert json.loads(post(url, "/tokenize", {"content": "<tool_call>"}))["tokens"] == [1]
    assert json.loads(post(url, "/slots/0?action=save", {}))["n_saved"] == 1
    assert upstream.requests == [] and spend.total == 0.0


def test_a_streamed_answer_arrives_as_the_mind_rebuilds_it(stack):
    upstream, url, _ = stack
    upstream.answers.append({"blocks": [{"type": "tool_use", "id": "toolu_1", "name": "file__find", "input": {"query": "a"}}]})
    lines = [line[6:] for line in post(url, "/v1/chat/completions", {
        "stream": True, "tools": [TOOL], "max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}).decode().splitlines()
        if line.startswith("data: ")]
    assert lines[-1] == "[DONE]"
    last = json.loads(lines[-2])
    assert last["choices"][0]["finish_reason"] == "tool_calls"
    assert last["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "file.find"


def test_only_a_prompt_past_the_context_is_a_400_for_the_mind(stack):
    upstream, url, _ = stack
    upstream.answers.append({"status": 400, "message": "prompt is too long: 2000000 tokens"})
    with pytest.raises(urllib.error.HTTPError) as long_prompt:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    assert long_prompt.value.code == 400
    upstream.answers.append({"status": 400, "message": "messages.0: something else"})
    with pytest.raises(urllib.error.HTTPError) as other:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    assert other.value.code == 422  # one that will not change is not asked again (VIVO1 F4)


def test_the_ceiling_stops_the_calls_and_survives_a_restart_with_counts_only(stack, tmp_path):
    upstream, url, spend = stack
    post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "secreto del dueño"}]})
    # 100×4 + 1000×0.20 + 10×5 + 50×20 per million.
    assert spend.total == pytest.approx(1650 / 1_000_000, abs=1e-6)
    log = (tmp_path / "gasto.jsonl").read_text(encoding="utf-8")
    assert "secreto" not in log
    assert traductor.Spend(tmp_path / "gasto.jsonl", 3.0).total == pytest.approx(spend.total, abs=1e-5)
    spend.ceiling = 0.0
    with pytest.raises(urllib.error.HTTPError) as stopped:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    assert stopped.value.code == 402
    assert len(upstream.requests) == 1


class CompatibleUpstream:
    """An API that speaks OpenAI's chat completions, keeping what it was sent."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        self.answers: list[dict] = []
        self.rule = None  # what it answers from what it was sent, instead of the next of answers
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def do_POST(self):  # noqa: N802
                outer.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                outer.headers.append({"path": self.path, "authorization": self.headers.get("Authorization")})
                answer = outer.rule(outer.requests[-1]) if outer.rule else outer.answers.pop(0)
                status = answer.pop("status", 200)
                data = json.dumps(answer).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def compatible_stack(tmp_path, provider="google", model="un-modelo"):
    upstream = CompatibleUpstream()
    spend = traductor.Spend(tmp_path / "gasto.jsonl", float("inf"))
    compatible = traductor.Compatible(upstream.url, "clave-secreta", model, provider)
    server = traductor.serve(traductor.Translator(None, spend, "medium", model, compatible), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return upstream, f"http://127.0.0.1:{server.server_address[1]}", server


def answer_with(message, finish="stop"):
    return {"id": "x", "model": "un-modelo", "choices": [{"index": 0, "finish_reason": finish, "message": message}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3}}


def test_a_compatible_api_gets_only_what_it_takes_with_its_key_on_its_path(tmp_path):
    upstream, url, server = compatible_stack(tmp_path, provider="compatible")
    upstream.answers.append(answer_with({"role": "assistant", "content": "hola"}))
    reply = json.loads(post(url, "/v1/chat/completions", {
        "messages": [{"role": "user", "content": "hola"}], "tools": [TOOL], "max_tokens": 768, "temperature": 0.2, "top_p": 0.8,
        "top_k": 20, "min_p": 0.0, "seed": 0, "logprobs": True, "logit_bias": [[1, False]], "id_slot": 0, "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": False}, "parallel_tool_calls": True}))
    server.shutdown()
    sent = upstream.requests[0]
    assert set(sent) == {"model", "messages", "tools", "max_tokens"}
    assert sent["max_tokens"] == traductor.MIN_MAX_TOKENS
    assert upstream.headers[0] == {"path": "/v1/chat/completions", "authorization": "Bearer clave-secreta"}
    assert reply["choices"][0]["message"]["content"] == "hola"


def test_gemini_gets_back_the_signature_of_a_call_the_mind_kept_without_it(tmp_path):
    upstream, url, server = compatible_stack(tmp_path)
    signature = {"google": {"thought_signature": "firma"}}
    upstream.answers.append(answer_with({"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function", "extra_content": signature,
         "function": {"name": "file__find", "arguments": "{}"}}]}, "tool_calls"))
    upstream.answers.append(answer_with({"role": "assistant", "content": "listo"}))
    first = json.loads(post(url, "/v1/chat/completions", {
        "messages": [{"role": "user", "content": "x"}], "tools": [TOOL], "max_tokens": 768}))
    call = first["choices"][0]["message"]["tool_calls"][0]
    assert call["function"]["name"] == "file.find"
    post(url, "/v1/chat/completions", {"tools": [TOOL], "max_tokens": 768, "messages": [
        {"role": "user", "content": "x"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": call["function"]}]},
        {"role": "tool", "tool_call_id": "c1", "content": "ok"}]})
    server.shutdown()
    sent = upstream.requests[1]["messages"][1]["tool_calls"][0]
    assert sent["extra_content"] == signature
    assert sent["function"]["name"] == "file__find"
    assert "max_tokens" in upstream.requests[1]


def test_a_fill_call_forces_the_tool_where_the_api_allows_it(tmp_path):
    upstream, url, server = compatible_stack(tmp_path)
    upstream.answers.append(answer_with({"role": "assistant", "content": ""}))
    post(url, "/v1/chat/completions", {"tools": [TOOL], "tool_choice": "required", "max_tokens": 300, "messages": [
        {"role": "user", "content": "x"}, {"role": "assistant", "content": "<tool_call>\n<function=file.find>\n"}]})
    server.shutdown()
    sent = upstream.requests[0]
    assert sent["tool_choice"] == {"type": "function", "function": {"name": "file__find"}}
    assert [m["role"] for m in sent["messages"]] == ["user"]


def test_a_compatible_apis_refusal_is_a_failure_for_the_mind_and_its_key_is_never_logged(tmp_path, capsys):
    upstream, url, server = compatible_stack(tmp_path)
    upstream.answers.append({"status": 401, "error": {"message": "bad key"}})
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    upstream.answers.append({"status": 400, "error": {"message": "This model's maximum context_length is 10"}})
    with pytest.raises(urllib.error.HTTPError) as too_long:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    server.shutdown()
    assert refused.value.code == 422
    assert too_long.value.code == 400
    assert "clave-secreta" not in capsys.readouterr().out


# What llama-server b11609 answered to every request of BAXY's for mistral:latest past its context (VIVO1 F4, 2026-11-09): its
# template cannot be read with tools («Automatic parser generation failed»).
TEMPLATE_REFUSED = {"code": 400, "type": "invalid_request_error", "message": (
    "Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at "
    "line 1, column 125 in source:\n...{{ raise_exception('Conversation roles must alternate user...\nError: Jinja Exception: Conversation "
    "roles must alternate user/assistant/user/assistant/...")}


def test_a_refusal_that_will_not_change_is_said_with_its_cause_once_and_never_asked_again(tmp_path, capsys):
    # VIVO1 F4: «400 invalid_request_error» with 5 retries and nothing said. Its cause, by the form of the server's error (never
    # its words); a refusal that will not change goes back as one (422, with its kind), streamed or not, before any answer; one
    # that may pass (a server that fell) as before (502).
    upstream, url, server = compatible_stack(tmp_path, provider="local", model="mistral:latest")
    upstream.answers.append({"status": 400, "error": TEMPLATE_REFUSED})
    upstream.answers.append({"status": 400, "error": TEMPLATE_REFUSED})
    upstream.answers.append({"status": 500, "error": {"message": "the server fell"}})
    asked = {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", asked)
    with pytest.raises(urllib.error.HTTPError) as streamed:
        post(url, "/v1/chat/completions", {**asked, "stream": True})
    with pytest.raises(urllib.error.HTTPError) as fell:
        post(url, "/v1/chat/completions", asked)
    server.shutdown()
    log = capsys.readouterr().out
    assert (refused.value.code, streamed.value.code, fell.value.code) == (422, 422, 502)
    assert json.loads(refused.value.read())["error"]["code"] == "plantilla"
    assert "ERROR[plantilla]: El servidor local no puede usar mistral:latest con las herramientas de BAXY" in log
    assert "Conversation roles" not in log and "Jinja" not in log
    assert len(upstream.requests) == 3


def test_the_connection_is_asked_of_the_api_before_anything_else(tmp_path):
    upstream, _, server = compatible_stack(tmp_path)
    compatible = traductor.Compatible(upstream.url, "clave", "m", "google")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", 1.0), "low", "m", compatible)

    class Listing(BaseHTTPRequestHandler):
        status = 200

        def log_message(self, format, *args):  # noqa: A002
            pass

        def do_GET(self):  # noqa: N802
            self.send_response(Listing.status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

    listing = ThreadingHTTPServer(("127.0.0.1", 0), Listing)
    threading.Thread(target=listing.serve_forever, daemon=True).start()
    compatible.url = f"http://127.0.0.1:{listing.server_address[1]}"
    assert traductor.connection_problem(translator) is None
    Listing.status = 401
    assert traductor.connection_problem(translator).code == "clave"
    Listing.status = 404  # a company is asked for its model by name: 404 is that it has none of that name
    assert traductor.connection_problem(translator).code == "modelo"
    compatible.provider = "compatible"  # another API with no listing is not refused for it
    assert traductor.connection_problem(translator) is None
    listing.shutdown()
    listing.server_close()
    assert traductor.connection_problem(translator).code == "red"
    server.shutdown()


@pytest.mark.parametrize(("status", "said"), [
    (200, None), (401, "clave"), (403, "permiso"), (404, "modelo"),
])
def test_anthropics_key_and_model_are_asked_for_free(status, said, tmp_path):
    class Models(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass

        def do_GET(self):  # noqa: N802
            data = json.dumps({"id": "claude-opus-5-5", "type": "model", "display_name": "Opus", "created_at": "2026-01-01T00:00:00Z"}
                              if status == 200 else {"type": "error", "error": {"type": "x", "message": "no"}}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Models)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = anthropic.Anthropic(api_key="k", base_url=f"http://127.0.0.1:{server.server_address[1]}", max_retries=0)
    translator = traductor.Translator(client, traductor.Spend(tmp_path / "g.jsonl", 1.0), "low")
    told = traductor.connection_problem(translator)
    assert (told and told.code) == said
    server.shutdown()


class FakeOllama:
    """Ollama's own API as 0.30.11 answers it (measured 2026-11-05)."""

    def __init__(self, models, answers=None, cloud=()):
        self.requests: list[dict] = []
        self.answers = list(answers or [])
        self.loads: list[int] = []
        self.loaded: dict[str, int] = {}
        self.load_fails: str | None = None
        self.failed_loads = 0
        outer = self

        def _elsewhere(name):
            return {"remote_model": name, "remote_host": "https://ollama.com:443"} if name in cloud else {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def _send(self, value):
                data = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802
                if self.path == "/api/ps":
                    self._send({"models": [{"name": name, "size": size, "size_vram": size} for name, size in outer.loaded.items()]})
                else:
                    self._send({"models": [{"name": name, "size": 5_200_000_000, "digest": "d-" + name, **_elsewhere(name)} for name in models]})

            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/api/show":
                    if body["model"] not in models:
                        self.send_error(404)
                        return
                    context, caps = models[body["model"]]
                    self._send({"capabilities": caps, "model_info": {"arq.context_length": context}, **_elsewhere(body["model"]),
                                "modelfile": "# FROM " + body["model"] + "\nFROM C:\\blobs\\sha256-" + body["model"] + "\nTEMPLATE x\n"})
                elif self.path == "/api/generate" and outer.load_fails:
                    outer.failed_loads += body.get("keep_alive") != 0
                    data = json.dumps({"error": outer.load_fails}).encode()
                    self.send_response(500)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif self.path == "/api/generate":
                    if body.get("keep_alive") == 0:
                        outer.loaded.pop(body["model"], None)
                    else:
                        outer.loads.append(body["options"]["num_ctx"])
                        outer.loaded[body["model"]] = 3_000_000_000 + 20_000 * body["options"]["num_ctx"]
                    self._send({"done": True})
                else:
                    outer.requests.append(body)
                    self._send(outer.answers.pop(0))

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


MODELS = {"grande:4b": (262144, ["completion", "tools", "thinking"]), "qwen3:8b": (40960, ["completion", "tools", "thinking"]),
          "sin-tools": (128000, ["completion"])}


def test_the_list_of_ollama_says_where_each_models_files_are(monkeypatch):
    # MOD1 V-07 (REV_VISTA, 2026-11-09): «Modelos en este PC» decía sólo el peso en disco de cada modelo. La App dice la VRAM
    # de cada uno con la cabecera de sus archivos (ModelMemory), como ya hace con el elegido: la lista dice dónde están.
    monkeypatch.delenv("BAXY_MIND_LLAMA_SERVER", raising=False)
    ollama = FakeOllama(MODELS)
    got = {m["id"]: m for m in traductor.list_models("local", ollama.url, "")["models"]}
    ollama.server.shutdown()
    assert got["grande:4b"]["modelFiles"] == ["C:\\blobs\\sha256-grande:4b"], "la línea FROM, no el comentario que nombra el modelo"
    assert got["sin-tools"]["modelFiles"] == ["C:\\blobs\\sha256-sin-tools"]


def test_the_list_of_ollama_says_which_models_fit_and_why_not(monkeypatch):
    monkeypatch.delenv("BAXY_MIND_LLAMA_SERVER", raising=False)
    ollama = FakeOllama(MODELS)
    got = {m["id"]: m for m in traductor.list_models("local", ollama.url, "")["models"]}
    ollama.server.shutdown()
    assert got["grande:4b"]["fits"] is True and got["grande:4b"]["label"] == "grande:4b · 4,8 GB", "5.2e9 bytes in 2³⁰, as every size BAXY says"
    # Lo que ocupa en disco, el «size» de /api/tags: lo que libera desinstalarlo (pestaña Modelo de la interfaz v5).
    assert got["grande:4b"]["bytes"] == 5_200_000_000
    assert got["grande:4b"]["diskBytes"] == 5_200_000_000
    assert got["qwen3:8b"]["fits"] is False and "40.960" in got["qwen3:8b"]["why"]
    assert got["sin-tools"]["fits"] is False and "herramientas" in got["sin-tools"]["why"]


def test_a_model_fits_by_its_own_context_against_what_the_chosen_profile_needs(monkeypatch, tmp_path):
    # VIVO1 F4: mistral:latest (32.768) was offered as fitting because BAXY's server would run it past what it declares, and
    # that server could not read its template with tools. What fits is by its own context, against the profile's need.
    engine = tmp_path / "llama-server.exe"
    engine.write_bytes(b"")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(engine))
    ollama = FakeOllama(MODELS)
    whole = {m["id"]: m for m in traductor.list_models("local", ollama.url, "")["models"]}
    small = {m["id"]: m for m in traductor.list_models("local", ollama.url, "", need=18_551)["models"]}
    ollama.server.shutdown()
    assert whole["qwen3:8b"]["fits"] is False and whole["qwen3:8b"]["context"] == 40960
    assert "40.960" in whole["qwen3:8b"]["why"] and "52.000" in whole["qwen3:8b"]["why"]
    assert whole["grande:4b"]["fits"] is True
    assert small["qwen3:8b"]["fits"] is True and small["qwen3:8b"]["why"] is None


def test_a_local_model_connects_only_where_the_profiles_prompt_fits_and_its_template_takes_the_tools(tmp_path, capsys):
    # VIVO1 F4: connected, «Conectado», and every turn refused. Past its own context it goes on BAXY's server only if that server
    # takes a request with tools for it (a small one, at once); else on Ollama, up to what it declares. There, a profile whose
    # prompt does not fit is said and it does not connect.
    ollama = FakeOllama(MODELS)
    refusing = CompatibleUpstream()
    refusing.answers.append({"status": 400, "error": TEMPLATE_REFUSED})

    class Engine:
        stopped = False

        def __init__(self, server, show, model, context):
            self.context = context

        def start(self):
            return refusing.url.rstrip("/")

        def stop(self):
            Engine.stopped = True

    whole = traductor.local_backend(ollama.url, "qwen3:8b", 78000, 52000)
    small = traductor.local_backend(ollama.url, "qwen3:8b", 78000, 18551)
    engine_file = tmp_path / "llama-server.exe"
    engine_file.write_bytes(b"")
    tried = traductor.local_backend(ollama.url, "qwen3:8b", 78000, 18551, str(engine_file), Engine)
    ollama.server.shutdown()
    assert whole[2].code == "perfil" and "40.960" in whole[2].text and "52.000" in whole[2].text and "perfil" in whole[2].text
    assert isinstance(small[0], traductor.Ollama) and small[0].num_ctx == 40960 and small[2] is None
    assert isinstance(tried[0], traductor.Ollama) and tried[1] is None and tried[2] is None and Engine.stopped
    assert refusing.requests[0]["tools"] and refusing.requests[0]["max_tokens"] == 1
    assert "plantilla" in capsys.readouterr().out


def alternating(request):
    """BAXY's server with mistral:latest's template (its GGUF's tokenizer.chat_template, VIVO1 F4): user and assistant only, one
    after the other. llama.cpp folds the system message into the first user one and gives a tool's result as the user's; two of
    the same in a row are refused as the template refuses them."""
    roles = ["user" if m["role"] in ("system", "tool") else m["role"] for m in request["messages"]]
    if request["messages"][0]["role"] == "system":
        roles = roles[1:] if roles[1:2] == ["user"] else ["user", *roles[1:]]
    if any(a == b for a, b in zip(roles, roles[1:])) or roles[:1] != ["user"]:
        return {"status": 400, "error": dict(TEMPLATE_REFUSED)}
    return answer_with({"role": "assistant", "content": "x"})


def test_bAXYs_server_is_tried_with_what_a_turn_of_the_mind_sends_and_not_with_less(tmp_path, capsys):
    # VIVO1 F4 on the NB, 2026-11-09: a probe of a system and a user message passed on BAXY's server, and every turn was refused:
    # the mind sends its clock, its notes and the person's words as user messages one after another (Mind.decide), and a tool's
    # result before a note. The probe has that shape; where it is refused, the model goes with Ollama.
    ollama = FakeOllama(MODELS)
    strict, lenient = CompatibleUpstream(), CompatibleUpstream()
    strict.rule = alternating
    lenient.rule = lambda request: answer_with({"role": "assistant", "content": "x"})
    engine_file = tmp_path / "llama-server.exe"
    engine_file.write_bytes(b"")

    def engine_on(upstream):
        class Engine:
            stopped = False

            def __init__(self, server, show, model, context):
                pass

            def start(self):
                return upstream.url.rstrip("/")

            def stop(self):
                Engine.stopped = True
        return Engine

    refused_engine, taken_engine = engine_on(strict), engine_on(lenient)
    refused = traductor.local_backend(ollama.url, "qwen3:8b", 78000, 18551, str(engine_file), refused_engine)
    taken = traductor.local_backend(ollama.url, "qwen3:8b", 78000, 18551, str(engine_file), taken_engine)
    ollama.server.shutdown()
    assert isinstance(refused[0], traductor.Ollama) and refused[1] is None and refused[2] is None and refused_engine.stopped
    said = capsys.readouterr().out
    assert "(plantilla)" in said and "va con Ollama, hasta 40.960 tokens" in said
    assert isinstance(taken[0], traductor.Compatible) and taken[1] is not None and not taken_engine.stopped
    roles = [m["role"] for m in lenient.requests[0]["messages"]]
    assert roles[:3] == ["system", "user", "user"] and "tool" in roles and roles[-1] == "user"
    assert lenient.requests[0]["tools"] and lenient.requests[0]["max_tokens"] == 1


def test_ollama_gets_its_own_shape_with_the_context_set_by_baxy_and_its_answer_comes_back_as_the_mind_reads_it(tmp_path):
    ollama = FakeOllama(MODELS, [
        {"message": {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_x", "function": {"index": 0, "name": "file__find", "arguments": {"query": "informe"}}}]},
         "done_reason": "stop", "prompt_eval_count": 158, "eval_count": 22},
        {"message": {"role": "assistant", "content": "Listo"}, "done_reason": "stop", "prompt_eval_count": 198, "eval_count": 3}])
    backend = traductor.Ollama(ollama.url, "grande:4b")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "grande:4b", backend)
    server = traductor.serve(translator, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    first = json.loads(post(url, "/v1/chat/completions", {"messages": [{"role": "user", "content": "x"}], "tools": [TOOL], "max_tokens": 768,
                                                          "temperature": 0.2, "seed": 0, "logprobs": True, "id_slot": 0, "cache_prompt": True}))
    sent = ollama.requests[0]
    assert sent["options"] == {"num_ctx": 78000, "num_predict": 768, "temperature": 0.2, "seed": 0}
    assert sent["think"] is False and sent["stream"] is False and sent["tools"][0]["function"]["name"] == "file__find"
    assert not {"logprobs", "id_slot", "cache_prompt", "max_tokens"} & set(sent)
    call = first["choices"][0]["message"]["tool_calls"][0]
    assert first["choices"][0]["finish_reason"] == "tool_calls"
    assert call["id"] == "call_x" and call["function"] == {"name": "file.find", "arguments": "{\"query\": \"informe\"}"}
    assert first["usage"] == {"prompt_tokens": 158, "completion_tokens": 22}
    post(url, "/v1/chat/completions", {"tools": [TOOL], "max_tokens": 768, "messages": [
        {"role": "user", "content": "x"}, {"role": "assistant", "content": "", "tool_calls": [call]},
        {"role": "tool", "tool_call_id": "call_x", "content": "informe.txt"}]})
    turns = ollama.requests[1]["messages"]
    assert turns[1]["tool_calls"][0]["function"] == {"name": "file__find", "arguments": {"query": "informe"}}
    assert turns[2] == {"role": "tool", "content": "informe.txt", "tool_name": "file__find"}
    server.shutdown()
    ollama.server.shutdown()


def test_what_ollama_is_told_to_do_now_goes_where_every_chat_template_takes_it():
    # Banco del NB 2026-11-08, Qwen3.5-2B en Ollama 0.40.15: «Jinja Exception: System message must be at the beginning.» (500)
    # a cada aviso (tool_choice none) y a cada llamada empezada: la plantilla del modelo sólo admite el sistema primero.
    backend = traductor.Ollama("http://127.0.0.1:9", "grande:4b")
    history = [{"role": "system", "content": "s"}, {"role": "user", "content": "abre la calculadora"},
               {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "function": {"name": "app.open", "arguments": "{}"}}]},
               {"role": "tool", "tool_call_id": "c1", "content": "corriendo"}]
    notice = backend.to_request({"messages": history, "tools": [TOOL], "tool_choice": "none", "max_tokens": 24})["messages"]
    started = backend.to_request({"messages": [*history[:2], {"role": "assistant", "content": "<tool_call>\n<function=file.find>\n"}],
                                  "tools": [TOOL]})["messages"]
    for sent in (notice, started):
        assert [m["role"] for m in sent].count("system") == 1 and sent[0]["role"] == "system"
    assert notice[-1] == {"role": "user", "content": "Answer in words now. Call no tool."}
    assert started[-1] == {"role": "user", "content": "Call the tool file__find now, with the arguments this conversation gives."}


def test_ollama_and_a_compatible_api_answer_without_anthropics_sdk(tmp_path, monkeypatch):
    # Banco del NB 2026-11-08: un runtime sin el SDK de Anthropic devolvía 502 a cada pedido a Ollama («se cortó
    # (ModuleNotFoundError)»): el SDK sólo hace falta para hablar con Anthropic.
    monkeypatch.setitem(sys.modules, "anthropic", None)
    ollama = FakeOllama(MODELS, [{"message": {"role": "assistant", "content": "4"}, "done_reason": "stop", "prompt_eval_count": 9, "eval_count": 1}])
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "grande:4b",
                                      traductor.Ollama(ollama.url, "grande:4b"))
    reply = translator.ask({"messages": [{"role": "user", "content": "2 más 2"}], "max_tokens": 64}, lambda text: None)
    assert reply["choices"][0]["message"]["content"] == "4"
    ollama.server.shutdown()


def test_a_small_model_gets_what_it_admits_and_cutting_the_prompt_is_said(tmp_path, capsys):
    ollama = FakeOllama(MODELS, [{"message": {"role": "assistant", "content": "ok"}, "done_reason": "stop", "prompt_eval_count": 50, "eval_count": 1}])
    backend = traductor.Ollama(ollama.url, "qwen3:8b")
    assert backend.num_ctx == 40960
    backend.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "palabra " * 4000}]}, {})
    assert "no le cabe" in capsys.readouterr().out
    ollama.server.shutdown()


def test_the_context_the_person_chose_is_what_ollama_gets_up_to_what_the_model_admits():
    ollama = FakeOllama(MODELS)
    assert traductor.Ollama(ollama.url, "grande:4b", 128000).num_ctx == 128000
    assert traductor.Ollama(ollama.url, "qwen3:8b", 128000).num_ctx == 40960
    ollama.server.shutdown()


def test_with_baxys_server_the_context_past_what_a_model_declares_is_still_offered_and_estimated(monkeypatch, tmp_path):
    monkeypatch.setattr(traductor, "commit_free", lambda: None)
    server = tmp_path / "llama-server.exe"
    server.write_bytes(b"")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(server))
    ollama = FakeOllama(MODELS)
    got = {m["id"]: m for m in traductor.list_models("local", ollama.url, "")["models"]}
    # It fits by its own context (VIVO1 F4: BAXY's server may not read its template); past it, a context the person chooses.
    assert got["qwen3:8b"]["fits"] is False and got["sin-tools"]["fits"] is False
    estimated = traductor.estimate(ollama.url, "qwen3:8b")
    assert [o["context"] for o in estimated["options"]] == list(traductor.OLLAMA_CHOICES) and estimated["recommended"] == 78000
    # Measured where Ollama allows; the rest follows from it.
    assert ollama.loads == [8192, 32768]
    assert estimated["options"][1]["bytes"] == 3_000_000_000 + 20_000 * 78000
    ollama.server.shutdown()


def test_the_engine_overrides_what_the_model_declares_and_runs_as_the_mind_runs_its_own(monkeypatch):
    show = {"model_info": {"qwen3.block_count": 36, "qwen3.context_length": 40960}, "modelfile": "# FROM qwen3:8b\nFROM C:\\m\\sha256-a\nTEMPLATE x\n"}
    assert traductor.model_file(show) == "C:\\m\\sha256-a"
    assert traductor.model_file({"modelfile": "# FROM qwen3:8b\n"}) is None
    engine = traductor.Engine("server.exe", show, "qwen3:8b", 78000)
    arguments = " ".join(engine.arguments("cuda"))
    for part in ("-m C:\\m\\sha256-a", "-c 78000", "-ngl 99", "--override-kv qwen3.context_length=int:78000", "-ctk q8_0", "--jinja", "--reasoning off"):
        assert part in arguments


def test_a_server_ends_with_the_process_that_started_it_even_when_that_one_is_killed(tmp_path):
    script = tmp_path / "padre.py"
    pid = tmp_path / "pid.txt"
    script.write_text(
        "import subprocess, sys, time\n"
        "from baxy_mind import external_model as t\n"
        "child = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(120)'])\n"
        "t._end_with_this_process(child)\n"
        f"open(r'{pid}', 'w').write(str(child.pid))\n"
        "time.sleep(120)\n", encoding="utf-8")
    parent = subprocess.Popen([sys.executable, str(script)], env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")})
    try:
        until = time.monotonic() + 40
        while time.monotonic() < until and not (pid.exists() and pid.read_text()):
            time.sleep(0.1)
        child = int(pid.read_text())
        assert str(child) in subprocess.run(["tasklist", "/FI", f"PID eq {child}", "/NH"], capture_output=True, text=True, errors="replace").stdout
        parent.kill()
        parent.wait(10)
        until = time.monotonic() + 10
        alive = True
        while alive and time.monotonic() < until:
            alive = str(child) in subprocess.run(["tasklist", "/FI", f"PID eq {child}", "/NH"], capture_output=True, text=True, errors="replace").stdout
            time.sleep(0.2)
        assert not alive
    finally:
        if parent.poll() is None:
            parent.kill()


def test_being_connected_means_the_model_loaded_with_its_context_or_it_is_said_why_not():
    ollama = FakeOllama(MODELS)
    backend = traductor.Ollama(ollama.url, "grande:4b", 96000)
    assert backend.load() is None and ollama.loads == [96000] and "grande:4b" in ollama.loaded
    ollama.loaded.clear()
    ollama.load_fails = "llama-server terminated: error loading model: unable to allocate CUDA_Host buffer"
    # REV_VISTA V-04: with its kind, which Settings says in its own language
    assert backend.load() == traductor.Refusal("memoria", "grande:4b no cabe en la memoria de este PC: elige otro modelo o menos contexto")
    ollama.load_fails = "algo distinto"
    assert backend.load() == traductor.Refusal("carga", "Ollama no pudo cargar grande:4b")
    ollama.server.shutdown()
    ollama.server.server_close()
    assert backend.load() == traductor.Refusal("carga", "Ollama no terminó de cargar grande:4b")


def test_every_failure_line_settings_reads_carries_its_kind():
    """REV_VISTA V-04 (2026-11-09): Settings says a failure in the person's language by its kind (ERROR[kind]); five lines were
    written with none («ERROR: …») and an English view showed their Spanish words. Every one goes through say()."""
    source = Path(traductor.__file__).read_text(encoding="utf-8")
    assert [line.strip() for line in source.splitlines() if '"ERROR' in line and "print(" in line] == [
        'print(f"ERROR[{refusal.code}]: {refusal.text}", flush=True)']


def test_a_local_model_that_does_not_fit_is_said_plainly(tmp_path, capsys):
    class Answer:
        provider = "local"

        def ask(self, body, names):
            import io
            raise urllib.error.HTTPError("http://x", 500, "x", {}, io.BytesIO(b'{"error":"cudaMalloc failed: out of memory"}'))

    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "grande:4b", Answer())
    with pytest.raises(traductor.UpstreamError):
        translator._ask_compatible({}, {}, lambda _text: None)
    out = capsys.readouterr().out
    assert "grande:4b no cabe en la memoria" in out and "cudaMalloc" not in out


def test_a_server_that_cannot_load_says_it_and_leaves_nothing(tmp_path, capsys, monkeypatch):
    script = tmp_path / "falla.py"
    script.write_text("print('cudaMalloc failed: out of memory')\nraise SystemExit(1)\n", encoding="utf-8")
    monkeypatch.setattr(traductor.Engine, "arguments", lambda self, backend: ["-I", str(script)])
    monkeypatch.setattr(traductor, "ENGINE_START_SECONDS", 20)
    import baxy_mind.llm_server as llm
    monkeypatch.setattr(llm, "declared_backend", lambda *a, **k: "cuda")
    monkeypatch.setattr(llm, "declared_build", lambda *a, **k: "x")
    engine = traductor.Engine(sys.executable, {}, "qwen3:8b", 200000)
    assert engine.start() is None
    assert "no cabe en la VRAM" in capsys.readouterr().out and engine.process.poll() is not None


def test_a_model_in_use_is_not_taken_out_to_measure_it(monkeypatch, tmp_path):
    monkeypatch.setattr(traductor, "commit_free", lambda: None)
    ollama = FakeOllama(MODELS)
    got = traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json", measure=False)
    assert ollama.loads == [] and got["options"][0]["bytes"] is None and "error" not in got
    traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json")
    assert ollama.loads == [8192, 32768]
    ollama.loads.clear()
    assert traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json", measure=False)["options"][0]["bytes"] is not None
    assert ollama.loads == []
    ollama.server.shutdown()


def test_a_model_that_would_leave_the_pc_without_memory_is_not_loaded_nor_measured(monkeypatch, tmp_path):
    monkeypatch.setattr(traductor, "commit_free", lambda: 6 * 2**30)
    # Whole on the card: its size, 2.75 GiB of the process's own and 3 GiB left for the person's programs.
    assert traductor.memory_problem("m", 0.25 * 2**30) is None
    assert traductor.memory_problem("m", 0.3 * 2**30) is not None
    assert traductor.memory_problem("m", 4 * 2**30) == ("m necesita unos 9,8 GB de RAM libre (RAM y archivo de paginación, donde Windows cuenta también lo que va a la tarjeta), "
        "contando lo que debe quedar para tus programas, y este PC tiene 6,0 GB: elige otro modelo o menos contexto")
    # 2026-11-09: «21,4 GB de memoria libre» was read as VRAM; it is what Windows must be able to promise, said apart.
    ollama = FakeOllama(MODELS)
    # The file of each is 5.2 GB (FakeOllama): with 6 GB free it is not even loaded to measure it.
    got = traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json")
    assert ollama.loads == [] and "elige otro modelo" in got["error"] and got["commitFreeBytes"] == 6 * 2**30
    assert got["options"][0]["bytes"] is None
    ollama.server.shutdown()


def test_what_a_model_needs_is_what_was_measured_or_at_least_its_file(tmp_path):
    ollama = FakeOllama(MODELS)
    cache = tmp_path / "e.json"
    assert traductor.expected_memory(ollama.url, "grande:4b", 78000, cache) == 5_200_000_000
    cache.write_text(json.dumps({"d-grande:4b": {"base": 1000.0, "perToken": 2.0}}), encoding="utf-8")
    assert traductor.expected_memory(ollama.url, "grande:4b", 78000, cache) == 157000.0
    ollama.server.shutdown()


def test_windows_says_how_much_it_can_still_promise():
    free = traductor.commit_free()
    assert free is None or free > 0


def test_the_memory_of_each_context_is_measured_once_and_the_model_is_taken_out_again(tmp_path, monkeypatch):
    monkeypatch.setattr(traductor, "commit_free", lambda: None)
    monkeypatch.delenv("BAXY_MIND_LLAMA_SERVER", raising=False)
    ollama = FakeOllama(MODELS)
    cache = tmp_path / "estimaciones.json"
    first = traductor.estimate(ollama.url, "grande:4b", cache)
    assert ollama.loads == [8192, 32768] and ollama.loaded == {}
    assert first["contextLength"] == 262144 and first["recommended"] == 78000
    assert [o["context"] for o in first["options"]] == [64000, 78000, 96000, 128000, 200000]
    assert first["options"][1]["bytes"] == 3_000_000_000 + 20_000 * 78000
    again = traductor.estimate(ollama.url, "grande:4b", cache)
    assert ollama.loads == [8192, 32768] and again["options"] == first["options"]
    ollama.server.shutdown()


def test_nothing_below_what_baxy_sends_is_ever_offered():
    assert traductor.context_choices(70000, engine=False) == [64000, 70000]
    assert traductor.context_choices(40960, engine=False) == []
    assert traductor.context_choices(20000, engine=True) == list(traductor.OLLAMA_CHOICES)
    assert traductor.context_choices(0, engine=False) == list(traductor.OLLAMA_CHOICES)


def test_with_ollama_gone_the_options_stay_without_their_memory():
    ollama = FakeOllama(MODELS)
    ollama.server.shutdown()
    ollama.server.server_close()
    got = traductor.estimate(ollama.url, "grande:4b")
    assert got["error"] == "Ollama no respondió" and got["options"][0]["bytes"] is None


def test_ollama_that_does_not_answer_or_lacks_the_model_is_said(tmp_path):
    ollama = FakeOllama(MODELS)
    spend = traductor.Spend(tmp_path / "g.jsonl", float("inf"))
    make = lambda model: traductor.Translator(None, spend, "low", model, traductor.Ollama(ollama.url, model))  # noqa: E731
    assert traductor.connection_problem(make("grande:4b")) is None
    told = traductor.connection_problem(make("no-esta"))
    assert told.code == "modelo" and "no-esta" in told.text and "grande:4b" in told.text
    ollama.server.shutdown()
    ollama.server.server_close()
    assert traductor.connection_problem(make("grande:4b")) == ("ollama", "Ollama no responde")


def _company(body, status=200):
    class Listing(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass

        def do_GET(self):  # noqa: N802
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Listing)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def test_a_companys_list_keeps_what_can_chat_and_a_refused_key_is_said():
    server, url = _company({"data": [{"id": "gpt-x"}, {"id": "text-embedding-3"}, {"id": "whisper-1"}, {"id": "models/gemini-y"}, {"id": "gpt-x-tts"}]})
    assert [m["id"] for m in traductor.list_models("openai", url, "k")["models"]] == ["gemini-y", "gpt-x"]
    server.shutdown()
    server, url = _company({}, status=401)
    assert traductor.list_models("google", url, "k")["code"] == "clave"
    server.shutdown()
    server.server_close()
    assert traductor.list_models("openai", url, "k") == {"error": "no hay conexión con OpenAI", "code": "red"}


def test_anthropics_list_comes_from_the_sdk():
    class Models(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass

        def do_GET(self):  # noqa: N802
            common = {"type": "model", "created_at": "2026-01-01T00:00:00Z"}
            data = json.dumps({"data": [{**common, "id": "claude-opus-5-5", "display_name": "Claude Opus 5.5", "lifecycle": "active"},
                                        {**common, "id": "claude-viejo", "display_name": "Viejo", "lifecycle": "retired"}],
                               "has_more": False, "first_id": None, "last_id": None}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Models)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = anthropic.Anthropic(api_key="k", base_url=f"http://127.0.0.1:{server.server_address[1]}", max_retries=0)
    assert traductor.list_models("anthropic", "", "", client) == {"models": [{"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "fits": True}]}
    server.shutdown()


def test_a_claude_with_no_effort_is_not_asked_for_it():
    request = traductor.to_request({"messages": [{"role": "user", "content": "x"}], "max_tokens": 10}, None, "claude-otro")
    assert "output_config" not in request
    assert traductor.to_request({"messages": [{"role": "user", "content": "x"}], "max_tokens": 10}, "low", "claude-otro")["output_config"] == {"effort": "low"}


def test_an_api_on_this_pc_needs_no_key_and_sends_no_empty_one(tmp_path):
    upstream = CompatibleUpstream()
    compatible = traductor.Compatible(upstream.url, "", "m", "compatible")
    local = traductor.serve(traductor.Translator(None, traductor.Spend(tmp_path / "l.jsonl", float("inf")), "low", "m", compatible), 0)
    threading.Thread(target=local.serve_forever, daemon=True).start()
    upstream.answers.append(answer_with({"role": "assistant", "content": "hola"}))
    post(f"http://127.0.0.1:{local.server_address[1]}", "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    assert upstream.headers[0]["authorization"] is None
    local.shutdown()


class Redirecting:
    """An API that sends every request to another address on another port, the other keeping what reaches it."""

    def __init__(self, status: int) -> None:
        self.reached: list[dict] = []
        outer = self

        class Other(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def _keep(self):
                outer.reached.append({"path": self.path, "headers": dict(self.headers)})
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            do_GET = do_POST = _keep  # noqa: N815

        class Sends(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def _send(self):
                self.send_response(status)
                self.send_header("Location", f"http://127.0.0.1:{outer.other.server_address[1]}{self.path}")
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_GET = do_POST = _send  # noqa: N815

        self.other = ThreadingHTTPServer(("127.0.0.1", 0), Other)
        self.sends = ThreadingHTTPServer(("127.0.0.1", 0), Sends)
        self.url = f"http://127.0.0.1:{self.sends.server_address[1]}"
        self.other_url = f"http://127.0.0.1:{self.other.server_address[1]}"
        for server in (self.other, self.sends):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.other.shutdown()
        self.sends.shutdown()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_takes_neither_the_key_nor_the_conversation_elsewhere(tmp_path, status, capsys):
    api = Redirecting(status)
    compatible = traductor.Compatible(api.url + "/v1", "clave-secreta", "m", "openai")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "m", compatible)
    with pytest.raises(traductor.UpstreamError):
        translator.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}, lambda _text: None)
    told = traductor.connection_problem(translator)
    api.close()
    assert api.reached == []
    assert told and told.code == "redirige"
    assert "clave-secreta" not in capsys.readouterr().out


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_a_redirect_takes_anthropics_key_nowhere(tmp_path, status, monkeypatch):
    api = Redirecting(status)
    monkeypatch.setattr(traductor, "ANTHROPIC_URL", api.url)
    client = traductor.anthropic_client("clave-secreta")
    client = client.with_options(max_retries=0)
    translator = traductor.Translator(client, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low")
    with pytest.raises(traductor.UpstreamError):
        translator.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}, lambda _text: None)
    told = traductor.connection_problem(translator)
    api.close()
    assert api.reached == []
    assert told and told.code == "redirige"


def test_what_the_machine_inherited_does_not_send_anthropics_key_elsewhere(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://otro.invalid")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-de-otro")
    client = traductor.anthropic_client("clave-de-la-persona")
    assert str(client.base_url).rstrip("/") == "https://api.anthropic.com"
    assert client.api_key == "clave-de-la-persona"
    assert client.auth_token is None


@pytest.fixture
def proxy(monkeypatch):
    """The proxy this PC has set, which answers everything and keeps what reaches it."""
    server = Redirecting(200)
    monkeypatch.setenv("HTTP_PROXY", server.other_url)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.setattr(urllib.request, "_opener", None)
    yield server
    server.close()


# «Otra» with a gateway on this PC is the same case, with a key: http is only taken for an address on this PC.
@pytest.mark.parametrize(("provider", "key"), [("local", ""), ("compatible", "clave-secreta")])
def test_an_address_on_this_pc_is_asked_directly_whatever_proxy_this_pc_has(proxy, provider, key):
    upstream = CompatibleUpstream()
    upstream.answers.append(answer_with({"role": "assistant", "content": "hola"}))
    compatible = traductor.Compatible(upstream.url, key, "m", provider)
    compatible.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "lo que no sale"}]}, {})
    upstream.server.shutdown()
    assert proxy.reached == []
    assert len(upstream.requests) == 1


def test_a_local_server_never_goes_through_the_proxy_even_where_python_does_not_call_its_address_local(proxy):
    compatible = traductor.Compatible("http://[::127.0.0.1]:1/v1", "", "m", "local")
    with pytest.raises(OSError):
        compatible.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "lo que no sale"}]}, {})
    assert proxy.reached == []


def test_a_company_is_still_reached_through_the_proxy_this_pc_has(proxy):
    compatible = traductor.Compatible("http://empresa.invalid/v1", "k", "m", "openai")
    compatible.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}, {})
    assert len(proxy.reached) == 1


def test_what_the_machine_inherited_neither_logs_bodies_nor_adds_headers(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_LOG", "debug")
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "x-de-otro: valor")
    client = traductor.anthropic_client("k")
    assert "ANTHROPIC_LOG" not in os.environ
    assert "x-de-otro" not in client.default_headers


def test_a_call_the_sdk_cannot_read_fails_for_the_mind_and_leaves_no_text_behind(stack, capsys):
    upstream, url, _ = stack
    upstream.answers.append({"blocks": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}, "raw": '{"q": "' + ECHOED + '\nmás"}'}]})
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    told = capsys.readouterr()
    assert refused.value.code == 502
    assert ECHOED not in told.out + told.err


def test_a_failure_while_serving_tells_its_kind_and_not_its_text(tmp_path, capsys):
    server = traductor.serve(traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", 1.0), "low"), 0)
    try:
        raise ValueError(ECHOED)
    except ValueError:
        server.handle_error(None, ("127.0.0.1", 0))
    server.server_close()
    told = capsys.readouterr()
    assert ECHOED not in told.out + told.err
    assert "ValueError" in told.out + told.err
    assert not told.out.startswith("ERROR"), "Settings shows lines that start so: a person's request ended is no failure of the key"


def test_nothing_else_can_share_the_translators_port(tmp_path):
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", 1.0), "low")
    server = traductor.serve(translator, 0)
    try:
        with pytest.raises(OSError):
            traductor.serve(translator, server.server_address[1])
    finally:
        server.server_close()


ECHOED = "Mi receta secreta de la abuela"


def test_a_compatible_apis_error_that_repeats_the_text_leaves_no_text_behind(tmp_path, capsys):
    upstream, url, server = compatible_stack(tmp_path)
    upstream.answers.append({"status": 422, "error": {"message": f"unsupported input: {ECHOED}", "code": "bad_input", "type": "invalid_request_error"}})
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": ECHOED}]})
    upstream.answers.append({"status": 400, "error": {"message": f"too long: {ECHOED}", "code": 400}})
    with pytest.raises(urllib.error.HTTPError) as too_long:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": ECHOED}]})
    server.shutdown()
    log = capsys.readouterr().out
    assert ECHOED not in log
    assert "ERROR[rechazo]: Google respondió 422 (bad_input)" in log
    assert (refused.value.code, too_long.value.code) == (422, 400)
    assert ECHOED not in refused.value.read().decode() + too_long.value.read().decode()


@pytest.mark.parametrize("status", [400, 429])
def test_anthropics_error_that_repeats_the_text_leaves_no_text_behind(stack, status, capsys):
    upstream, url, _ = stack
    upstream.answers.append({"status": status, "message": f"invalid: {ECHOED}"})
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": ECHOED}]})
    log = capsys.readouterr().out
    assert ECHOED not in log
    assert ("ERROR[rechazo]: Anthropic respondió 400 (invalid_request_error)" if status == 400 else "ERROR[limite]: Anthropic limitó") in log
    assert ECHOED not in refused.value.read().decode()


def test_anthropics_too_long_still_reaches_the_mind_as_too_long(stack):
    upstream, url, _ = stack
    upstream.answers.append({"status": 400, "message": "prompt is too long: 300000 tokens"})
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    assert refused.value.code == 400


def test_a_key_with_a_line_break_is_not_written_to_the_log(tmp_path, capsys):
    compatible = traductor.Compatible("http://127.0.0.1:9/v1", "sk-parte\nsecreta", "m", "openai")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "m", compatible)
    with pytest.raises(traductor.UpstreamError):
        translator.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}, lambda _text: None)
    log = capsys.readouterr().out
    assert "secreta" not in log
    assert "ERROR" in log


class Cutting:
    """An API whose connection breaks after ``sent`` bytes of its answer."""

    def __init__(self, sent: bytes = b"") -> None:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers["Content-Length"]))
                if sent:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(sent)
                    self.wfile.flush()
                # A reset, not a clean close.
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                self.connection.close()
                self.close_connection = True

            def handle_one_request(self):
                try:
                    super().handle_one_request()
                except (OSError, ValueError):
                    self.close_connection = True

            def finish(self):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def _ask_streaming(url):
    request = urllib.request.Request(url + "/v1/chat/completions", headers={"Content-Type": "application/json"}, data=json.dumps({
        "stream": True, "max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}).encode())
    with urllib.request.urlopen(request, timeout=30) as reply:
        return reply.read().decode()


@pytest.mark.parametrize("stream", [True, False])
def test_a_connection_cut_before_the_answer_is_a_failure_for_the_mind(tmp_path, stream, capsys):
    api = Cutting()
    compatible = traductor.Compatible(api.url + "/v1", "k", "m", "local")
    server = traductor.serve(traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "m", compatible), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        # Before its first word, streamed or not, an HTTP failure (as llama-server's): one that may pass.
        with pytest.raises(urllib.error.HTTPError) as refused:
            post(url, "/v1/chat/completions", {"max_tokens": 768, "stream": stream, "messages": [{"role": "user", "content": "x"}]})
        assert refused.value.code == 502
    finally:
        server.shutdown()
    assert "ERROR" in capsys.readouterr().out


def test_an_answer_cut_halfway_is_not_given_to_the_mind_as_a_whole_one(tmp_path, capsys):
    start = {"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": traductor.MODEL, "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": USAGE}}
    block = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
    delta = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Voy a borrar"}}
    sent = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in (start, block, delta)).encode()
    api = Cutting(sent)
    client = anthropic.Anthropic(api_key="k", base_url=api.url, max_retries=0)
    server = traductor.serve(traductor.Translator(client, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low"), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # The reset may take the words already sent with it (Windows drops what was not read yet): then the cut came before the first
    # word, and it is the answer's HTTP status. Either way, never a whole answer.
    try:
        told = _ask_streaming(f"http://127.0.0.1:{server.server_address[1]}")
    except urllib.error.HTTPError as error:
        assert error.code == 502
        told = error.read().decode()
    finally:
        server.shutdown()
    assert '"error"' in told and "finish_reason" not in told
    assert "ERROR" in capsys.readouterr().out


def test_with_no_ceiling_written_nothing_stops_the_calls(tmp_path):
    upstream = Upstream()
    spend = traductor.Spend(tmp_path / "g.jsonl", float("inf"))
    spend.total = 1_000_000.0
    client = anthropic.Anthropic(api_key="k", base_url=upstream.url, max_retries=0)
    translator = traductor.Translator(client, spend, "low")
    assert spend.spent is False
    reply = translator.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}, lambda _text: None)
    assert reply["choices"][0]["message"]["content"] == "ok"
    upstream.server.shutdown()


def test_a_model_whose_prices_are_unknown_costs_nothing_on_the_counter_and_says_so_by_its_zero():
    usage = type("U", (), {"input_tokens": 1000, "output_tokens": 1000})()
    assert traductor.cost(usage, "un-modelo") == 0.0
    assert traductor.cost(usage, "claude-opus-5-5") == pytest.approx(0.024)


@pytest.mark.skipif(not MIND_PYTHON.is_file(), reason="the mind's runtime is not on this machine")
@pytest.mark.parametrize(("context", "shrinks"), [("", True), ("200000", False)])
def test_a_prompt_past_the_local_models_context_cuts_nothing_with_the_context_of_an_api(stack, tmp_path, context, shrinks):
    """Uso real 2026-11-05: 80,000 tokens read on the local model's 77,824 cut the history at every step, and each cut
    restarts the API's cache. ExternalModel gives the mind BAXY_RENEW_CTX=200000."""
    upstream, url, _ = stack
    upstream.usage = {"input_tokens": 2, "output_tokens": 0, "cache_read_input_tokens": 80000, "cache_creation_input_tokens": 0}
    upstream.answers.extend([
        {"blocks": [{"type": "text", "text": "Hola."}]},
        {"blocks": [{"type": "tool_use", "id": "toolu_1", "name": "file*", "input": {"query": "informe"}}]},
        {"blocks": [{"type": "text", "text": "Listo."}]}, {"blocks": [{"type": "text", "text": "Listo."}]}])
    env = {k: v for k, v in os.environ.items() if not k.startswith("BAXY_")}
    env.update(PYTHONPATH=str(REPO / "src"), PYTHONUTF8="1", LOCALAPPDATA=str(tmp_path), BAXY_MIND_LLAMA_REMOTE=url.rsplit(":", 1)[1],
               BAXY_MIND_LLM_GGUF=str(tmp_path / "x.gguf"), BAXY_MIND_LLAMA_SERVER=str(tmp_path / "llama-server.exe"),
               BAXY_RENEW_PREFILL="0", BAXY_RENEW_WAKE_WARM="0", BAXY_RENEW_TRACE_DIR=str(tmp_path / "trace"))
    if context:
        env["BAXY_RENEW_CTX"] = context
    mind = subprocess.Popen([str(MIND_PYTHON), "-m", "baxy_mind"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, cwd=tmp_path)
    lines: list[dict] = []
    threading.Thread(target=lambda: lines.extend(json.loads(raw) for raw in mind.stdout), daemon=True).start()

    def ask(message):
        mind.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
        mind.stdin.flush()
        import time
        until = time.monotonic() + 60
        while time.monotonic() < until:
            for line in list(lines):
                if line.get("id") == message["id"] and line.get("type") != "catalog.progress":
                    return line
            time.sleep(0.05)
        raise AssertionError(lines)

    try:
        ask({"type": "catalog.configure", "id": 1, "capabilities": [
            {"name": "file.find", "description": "Busca archivos.", "risk": "read_only",
             "argumentsSchema": {"type": "object", "properties": {"query": {"type": "string"}}}}]})
        ask({"type": "turn.decide", "id": 2, "text": "hola"})
        # a turn before this one: what a cut makes room from
        ask({"type": "turn.decide", "id": 3, "text": "busca el informe"})
        ask({"type": "turn.continue", "id": 4, "result": {"status": "completed", "operation": "file.find", "found": ["informe.txt"]}})
    finally:
        mind.stdin.close()
        mind.wait(timeout=20)
    trace = (tmp_path / "trace" / "turns.jsonl").read_text(encoding="utf-8")
    assert ("context_shrunk" in trace) is shrinks


@pytest.mark.skipif(not MIND_PYTHON.is_file(), reason="the mind's runtime is not on this machine")
@pytest.mark.parametrize("through_a_proxy", [False, True])
def test_the_real_mind_decides_through_the_translator(stack, tmp_path, through_a_proxy, request):
    """python -m baxy_mind, as the App starts it, on the translator's port: its warm-up, a turn that calls a tool, the tool's
    result and the last answer. A proxy this PC has set takes none of it: the mind's server is on this PC."""
    upstream, url, _ = stack
    pc_proxy = request.getfixturevalue("proxy") if through_a_proxy else None
    upstream.answers.extend([
        {"blocks": [{"type": "thinking"}, {"type": "tool_use", "id": "toolu_1", "name": "file*", "input": {"query": "informe"}}]},
        {"blocks": [{"type": "text", "text": "Encontré el informe."}]}])
    env = {k: v for k, v in os.environ.items() if not k.startswith("BAXY_")}
    env.update(PYTHONPATH=str(REPO / "src"), PYTHONUTF8="1", LOCALAPPDATA=str(tmp_path),
               BAXY_MIND_LLAMA_REMOTE=url.rsplit(":", 1)[1], BAXY_MIND_LLM_GGUF=str(tmp_path / "x.gguf"),
               BAXY_MIND_LLAMA_SERVER=str(tmp_path / "llama-server.exe"), BAXY_RENEW_PREFILL="0", BAXY_RENEW_WAKE_WARM="0",
               BAXY_RENEW_TRACE_DIR=str(tmp_path / "trace"))
    mind = subprocess.Popen([str(MIND_PYTHON), "-m", "baxy_mind"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, cwd=tmp_path)
    box = {"lines": []}

    def read():
        for raw in mind.stdout:
            box["lines"].append(json.loads(raw))

    threading.Thread(target=read, daemon=True).start()

    def send(message):
        mind.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
        mind.stdin.flush()

    def wait(request_id):
        import time
        until = time.monotonic() + 60
        while time.monotonic() < until:
            # A «progress» line says the model advanced (uso-124: a streamed answer from the translator too), as the App
            # reads it (MindSidecarClient): the request goes on, it is not the reply.
            for line in box["lines"]:
                if line.get("id") == request_id and line.get("type") not in ("catalog.progress", "progress"):
                    return line
            assert mind.poll() is None, box["lines"]
            time.sleep(0.05)
        raise AssertionError(f"no reply to {request_id}: {box['lines']}")

    try:
        send({"type": "catalog.configure", "id": 1, "capabilities": [
            {"name": "file.find", "description": "Busca archivos.", "risk": "read_only",
             "argumentsSchema": {"type": "object", "properties": {"query": {"type": "string"}}}}]})
        assert wait(1).get("type") != "error", box["lines"]
        send({"type": "turn.decide", "id": 2, "text": "busca el informe"})
        step = wait(2)
        assert step["kind"] == "action" and step["operation"] == "file.find", step
        assert step["arguments"] == {"query": "informe"}
        send({"type": "turn.continue", "id": 3, "result": {"status": "completed", "operation": "file.find", "found": ["informe.txt"]}})
        last = wait(3)
        assert "Encontré el informe." in json.dumps(last, ensure_ascii=False), last
        assert len(upstream.requests) >= 2
        assert all("temperature" not in r for r in upstream.requests)
        assert pc_proxy is None or pc_proxy.reached == []
    finally:
        mind.stdin.close()
        mind.wait(timeout=20)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_a_model_ollama_runs_in_its_cloud_is_not_offered_because_it_would_leave_this_pc(monkeypatch):
    monkeypatch.delenv("BAXY_MIND_LLAMA_SERVER", raising=False)
    ollama = FakeOllama({"grande:4b": MODELS["grande:4b"], "nube:cloud": MODELS["grande:4b"]}, cloud={"nube:cloud"})
    got = {m["id"]: m for m in traductor.list_models("local", ollama.url, "")["models"]}
    ollama.server.shutdown()
    assert got["grande:4b"]["fits"] is True
    assert got["nube:cloud"]["fits"] is False and "fuera de este PC" in got["nube:cloud"]["why"]


# With a server of BAXY's the file would run past the check of what connects, so that way is tried too.
@pytest.mark.parametrize("engine", [False, True])
def test_a_model_ollama_runs_in_its_cloud_does_not_connect_and_is_sent_nothing(tmp_path, capsys, monkeypatch, engine):
    server = tmp_path / "llama-server.exe"
    server.write_bytes(b"")
    if engine:
        monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(server))
    else:
        monkeypatch.delenv("BAXY_MIND_LLAMA_SERVER", raising=False)
    monkeypatch.setattr(traductor, "memory_problem", lambda *_, **__: None)
    monkeypatch.setattr(traductor.Engine, "start", lambda self: pytest.fail("the engine started"))
    monkeypatch.setattr(traductor, "serve", lambda *_: pytest.fail("it connected"))
    ollama = FakeOllama({"nube:cloud": (40960, ["completion", "tools"])}, cloud={"nube:cloud"})
    code = traductor.main(["--proveedor", "local", "--modelo", "nube:cloud", "--url", ollama.url, "--contexto", "78000",
                           "--gasto", str(tmp_path / "g.jsonl"), "--sin-comprobar"])
    ollama.server.shutdown()
    assert code == 3
    assert "fuera de este PC" in capsys.readouterr().out
    assert ollama.loads == [] and ollama.requests == []


def test_what_ollama_lists_in_its_cloud_is_refused_even_if_it_could_not_say_so_a_moment_before(tmp_path):
    ollama = FakeOllama({"nube:cloud": MODELS["grande:4b"]}, cloud={"nube:cloud"})
    backend = traductor.Ollama(ollama.url, "nube:cloud")
    backend.remote = False
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "nube:cloud", backend)
    problem = traductor.connection_problem(translator)
    ollama.server.shutdown()
    assert problem.code == "nube" and "fuera de este PC" in problem.text


def test_nothing_on_the_way_to_ollama_goes_through_the_proxy_this_pc_has(proxy, monkeypatch, tmp_path):
    monkeypatch.delenv("BAXY_MIND_LLAMA_SERVER", raising=False)
    ollama = FakeOllama(MODELS, [{"message": {"role": "assistant", "content": "lo que no sale"}, "done": True}])
    traductor.list_models("local", ollama.url, "")
    traductor.expected_memory(ollama.url, "grande:4b", 78000, None)
    traductor.estimate(ollama.url, "grande:4b")
    backend = traductor.Ollama(ollama.url, "grande:4b")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "grande:4b", backend)
    traductor.connection_problem(translator)
    backend.load()
    backend.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "lo que no sale"}]}, {})
    ollama.server.shutdown()
    assert proxy.reached == []
    assert len(ollama.requests) == 1


def test_the_list_of_a_company_goes_through_the_proxy_and_the_list_on_this_pc_does_not(proxy):
    assert "error" not in traductor.list_models("openai", "http://empresa.invalid/v1", "k")
    assert len(proxy.reached) == 1
    upstream, url = _company({"data": [{"id": "m"}]})
    assert [m["id"] for m in traductor.list_models("compatible", url, "k")["models"]] == ["m"]
    upstream.shutdown()
    assert len(proxy.reached) == 1


@pytest.mark.parametrize("provider", ["compatible", "local"])
def test_a_list_follows_no_redirect_with_the_key(provider):
    server = Redirecting(302)
    answer = traductor.list_models(provider, server.url, "clave-secreta")
    reached = list(server.reached)
    server.close()
    assert answer == {"error": "esa dirección redirige a otra: escribe la final", "code": "redirige"}
    assert reached == []


def test_a_list_asked_without_the_key_says_that_and_not_that_it_was_refused():
    server, url = _company({}, status=401)
    answer = traductor.list_models("compatible", url, "")
    server.shutdown()
    assert "clave" in answer["error"] and "rechazó" not in answer["error"]


def test_the_list_of_anthropic_goes_to_anthropic_with_the_key_of_settings(monkeypatch, capsys):
    seen = []

    class Client:
        class models:  # noqa: N801
            @staticmethod
            def list():
                return [type("Model", (), {"id": "claude-x", "display_name": "X", "lifecycle": "active"})()]

    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-ajustes")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(traductor, "anthropic_client", lambda key: seen.append(key) or Client)
    assert traductor.main(["--listar", "--proveedor", "anthropic"]) == 0
    assert seen == ["clave-de-ajustes"]
    assert json.loads(capsys.readouterr().out)["models"][0]["id"] == "claude-x"


def test_ollama_gone_in_the_middle_of_a_turn_is_a_failure_the_mind_reads(tmp_path, capsys):
    backend = traductor.Ollama("http://127.0.0.1:9", "m")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "m", backend)
    with pytest.raises(traductor.UpstreamError) as failure:
        translator.ask({"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]}, lambda _text: None)
    assert failure.value.status == 502
    assert "Ollama" in capsys.readouterr().out


def test_the_estimate_loads_nothing_for_a_model_in_ollamas_cloud():
    ollama = FakeOllama({"nube:cloud": MODELS["grande:4b"]}, cloud={"nube:cloud"})
    answer = traductor.estimate(ollama.url, "nube:cloud")
    ollama.server.shutdown()
    assert ollama.loads == []
    assert "fuera de este PC" in answer["error"]


class NotHttp:
    """Something on a port that answers words and no HTTP, which http.client quotes in its error."""

    def __init__(self) -> None:
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.listener.getsockname()[1]}"
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                connection, _ = self.listener.accept()
            except OSError:
                return
            with connection:
                connection.recv(65536)
                connection.sendall(b"PALABRAS-DE-LA-API lo que no sale\r\n\r\n")


@pytest.mark.parametrize("provider", ["compatible", "local"])
def test_a_server_that_does_not_speak_http_is_said_and_its_words_stay_out_of_the_log(tmp_path, provider):
    server = NotHttp()
    log = tmp_path / "traductor.log"
    environment = {**os.environ, "PYTHONPATH": str(REPO / "src"), "BAXY_EXTERNAL_API_KEY": "k", "PYTHONUTF8": "1"}
    environment.pop("BAXY_MIND_LLAMA_SERVER", None)
    done = subprocess.run([sys.executable, "-m", "baxy_mind.external_model", "--proveedor", provider, "--modelo", "m", "--url", server.url,
                           "--puerto", "0", "--gasto", str(tmp_path / "g.jsonl"), "--registro", str(log)],
                          env=environment, capture_output=True, text=True, timeout=120)
    server.listener.close()
    written = log.read_text(encoding="utf-8")
    assert done.returncode == 3
    assert "PALABRAS" not in written and "PALABRAS" not in done.stderr
    assert "ERROR" in written


def test_a_failure_nobody_expected_leaves_its_kind_in_the_log_and_not_its_words(tmp_path):
    log = tmp_path / "traductor.log"
    fails = ("from baxy_mind import external_model as t\n"
             "def problem(_):\n"
             "    raise ValueError('PALABRAS-DE-LA-API')\n"
             "t.connection_problem = problem\n"
             f"t.main(['--proveedor', 'compatible', '--modelo', 'm', '--url', 'http://127.0.0.1:9', '--gasto', {str(tmp_path / 'g.jsonl')!r}, '--registro', {str(log)!r}])\n")
    environment = {**os.environ, "PYTHONPATH": str(REPO / "src"), "BAXY_EXTERNAL_API_KEY": "k", "PYTHONUTF8": "1"}
    done = subprocess.run([sys.executable, "-c", fails], env=environment, capture_output=True, text=True, timeout=120)
    written = log.read_text(encoding="utf-8")
    assert done.returncode != 0
    assert "PALABRAS" not in written
    assert "ValueError" in written


def test_only_counts_are_kept_of_what_a_compatible_api_calls_its_counts(tmp_path, capsys):
    class Answer:
        provider = "compatible"

        def ask(self, body, names):
            return {"choices": [{"finish_reason": "PALABRAS en el final", "message": {"role": "assistant", "content": "hola"}}],
                    "usage": {"prompt_tokens": "PALABRAS repetidas", "completion_tokens": 7}}

    spent = tmp_path / "g.jsonl"
    translator = traductor.Translator(None, traductor.Spend(spent, float("inf")), "low", "m", Answer())
    translator._ask_compatible({}, {}, lambda _text: None)
    assert "PALABRAS" not in capsys.readouterr().out
    kept = json.loads(spent.read_text(encoding="utf-8"))
    assert "PALABRAS" not in json.dumps(kept)
    assert (kept["in"], kept["out"]) == (0, 7)


# Pedido del dueño 2026-11-08: «vi varios errores» con OpenAI y Anthropic. Each refusal says what happened and what to do, by
# the status and the code each company documents, with its kind for the view's other language.
@pytest.mark.parametrize(("status", "error", "code", "words"), [
    (401, {"message": "Incorrect API key provided", "type": "invalid_request_error"}, "clave", "rechazó la clave"),
    (429, {"message": "no money", "type": "insufficient_quota", "code": "credit_balance_exhausted"}, "saldo", "no tiene saldo"),
    (429, {"message": "spend", "type": "insufficient_quota", "code": "project_spend_limit_exceeded"}, "saldo", "límite de gasto"),
    (429, {"message": "slow down", "type": "rate_limit_error"}, "limite", "espera un minuto"),
    (404, {"message": "nope", "code": "model_not_found"}, "modelo", "no tiene el modelo un-modelo"),
    (503, {"message": "busy", "code": "server_is_overloaded"}, "saturado", "saturado"),
    (500, {"message": "boom"}, "caido", "fallo en su servidor (500)"),
])
def test_each_refusal_of_openai_says_what_happened_and_what_to_do(tmp_path, capsys, status, error, code, words):
    upstream, url, server = compatible_stack(tmp_path, provider="openai")
    upstream.answers.append({"status": status, "error": error})
    with pytest.raises(urllib.error.HTTPError):
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    server.shutdown()
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("ERROR"))
    assert line.startswith(f"ERROR[{code}]: OpenAI ") and words in line
    assert error["message"] not in line


@pytest.mark.parametrize(("status", "kind", "message", "code"), [
    (401, "authentication_error", "invalid x-api-key", "clave"),
    (402, "billing_error", "card declined", "saldo"),
    (400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API.", "saldo"),
    (400, "invalid_request_error", "You have reached your specified API usage limits.", "saldo"),
    (429, "rate_limit_error", "slow", "limite"),
    (529, "overloaded_error", "Overloaded", "saturado"),
])
def test_each_refusal_of_anthropic_says_what_happened_and_what_to_do(stack, capsys, status, kind, message, code):
    upstream, url, _ = stack
    upstream.answers.append({"status": status, "type": kind, "message": message})
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("ERROR"))
    assert line.startswith(f"ERROR[{code}]: Anthropic ")
    assert message not in line
    assert refused.value.code == (502 if code in traductor.PASSING else 422)


def test_a_runtime_without_anthropics_sdk_says_so_instead_of_closing(monkeypatch, capsys, tmp_path):
    """Uso real 2026-11-08 02:07: the runtime of this PC and of the notebook predate the SDK, and the translator ended with
    «Fallo: ModuleNotFoundError»; Settings said only that it did not start, and the list could not be read."""
    monkeypatch.setitem(sys.modules, "anthropic", None)
    assert traductor.main(["--listar", "--proveedor", "anthropic"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["code"] == "sdk" and "Anthropic" in listed["error"]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert traductor.main(["--gasto", str(tmp_path / "g.jsonl"), "--proveedor", "anthropic"]) == 3
    assert capsys.readouterr().out.startswith("ERROR[sdk]: ")


def test_openai_goes_by_its_responses_api_and_gets_back_the_reasoning_of_each_call(tmp_path):
    """gpt-6.1-sol and gpt-6.1-terra call tools only by the Responses API (developers.openai.com/api/docs/models/gpt-6.1-sol),
    and a reasoning model's reasoning items go back with the call's output (guides/function-calling)."""
    upstream = CompatibleUpstream()
    responses = traductor.Responses(upstream.url, "clave-secreta", "gpt-6.1-sol", "openai")
    spend = traductor.Spend(tmp_path / "g.jsonl", float("inf"))
    server = traductor.serve(traductor.Translator(None, spend, "medium", "gpt-6.1-sol", responses), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    thought = {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "cifrado"}
    arguments = json.dumps({"query": "x"})
    upstream.answers.append({"id": "resp_1", "model": "gpt-6.1-sol", "output": [
        thought, {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "file__find", "arguments": arguments}],
        "usage": {"input_tokens": 50, "output_tokens": 9}})
    upstream.answers.append({"id": "resp_2", "model": "gpt-6.1-sol", "output": [
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Listo."}]}],
        "usage": {"input_tokens": 70, "output_tokens": 3}})
    system = {"role": "system", "content": "Eres BAXY."}
    first = json.loads(post(url, "/v1/chat/completions", {"max_tokens": 768, "tools": [TOOL], "parallel_tool_calls": True,
                                                           "messages": [system, {"role": "user", "content": "busca x"}]}))
    call = first["choices"][0]["message"]["tool_calls"][0]
    assert (first["choices"][0]["finish_reason"], call["function"]["name"]) == ("tool_calls", "file.find")
    second = json.loads(post(url, "/v1/chat/completions", {"max_tokens": 768, "tools": [TOOL], "messages": [
        system, {"role": "user", "content": "busca x"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": call["id"], "type": "function", "function": call["function"]}]},
        {"role": "tool", "tool_call_id": call["id"], "content": "un archivo"}]}))
    server.shutdown()
    assert second["choices"][0]["message"]["content"] == "Listo."
    assert second["usage"] == {"prompt_tokens": 70, "completion_tokens": 3}
    assert [h["path"] for h in upstream.headers] == ["/v1/responses", "/v1/responses"]
    sent = upstream.requests[1]
    assert sent["store"] is False and sent["max_output_tokens"] == traductor.MIN_MAX_TOKENS
    assert sent["tools"][0] == {"type": "function", "name": "file__find", "description": "Busca.",
                                "parameters": TOOL["function"]["parameters"]}
    assert sent["input"] == [
        {"role": "developer", "content": "Eres BAXY."}, {"role": "user", "content": "busca x"}, thought,
        {"type": "function_call", "call_id": "call_1", "name": "file__find", "arguments": arguments},
        {"type": "function_call_output", "call_id": "call_1", "output": "un archivo"}]
    assert not {"temperature", "messages", "max_completion_tokens"} & set(sent)


def test_a_model_openai_does_not_have_is_said_before_the_first_turn(tmp_path):
    server, url = _company({"error": {"message": "The model does not exist", "code": "model_not_found"}}, status=404)
    responses = traductor.Responses(url, "k", "gpt-sin-esto", "openai")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", 1.0), "low", "gpt-sin-esto", responses)
    told = traductor.connection_problem(translator)
    server.shutdown()
    assert told is not None and told.code == "modelo" and "gpt-sin-esto" in told.text


NOTICE = {"max_tokens": 24, "tool_choice": "none", "temperature": 0.0, "tools": [TOOL], "messages": [
    {"role": "user", "content": "busca vuelos a Lima"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "file.find", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c1", "content": "{\"status\": \"running\"}\n[Escribe sólo una frase...]"}]}


def test_a_notice_reaches_the_model_and_its_words_come_back(stack):
    """Pedido del dueño 2026-11-08: with the stock model BAXY says what it is doing during a mission of several steps, and with
    another model it says nothing until the end. Those words are the model's notice (Mind.notice_of: 24 tokens, no tool), which the
    translator answered itself with nothing; it goes to the model now, with the low effort a phrase of 24 tokens needs."""
    upstream, url, _ = stack
    upstream.answers.append({"blocks": [{"type": "text", "text": "Busco vuelos a Lima."}]})
    reply = json.loads(post(url, "/v1/chat/completions", NOTICE))
    assert reply["choices"][0]["message"]["content"] == "Busco vuelos a Lima."
    assert reply["choices"][0]["finish_reason"] == "stop"
    assert len(upstream.requests) == 1
    assert upstream.requests[0]["output_config"]["effort"] == "low"
    assert upstream.requests[0]["tool_choice"] == {"type": "none"}


def test_a_notice_reaches_a_compatible_api_and_ollama_too(tmp_path):
    upstream, url, server = compatible_stack(tmp_path, provider="compatible")
    upstream.answers.append(answer_with({"role": "assistant", "content": "Busco vuelos a Lima."}))
    reply = json.loads(post(url, "/v1/chat/completions", NOTICE))
    server.shutdown()
    assert reply["choices"][0]["message"]["content"] == "Busco vuelos a Lima."
    assert upstream.requests[0]["tool_choice"] == "none"


CAPTURE = {"max_tokens": 800, "messages": [{"role": "user", "content": [
    {"type": "text", "text": "Describe esta captura."},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="}}]}]}


def test_a_model_that_does_not_see_is_sent_no_image_and_says_so(tmp_path):
    """Pedido del dueño 2026-11-08: «si el modelo no tiene visión, que BAXY ya no podrá usar la visión, y listo». A capture's
    description for a model Ollama says does not see goes nowhere: it would answer on what it never saw."""
    ollama = FakeOllama(MODELS)
    backend = traductor.Ollama(ollama.url, "grande:4b")
    assert backend.sees is False
    server = traductor.serve(traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "grande:4b", backend), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(f"http://127.0.0.1:{server.server_address[1]}", "/v1/chat/completions", CAPTURE)
    server.shutdown()
    ollama.server.shutdown()
    assert refused.value.code == 501
    assert json.loads(refused.value.read())["error"]["code"] == "model_without_vision"
    assert ollama.requests == []


def test_a_model_that_sees_gets_its_image_and_the_list_says_which_ones_see(tmp_path, monkeypatch):
    ollama = FakeOllama({**MODELS, "ve:4b": (262144, ["completion", "tools", "vision"])})
    assert traductor.Ollama(ollama.url, "ve:4b").sees is True
    listed = {m["id"]: m["vision"] for m in traductor.list_models("local", ollama.url, "")["models"]}
    ollama.server.shutdown()
    assert listed["ve:4b"] is True and listed["grande:4b"] is False


def test_claude_that_takes_images_gets_them_and_one_that_does_not_is_sent_none(stack):
    upstream, url, _ = stack
    upstream.answers.append({"blocks": [{"type": "text", "text": "Una ventana."}]})
    assert json.loads(post(url, "/v1/chat/completions", CAPTURE))["choices"][0]["message"]["content"] == "Una ventana."
    assert upstream.requests[-1]["messages"][0]["content"][1]["type"] == "image"



def test_whether_openai_or_gemini_see_is_not_assumed_it_is_tried_and_a_refusal_says_it(tmp_path):
    """Líder 2026-11-08: «no todos sus modelos ven… nunca "sí" por defecto». Their models APIs do not say a model's modalities, so
    it is not known: the first image goes, and a refusal of it as a request it cannot take says this model does not see, from then on."""
    upstream, url, server = compatible_stack(tmp_path, provider="google")
    upstream.rule = lambda sent: (
        {"status": 400, "error": {"message": "image input is not supported", "status": "INVALID_ARGUMENT"}} if _images(sent)
        else answer_with({"role": "assistant", "content": "No veo ninguna imagen."}))
    props = json.loads(urllib.request.urlopen(url + "/props", timeout=10).read())
    assert props["vision"] is None
    with pytest.raises(urllib.error.HTTPError) as first:
        post(url, "/v1/chat/completions", CAPTURE)
    with pytest.raises(urllib.error.HTTPError) as second:
        post(url, "/v1/chat/completions", CAPTURE)
    props = json.loads(urllib.request.urlopen(url + "/props", timeout=10).read())
    server.shutdown()
    assert (first.value.code, second.value.code) == (501, 501)
    # Revisión total (M4): refused with a small image too, and answered without any: it is the image it does not take.
    assert [len(_images(sent)) for sent in upstream.requests] == [1, 1, 0], "known now: the second image goes nowhere"
    assert _images(upstream.requests[1]) == [traductor.PROBE_IMAGE]
    assert json.loads(first.value.read())["error"]["code"] == "model_without_vision"  # never the answer about no image
    assert props["vision"] is False
    assert traductor.Responses("https://api.openai.com/v1", "k", "gpt-6.1-sol", "openai").sees is None


def _images(sent: dict) -> list[str]:
    """The images of a chat completions request, as their URLs."""
    return [part["image_url"]["url"] for message in sent.get("messages") or [] if isinstance(message.get("content"), list)
            for part in message["content"] if part.get("type") == "image_url"]


# A capture too large for the model: OpenAI rejects an image past its patch limit instead of resizing it
# (developers.openai.com/api/docs/guides/images-vision, «Images that exceed the 30,000-patch limit after processing are
# rejected, not automatically resized to meet it»), and Claude one past its pixel limit with an invalid_request_error
# (platform.claude.com/docs/en/build-with-claude/vision). Both read 2026-11-09.
LARGE_CAPTURE = {"max_tokens": 800, "messages": [{"role": "user", "content": [
    {"type": "text", "text": "Describe esta captura."},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + "iVBORw0KGgo" * 400 + "="}}]}]}


def _too_large(sent: dict) -> dict:
    if any(len(url) > 2000 for url in _images(sent)):
        return {"status": 400, "error": {"message": "Invalid image: it is larger than this model accepts.",
                                         "type": "invalid_request_error", "code": "image_too_large"}}
    return answer_with({"role": "assistant", "content": "Una ventana."})


def test_an_image_refused_for_its_size_does_not_say_the_model_cannot_see(tmp_path):
    """Revisión total (M4): any 400, 415 or 422 to a request with an image, with the model's sight not known, marked the model
    «sin visión» for the whole session. A model that takes a small image sees: what it refused was that image."""
    upstream, url, server = compatible_stack(tmp_path, provider="openai")
    upstream.rule = _too_large
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", LARGE_CAPTURE)
    props = json.loads(urllib.request.urlopen(url + "/props", timeout=10).read())
    seen = json.loads(post(url, "/v1/chat/completions", CAPTURE))
    with pytest.raises(urllib.error.HTTPError) as again:
        post(url, "/v1/chat/completions", LARGE_CAPTURE)
    server.shutdown()
    assert refused.value.code == 422 and again.value.code == 422  # the API's own refusal, not «no vision here» (501)
    assert props["vision"] is None
    assert seen["choices"][0]["message"]["content"] == "Una ventana."
    # the large one, the same request with the small image (taken: nothing more is asked), the capture, and the large one
    # again, alone: a model that took an image is not tried again.
    assert [_images(sent) == [traductor.PROBE_IMAGE] for sent in upstream.requests] == [False, True, False, False]


def test_a_request_refused_for_another_field_does_not_say_the_model_cannot_see(tmp_path):
    # developers.openai.com/api/docs/guides/error-codes (read 2026-11-09): «400 - Invalid service_tier argument … as an
    # invalid_request_error with error.param set to service_tier». Refused with a small image and with none: not the image.
    upstream, url, server = compatible_stack(tmp_path, provider="openai")
    upstream.rule = lambda sent: {"status": 400, "error": {
        "message": "Invalid service_tier argument: The requested service tier is not allowed for this project.",
        "type": "invalid_request_error", "param": "service_tier"}}
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", CAPTURE)
    props = json.loads(urllib.request.urlopen(url + "/props", timeout=10).read())
    server.shutdown()
    assert refused.value.code == 422
    assert props["vision"] is None
    assert [len(_images(sent)) for sent in upstream.requests] == [1, 1, 0]


def test_a_model_that_answered_an_image_is_not_blind_for_a_later_refusal(tmp_path):
    upstream, url, server = compatible_stack(tmp_path, provider="openai")
    upstream.rule = _too_large
    assert json.loads(post(url, "/v1/chat/completions", CAPTURE))["choices"][0]["message"]["content"] == "Una ventana."
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", LARGE_CAPTURE)
    props = json.loads(urllib.request.urlopen(url + "/props", timeout=10).read())
    server.shutdown()
    assert refused.value.code == 422 and props["vision"] is None
    assert len(upstream.requests) == 2, "it took an image before: nothing is tried"


def test_a_failure_that_is_not_a_refusal_of_the_request_tries_nothing(tmp_path):
    # 429 and 5xx say nothing of what the request holds: as before, they are the mind's to ask again.
    upstream, url, server = compatible_stack(tmp_path, provider="openai")
    upstream.rule = lambda sent: {"status": 429, "error": {"message": "Rate limit reached", "type": "rate_limit_error"}}
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", CAPTURE)
    server.shutdown()
    assert refused.value.code == 502 and len(upstream.requests) == 1


def test_claudes_spend_limit_on_a_capture_does_not_say_claude_cannot_see(stack):
    # platform.claude.com/docs/en/api/errors (read 2026-11-09): «The API also returns a 400 when usage reaches an
    # organization or workspace spend limit you set». With the Models API silent on images (anthropic_sees None), that 400
    # to a capture's description marked Claude «sin visión» until BAXY was started again.
    upstream, url, _ = stack
    limit = {"status": 400, "message": "You have reached your specified API usage limits. You will regain access on 2026-12-01."}
    upstream.answers.extend([dict(limit), dict(limit), dict(limit)])
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", CAPTURE)
    props = json.loads(urllib.request.urlopen(url + "/props", timeout=10).read())
    assert refused.value.code == 422 and json.loads(refused.value.read())["error"]["code"] == "saldo"
    assert props["vision"] is None
    assert len(upstream.requests) == 3  # the capture, the same with a small image, and without any: all refused


def test_the_small_image_is_a_well_formed_png():
    # W3C PNG (third edition), 5.2-5.3: the signature, then chunks of length, type, data and the CRC-32 of type and data;
    # IHDR's width, height, bit depth 8 and colour type 0 (greyscale); IDAT inflates to one filter byte and the row.
    import base64
    import zlib
    kind, _, data = traductor.PROBE_IMAGE.partition(",")
    png = base64.b64decode(data)
    assert kind == "data:image/png;base64" and png[:8] == b"\x89PNG\r\n\x1a\n"
    chunks, at = [], 8
    while at < len(png):
        (length,) = struct.unpack(">I", png[at:at + 4])
        name, body = png[at + 4:at + 8], png[at + 8:at + 8 + length]
        assert struct.unpack(">I", png[at + 8 + length:at + 12 + length])[0] == zlib.crc32(name + body)
        chunks.append((name, body))
        at += 12 + length
    assert [name for name, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    width, height, depth, colour = struct.unpack(">IIBB", chunks[0][1][:10])
    assert (width, height, depth, colour) == (64, 64, 8, 0)
    assert len(zlib.decompress(chunks[1][1])) == height * (width + 1)


def test_a_request_keeps_its_words_and_settings_when_its_images_are_changed_or_left_out():
    body = {"max_tokens": 800, "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": [
        {"type": "text", "text": "Describe esta captura."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA", "detail": "high"}}]}]}
    small, none = traductor._with_images(body, traductor.PROBE_IMAGE), traductor._with_images(body, None)
    assert small["messages"][1]["content"] == [
        {"type": "text", "text": "Describe esta captura."},
        {"type": "image_url", "image_url": {"url": traductor.PROBE_IMAGE, "detail": "high"}}]
    assert none["messages"][1]["content"] == [{"type": "text", "text": "Describe esta captura."}]
    assert small["max_tokens"] == none["max_tokens"] == 800 and small["messages"][0] == none["messages"][0] == body["messages"][0]
    assert body["messages"][1]["content"][1]["image_url"]["url"] == "data:image/png;base64,AAAA"  # the request itself is untouched


def test_claude_sees_what_its_models_api_says_of_it(tmp_path):
    def capabilities(image: bool | None):
        class Models(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def do_GET(self):  # noqa: N802
                caps = {} if image is None else {"image_input": {"supported": image}, "effort": {"supported": True}}
                data = json.dumps({"id": "claude-opus-5-5", "type": "model", "display_name": "Opus", "created_at": "2026-01-01T00:00:00Z",
                                   **({"capabilities": caps} if caps else {})}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Models)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        client = anthropic.Anthropic(api_key="k", base_url=f"http://127.0.0.1:{server.server_address[1]}", max_retries=0)
        translator = traductor.Translator(client, traductor.Spend(tmp_path / "g.jsonl", 1.0), "low")
        assert traductor.connection_problem(translator) is None
        server.shutdown()
        return translator.sees

    assert capabilities(True) is True
    assert capabilities(False) is False
    assert capabilities(None) is None, "not said: not known"


def test_the_estimate_says_the_models_files_so_the_app_works_out_its_vram_from_their_headers(monkeypatch, tmp_path):
    # Encargo del dueño 2026-11-08 («nunca mentir» con la VRAM): Ollama's own size left out 120-124 MiB that nvidia-smi saw
    # (the CUDA runtime), so the App says the VRAM from the files' headers (ModelMemory) and these are only where they are.
    monkeypatch.setattr(traductor, "commit_free", lambda: None)
    ollama = FakeOllama(MODELS)
    got = traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json", measure=False)
    assert got["modelFiles"] == ["C:\\blobs\\sha256-grande:4b"]
    ollama.server.shutdown()


def test_a_model_ollama_could_not_load_is_not_loaded_again_by_the_next_estimate(monkeypatch, tmp_path):
    # 2026-11-09, PC: the view asked the estimate of a model whose load crashed Ollama's runner (0xc0000005 in ggml-base.dll),
    # and every ask loaded it again: 9 crashes in 22 minutes. A failed measure is kept, and the next estimate says it.
    monkeypatch.setattr(traductor, "commit_free", lambda: None)
    ollama = FakeOllama(MODELS)
    ollama.load_fails = "llama runner process has terminated: exit status 0xc0000005"
    first = traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json")
    again = traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json")
    kept = traductor.expected_memory(ollama.url, "grande:4b", 78000, tmp_path / "e.json")
    ollama.server.shutdown()
    assert first["error"] == "Ollama no pudo cargarlo" and again["error"] == "Ollama no pudo cargarlo"
    assert ollama.failed_loads == 1, "one load, not one per ask"
    assert kept == 5_200_000_000, "with no measure kept, the RAM check goes by the file"


def test_measuring_a_model_counts_it_as_ollama_may_split_it_since_nothing_says_it_fits_the_card(monkeypatch, tmp_path):
    # INT18 blind review: the load that measures a model comes before any VRAM check (ExternalModel.StartAsync measures first),
    # and Ollama splits what does not fit the free VRAM, which takes up to 1.7 per byte (measured 2026-11-05 and 06). Its RAM
    # check is the larger of the two rules, never less than before vram-contexto (×1.7 + 3 GiB).
    monkeypatch.setattr(traductor, "commit_free", lambda: 11 * 2**30)
    ollama = FakeOllama(MODELS)
    # 5.2 GB (FakeOllama's file): whole on the card 10.6 GiB, split 11.2 GiB; with 11 GiB to promise it is not loaded.
    got = traductor.estimate(ollama.url, "grande:4b", tmp_path / "e.json")
    ollama.server.shutdown()
    assert ollama.loads == [] and "elige otro modelo" in got["error"]
    # Small, the rule for whole on the card is the larger one, and it stands.
    assert traductor.memory_problem("m", 1 * 2**30, partial=None) == traductor.memory_problem("m", 1 * 2**30)
    assert traductor.memory_problem("m", 4.84 * 2**30, partial=None) == traductor.memory_problem("m", 4.84 * 2**30, partial=True)


def test_connecting_checks_the_ram_with_the_apps_estimate_and_where_it_goes(monkeypatch):
    # INT18 blind review: a measure refused or failed leaves nothing kept, and connecting went by the file alone, whole on the
    # card. With the App's estimate from the model's files (what the view says) and «whole» only when the App saw it fit.
    monkeypatch.setattr(traductor, "commit_free", lambda: 16 * 2**30)
    file = 8 * 2**30
    # 12 GiB at its context: 12 + 2.75 + 3 = 17.75 > 16, refused; by the file alone 13.75 passed.
    assert traductor.connect_memory_problem("m", file, 12 * 2**30, partial=False, whole=True, on_engine=False) is not None
    # Where it goes not known: the larger rule (8 × 1.7 + 3 = 16.6 > 16), never the file whole on the card.
    assert traductor.connect_memory_problem("m", file, 0, partial=False, whole=False, on_engine=False) is not None
    # Known whole on the card (the App saw 9 GiB fit), it goes by that: 9 + 5.75 = 14.75.
    assert traductor.connect_memory_problem("m", file, 9 * 2**30, partial=False, whole=True, on_engine=False) is None
    # Ollama measured more than the files say (12 GiB, e.g. OLLAMA_NUM_PARALLEL): the larger, 12 + 5.75 = 17.75.
    assert traductor.connect_memory_problem("m", 12 * 2**30, 9 * 2**30, partial=False, whole=True, on_engine=False) is not None
    # Partly in RAM, the person's choice: × 1.7. BAXY's own server keeps every layer on the card: whole.
    assert traductor.connect_memory_problem("m", file, 9 * 2**30, partial=True, whole=False, on_engine=False) is not None
    assert traductor.connect_memory_problem("m", file, 9 * 2**30, partial=True, whole=False, on_engine=True) is None


def test_a_model_whole_on_the_card_needs_its_size_and_what_the_process_holds_not_its_size_times_1_7(monkeypatch):
    # Measured on the PC on 2026-11-09 (RTX 4060 Ti, six loads whole on the GPU, llama-server and Ollama): the commit charge grew
    # as the card did, 1:1 (WDDM backs video memory with system commit), plus 0.9-2.4 GiB beside it. ×1.7 blocked a 6 GB model
    # on a PC with 12 GB to promise; partly in RAM (the person's choice) the earlier ×1.7 stands.
    monkeypatch.setattr(traductor, "commit_free", lambda: 12 * 2**30)
    assert traductor.memory_problem("m", 6 * 2**30) is None
    assert traductor.memory_problem("m", 6.5 * 2**30) is not None
    assert traductor.memory_problem("m", 6 * 2**30, partial=True) is not None
