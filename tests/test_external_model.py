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
                    data = json.dumps({"type": "error", "error": {"type": "invalid_request_error", "message": answer["message"]}}).encode()
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


def test_the_warm_up_the_notice_and_what_only_llama_server_has_cost_nothing(stack):
    upstream, url, spend = stack
    warm = post(url, "/v1/chat/completions", {"stream": True, "max_tokens": 1, "tools": [TOOL],
                                              "messages": [{"role": "user", "content": "hola"}]}).decode()
    assert "\"usage\"" in warm and "[DONE]" in warm
    post(url, "/v1/chat/completions", {"max_tokens": 24, "tool_choice": "none", "tools": [TOOL], "messages": []})
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
    assert other.value.code == 502


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
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

            def do_POST(self):  # noqa: N802
                outer.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                outer.headers.append({"path": self.path, "authorization": self.headers.get("Authorization")})
                answer = outer.answers.pop(0)
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
    upstream, url, server = compatible_stack(tmp_path, provider="openai")
    upstream.answers.append(answer_with({"role": "assistant", "content": "hola"}))
    reply = json.loads(post(url, "/v1/chat/completions", {
        "messages": [{"role": "user", "content": "hola"}], "tools": [TOOL], "max_tokens": 768, "temperature": 0.2, "top_p": 0.8,
        "top_k": 20, "min_p": 0.0, "seed": 0, "logprobs": True, "logit_bias": [[1, False]], "id_slot": 0, "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": False}, "parallel_tool_calls": True}))
    server.shutdown()
    sent = upstream.requests[0]
    assert set(sent) == {"model", "messages", "tools", "max_completion_tokens"}
    assert sent["max_completion_tokens"] == traductor.MIN_MAX_TOKENS
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
    assert refused.value.code == 502
    assert too_long.value.code == 400
    assert "clave-secreta" not in capsys.readouterr().out


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
    assert traductor.connection_problem(translator) == "la API rechazó la clave"
    Listing.status = 404  # an API with no listing is not refused for it
    assert traductor.connection_problem(translator) is None
    listing.shutdown()
    listing.server_close()
    assert traductor.connection_problem(translator) == "no hay conexión con la API"
    server.shutdown()


@pytest.mark.parametrize(("status", "said"), [
    (200, None), (401, "la API rechazó la clave"), (404, "no existe el modelo claude-opus-5-5"),
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
    assert traductor.connection_problem(translator) == said
    server.shutdown()


class FakeOllama:
    """Ollama's own API as 0.30.11 answers it (measured 2026-11-05)."""

    def __init__(self, models, answers=None, cloud=()):
        self.requests: list[dict] = []
        self.answers = list(answers or [])
        self.loads: list[int] = []
        self.loaded: dict[str, int] = {}
        self.load_fails: str | None = None
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


def test_the_list_of_ollama_says_which_models_fit_and_why_not(monkeypatch):
    monkeypatch.delenv("BAXY_MIND_LLAMA_SERVER", raising=False)
    ollama = FakeOllama(MODELS)
    got = {m["id"]: m for m in traductor.list_models("local", ollama.url, "")["models"]}
    ollama.server.shutdown()
    assert got["grande:4b"]["fits"] is True and got["grande:4b"]["label"] == "grande:4b · 5,2 GB"
    assert got["qwen3:8b"]["fits"] is False and "40.960" in got["qwen3:8b"]["why"]
    assert got["sin-tools"]["fits"] is False and "herramientas" in got["sin-tools"]["why"]


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


def test_with_baxys_server_a_model_that_declares_little_is_not_refused_for_it(monkeypatch, tmp_path):
    monkeypatch.setattr(traductor, "commit_free", lambda: None)
    server = tmp_path / "llama-server.exe"
    server.write_bytes(b"")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(server))
    ollama = FakeOllama(MODELS)
    got = {m["id"]: m for m in traductor.list_models("local", ollama.url, "")["models"]}
    assert got["qwen3:8b"]["fits"] is True and got["sin-tools"]["fits"] is False
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
    assert backend.load() == "grande:4b no cabe en la memoria de este PC: elige otro modelo o menos contexto"
    ollama.load_fails = "algo distinto"
    assert backend.load() == "Ollama no pudo cargar grande:4b"
    ollama.server.shutdown()
    ollama.server.server_close()
    assert backend.load() == "Ollama no terminó de cargar grande:4b"


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
    assert traductor.memory_problem("m", 2.5 * 2**30, traductor.COMMIT_PER_BYTE_ENGINE) is None
    assert traductor.memory_problem("m", 2.6 * 2**30, traductor.COMMIT_PER_BYTE_ENGINE) is not None
    # By Ollama the same model takes more: 1.7 GB is what fits there.
    assert traductor.memory_problem("m", 1.7 * 2**30) is None
    assert traductor.memory_problem("m", 2.5 * 2**30) is not None
    assert traductor.memory_problem("m", 4 * 2**30, traductor.COMMIT_PER_BYTE_ENGINE) == "m necesita unos 7,8 GB de memoria libre, contando lo que debe quedar para tus programas, y este PC tiene 6,0 GB: elige otro modelo o menos contexto"
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
    assert "no-esta" in told and "grande:4b" in told
    ollama.server.shutdown()
    ollama.server.server_close()
    assert traductor.connection_problem(make("grande:4b")) == "Ollama no responde"


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
    assert traductor.list_models("google", url, "k") == {"error": "la API rechazó la clave"}
    server.shutdown()
    server.server_close()
    assert traductor.list_models("openai", url, "k") == {"error": "no hay conexión"}


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
    assert told and "redirige" in told
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
    assert told == f"la API respondió {status}"


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
    assert "ERROR: la API respondió 422 (bad_input)" in log
    assert (refused.value.code, too_long.value.code) == (502, 400)
    assert ECHOED not in refused.value.read().decode() + too_long.value.read().decode()


@pytest.mark.parametrize("status", [400, 429])
def test_anthropics_error_that_repeats_the_text_leaves_no_text_behind(stack, status, capsys):
    upstream, url, _ = stack
    upstream.answers.append({"status": status, "message": f"invalid: {ECHOED}"})
    with pytest.raises(urllib.error.HTTPError) as refused:
        post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": ECHOED}]})
    log = capsys.readouterr().out
    assert ECHOED not in log
    assert f"ERROR: la API respondió {status} (invalid_request_error)" in log
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
        if stream:
            told = _ask_streaming(url)
            assert '"error"' in told and "finish_reason" not in told
        else:
            with pytest.raises(urllib.error.HTTPError) as refused:
                post(url, "/v1/chat/completions", {"max_tokens": 768, "messages": [{"role": "user", "content": "x"}]})
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
    try:
        told = _ask_streaming(f"http://127.0.0.1:{server.server_address[1]}")
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
            for line in box["lines"]:
                if line.get("id") == request_id and line.get("type") != "catalog.progress":
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
    monkeypatch.setattr(traductor, "memory_problem", lambda *_: None)
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
    assert "fuera de este PC" in problem


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
    assert answer == {"error": "esa dirección redirige a otra: escribe la final"}
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
