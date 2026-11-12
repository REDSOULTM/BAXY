"""A model behind a company's API, with the person's own key, as the llama-server the mind talks to. Off by default: the App
starts this only when the person turned it on in Settings (src/Baxy.App/ExternalModel.cs).

The mind reaches a server on a loopback port with BAXY_MIND_LLAMA_REMOTE, and then starts no llama-server of its own. This
listens on that port, answers what only llama-server has (health, props, tokens, slots) by itself, and sends a person's
turns to Anthropic's Messages API or to an API that speaks OpenAI's chat completions (OpenAI, Gemini's compatibility
endpoint, others). It listens on 127.0.0.1 only and writes no conversation anywhere: its log holds token counts, cost and each failure's status
and code, never an API's words, which may repeat what was sent. It follows no redirect (urllib and the SDK would, with what was
sent).

What stays off here, because the API has no such thing: the doubt (no logprobs, so doubt.read returns None and nothing is
held), reading ahead, and Claude's own reasoning between steps (the mind cuts its history, which would invalidate those
blocks, so they are never sent back).
"""

from __future__ import annotations

import argparse
import base64
import http.client
import ipaddress
import json
import os
import re
import secrets
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, NamedTuple

MODEL = "claude-opus-5-5"
ANTHROPIC_URL = "https://api.anthropic.com"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# USD per million tokens (the Claude API skill's table, cached 2026-10-06). A cache write is 1.25× input. The ceiling can
# only be kept for a model listed here: another provider's prices are not known to this tool, and its console holds the limit.
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "cache_read": 0.20, "cache_write": 5.00, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cache_read": 0.20, "cache_write": 2.50, "output": 10.00},
    # platform.claude.com/docs/en/about-claude/pricing, read 2026-11-08 (cache reads 0.25 for this one).
    "claude-fable-5-1": {"input": 10.00, "cache_read": 0.25, "cache_write": 12.50, "output": 50.00},
}
# max_tokens is a hard cap on thinking plus text (thinking cannot be turned off on this model), and the mind asks for 768.
MIN_MAX_TOKENS = 8000
# What the mind asks for a phrase and not a decision (its notice asks for 24; a decision, 768).
SHORT_REPLY_TOKENS = 64
_ID = re.compile(r"[^a-zA-Z0-9_-]")
_FILL = re.compile(r"^<tool_call>\s*<function=([^>\s]+)>")
_DATA_URL = re.compile(r"^data:(image/[a-z+.-]+);base64,(.+)$", re.S)
_ERROR_CODE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
# An API's «this request cannot be taken as it is» (RFC 9110 §15.5: 400 Bad Request, 415 Unsupported Media Type, 422
# Unprocessable Content): what a model with no vision answers to an image, and what any other fault of a request gets.
NOT_TAKEN = (400, 415, 422)


def _small_png(side: int = 64) -> str:
    """A grey square as a PNG data URL (W3C PNG: signature, IHDR, IDAT, IEND; 8-bit greyscale, each row with filter 0):
    an image no model that sees refuses for what it is."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = (b"\x00" + b"\x80" * side) * side
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 0, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


# Revisión total (M4, 2026-11-09): the image a refused request is asked again with (Translator.refused_its_images).
PROBE_IMAGE = _small_png()


def _with_images(body: dict[str, Any], url: str | None) -> dict[str, Any]:
    """``body`` with ``url`` in place of each of its images, or with none of them (None)."""
    messages = []
    for message in body.get("messages") or []:
        content = message.get("content")
        if isinstance(content, list):
            message = {**message, "content": [
                {**part, "image_url": {**(part.get("image_url") or {}), "url": url}} if part.get("type") == "image_url" else part
                for part in content if url is not None or part.get("type") != "image_url"]}
        messages.append(message)
    return {**body, "messages": messages}


class UpstreamError(Exception):
    def __init__(self, status: int, message: str, upstream: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        # The API's own status, when it answered one.
        self.upstream = upstream
        # Its kind (Refusal.code), for the mind and the App to say why.
        self.code = code


# Refusals that may pass by themselves: asked again, as a server that fell (502). Any other will not change on its own: it goes
# back as one (422), which neither LlmServer nor the mind asks again (VIVO1 F4, 2026-11-09: 5 requests for a template refusal).
PASSING = frozenset({"limite", "saturado", "caido", "lento", "red", "cortado"})


def refused(said: Refusal, too_long: bool = False, upstream: int | None = None) -> UpstreamError:
    """The failure the mind gets for an API's refusal: 400 for a prompt past the context (the mind makes room), 502 for one that
    may pass, 422 for one that will not."""
    status = 400 if too_long else 502 if said.code in PASSING else 422
    return UpstreamError(status, said.text, upstream=upstream, code=said.code)


class _MindLeft(Exception):
    """The mind stopped reading an answer (its time ran out, or it was relaunched): no failure of the API."""


# What a model behind Ollama needs: the prompt, about 49,000 tokens with BAXY's tools, and room to answer and for the turn. Ollama
# cuts a prompt past num_ctx to half of it (measured on 0.30.11: 12,021 tokens read whole at 16,384, 4,098 at 8,192), and caps
# num_ctx at the context_length the model declares, as llama-server does. That number is a declaration and not a wall: qwen3:8b
# declares 40,960 and, with it overridden in BAXY's own server, read 49,545 tokens whole at 78,000 (Engine). By default, the room
# BAXY's own model has (77,824).
OLLAMA_CONTEXT = 78000
OLLAMA_NEEDS = 52000
OLLAMA_CHOICES = (64000, 78000, 96000, 128000, 200000)
# Two loads are enough to know a model's memory at any context: Ollama's own size, a base plus a cost per token. Predicted from
# these two, measured on 2026-11-05: 3-5 % off between 64,000 and 200,000. No formula over the model's metadata gets near it: the
# same one is 9 % off for a Qwen 3 and three times over for a Qwen 3.5, whose layers do not all keep a cache.
OLLAMA_PROBES = (8192, 32768)
OLLAMA_CLOUD = "corre fuera de este PC, en la nube de Ollama"
# What is left for everything else when a model loads. On 2026-11-05 a model of 10.8 GB left this PC with 0.3 GB of its commit limit,
# and Windows began failing other programs' allocations: Opera and WebView2 ended with 0xe0000008.
MEMORY_RESERVE = 3 * 2**30
# What a model whole on the card adds to the commit charge beside its own size: measured on the PC on 2026-11-09 (RTX 4060 Ti,
# llama-server with the product's arguments and Ollama 0.40.15, six loads, documentacion/VRAM_ESTIMADA.md) the charge grew as
# the card did, 1:1 (WDDM backs video memory with system memory, learn.microsoft.com «Mapping virtual addresses to a memory
# segment»), plus 0.9-2.4 GiB of the process's own; a mapped file does not count (Russinovich, «Pushing the Limits of Windows:
# Virtual Memory»), and it was even less with mmap. 2.75 GiB covers the most measured and Ollama's own count being ~124 MiB short.
# The App says the same before a download (OpenModels.CommitHost; ModelMemoryTests holds both equal).
COMMIT_HOST = int(2.75 * 2**30)
# Partly in RAM, only when the person chose it: what was measured on 2026-11-05 and 06, up to 1.7 per byte (mistral-nemo:12b,
# 20 GB for 12.7).
COMMIT_PER_BYTE_PARTIAL = 1.7
# Reading a large model off the disk for the first time (ExternalModel.LocalStartBudget allows for this and the translator's start).
ENGINE_START_SECONDS = 170
# A company's list also has what cannot chat: only this tells a model apart there, and it decides nothing the person says.
NOT_CHAT = re.compile(r"embed|whisper|tts|dall-e|moderation|image|realtime|audio|transcribe|sora|veo|imagen|aqa|search-api|computer-use", re.I)
# The API's base for each provider that speaks OpenAI's chat completions (Gemini: ai.google.dev/gemini-api/docs/openai).
BASE_URLS = {"openai": "https://api.openai.com/v1", "google": "https://generativelanguage.googleapis.com/v1beta/openai"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect comes back as the HTTPError it is: urllib would carry the key elsewhere, even from https to http."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _on_this_pc(url: str) -> bool:
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        return host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _opener(direct: bool) -> Callable[..., Any]:
    """What sends: never along a redirect, and direct, past a proxy set on this PC, for what goes to this PC and must stay here."""
    return urllib.request.build_opener(_NoRedirect, *([urllib.request.ProxyHandler({})] if direct else [])).open


_direct = _opener(True)


def _elsewhere(fields: dict[str, Any]) -> bool:
    """A model Ollama runs in its cloud, however it is named (ListModelResponse and ShowResponse, ollama's api/types.go): what is
    sent to it leaves this PC through the Ollama on this PC, and «Local» says nothing leaves."""
    return bool(fields.get("remote_host") or fields.get("remote_model"))


class Refusal(NamedTuple):
    """What failed, for Settings: its kind (the view says it in the other language by it: EXTERNAL_ERROR) and its words."""

    code: str
    text: str


def say(refusal: Refusal) -> None:
    """The line Settings shows (ExternalModel.LastError): «ERROR[kind]: words»."""
    print(f"ERROR[{refusal.code}]: {refusal.text}", flush=True)


COMPANIES = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "compatible": "Esa API", "local": "El servidor local"}


def _within(provider: str) -> str:
    """The company's name inside a sentence."""
    name = COMPANIES.get(provider, "La API")
    return name if provider in ("anthropic", "openai", "google") else name[0].lower() + name[1:]


# Refusals for money, not for the request. OpenAI's 429 codes and their type (developers.openai.com/api/docs/guides/error-codes:
# «The broader error.type can still be insufficient_quota»); Anthropic's billing_error (platform.claude.com/docs/en/api/errors).
_MONEY = {"insufficient_quota", "credit_balance_exhausted", "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
          "billing_error"}
# Anthropic names two only in its message: the spend limit the person set, a 400 «You have reached your specified API usage
# limits» (platform.claude.com/docs/en/api/rate-limits), and an empty balance, «Your credit balance is too low» (users' reports).
_MONEY_SAID = ("specified api usage limits", "credit balance")


def _no_credit(fields: list[Any], message: str) -> bool:
    """Only whether the message says so is read: its words may repeat the request and are never kept."""
    return any(field in _MONEY for field in fields if isinstance(field, str)) or any(said in message for said in _MONEY_SAID)


# How a server on this PC says the model's chat template cannot be read with BAXY's conversation and tools (its form, never its
# words, which quote the template): llama-server b11609, «Unable to generate parser for this template. Automatic parser generation
# failed … Jinja Exception: Conversation roles must alternate» (mistral:latest, VIVO1 F4, 2026-11-09); Ollama 0.40.15, «chat
# template prompt error … Jinja Exception: System message must be at the beginning.» (Qwen3.5, 2026-11-08).
TEMPLATE_REFUSED = ("unable to generate parser for this template", "jinja exception", "chat template")


def explain(provider: str, model: str, status: int, body: Any) -> Refusal:
    """A refusal in words safe to keep and concrete: what happened, by its status and the code the API gives it (OpenAI:
    {"error": {"code", "type"}}; Anthropic: {"type": "error", "error": {"type"}}; Gemini: [{"error": {"status"}}])."""
    error = body[0] if isinstance(body, list) and body else body
    error = error.get("error") if isinstance(error, dict) else None
    fields = [error.get(name) for name in ("code", "type", "status")] if isinstance(error, dict) else []
    code = next((field for field in fields if isinstance(field, str) and _ERROR_CODE.fullmatch(field)), None)
    message = str(error.get("message") or "").lower() if isinstance(error, dict) else ""
    company = COMPANIES.get(provider, "La API")
    if provider == "local" and status in (400, 500) and any(form in message for form in TEMPLATE_REFUSED):
        return Refusal("plantilla", f"{company} no puede usar {model} con las herramientas de BAXY: la plantilla de chat del "
                                    "modelo no acepta la conversación. Elige otro modelo")
    if 300 <= status < 400:
        return Refusal("redirige", "esa dirección redirige a otra y BAXY no la sigue: escribe la final")
    if status == 402 or _no_credit(fields, message):
        return Refusal("saldo", f"{company} no atiende: tu cuenta no tiene saldo o llegó a su límite de gasto. Revísalo en la consola de {_within(provider)}")
    if status == 401:
        return Refusal("clave", f"{company} rechazó la clave: comprueba que la copiaste entera o crea otra en su consola")
    if status == 403:
        return Refusal("permiso", f"{company} no da permiso a esta clave para usar {model}")
    if status == 404:
        return Refusal("modelo", f"{company} no tiene el modelo {model}: elige otro de la lista")
    if status == 429:
        return Refusal("limite", f"{company} limitó por un momento las llamadas de tu cuenta: espera un minuto y vuelve a pedirlo")
    if status in (503, 529):
        return Refusal("saturado", f"{company} está saturado ahora mismo: vuelve a intentarlo en unos minutos")
    if status >= 500:
        return Refusal("caido", f"{company} tuvo un fallo en su servidor ({status}): vuelve a intentarlo más tarde")
    return Refusal("rechazo", f"{company} respondió {status}" + (f" ({code})" if code else ""))


def _count(value: Any) -> int:
    """A count from an API that is not this tool's: anything else in its place may repeat what was sent, and it goes to the log."""
    return value if isinstance(value, int) else 0


def _wire_name(name: str) -> str:
    return _ID.sub("__", name)


def _tool(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool.get("function") or tool
    schema = function.get("parameters") or {"type": "object", "properties": {}}
    return {"name": _wire_name(str(function["name"])), "description": str(function.get("description") or ""),
            "input_schema": schema}


def _content(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    blocks: list[dict[str, Any]] = []
    for part in content or []:
        kind = part.get("type")
        if kind == "text" and part.get("text"):
            blocks.append({"type": "text", "text": part["text"]})
        elif kind == "image_url":
            url = (part.get("image_url") or {}).get("url") or ""
            image = _DATA_URL.match(url)
            if image:
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": image[1], "data": image[2]}})
            else:
                blocks.append({"type": "image", "source": {"type": "url", "url": url}})
    return blocks


def to_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """OpenAI-shaped messages as the API's: the system text, the turns, and the tool a fill_call started (it writes the
    call's opening as the last assistant message, a prefill the API refuses)."""
    system: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    started: str | None = None
    for index, message in enumerate(messages):
        role = message.get("role")
        if role == "system":
            system.extend(_content(message.get("content")))
        elif role == "tool":
            block = {"type": "tool_result", "tool_use_id": _ID.sub("_", str(message.get("tool_call_id"))),
                     "content": _content(message.get("content")) or [{"type": "text", "text": "(empty)"}]}
            # All the results of one step go in one user message, right after the calls.
            if turns and turns[-1]["role"] == "user" and turns[-1]["content"][-1].get("type") == "tool_result":
                turns[-1]["content"].append(block)
            else:
                turns.append({"role": "user", "content": [block]})
        elif role == "assistant":
            text = message.get("content")
            if index == len(messages) - 1 and isinstance(text, str) and not message.get("tool_calls"):
                fill = _FILL.match(text)
                started = _wire_name(fill[1]) if fill else None
                continue  # the API takes no prefill
            blocks = _content(text)
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                blocks.append({"type": "tool_use", "id": _ID.sub("_", str(call.get("id"))),
                               "name": _wire_name(str(function.get("name"))),
                               "input": arguments if isinstance(arguments, dict) else {}})
            if blocks:
                turns.append({"role": "assistant", "content": blocks})
        else:
            turns.append({"role": "user", "content": _content(message.get("content")) or [{"type": "text", "text": "."}]})
    return system, turns, started


def to_request(body: dict[str, Any], effort: str | None, model: str = MODEL) -> dict[str, Any]:
    """The Messages request of a chat body. temperature, top_p, top_k, seed, logit_bias and logprobs have no place on
    this model (a 400, or nothing to send them to); forced tool use is a 400 too, so a fill_call asks in words."""
    system, turns, started = to_messages(body.get("messages") or [])
    # A reply of a few words (the notice: 24 tokens) at the effort of a decision would think for seconds first: this model always
    # thinks, and effort is what sets how much (platform.claude.com/docs/en/build-with-claude/effort).
    if effort and 0 < int(body.get("max_tokens") or 0) <= SHORT_REPLY_TOKENS:
        effort = "low"
    output: dict[str, Any] = {"effort": effort} if effort else {}
    response_format = body.get("response_format") or {}
    if response_format.get("type") == "json_schema":
        output["format"] = {"type": "json_schema", "schema": response_format["json_schema"]["schema"]}
    request: dict[str, Any] = {
        "model": model, "max_tokens": max(int(body.get("max_tokens") or 0), MIN_MAX_TOKENS), "messages": turns,
        "cache_control": {"type": "ephemeral"},
    }
    if output:
        request["output_config"] = output
    if model in PRICES:
        request.update(betas=[FALLBACK_BETA], fallbacks="default")
    if system:
        request["system"] = system
    tools = [_tool(tool) for tool in body.get("tools") or []]
    if tools:
        request["tools"] = tools
        if body.get("tool_choice") == "none":
            request["tool_choice"] = {"type": "none"}
        elif body.get("parallel_tool_calls") is False:
            request["tool_choice"] = {"type": "auto", "disable_parallel_tool_use": True}
    if started:
        turns.append({"role": "system", "content": f"Call the tool {started} now, with the arguments this conversation gives."})
    return request


def _finish(stop_reason: str | None) -> str:
    return {"tool_use": "tool_calls", "max_tokens": "length"}.get(stop_reason or "", "stop")


def to_reply(message: Any, names: dict[str, str]) -> dict[str, Any]:
    """The API's message as the shape chat() reads: text and calls; thinking blocks are left out on purpose."""
    text = "".join(block.text for block in message.content if block.type == "text")
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        text = f"(Opus declined this request: {category or 'no category'}.)"
    calls = [{"id": block.id, "type": "function",
              "function": {"name": names.get(block.name, block.name), "arguments": json.dumps(block.input, ensure_ascii=False)}}
             for block in message.content if block.type == "tool_use"]
    reply: dict[str, Any] = {"role": "assistant", "content": text}
    if calls:
        reply["tool_calls"] = calls
    usage = message.usage
    read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    written = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    return {"id": message.id, "object": "chat.completion", "model": message.model,
            "choices": [{"index": 0, "finish_reason": _finish(message.stop_reason), "message": reply}],
            "usage": {"prompt_tokens": int(usage.input_tokens) + read + written,
                      "completion_tokens": int(usage.output_tokens)}}


def _show(url: str, model: str) -> dict[str, Any]:
    request = urllib.request.Request(url + "/api/show", data=json.dumps({"model": model}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with _direct(request, timeout=20) as reply:
        return json.loads(reply.read())


def _context_length(show: dict[str, Any]) -> int:
    return next((int(v) for k, v in (show.get("model_info") or {}).items() if k.endswith(".context_length")), 0)


class Ollama:
    """A model the person downloaded in Ollama, through its own API (its OpenAI-shaped one takes no context size, and left to its
    default it reads 2,050 of 49,000 tokens and still answers): BAXY sets the context itself, up to what the model admits.
    A model that does not fit still runs if the person chose it, and the log says so."""

    provider = "local"

    def __init__(self, url: str, model: str, context: int = 0) -> None:
        self.url, self.model = url.rstrip("/"), model
        try:
            show = _show(self.url, model)
        except (OSError, http.client.HTTPException, ValueError):
            show = {}
        self.context = _context_length(show)
        asked = context or OLLAMA_CONTEXT
        self.num_ctx = min(self.context, asked) if self.context else asked
        self.thinks = "thinking" in (show.get("capabilities") or [])
        # Whether it sees: Ollama says so of each model (/api/show «capabilities», «vision»; docs/api.md). One installed with no
        # projector does not, and is not made to.
        self.sees: bool | None = "vision" in (show.get("capabilities") or []) if show else None
        self.remote = _elsewhere(show)

    @property
    def unreachable(self) -> str:
        return f"Ollama no responde en {self.url}"

    def load(self) -> Refusal | None:
        """Into memory now, with the context of every request (with no prompt, Ollama only loads): being connected means it loaded. What
        failed, if it did."""
        body = {"model": self.model, "keep_alive": "30m", "options": {"num_ctx": self.num_ctx}}
        request = urllib.request.Request(self.url + "/api/generate", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with _direct(request, timeout=ENGINE_START_SECONDS):
                return None
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            return (Refusal("memoria", f"{self.model} no cabe en la memoria de este PC: elige otro modelo o menos contexto") if _no_memory(detail)
                    else Refusal("carga", f"Ollama no pudo cargar {self.model}"))
        except (OSError, http.client.HTTPException):
            return Refusal("carga", f"Ollama no terminó de cargar {self.model}")

    def to_request(self, body: dict[str, Any]) -> dict[str, Any]:
        source = list(body.get("messages") or [])
        forced: str | None = None
        if source and source[-1].get("role") == "assistant" and isinstance(source[-1].get("content"), str):
            fill = _FILL.match(source[-1]["content"])
            if fill:
                forced = _wire_name(fill[1])
                source = source[:-1]
        messages: list[dict[str, Any]] = []
        names: dict[str, str] = {}
        for message in source:
            sent: dict[str, Any] = {"role": message.get("role")}
            content = message.get("content")
            if isinstance(content, list):
                sent["content"] = "".join(str(p.get("text") or "") for p in content if p.get("type") == "text")
                images = [_DATA_URL.match((p.get("image_url") or {}).get("url") or "") for p in content if p.get("type") == "image_url"]
                if any(images):
                    sent["images"] = [m[2] for m in images if m]
            else:
                sent["content"] = content or ""
            if message.get("tool_calls"):
                calls = []
                for call in message["tool_calls"]:
                    function = call.get("function") or {}
                    wire = _wire_name(str(function.get("name")))
                    names[str(call.get("id"))] = wire
                    try:
                        arguments = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    calls.append({"id": call.get("id"), "function": {"name": wire, "arguments": arguments if isinstance(arguments, dict) else {}}})
                sent["tool_calls"] = calls
            if message.get("role") == "tool":
                sent["tool_name"] = names.get(str(message.get("tool_call_id")), "")
            messages.append(sent)
        # Ollama's /api/chat has no tool_choice (https://docs.ollama.com/api/chat): what to do now goes as the last turn, a user's,
        # because the model's own chat template may take a system message only first (Qwen3.5 in Ollama 0.40.15: «System
        # message must be at the beginning.», a 500 to each notice and each started call; banco del NB 2026-11-08).
        if forced:
            messages.append({"role": "user", "content": f"Call the tool {forced} now, with the arguments this conversation gives."})
        elif body.get("tool_choice") == "none":
            messages.append({"role": "user", "content": "Answer in words now. Call no tool."})
        options: dict[str, Any] = {"num_ctx": self.num_ctx, "num_predict": int(body.get("max_tokens") or 768)}
        options.update({k: body[k] for k in ("temperature", "top_p", "top_k", "seed") if body.get(k) is not None})
        request: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False, "keep_alive": "30m", "options": options}
        if self.thinks:
            request["think"] = False
        tools = [{"type": "function", "function": {
            **(tool.get("function") or tool), "name": _wire_name(str((tool.get("function") or tool)["name"]))}}
            for tool in body.get("tools") or []]
        if tools:
            request["tools"] = tools
        schema = (body.get("response_format") or {}).get("json_schema") or {}
        if schema.get("schema"):
            request["format"] = schema["schema"]
        return request

    def ask(self, body: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(self.url + "/api/chat", data=json.dumps(self.to_request(body)).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        # It may load first and reads its whole prompt the first time (MindSidecarClient's budget is 300 s).
        with _direct(request, timeout=290) as reply:
            answer = json.loads(reply.read())
        message = answer.get("message") or {}
        calls = []
        for index, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            wire = str(function.get("name"))
            calls.append({"id": str(call.get("id") or f"call_{index}_{time.monotonic_ns()}"), "type": "function",
                          "function": {"name": names.get(wire, wire), "arguments": json.dumps(function.get("arguments") or {}, ensure_ascii=False)}})
        reply_message: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
        if calls:
            reply_message["tool_calls"] = calls
        read = int(answer.get("prompt_eval_count") or 0)
        sent = len(json.dumps([body.get("messages"), body.get("tools")], ensure_ascii=False)) // 4
        if read and read < sent // 2:
            say(Refusal("corto", f"{self.model} leyó {read} tokens de unos {sent}: no le cabe lo que BAXY le envía"))
        finish = "tool_calls" if calls else ("length" if answer.get("done_reason") == "length" else "stop")
        return {"id": "ollama", "object": "chat.completion", "model": self.model,
                "choices": [{"index": 0, "finish_reason": finish, "message": reply_message}],
                "usage": {"prompt_tokens": read, "completion_tokens": int(answer.get("eval_count") or 0)}}


def _ollama_post(url: str, path: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url + path, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with _direct(request, timeout=timeout) as reply:
        return json.loads(reply.read())


def _ollama_running(url: str) -> list[dict[str, Any]]:
    with _direct(url + "/api/ps", timeout=15) as reply:
        return json.loads(reply.read()).get("models") or []


def commit_free() -> int | None:
    """What Windows can still promise (RAM and page file): a model's memory on the graphics card counts against it too."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class Status(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD), ("values", ctypes.c_uint64 * 7)]

    status = Status()
    status.length = ctypes.sizeof(Status)
    # values[3]: ullAvailPageFile.
    return int(status.values[3]) if ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(status)) else None


def _gigabytes(size: float) -> str:
    return f"{size / 2**30:.1f}".replace(".", ",")


def _no_memory(detail: str) -> bool:
    return "out of memory" in detail.lower() or "unable to allocate" in detail.lower()


def memory_problem(model: str, needed: float, partial: bool | None = False) -> str | None:
    """Why this model must not load (what Windows must be able to promise and what it can), or None: whole on the card, its size
    and COMMIT_HOST; partly in RAM, COMMIT_PER_BYTE_PARTIAL; where it goes not known (None: Ollama splits what does not fit the
    free VRAM), the larger of the two; and MEMORY_RESERVE left for the person's programs."""
    free = commit_free()
    whole, split = needed + COMMIT_HOST, needed * COMMIT_PER_BYTE_PARTIAL
    wanted = (split if partial else whole if partial is False else max(whole, split)) + MEMORY_RESERVE
    if free is None or wanted <= free:
        return None
    # RAM, not VRAM: what Windows must be able to promise (2026-11-09: «memoria libre» alone was read as the card's).
    return (f"{model} necesita unos {_gigabytes(wanted)} GB de RAM libre (RAM y archivo de paginación, donde Windows cuenta también lo que va a la tarjeta), "
            f"contando lo que debe quedar para tus programas, y este PC tiene {_gigabytes(free)} GB: elige otro modelo o menos contexto")


def connect_memory_problem(model: str, measured: float, card_bytes: float, partial: bool, whole: bool, on_engine: bool) -> str | None:
    """memory_problem when connecting. What it takes is the larger of the App's estimate from the model's files at this context
    (card_bytes, what the view says; ModelMemory, above what the card showed in 22 loads) and Ollama's measure or the file
    (expected_memory), since Ollama may run with more than the files say (OLLAMA_NUM_PARALLEL). Where it goes: partly in RAM when the person chose it, on Ollama; whole on the card when the App saw it
    fit the free VRAM, or on BAXY's own server, which keeps every layer there; not known otherwise, and then the larger rule."""
    split = True if partial and not on_engine else False if whole or on_engine else None
    return memory_problem(model, max(card_bytes, measured), partial=split)


def expected_memory(url: str, model: str, context: int, cache: Path | None) -> float:
    """What this model takes with this context: what --estimar measured, or at least its file."""
    url = url.rstrip("/")
    with _direct(url + "/api/tags", timeout=15) as reply:
        row = next((m for m in json.loads(reply.read()).get("models") or [] if m.get("name") == model), {})
    known = json.loads(cache.read_text(encoding="utf-8")).get(str(row.get("digest"))) if cache is not None and cache.exists() else None
    return known["base"] + known["perToken"] * context if known and "base" in known else float(row.get("size") or 0)


def _measure_memory(url: str, model: str, context_length: int) -> dict[str, float]:
    low, high = OLLAMA_PROBES
    if context_length and context_length < high:
        low, high = context_length // 4, context_length
    sizes = []
    try:
        for context in (low, high):
            # With no prompt, Ollama only loads the model.
            _ollama_post(url, "/api/generate", {"model": model, "keep_alive": "1m", "options": {"num_ctx": context}}, 170)
            sizes.append(next(int(m.get("size") or 0) for m in _ollama_running(url) if m.get("name") == model))
    finally:
        _ollama_post(url, "/api/generate", {"model": model, "keep_alive": 0}, 30)
        until = time.monotonic() + 15
        while time.monotonic() < until and any(m.get("name") == model for m in _ollama_running(url)):
            time.sleep(0.25)
    per_token = (sizes[1] - sizes[0]) / (high - low)
    return {"base": sizes[0] - per_token * low, "perToken": per_token}


def context_choices(context_length: int, engine: bool) -> list[int]:
    """The sizes worth offering: never less than BAXY's prompt needs. With BAXY's server, whatever the model declares; with no
    server, only up to it."""
    if engine or not context_length:
        return list(OLLAMA_CHOICES)
    choices = [c for c in OLLAMA_CHOICES if c <= context_length]
    if OLLAMA_NEEDS <= context_length < OLLAMA_CHOICES[-1]:
        choices.append(context_length)
    return sorted(set(choices))


def estimate(url: str, model: str, cache: Path | None = None, measure: bool = True) -> dict[str, Any]:
    """The context sizes for this model and the memory each takes, for the person to weigh before talking to it. Measured once per
    version of the model: the model loads for some seconds and is taken out again."""
    url = url.rstrip("/")
    answer: dict[str, Any] = {"options": [{"context": c, "bytes": None} for c in OLLAMA_CHOICES], "recommended": OLLAMA_CONTEXT}
    try:
        show = _show(url, model)
        with _direct(url + "/api/tags", timeout=15) as reply:
            row = next((m for m in json.loads(reply.read()).get("models") or [] if m.get("name") == model), {})
        digest = str(row.get("digest") or model)
        if _elsewhere(row) or _elsewhere(show):
            answer["error"] = f"{model} {OLLAMA_CLOUD}"
            return answer
        answer["commitFreeBytes"] = commit_free()
        context_length = _context_length(show)
        choices = context_choices(context_length, engine_path() is not None and model_file(show) is not None)
        answer.update(contextLength=context_length, options=[{"context": c, "bytes": None} for c in choices],
                      recommended=OLLAMA_CONTEXT if OLLAMA_CONTEXT in choices else max(choices, default=0))
        # Where Ollama keeps the model and its projector: the App says the VRAM from their headers (ModelMemory), since
        # Ollama's own size left out the 120-124 MiB of the CUDA runtime that nvidia-smi saw (2026-11-08).
        answer["modelFiles"] = model_files(show)
        known: dict[str, Any] = {}
        if cache is not None and cache.exists():
            known = json.loads(cache.read_text(encoding="utf-8"))
        memory = known.get(digest)
        # A load Ollama could not do is kept, not done again on the next ask (2026-11-09: the view asking again and again
        # crashed Ollama's runner 9 times in 22 minutes). Connecting still tries once, and says why if it fails.
        if memory is not None and "failed" in memory:
            answer["error"] = "Ollama no pudo cargarlo"
            return answer
        if memory is None and not measure:
            return answer
        if memory is None:
            # Measuring loads it: not on a PC that would start failing programs for it. Nothing has checked the card yet
            # (ExternalModel measures before it can say what fits), so Ollama may split it (INT18 blind review).
            problem = memory_problem(model, float(row.get("size") or 0), partial=None)
            if problem:
                answer["error"] = problem
                return answer
            try:
                memory = _measure_memory(url, model, context_length)
            except urllib.error.HTTPError as error:
                if error.code == 500 and cache is not None:
                    known[digest] = {"failed": "carga"}
                    cache.write_text(json.dumps(known), encoding="utf-8")
                raise
            known[digest] = memory
            if cache is not None:
                cache.write_text(json.dumps(known), encoding="utf-8")
        answer["options"] = [{"context": c, "bytes": int(memory["base"] + memory["perToken"] * c)} for c in choices]
        # What takes the card now and goes when another context is chosen.
        answer["loadedBytes"] = sum(int(m.get("size_vram") or 0) for m in _ollama_running(url))
    except urllib.error.HTTPError as error:
        answer["error"] = "Ollama no pudo cargarlo" if error.code == 500 else f"Ollama respondió {error.code}"
    except (ValueError, OSError, http.client.HTTPException, StopIteration):
        answer["error"] = "Ollama no respondió"
    return answer


def short_of(context: int, need: int) -> str:
    return f"admite {context:,} tokens de contexto y el perfil de herramientas elegido necesita unos {need:,}".replace(",", ".")


def engine_takes_tools(address: str, model: str, key: str = "") -> Refusal | None:
    """Whether BAXY's server reads this model's template with what a turn of the mind sends: one tool and one token, before
    anything is said to be connected. llama-server applies the template to the whole conversation and refuses the request if the
    template does (mistral:latest, VIVO1 F4: its GGUF's template takes only user and assistant one after the other). A probe of a
    system and a user message passed there, and every turn failed: the mind's clock, notes and the person's words are user messages
    in a row (Mind.decide), and a tool's result comes before a note. The probe has that shape."""
    tool = {"type": "function", "function": {"name": "probe", "description": "probe", "parameters": {"type": "object", "properties": {}}}}
    call = {"id": "probe_1", "type": "function", "function": {"name": "probe", "arguments": "{}"}}
    body = {"model": model, "max_tokens": 1, "tools": [tool], "messages": [
        {"role": "system", "content": "s"}, {"role": "user", "content": "12:00"}, {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "", "tool_calls": [call]}, {"role": "tool", "tool_call_id": "probe_1", "content": "ok"},
        {"role": "user", "content": "[nota]"}]}
    request = urllib.request.Request(address.rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})})
    try:
        with _direct(request, timeout=ENGINE_START_SECONDS):
            return None
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read())
        except ValueError:
            detail = None
        return explain("local", model, error.code, detail)
    except (OSError, http.client.HTTPException):
        return Refusal("carga", f"{model} no respondió en el servidor de BAXY")


def local_backend(url: str, model: str, context: int, need: int, server: str | None = None,
                  engine_class: Any = None) -> tuple[Ollama | Compatible, Any, Refusal | None]:
    """Where a model of Ollama runs, and whether BAXY can use it there: past its own context on BAXY's server (``server``) if that
    server takes its template with tools; else on Ollama, up to what it declares. Where it runs, the profile's prompt must fit
    (``need``): if not, the refusal says so and nothing connects. (backend, engine or None, refusal or None)."""
    ollama = Ollama(url, model, context)
    if ollama.context and context > ollama.context and server:
        show = _show(url.rstrip("/"), model)
        if model_file(show):
            engine = (engine_class or Engine)(server, show, model, context)
            address = engine.start()
            if address is None:
                return ollama, None, Refusal("carga", f"{model} no pudo cargarse en el servidor de BAXY con {context:,} tokens".replace(",", "."))
            # PRV1 (PRIV-04): BAXY's server asks its key of every request (Engine.key); the mind's calls reach it through
            # this translator, which carries it as it carries a company's.
            key = str(getattr(engine, "key", "") or "")
            problem = engine_takes_tools(address, model, key)
            if problem is None:
                return Compatible(address, key, model, "local"), engine, None
            engine.stop()
            print(f"{model}: {problem.text}. Con el servidor de BAXY no pasa de su contexto: va con Ollama, hasta "
                  f"{f'{ollama.context:,}'.replace(',', '.')} tokens ({problem.code})", flush=True)
    if need and ollama.num_ctx < need:
        return ollama, None, Refusal("perfil", f"{model} {short_of(ollama.num_ctx, need)}: elige un perfil más pequeño en Ajustes → "
                                               "Herramientas, u otro modelo")
    return ollama, None, None


def engine_path() -> str | None:
    """BAXY's own llama-server: past what a model declares, the one way to give it more context."""
    path = os.environ.get("BAXY_MIND_LLAMA_SERVER", "")
    return path if path and os.path.isfile(path) else None


def model_files(show: dict[str, Any]) -> list[str]:
    """Where Ollama keeps a model's files, the model first and then its projector (each FROM line of /api/show's modelfile)."""
    return [path.strip() for path in re.findall(r"^FROM (.+)$", str(show.get("modelfile") or ""), re.M)]


def model_file(show: dict[str, Any]) -> str | None:
    """Where Ollama keeps the model's file (/api/show's modelfile; its first line, a comment, names the model instead)."""
    found = re.search(r"^FROM (.+)$", str(show.get("modelfile") or ""), re.M)
    return found[1].strip() if found else None


def _end_with_this_process(process: subprocess.Popen[bytes]) -> None:
    """A Windows job that closes when this process ends, however it ends, and takes the server with it: closed from outside, this
    process cannot stop it, and the server then keeps the graphics card from the next model (seen on 2026-11-05, 10.8 GB)."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("user", ctypes.c_int64 * 2), ("flags", wintypes.DWORD), ("working", ctypes.c_size_t * 2), ("active", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", ctypes.c_uint64 * 6), ("memory", ctypes.c_size_t * 4)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    job = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    # 9: JobObjectExtendedLimitInformation. The handle is left open on purpose: only this process's end closes it.
    if not job or not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)) \
            or not kernel.AssignProcessToJobObject(job, int(process._handle)):  # type: ignore[attr-defined]
        print(f"El motor no quedó atado a este proceso: {ctypes.get_last_error()}", flush=True)


class Engine:
    """The file of a model Ollama downloaded, on BAXY's own llama-server, with the same settings the mind gives its model and the
    limit the file declares overridden (--override-kv). The server's GPU is the one BAXY already chose for this PC."""

    def __init__(self, server: str, show: dict[str, Any], model: str, context: int) -> None:
        self.server, self.show, self.model, self.context = server, show, model, context
        self.process: subprocess.Popen[bytes] | None = None
        self.port = 0
        # PRV1 (PRIV-04): a key of its own at each start, as the mind's server has (llm_server.server_key): without one any
        # page or program of this PC could ask this model. Only this translator has it.
        self.key = secrets.token_urlsafe(32)

    def arguments(self, backend: str) -> list[str]:
        from .llm_server import flash_attention, kv_types, slots

        kv = kv_types("")
        limit = next(k for k in self.show["model_info"] if k.endswith(".context_length"))
        return [
            "-m", str(model_file(self.show)), "--host", "127.0.0.1", "--port", str(self.port), "--alias", self.model,
            "-ngl", "99", "-c", str(self.context), *slots(backend), "-fa", flash_attention(backend, kv), "-ctk", kv[0], "-ctv", kv[1],
            "--jinja", "--reasoning", "off", "--reasoning-budget", "0", "--load-mode", "none", "-cram", "0", "-ctxcp", "10",
            "--override-kv", f"{limit}=int:{self.context}",
        ]

    def start(self) -> str | None:
        """Its address, or None with the cause said: the App reads it from the log."""
        from .llm_server import _free_port, declared_backend, declared_build, server_environment

        self.port = _free_port()
        backend = declared_backend(self.server, declared_build(self.server))
        output = tempfile.TemporaryFile()
        self.process = subprocess.Popen([self.server, *self.arguments(backend)], cwd=os.path.dirname(self.server), stdout=output, stderr=subprocess.STDOUT,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=server_environment(self.key, backend))
        _end_with_this_process(self.process)
        url = f"http://127.0.0.1:{self.port}"
        until = time.monotonic() + ENGINE_START_SECONDS
        while time.monotonic() < until and self.process.poll() is None:
            try:
                with _direct(url + "/health", timeout=3):
                    return url + "/v1"
            except (OSError, http.client.HTTPException):
                time.sleep(0.25)
        self.stop()
        output.seek(0)
        short = b"out of memory" in output.read().lower()
        say(Refusal("vram", f"{self.model} con {self.context} tokens de contexto no cabe en la VRAM: elige menos contexto") if short
            else Refusal("carga", f"{self.model} con {self.context} tokens de contexto no pudo cargarse"))
        return None

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()


def list_models(provider: str, url: str, key: str, client: Any = None, need: int = OLLAMA_NEEDS) -> dict[str, Any]:
    """What this key or this PC can use, for the list in Settings: {"models": [{"id", "label", "fits", "why"}]} or {"error"}.
    Asking costs nothing. A model of Ollama fits by its own context against ``need``, the context the tool profile's prompt and a
    turn take (the App says it, --necesita): not by BAXY's server, which may not read its template (VIVO1 F4, local_backend)."""
    try:
        if provider == "anthropic":
            return {"models": [{"id": m.id, "label": m.display_name or m.id, "fits": True} for m in client.models.list() if m.lifecycle != "retired"]}
        if provider == "local":
            with _direct(url.rstrip("/") + "/api/tags", timeout=15) as reply:
                tags = json.loads(reply.read())
            models = []
            for item in tags.get("models") or []:
                name = str(item.get("name"))
                show = _show(url.rstrip("/"), name)
                context = _context_length(show)
                tools = "tools" in (show.get("capabilities") or [])
                sees = "vision" in (show.get("capabilities") or [])
                why = OLLAMA_CLOUD if _elsewhere(item) or _elsewhere(show) else "no sabe usar herramientas" if not tools else None
                if why is None and context and context < need:
                    why = short_of(context, need)
                # «size» of /api/tags is what the model takes on disk («List Local Models», https://github.com/ollama/ollama/blob/main/docs/api.md): what removing it frees.
                weight = int(item.get("size") or 0)
                size = _gigabytes(weight)
                # «bytes» for the Model tab's uninstall (modelos-abiertos), «diskBytes» as vram-contexto named it: the same weight.
                # «modelFiles» for the App alone, which says each row's VRAM from their headers as it does for the chosen one
                # (MOD1 V-07: the list said the weight on disk and nothing of the card) and gives the view no path.
                models.append({"id": name, "label": f"{name} · {size} GB", "fits": why is None, "why": why, "vision": sees,
                               "bytes": weight or None, "diskBytes": weight, "context": context or None,
                               "modelFiles": model_files(show)})
            return {"models": models}
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        with _opener(_on_this_pc(url))(urllib.request.Request(url.rstrip("/") + "/models", headers=headers), timeout=15) as reply:
            listing = json.loads(reply.read())
        ids = [str(m.get("id") or m.get("name") or "").removeprefix("models/") for m in listing.get("data") or listing.get("models") or []]
        chat = [i for i in ids if i and (provider == "compatible" or not NOT_CHAT.search(i))]
        return {"models": [{"id": i, "label": i, "fits": True} for i in sorted(chat)]}
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400:
            return {"error": "esa dirección redirige a otra: escribe la final", "code": "redirige"}
        if error.code in (401, 403) and not key and provider != "anthropic":
            return {"error": "esa dirección pide su clave: pégala otra vez o activa la opción", "code": "clave"}
        try:
            body = json.loads(error.read())
        except ValueError:
            body = None
        said = explain(provider, "", error.code, body)
        return {"error": said.text, "code": said.code}
    except (ValueError, OSError, http.client.HTTPException):
        return {"error": f"no hay conexión con {_within(provider)}", "code": "red"}
    except Exception as error:  # noqa: BLE001 - the SDK's errors, said as the view's text
        status = getattr(error, "status_code", None)
        if isinstance(status, int):
            said = explain(provider, "", status, getattr(error, "body", None))
            return {"error": said.text, "code": said.code}
        return {"error": f"no hay conexión con {_within(provider)}", "code": "red"}


def cost(usage: Any, model: str = MODEL) -> float:
    """The call's USD, or 0.0 for a model whose prices this tool does not know."""
    price = PRICES.get(model)
    if price is None:
        return 0.0
    read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    written = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    return (int(usage.input_tokens) * price["input"] + read * price["cache_read"] + written * price["cache_write"]
            + int(usage.output_tokens) * price["output"]) / 1_000_000


class Compatible:
    """An API that speaks OpenAI's chat completions. Only what such an API takes goes out: the sampling and slot settings
    are llama-server's, and models that reason refuse a temperature. Gemini 3 refuses a later call whose earlier tool call
    lost its thought signature (ai.google.dev/gemini-api/docs/generate-content/thought-signatures), and the mind keeps only
    a call's id, name and arguments, so whatever else the API sent with a call goes back with it."""

    def __init__(self, url: str, key: str, model: str, provider: str) -> None:
        self.url, self.key, self.model, self.provider = url.rstrip("/"), key, model, provider
        # Whether it sees: not known for a company's API that speaks OpenAI's format (OpenAI's and Gemini's models APIs give no
        # model's modalities, and both have models of text only: líder 2026-11-08, never «yes» by default), so the first image is
        # tried (Translator.unseeing); BAXY's own server of an Ollama model (Engine) loads no projector.
        self.sees: bool | None = False if provider == "local" else None
        # A proxy set on this PC would take away, key included, what goes to an address on this PC.
        direct = provider == "local" or _on_this_pc(url)
        # A model on this PC may load first and reads its whole prompt the first time (MindSidecarClient's budget is 300 s).
        self.timeout = 290 if direct else 85
        self.open = _opener(direct)
        self.extras: dict[str, dict[str, Any]] = {}
        self.calls: dict[str, str] = {}

    @property
    def unreachable(self) -> str:
        if self.provider in ("local", "compatible") and _on_this_pc(self.url):
            return f"no responde el servidor local en {self.url}"
        return f"no hay conexión con {_within(self.provider)}: revisa la conexión a internet"

    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        return headers

    def to_request(self, body: dict[str, Any]) -> dict[str, Any]:
        messages = list(body.get("messages") or [])
        forced: str | None = None
        if messages and messages[-1].get("role") == "assistant" and isinstance(messages[-1].get("content"), str):
            fill = _FILL.match(messages[-1]["content"])
            if fill:
                forced = _wire_name(fill[1])
                messages = messages[:-1]
        sent = []
        for message in messages:
            sent.append(message)
            if message.get("tool_calls"):
                calls = []
                for call in message["tool_calls"]:
                    function = call.get("function") or {}
                    calls.append({**call, **self.extras.get(str(call.get("id")), {}),
                                  "function": {**function, "name": _wire_name(str(function.get("name")))}})
                sent[-1] = {**message, "tool_calls": calls}
        request: dict[str, Any] = {"model": self.model, "messages": sent, "max_tokens": max(int(body.get("max_tokens") or 0), MIN_MAX_TOKENS)}
        tools = [{"type": "function", "function": {
            **(tool.get("function") or tool), "name": _wire_name(str((tool.get("function") or tool)["name"]))}}
            for tool in body.get("tools") or []]
        if tools:
            request["tools"] = tools
            if forced:
                request["tool_choice"] = {"type": "function", "function": {"name": forced}}
            elif body.get("tool_choice") == "none":
                request["tool_choice"] = "none"
        if body.get("response_format"):
            request["response_format"] = body["response_format"]
        return request

    def ask(self, body: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.url + "/chat/completions", data=json.dumps(self.to_request(body)).encode("utf-8"), headers=self.headers())
        with self.open(request, timeout=self.timeout) as reply:
            answer = json.loads(reply.read())
        message = (answer.get("choices") or [{}])[0].get("message") or {}
        for call in message.get("tool_calls") or []:
            extra = {key: value for key, value in call.items() if key not in ("id", "type", "function", "index")}
            if extra:
                self.extras[str(call.get("id"))] = extra
            function = call.get("function") or {}
            function["name"] = names.get(function.get("name"), function.get("name"))
        return answer


def _input_content(content: Any) -> str | list[dict[str, Any]]:
    """A chat message's content as the Responses API takes it: text as is, and each part as an input_text or input_image."""
    if not isinstance(content, list):
        return str(content or "")
    parts: list[dict[str, Any]] = []
    for part in content:
        if part.get("type") == "text" and part.get("text"):
            parts.append({"type": "input_text", "text": part["text"]})
        elif part.get("type") == "image_url":
            parts.append({"type": "input_image", "image_url": (part.get("image_url") or {}).get("url") or ""})
    return parts


class Responses(Compatible):
    """OpenAI by its Responses API, the one its current models take tools by: gpt-6.1-sol and gpt-6.1-terra call tools only
    there (developers.openai.com/api/docs/models/gpt-6.1-sol). Stateless (store false: nothing of the conversation is kept by
    OpenAI for later), so the reasoning items that came with a call go back with it, as the function-calling guide asks
    (developers.openai.com/api/docs/guides/function-calling, «must also be passed back with tool call outputs»): they are
    encrypted and this keeps them by the call they came with, as Compatible keeps Gemini's signatures."""

    def to_request(self, body: dict[str, Any]) -> dict[str, Any]:
        messages = list(body.get("messages") or [])
        forced: str | None = None
        if messages and messages[-1].get("role") == "assistant" and isinstance(messages[-1].get("content"), str):
            fill = _FILL.match(messages[-1]["content"])
            if fill:
                forced = _wire_name(fill[1])
                messages = messages[:-1]
        items: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role == "tool":
                items.append({"type": "function_call_output", "call_id": str(message.get("tool_call_id")),
                              "output": message["content"] if isinstance(message.get("content"), str)
                              else "".join(str(p.get("text") or "") for p in message.get("content") or [] if p.get("type") == "text")})
                continue
            content = _input_content(message.get("content"))
            if content:
                items.append({"role": "developer" if role == "system" else role, "content": content})
            for call in message.get("tool_calls") or [] if role == "assistant" else []:
                function = call.get("function") or {}
                items.extend(self.extras.get(str(call.get("id")), {}).get("reasoning") or [])
                items.append({"type": "function_call", "call_id": str(call.get("id")), "name": _wire_name(str(function.get("name"))),
                              "arguments": function.get("arguments") or "{}"})
        request: dict[str, Any] = {"model": self.model, "input": items, "store": False,
                                   "max_output_tokens": max(int(body.get("max_tokens") or 0), MIN_MAX_TOKENS)}
        tools = [{"type": "function", "name": _wire_name(str((tool.get("function") or tool)["name"])),
                  "description": str((tool.get("function") or tool).get("description") or ""),
                  "parameters": (tool.get("function") or tool).get("parameters") or {"type": "object", "properties": {}}}
                 for tool in body.get("tools") or []]
        if tools:
            request["tools"] = tools
            if forced:
                request["tool_choice"] = {"type": "function", "name": forced}
            elif body.get("tool_choice") == "none":
                request["tool_choice"] = "none"
            if body.get("parallel_tool_calls") is False:
                request["parallel_tool_calls"] = False
        schema = (body.get("response_format") or {}).get("json_schema") or {}
        if schema.get("schema"):
            request["text"] = {"format": {"type": "json_schema", "name": str(schema.get("name") or "answer"), "schema": schema["schema"],
                                          "strict": bool(schema.get("strict"))}}
        return request

    def ask(self, body: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.url + "/responses", data=json.dumps(self.to_request(body)).encode("utf-8"), headers=self.headers())
        with self.open(request, timeout=self.timeout) as reply:
            answer = json.loads(reply.read())
        text, calls, reasoning = "", [], []
        for item in answer.get("output") or []:
            kind = item.get("type")
            if kind == "reasoning":
                reasoning.append(item)
            elif kind == "message":
                text += "".join(str(part.get("text") or "") for part in item.get("content") or [] if part.get("type") == "output_text")
            elif kind == "function_call":
                call_id = str(item.get("call_id"))
                if reasoning:
                    self.extras[call_id] = {"reasoning": reasoning}
                    reasoning = []
                wire = str(item.get("name"))
                calls.append({"id": call_id, "type": "function",
                              "function": {"name": names.get(wire, wire), "arguments": str(item.get("arguments") or "{}")}})
        message: dict[str, Any] = {"role": "assistant", "content": text}
        if calls:
            message["tool_calls"] = calls
        cut = answer.get("status") == "incomplete" and (answer.get("incomplete_details") or {}).get("reason") == "max_output_tokens"
        usage = answer.get("usage") or {}
        return {"id": str(answer.get("id") or "openai"), "object": "chat.completion", "model": str(answer.get("model") or self.model),
                "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "length" if cut else "stop", "message": message}],
                "usage": {"prompt_tokens": _count(usage.get("input_tokens")), "completion_tokens": _count(usage.get("output_tokens"))}}


class Spend:
    """What has been spent, kept across starts in a file of counts only, against a ceiling that stops the calls."""

    def __init__(self, path: Path, ceiling: float) -> None:
        self.path, self.ceiling = path, ceiling
        self.total = 0.0
        self._lock = threading.Lock()
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                self.total += float(json.loads(line)["usd"])

    @property
    def spent(self) -> bool:
        return self.total >= self.ceiling

    def add(self, message: Any, seconds: float) -> None:
        usage = message.usage
        self.count(message.model, message.stop_reason, usage.input_tokens, usage.output_tokens,
                   getattr(usage, "cache_read_input_tokens", 0), getattr(usage, "cache_creation_input_tokens", 0),
                   cost(usage, message.model), seconds)

    def count(self, model: str, stop: Any, tokens_in: Any, tokens_out: Any, read: Any, written: Any, usd: float,
              seconds: float) -> None:
        with self._lock:
            self.total += usd
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps({
                    "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model, "stop": stop, "in": tokens_in, "out": tokens_out,
                    "cache_read": read, "cache_write": written, "s": round(seconds, 1), "usd": round(usd, 5)}) + "\n")
        limit = f" de {self.ceiling:.2f}" if self.ceiling != float("inf") else ""
        print(f"{time.strftime('%H:%M:%S')} {seconds:5.1f} s  {tokens_in} + {tokens_out} tokens  {usd:.4f} USD  "
              f"llevas {self.total:.2f}{limit} USD", flush=True)


class Translator:
    def __init__(self, client: Any, spend: Spend, effort: str | None, model: str = MODEL, compatible: Compatible | Ollama | None = None) -> None:
        self.client, self.spend, self.effort, self.model, self.compatible = client, spend, effort, model, compatible
        # Claude's models say whether they take images (Models API «capabilities.image_input», read in connection_problem); not
        # said, not known.
        self.anthropic_sees: bool | None = None
        # Whether the model in use answered a request with an image: a later refusal of one is then that request's.
        self.took_image = False

    @property
    def sees(self) -> bool | None:
        """Whether the model in use takes images: False is known, None is not known (it is asked)."""
        return self.compatible.sees if self.compatible is not None else self.anthropic_sees

    def unseeing(self, body: dict[str, Any]) -> bool:
        """A request with an image for a model that does not see (the capture's description, the click's vision): sending it
        would have it answer on what it never saw. Pedido del dueño 2026-11-08: a model with no vision is used as it is."""
        return self.images(body) and self.sees is False

    @staticmethod
    def images(body: dict[str, Any]) -> bool:
        return any(isinstance(m.get("content"), list) and any(p.get("type") == "image_url" for p in m["content"])
                   for m in body.get("messages") or [])

    def learned_unseeing(self) -> None:
        """An API refused an image as a request it cannot take: its model does not see, from now on."""
        if self.compatible is not None:
            self.compatible.sees = False
        else:
            self.anthropic_sees = False

    def refused_its_images(self, body: dict[str, Any], refusal: UpstreamError) -> bool:
        """Whether ``refusal`` of ``body``, a request with images to a model whose sight is not known, says the model does
        not see. Revisión total (M4, 2026-11-09): any 400, 415 or 422 said so, for the whole session, and an API answers
        those to a model that sees too: an image past its limits (OpenAI, «Images that exceed the 30,000-patch limit after
        processing are rejected, not automatically resized», developers.openai.com/api/docs/guides/images-vision; Claude,
        «rejected with an invalid_request_error», platform.claude.com/docs/en/build-with-claude/vision), another field of
        the request («400 - Invalid service_tier argument», developers.openai.com/api/docs/guides/error-codes), a spend
        limit («The API also returns a 400 when usage reaches … spend limit», platform.claude.com/docs/en/api/errors),
        or just «400: Bad Request (missing parameters, invalid JSON, etc.)» (docs.ollama.com/api/errors); all read
        2026-11-09. No API says in a typed field that it was the image, and the words of each differ, so the model is
        asked: the same request with a small image (PROBE_IMAGE) and, if that one is refused the same way, with no image.
        Only one that refuses the small image and answers without any does not see. One that takes the small image sees
        (took_image: nothing is tried for it again), and one that refuses all three refused something else. The two
        requests go only after a refusal, once per model that does not see; their answers are never used."""
        if self.sees is not None or self.took_image or refusal.upstream not in NOT_TAKEN or not self.images(body):
            return False
        small = self._refusal_of(_with_images(body, PROBE_IMAGE))
        if small is None or small.upstream not in NOT_TAKEN:
            return False
        blind = self._refusal_of(_with_images(body, None)) is None
        print(f"{self.model}: rechazó también una imagen pequeña y " + ("contestó sin ninguna: no ve imágenes" if blind
              else "la petición sin ninguna: lo rechazado no es la imagen"), flush=True)
        return blind

    def _refusal_of(self, body: dict[str, Any]) -> UpstreamError | None:
        """How the API refused ``body``, or None when it answered it."""
        try:
            self.ask(body, lambda _text: None)
        except UpstreamError as refusal:
            return refusal
        except Exception:  # noqa: BLE001 - as Handler._reply: whatever cut the answer, nothing is learned from it
            return UpstreamError(502, "the connection to the API was cut")
        return None

    def _ask_compatible(self, body: dict[str, Any], names: dict[str, str], on_text: Callable[[str], None]) -> dict[str, Any]:
        started = time.monotonic()
        try:
            answer = self.compatible.ask(body, names)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            try:
                said = explain(self.compatible.provider, self.model, error.code, json.loads(detail))
            except ValueError:
                said = explain(self.compatible.provider, self.model, error.code, None)
            if self.compatible.provider == "local" and _no_memory(detail):
                said = Refusal("memoria", f"{self.model} no cabe en la memoria de este PC: elige otro modelo o menos contexto")
            say(said)
            too_long = error.code == 400 and any(word in detail.lower() for word in ("context_length", "too long", "exceeds"))
            raise refused(said, too_long, upstream=error.code) from error
        except TimeoutError as error:
            say(Refusal("lento", f"{COMPANIES.get(self.compatible.provider, 'La API')} no respondió a tiempo: vuelve a pedirlo"))
            raise UpstreamError(502, "the API did not answer in time") from error
        except (OSError, http.client.HTTPException, ValueError) as error:
            # Not its text: a key that does not fit a header comes back in it.
            say(Refusal("red", self.compatible.unreachable))
            raise UpstreamError(502, "no connection to the API") from error
        usage = answer.get("usage") or {}
        finish = (answer.get("choices") or [{}])[0].get("finish_reason")
        self.spend.count(self.model, finish if isinstance(finish, str) and _ERROR_CODE.fullmatch(finish) else None, _count(usage.get("prompt_tokens")),
                         _count(usage.get("completion_tokens")), 0, 0, 0.0, time.monotonic() - started)
        text = ((answer.get("choices") or [{}])[0].get("message") or {}).get("content")
        if text:
            on_text(text)
        self.took_image = self.took_image or self.images(body)
        return answer

    def local(self, body: dict[str, Any]) -> dict[str, Any] | None:
        """A reply that costs nothing, for what is not a decision: the warm-up (one token, to read the prompt into a slot
        this server does not have). The notice while a call runs (Mind.notice_of) is the model's own words and goes to it: answered
        here with nothing, BAXY said nothing during a mission with any model but its own (pedido del dueño 2026-11-08); its time
        is the mind's, by what a decision takes here."""
        tokens = int(body.get("max_tokens") or 0)
        if tokens == 1:
            estimate = len(json.dumps([body.get("messages"), body.get("tools")], ensure_ascii=False)) // 4
            return {"id": "local", "object": "chat.completion", "model": self.model,
                    "choices": [{"index": 0, "finish_reason": "length", "message": {"role": "assistant", "content": ""}}],
                    "usage": {"prompt_tokens": estimate, "completion_tokens": 1}}
        return None

    def ask(self, body: dict[str, Any], on_text: Callable[[str], None]) -> dict[str, Any]:
        if self.spend.spent:
            print(f"TOPE DE GASTO: {self.spend.total:.2f} de {self.spend.ceiling:.2f} USD. No se llama a la API.", flush=True)
            raise UpstreamError(402, "the test's spending ceiling is reached")
        names = {_wire_name(str((t.get("function") or t)["name"])): str((t.get("function") or t)["name"])
                 for t in body.get("tools") or []}
        if self.compatible is not None:
            return self._ask_compatible(body, names, on_text)
        import anthropic  # only Anthropic's path needs it (Ollama and the compatible APIs do not); the mind never imports this module

        started = time.monotonic()
        try:
            with self.client.beta.messages.stream(**to_request(body, self.effort, self.model)) as stream:
                for text in stream.text_stream:
                    on_text(text)
                message = stream.get_final_message()
        except anthropic.BadRequestError as error:
            said = explain("anthropic", self.model, 400, error.body)
            say(said)
            # The mind reads a 400 as «past the context» and cuts its history: only that one goes through as a 400.
            too_long = "too long" in str(error.message).lower()
            raise refused(said, too_long, upstream=400) from error
        except anthropic.APIStatusError as error:
            said = explain("anthropic", self.model, error.status_code, error.body)
            say(said)
            raise refused(said, upstream=error.status_code) from error
        except anthropic.APITimeoutError as error:
            say(Refusal("lento", "Anthropic no respondió a tiempo: vuelve a pedirlo"))
            raise UpstreamError(502, "the API did not answer in time") from error
        except anthropic.APIConnectionError as error:
            say(Refusal("red", "no hay conexión con Anthropic: revisa la conexión a internet"))
            raise UpstreamError(502, "no connection to the API") from error
        except (anthropic.APIError, ValueError) as error:
            # The SDK's words quote what it could not read, a call's arguments among them.
            say(Refusal("ilegible", f"Anthropic respondió algo que no se pudo leer ({type(error).__name__})"))
            raise UpstreamError(502, "an answer that could not be read") from error
        self.spend.add(message, time.monotonic() - started)
        self.took_image = self.took_image or self.images(body)
        return to_reply(message, names)

    def tokens(self, text: str) -> list[int]:
        # The mind only needs <tool_call> to be one token and a count of about the right size for what fits its context.
        return [1] if text == "<tool_call>" else [0] * (len(text) // 4 + 1)


def _handler(translator: Translator) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - no request lines in the console
            pass

        def _json(self, status: int, value: dict[str, Any]) -> None:
            data = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _from_a_page(self) -> bool:
            """A page in a browser reaches this port too, and each call spends the person's key: its requests carry an
            Origin, or another Host through a name rebound to this address. BAXY's own processes send neither."""
            if self.headers.get("Origin") is None and self.headers.get("Host") == f"127.0.0.1:{self.server.server_address[1]}":
                return False
            self._json(403, {"error": {"message": "forbidden"}})
            return True

        def do_GET(self) -> None:  # noqa: N802
            if self._from_a_page():
                return
            if self.path == "/health":
                self._json(200, {"status": "ok"})
            elif self.path == "/props":
                self._json(200, {"total_slots": 1, "model_path": translator.model, "build_info": "external_model",
                                 "default_generation_settings": {"n_ctx": 0}, "vision": translator.sees})
            else:
                self._json(404, {"error": {"message": "not found"}})

        def _event(self, value: dict[str, Any] | str) -> None:
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            self.wfile.write(f"data: {text}\n\n".encode("utf-8"))
            self.wfile.flush()

        def _text(self, text: str) -> None:
            try:
                self._event({"choices": [{"index": 0, "delta": {"content": text}}]})
            except OSError as error:
                raise _MindLeft from error

        def _reply(self, body: dict[str, Any], on_text: Callable[[str], None]) -> dict[str, Any]:
            """What the API answered, or a failure the mind can read: anything else ends the answer where it was cut, and
            the mind would take that for a whole answer, empty or half said."""
            try:
                return translator.local(body) or translator.ask(body, on_text)
            except (UpstreamError, _MindLeft):
                raise
            except Exception as error:  # noqa: BLE001 - its kind only: the words may quote what was sent
                say(Refusal("cortado", f"la conexión con el modelo se cortó ({type(error).__name__})"))
                raise UpstreamError(502, "the connection to the API was cut") from error

        def _chat(self, body: dict[str, Any]) -> None:
            if translator.unseeing(body):
                # 501: this server has no such thing (the core reads it as no vision here, CaptureVisionAdapter).
                self._json(501, {"error": {"code": "model_without_vision", "message": "the model in use does not see images"}})
                return
            if not body.get("stream"):
                try:
                    reply = self._reply(body, lambda _text: None)
                except UpstreamError as error:
                    # Not known whether it sees, and it refuses an image while it answers the same request without one:
                    # it does not.
                    if translator.refused_its_images(body, error):
                        translator.learned_unseeing()
                        self._json(501, {"error": {"code": "model_without_vision", "message": "the model in use does not see images"}})
                        return
                    self._json(error.status, {"error": {"code": error.code, "message": str(error)}})
                    return
                self._json(200, reply)
                return
            # As llama-server: a failure before the first word is the answer's HTTP status (LlmServer reads it, and the mind does
            # not take it for a broken stream to ask again: VIVO1 F4); one after it, an event in the stream.
            opened = False

            def open_stream() -> None:
                nonlocal opened
                if not opened:
                    opened = True
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()

            def text(words: str) -> None:
                open_stream()
                self._text(words)

            try:
                reply = self._reply(body, text)
            except _MindLeft:
                return
            except UpstreamError as error:
                if opened:
                    self._event({"error": {"code": error.code, "message": str(error)}})
                else:
                    self._json(error.status, {"error": {"code": error.code, "message": str(error)}})
                return
            open_stream()
            message = reply["choices"][0]["message"]
            delta: dict[str, Any] = {}
            if message.get("tool_calls"):
                delta["tool_calls"] = [{**call, "index": i} for i, call in enumerate(message["tool_calls"])]
            self._event({"id": reply["id"], "model": reply["model"], "usage": reply["usage"],
                         "choices": [{"index": 0, "delta": delta, "finish_reason": reply["choices"][0]["finish_reason"]}]})
            self._event("[DONE]")

        def do_POST(self) -> None:  # noqa: N802
            # All of it even to refuse: closing over an unread body resets the connection, and the refusal may not arrive.
            sent = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self._from_a_page():
                return
            body = json.loads(sent or b"{}")
            path = self.path.split("?")[0]
            if path == "/v1/chat/completions":
                self._chat(body)
            elif path == "/tokenize":
                self._json(200, {"tokens": translator.tokens(str(body.get("content") or ""))})
            elif path == "/apply-template":
                self._json(200, {"prompt": ""})
            elif path == "/completion":
                self._json(200, {"content": ""})
            elif path.startswith("/slots/"):
                # No slot here: the kept prefix and the vision's set-aside state have nothing to save or put back.
                self._json(200, {"n_saved": 1, "n_restored": 1, "n_erased": 1})
            else:
                self._json(404, {"error": {"message": "not found"}})

    return Handler


# The translator's runtime predates the SDK (the lock has it since 2026-11-05, 755ec048c): said as it is, not as a closed translator.
NO_SDK = Refusal("sdk", "a esta instalación de BAXY le falta el componente de Anthropic: actualiza BAXY o reinstálalo")


def anthropic_client(key: str) -> Any:
    """Anthropic's own address with the person's own key, as Settings says. Left to itself the SDK takes both from whatever
    this machine has in ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN and a profile, follows redirects, adds the headers of
    ANTHROPIC_CUSTOM_HEADERS, and with ANTHROPIC_LOG writes each request's body to this log."""
    os.environ.pop("ANTHROPIC_LOG", None)
    os.environ.pop("ANTHROPIC_CUSTOM_HEADERS", None)
    import anthropic

    return anthropic.Anthropic(api_key=key, base_url=ANTHROPIC_URL, http_client=anthropic.DefaultHttpxClient(follow_redirects=False))


def connection_problem(translator: Translator) -> Refusal | None:
    """Why this key or model cannot work, asked before anything else: listing costs nothing, and the person learns at once
    rather than at their first turn. An API that has no such listing is not refused for it."""
    compatible = translator.compatible
    if isinstance(compatible, Ollama):
        try:
            with _direct(compatible.url + "/api/tags", timeout=15) as reply:
                rows = {str(m.get("name")): m for m in json.loads(reply.read()).get("models") or []}
        except (OSError, http.client.HTTPException, ValueError):
            return Refusal("ollama", "Ollama no responde")
        if compatible.model not in rows:
            return Refusal("modelo", f"Ollama no tiene el modelo {compatible.model}; tiene: {', '.join(sorted(rows))[:200]}")
        return Refusal("nube", f"{compatible.model} {OLLAMA_CLOUD}") if _elsewhere(rows[compatible.model]) else None
    if compatible is not None:
        # A company's list may leave out models it does serve, so its model is asked by its name (OpenAI's and Gemini's
        # «Retrieve a model»: developers.openai.com/api/reference/resources/models, ai.google.dev/gemini-api/docs/openai).
        company = compatible.provider in ("openai", "google")
        path = "/models/" + urllib.parse.quote(compatible.model, safe="") if company else "/models"
        request = urllib.request.Request(compatible.url + path, headers=compatible.headers())
        try:
            with compatible.open(request, timeout=15) as reply:
                listing = json.loads(reply.read())
        except urllib.error.HTTPError as error:
            if 300 <= error.code < 400:
                return Refusal("redirige", "esa dirección redirige a otra: escribe la final")
            if error.code in (401, 402, 403, 429) or (company and error.code == 404):
                try:
                    body = json.loads(error.read())
                except ValueError:
                    body = None
                return explain(compatible.provider, compatible.model, error.code, body)
            return None
        except (OSError, http.client.HTTPException):
            return Refusal("red", compatible.unreachable)
        except ValueError:
            return None
        ids = {str(m.get("id")) for m in listing.get("data") or [] if isinstance(m, dict)} if isinstance(listing, dict) else set()
        # Only a server on this PC: a company's list may leave out models it does serve.
        if compatible.provider == "local" and ids and compatible.model not in ids:
            return Refusal("modelo", f"ese servidor no tiene el modelo {compatible.model}; tiene: {', '.join(sorted(ids))[:200]}")
        return None
    import anthropic

    try:
        capabilities = translator.client.models.retrieve(translator.model).capabilities
        # The list offers every model of this key, and one with no effort answers a 400 to asking for it.
        if capabilities is not None and not capabilities.effort.supported:
            translator.effort = None
        image_input = getattr(capabilities, "image_input", None) if capabilities is not None else None
        if image_input is not None and isinstance(getattr(image_input, "supported", None), bool):
            translator.anthropic_sees = image_input.supported
    except anthropic.APIStatusError as error:
        return explain("anthropic", translator.model, error.status_code, error.body)
    except anthropic.APIConnectionError:
        return Refusal("red", "no hay conexión con Anthropic: revisa la conexión a internet")
    return None


class _Server(ThreadingHTTPServer):
    # Windows' SO_REUSEADDR would let another process listen on this port too, and take some of the person's turns.
    allow_reuse_address = False

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Its kind only: a traceback quotes the API's words, and this console is the log. Not an ERROR line, which Settings
        shows: the mind going away in the middle of an answer says nothing about the key."""
        print(f"Fallo al atender una petición: {sys.exc_info()[0].__name__}", flush=True)


def serve(translator: Translator, port: int) -> ThreadingHTTPServer:
    return _Server(("127.0.0.1", port), _handler(translator))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A model by API as the mind's llama-server.")
    parser.add_argument("--puerto", type=int, default=8099)
    parser.add_argument("--tope-usd", type=float, default=float("inf"), help="stops calling the API past this total; none by default")
    parser.add_argument("--esfuerzo", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--gasto", type=Path, help="counts and cost, never a conversation")
    parser.add_argument("--listar", action="store_true", help="print what this key or this PC can use, as JSON, and end")
    parser.add_argument("--estimar", action="store_true", help="print this Ollama model's context sizes and their memory, as JSON, and end")
    parser.add_argument("--estimaciones", type=Path, help="what --estimar already measured")
    parser.add_argument("--sin-medir", action="store_true", help="--estimar only says what is known: the model is in use, and measuring takes it out")
    parser.add_argument("--contexto", type=int, default=0, help="the context an Ollama model gets")
    parser.add_argument("--en-parte", action="store_true", help="the person chose to run it partly in RAM at this context (ExternalModel)")
    parser.add_argument("--vram-bytes", type=int, default=0, help="the App's estimate from the model's files at this context (ExternalModel.MemoryArguments)")
    parser.add_argument("--entero", action="store_true", help="the App saw that estimate fit the free VRAM: whole on the card")
    parser.add_argument("--necesita", type=int, default=0,
                        help="the context the tool profile's prompt and a turn take: a local model with less is not offered nor connected")
    parser.add_argument("--proveedor", default="anthropic", choices=["anthropic", "openai", "google", "local", "compatible"])
    parser.add_argument("--modelo", default=MODEL)
    parser.add_argument("--url", default="", help="the base URL of an OpenAI-compatible API")
    parser.add_argument("--registro", type=Path, help="write this console to a file (the App reads its last failure)")
    parser.add_argument("--con-padre", action="store_true", help="end when stdin closes: the App that started this is gone")
    parser.add_argument("--sin-comprobar", action="store_true", help="do not ask the API whether the key works")
    args = parser.parse_args(argv)
    if args.estimar:
        print(json.dumps(estimate(args.url, args.modelo, args.estimaciones, not args.sin_medir), ensure_ascii=False), flush=True)
        return 0
    if args.listar:
        key = os.environ.get("BAXY_EXTERNAL_API_KEY", "")
        client = None
        if args.proveedor == "anthropic":
            try:
                client = anthropic_client(os.environ.get("ANTHROPIC_API_KEY", ""))
            except ImportError:
                print(json.dumps({"error": NO_SDK.text, "code": NO_SDK.code}, ensure_ascii=False), flush=True)
                return 0
        print(json.dumps(list_models(args.proveedor, args.url or BASE_URLS.get(args.proveedor, ""), key, client, args.necesita or OLLAMA_NEEDS), ensure_ascii=False), flush=True)
        return 0
    if args.gasto is None:
        parser.error("--gasto is required")
    if args.registro:
        args.registro.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = args.registro.open("w", encoding="utf-8", buffering=1)
        # Its kind only, as _Server.handle_error: a traceback quotes the API's words, and this console is the log.
        sys.excepthook = lambda kind, _value, _traceback: print(f"Fallo: {kind.__name__}", flush=True)
    engine: Engine | None = None
    if args.con_padre:
        # With its server, which holds the graphics card otherwise.
        threading.Thread(target=lambda: (sys.stdin.read(), engine and engine.stop(), os._exit(0)), daemon=True).start()
    spend = Spend(args.gasto, args.tope_usd)
    if args.proveedor == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Falta ANTHROPIC_API_KEY. Define la variable en esta consola y vuelve a lanzar.", file=sys.stderr)
            return 2
        try:
            client = anthropic_client(os.environ["ANTHROPIC_API_KEY"])
        except ImportError:
            say(NO_SDK)
            return 3
        translator = Translator(client, spend, args.esfuerzo, args.modelo)
    else:
        key = os.environ.get("BAXY_EXTERNAL_API_KEY", "")
        url = args.url or BASE_URLS.get(args.proveedor, "")
        if not url or (not key and args.proveedor in ("openai", "google")):
            print("Falta BAXY_EXTERNAL_API_KEY o la URL de la API.", file=sys.stderr)
            return 2
        # No ceiling is kept for these: their prices are not known here.
        spend.ceiling = float("inf")
        if args.proveedor == "local":
            try:
                # Past what the model declares, it goes on BAXY's own server (Engine below).
                on_engine = args.contexto > _context_length(_show(url.rstrip("/"), args.modelo)) and engine_path() is not None
                problem = connect_memory_problem(args.modelo, expected_memory(url, args.modelo, args.contexto, args.estimaciones),
                                                 args.vram_bytes, args.en_parte, args.entero, on_engine)
            except (ValueError, OSError, http.client.HTTPException):
                problem = None  # said below, when it does not answer
            if problem:
                say(Refusal("memoria", problem))
                return 3
        backend: Compatible | Ollama
        if args.proveedor == "local":
            if Ollama(url, args.modelo, args.contexto).remote:
                say(Refusal("nube", f"{args.modelo} {OLLAMA_CLOUD}"))
                return 3
            backend, engine, refusal = local_backend(url, args.modelo, args.contexto, args.necesita, engine_path())
            if refusal:
                say(refusal)
                return 3
        else:
            backend = Responses(url, key, args.modelo, args.proveedor) if args.proveedor == "openai" else Compatible(url, key, args.modelo, args.proveedor)
        translator = Translator(None, spend, args.esfuerzo, args.modelo, backend)
    problem = None if args.sin_comprobar else connection_problem(translator)
    if not problem and not args.sin_comprobar and isinstance(translator.compatible, Ollama):
        problem = translator.compatible.load()
    if problem:
        say(problem)
        if engine:
            engine.stop()
        return 3
    server = serve(translator, args.puerto)
    print(f"Traductor en 127.0.0.1:{args.puerto} · {args.proveedor} · {args.modelo} · esfuerzo {args.esfuerzo} · "
          f"llevas {spend.total:.2f} USD", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
