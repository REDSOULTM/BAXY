"""The local model server: one llama-server process owned by the mind, one slot, its prompt prefix kept in cache and on disk."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


class _StreamBroken(Exception):
    """A streamed chat ended with an error after its first token, or its stream could not be read."""


def _tell(on_text: Callable[[str | None, bool], bool], text: str | None, done: bool) -> bool:
    """What the model has written so far to the voice's look-ahead, which never fails the answer."""
    try:
        return bool(on_text(text, done))
    except Exception:  # noqa: BLE001 - a failing look-ahead is dropped
        return True


class LlmServer:
    # One slot (slot 0): every request (the person's turns and the heartbeat, which keeps the same tools and a system
    # text of its own) starts from the same cached tools. A second slot only served the composition and the forced arguments,
    # which the native loop no longer makes; it cost 950 MiB of VRAM (measured on the notebook, 2026-10-15).

    # Review 2026-10-22: the App ends a turn's request at 30 s (MindSidecarClient.TurnRequestTimeout), and the mind waited
    # up to 120 s for a chat, 30 s for a fill and 10 s for a name, answering after the App had given up. Every call of
    # one request shares this budget (``deadline``, set per request by __main__; None for the warm-up and
    # session.load); spent, the request ends with an error, and the closed connection frees the slot.
    REQUEST_SECONDS = 24.0

    def __init__(self, gguf: str, server: str, gpu_layers: str = "99", context: int = 32768,
                 extra_args: list[str] | None = None, log_name: str = "llama-server.log",
                 kv: tuple[str, str] | None = None) -> None:
        self.gguf = gguf
        # The KV cache's types (K, V): BAXY_RENEW_KV when not given (kv_types), q8_0 and q8_0 by default.
        self.kv = kv or kv_types(os.environ.get("BAXY_RENEW_KV", ""))
        self.extra_args = list(extra_args or [])
        self.log_name = log_name
        self.server = server
        self.gpu_layers = gpu_layers
        self.context = context
        # PLAN_GENERAL A5: a pinned port lets the click's vision stage (BAXY_VISION_ENDPOINT) reach this same server.
        self.port = _pinned_port() or _free_port()
        self._process: subprocess.Popen | None = None
        self._ready = threading.Event()
        self._failure: str | None = None
        self.deadline: float | None = None
        # Where the server writes a slot's state (--slot-save-path): the prompt prefix kept between starts (V1) and the
        # state a vision question sets aside (BAXY_VISION_SLOT_DIR, the same folder).
        self.slot_dir = _slot_dir()
        self._settings: list[str] = []  # the server's arguments but its address, set by start (part of the prefix key)
        # Al máximo, palancas 2 y 5 (early.py): the text the last prefill left in the slot, while no other call of this
        # mind has used the slot since; None otherwise. A prefill of that same text is not sent again: with the slot
        # already holding all of it, a hybrid model must go back to a checkpoint to read its last token again.
        self.resident: str | None = None

    @property
    def name(self) -> str:
        return Path(self.gguf).name

    def start(self) -> None:
        vision = _vision_args()
        self._settings = [
            "-ngl", self.gpu_layers, "-c", str(self.context), "-np", "1", "-fa", "on",
            "-ctk", self.kv[0], "-ctv", self.kv[1], "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
            # Read the GGUF into the GPU without mapping it: a mapped model keeps its pages in the working set after
            # they reach the GPU (measured on the PC 2026-10-15: RAM 3237 → 1132 MiB, same VRAM 3905 MiB and speed).
            "--load-mode", "none",
            # Al máximo 3.3 (2026-10-22): no prompt cache in RAM, and at most 10 context checkpoints instead of 32. The
            # cache (1,536 MiB) held nothing: it only takes a prompt the slot is losing over half of (f_keep < 0.5,
            # server-context.cpp:1751 at b11609), and no prompt with its state and checkpoints fit it
            # (server-task.cpp:1735). The checkpoints live in RAM (~50 MiB each): up to ~1.1 GB less in a long session
            # (the notebook's count, not yet measured). With the list full llama.cpp first drops the other tasks'
            # checkpoints closer than -cms to the one before, never the first, then the oldest
            # (server-context.cpp:2537-2563), so the one at the prefix's end stays. The two flags go together: with 10
            # checkpoints a prompt would fit the cache, and the RAM would grow instead. The spacing stays llama.cpp's
            # (every 512 tokens cost ~46 ms per decision and 55 MiB of VRAM, decision2 d6 vs d6b, 2026-10-15). Watch
            # «erasing old context checkpoint» with n_tokens ≈ the prefix in llama-server.log: it should stay at 0.
            "-cram", "0", "-ctxcp", "10",
        ] + vision + ["--slot-save-path", str(self.slot_dir)] + self.extra_args
        command = [self.server, "-m", self.gguf, "--host", "127.0.0.1", "--port", str(self.port), *self._settings]
        # A state a vision question set aside and never put back holds the person's conversation: none is kept. The
        # kept prefix (PREFIX) is not one of them: it is saved before any turn (Mind.warm).
        self.slot_dir.mkdir(parents=True, exist_ok=True)
        self.forget_set_aside()
        log_dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew"
        log_dir.mkdir(parents=True, exist_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # The server writes its log through its own inherited handle: the mind's copy is closed once it started.
        with open(log_dir / self.log_name, "w", encoding="utf-8") as log:
            self._process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        threading.Thread(target=self._wait_health, daemon=True).start()

    def _wait_health(self) -> None:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                self._failure = f"llama-server exited with {self._process.returncode}"
                return
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as reply:
                    if reply.status == 200:
                        self._ready.set()
                        return
            except Exception:  # noqa: BLE001 - still loading
                time.sleep(0.3)
        self._failure = "llama-server did not become healthy"

    def wait_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while not self._ready.wait(0.25):
            if self._failure is not None or time.monotonic() > deadline:
                raise RuntimeError(self._failure or "llama-server is not ready")

    def startup_failure(self) -> dict[str, Any]:
        """The App's startup-failure shape (MindStartupFailure): why the model did not come up."""
        code = self._process.poll() if self._process is not None else None
        if code is not None:
            return {"cause": "proceso_salio", "exitCode": code}
        return {"cause": "tiempo"}

    def _alive(self) -> None:
        """The model server died: the sidecar exits, so the App sees the mind close and relaunches it. Before every call
        to it (review 2026-10-22: only chat() checked, and the history's tokenize raised URLError first, so the mind
        stayed up without its model and was never relaunched)."""
        if self._process is not None and self._process.poll() is not None:
            os._exit(70)

    def _within(self, timeout: float) -> float:
        """A call's timeout within the request's budget (REQUEST_SECONDS); spent, the request ends (TimeoutError)."""
        self._alive()
        if self.deadline is None:
            return timeout
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("the request's time budget is spent")
        return min(timeout, left)

    def chat(self, body: dict[str, Any], *, timeout: float = 120.0,
             on_text: Callable[[str | None, bool], bool] | None = None) -> dict[str, Any]:
        """One chat completion on the one slot, whose prefix stays cached between turns. With ``on_text`` it streams
        (_stream) and returns the same reply, unless it asks for token probabilities (below)."""
        self.wait_ready(self._within(timeout))
        self.resident = None
        # The doubt (doubt.read) reads every token's logprobs. Streamed, b11609 sends a token's logprobs only on a
        # chunk whose parse adds a difference (server-task.cpp:1136-1145; the first token's always, with the role):
        # the tokens of «<tool_call>», «<function=» and a name being parsed, and text the partial parser holds back,
        # add none, and their probabilities are never sent. A call that asks for them is not streamed.
        if on_text is not None and not body.get("logprobs"):
            try:
                return self._stream(body, timeout, on_text)
            except _StreamBroken:
                # A stream can fail where the same request does not: compute_diffs throws when a partial parse saw a
                # call the final parse does not (common/chat.cpp:255-267; a malformed call the non-streamed reply
                # returns as text). Asked again without streaming, on the same budget: the same answer (fixed seed).
                _tell(on_text, None, True)
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({**body, "id_slot": 0, "cache_prompt": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self._within(timeout)) as reply:
            return json.loads(reply.read())

    def _stream(self, body: dict[str, Any], timeout: float,
                on_text: Callable[[str | None, bool], bool]) -> dict[str, Any]:
        """Al máximo 9.4 (2026-10-22): the chat streamed (SSE) and its reply built as the non-streamed one is
        (common_chat_msg::to_json_oaicompat, common/chat.cpp:156-235; to_json_oaicompat_chat, server-task.cpp:410-452):
        choices[0] with finish_reason, index and the message (role, content, reasoning_content, tool_calls), usage and
        timings. While the answer is words, its text so far goes to ``on_text`` after each delta (and once more, done,
        at the end) until it returns True; once a call starts (or the words are a call written as text), ``on_text``
        gets None, done: what it foresaw is dropped.

        At b11609 streaming only changes how the result is sent: sampling is the same (server-context.cpp:2020,
        send_partial_response after the same add_token), the final message is parsed from the same accumulated text
        (common_chat_session feed/finish, common/chat.cpp:1740-1759; server-task.h:408-410), and the deltas are its
        successive differences (compute_diffs, common/chat.cpp:236-299; server_chat_msg_diff_to_json_oaicompat,
        server-chat.cpp:621-649): content and arguments as suffixes (string_diff, chat.cpp:58-71), a call's id and name
        whole whenever they change (a name that grows comes whole again). The last chunk carries the timings and, with
        include_usage, the usage (server-task.cpp:454-509). An error before the first token still comes as an HTTP
        error (a context overflow's 400, server-context.cpp:4902-4914); one later is _StreamBroken."""
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({**body, "stream": True, "stream_options": {"include_usage": True}, "id_slot": 0,
                             "cache_prompt": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        content, reasoning = "", ""
        calls: dict[int, dict[str, Any]] = {}
        head: dict[str, Any] = {}
        finish: Any = None
        index = 0
        telling = True
        with urllib.request.urlopen(request, timeout=self._within(timeout)) as reply:
            try:
                for raw in reply:
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if "error" in chunk:
                        raise _StreamBroken(str(chunk["error"]))
                    head.update({key: chunk[key] for key in ("created", "id", "model", "system_fingerprint", "usage",
                                                             "timings") if key in chunk})
                    for choice in chunk.get("choices") or []:
                        index = choice.get("index", index)
                        finish = choice.get("finish_reason") or finish
                        delta = choice.get("delta") or {}
                        reasoning += delta.get("reasoning_content") or ""
                        for call in delta.get("tool_calls") or []:
                            held = calls.setdefault(int(call.get("index") or 0),
                                                    {"type": "function", "function": {"name": "", "arguments": ""}})
                            function = call.get("function") or {}
                            if call.get("id"):
                                held["id"] = call["id"]
                            if function.get("name"):
                                held["function"]["name"] = function["name"]
                            held["function"]["arguments"] += function.get("arguments") or ""
                            if telling:
                                _tell(on_text, None, True)  # a call: what was foreseen is dropped, nothing more told
                                telling = False
                        if delta.get("content"):
                            content += delta["content"]
                            if telling and ("<tool_call>" in content or "<function=" in content):
                                _tell(on_text, None, True)  # a call written as text: dropped as well
                                telling = False
                            elif telling:
                                telling = not _tell(on_text, content, False)
                    self._within(timeout)  # the request's budget holds while the answer is written
            except (ValueError, http.client.HTTPException, ConnectionError) as error:
                raise _StreamBroken(repr(error)) from error
        if telling:
            _tell(on_text, content, True)
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if reasoning:
            message["reasoning_content"] = reasoning
        if calls:
            message["tool_calls"] = [calls[key] for key in sorted(calls)]
        return {"choices": [{"finish_reason": finish or "length", "index": index, "message": message}],
                **{key: head[key] for key in ("created", "id", "model", "system_fingerprint") if key in head},
                "object": "chat.completion", **{key: head[key] for key in ("usage", "timings") if key in head}}

    def template(self, body: dict[str, Any], timeout: float = 10.0) -> str:
        """The chat's own prompt as the server renders it (/apply-template). Al máximo V3 (2026-10-22): once per
        decision, for all of its rivals (complete_name); each rival rendered the whole prompt again (decisions with
        System One took 1.5-2.75 s against 1.1-1.4 s)."""
        self.wait_ready(self._within(timeout))
        return self._post("/apply-template", {k: body[k] for k in ("messages", "tools", "chat_template_kwargs")},
                          timeout)["prompt"]

    def complete_name(self, prompt: str, written: str, timeout: float = 10.0) -> str:
        """The rest of a tool name the model would write after `written` (its call so far), greedy, on the same slot:
        the chat's own prompt (template) plus that text, stopped at the name's end."""
        self.resident = None
        reply = self._post("/completion", {"prompt": prompt + written, "n_predict": 24, "temperature": 0.0,
                                           "stop": [">", "\n"], "cache_prompt": True, "id_slot": 0}, timeout)
        return str(reply.get("content", ""))

    def prefill(self, prompt: str, timeout: float = 60.0) -> dict[str, Any]:
        """``prompt`` (a chat's own text, as /apply-template renders it) read into the slot with nothing written: one
        token to predict, sampled and never decoded, so the slot then holds exactly the prompt's tokens (the warm-up's
        max_tokens 1 left n_tokens equal to its prompt's, llama-server.log). Tokenized as the chat's own prompt is
        (special tokens parsed, no BOS for this model). The text the slot already holds (``resident``) is not sent
        again: its reply then has no timings and says ``resident``."""
        self.wait_ready(self._within(timeout))
        if prompt == self.resident:
            return {"resident": True}
        self.resident = None
        reply = self._post("/completion", {"prompt": prompt, "n_predict": 1, "temperature": 0.0, "cache_prompt": True,
                                           "id_slot": 0}, timeout)
        self.resident = prompt
        return reply

    def fill_call(self, body: dict[str, Any], wire: str, timeout: float = 30.0) -> dict[str, Any] | None:
        """The model's arguments for one tool another layer chose (System One, piece A): the same chat, with the call
        already started as the assistant's last message, so the prompt and its cached prefix stay the same and only the
        arguments are written. tool_choice «required» keeps the call grammar active from that prefix on, inside this
        tool's own parameters (llama.cpp b11609: common/sampling.cpp, common/chat.cpp, common/parsers/qwen3-coder.cpp).
        Returns the parsed call {"name", "arguments"} or None. Auditoría de la mente (w8): not the decision's token
        probabilities (logprobs, top_logprobs 10), which nothing reads of a fill; the server sorted the vocabulary at
        every argument token for them (al máximo 9.5's cost, −20 to −100 ms expected); greedy, the same arguments."""
        messages = [*body["messages"], {"role": "assistant", "content": f"<tool_call>\n<function={wire}>\n"}]
        request = {**{k: v for k, v in body.items()
                      if k not in ("logit_bias", "tool_choice", "max_tokens", "logprobs", "top_logprobs")},
                   "messages": messages, "tool_choice": "required", "parallel_tool_calls": False,
                   "continue_final_message": True, "add_generation_prompt": False, "max_tokens": 300,
                   "temperature": 0.0, "id_slot": 0, "cache_prompt": True}
        self.resident = None
        reply = self._post("/v1/chat/completions", request, timeout)
        calls = (reply.get("choices") or [{}])[0].get("message", {}).get("tool_calls") or []
        if not calls:
            return None
        call = calls[0].get("function") or {}
        try:
            arguments = json.loads(call.get("arguments") or "{}")
        except json.JSONDecodeError:
            return None
        return {"name": call.get("name"), "arguments": arguments if isinstance(arguments, dict) else {},
                "timings": reply.get("timings") or {}}

    def _post(self, path: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self._within(timeout)) as reply:
            return json.loads(reply.read())

    def tokenize(self, text: str) -> list[int]:
        """The model's tokens for a text, special tokens included (<tool_call> is one)."""
        self.wait_ready(self._within(600))
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/tokenize",
            data=json.dumps({"content": text, "parse_special": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self._within(30)) as reply:
            return list(json.loads(reply.read())["tokens"])

    # ---- the prompt prefix kept between starts (al máximo V1) -------------------------------------------------------
    # Every start re-read the tools and the system prompt (~44,600 tokens, 18.3 s in llama-server.log) and the App was
    # ready at ~22-23 s. The slot's state after the warm-up is saved with the server's own slot save (the vision's:
    # 42,910 tokens restored in 0.74 s) under a key of everything that makes that state; the next start restores it.

    def prefix_key(self, warm: Any) -> str:
        """The key of the slot's state after the warm-up: the requests that make it (``warm``: the tools, the installed
        applications among them, and the system prompt), the server's arguments but its address (context, KV cache
        types, projector…), the GGUF and the server binary (size and time: hashing 2.7 GB costs what is saved) and the
        server's build as it tells it."""
        self.wait_ready(self._within(600))
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/props", timeout=self._within(10)) as reply:
                build = str(json.loads(reply.read()).get("build_info") or "")
        except (OSError, ValueError, http.client.HTTPException):
            build = ""
        identity = {"settings": self._settings, "gguf": _stamp(self.gguf), "server": _stamp(self.server),
                    "build": build, "warm": warm}
        return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]

    def restore_prefix(self, key: str) -> dict[str, Any] | None:
        """The slot back to the state saved under ``key``, and the facts kept beside it; None when there is none or the
        server could not restore it (the warm-up then runs as always)."""
        state = self.slot_dir / f"{PREFIX}{key}.slot"
        try:
            facts = json.loads(state.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(facts, dict) or not state.is_file():
            return None
        self.resident = None
        try:
            reply = self._post("/slots/0?action=restore", {"filename": state.name}, 120)
        except (OSError, ValueError, http.client.HTTPException):
            return None
        if int(reply.get("n_restored") or 0) <= 0:
            return None
        try:
            os.utime(state.with_suffix(".json"))  # the state used last: save_prefix keeps it (P0.9)
        except OSError:
            pass  # held this moment: the state was restored all the same
        return facts

    def save_prefix(self, key: str, facts: dict[str, Any]) -> bool:
        """The slot's state saved under ``key`` with ``facts`` beside it, and the state of one other key: the one saved
        or restored last; every other is removed (each is ~1 GB). Only the prefix may be in the slot: Mind.warm saves
        it before any turn. P0.9 (feria, 2026-10-27): with every other state removed, one start whose prefix had
        another key (its tools from a catalog that came late) cost the next usual start the whole prefix too (~30 s)."""
        state = self.slot_dir / f"{PREFIX}{key}.slot"
        kept = state.with_suffix(".json")
        # Saving only spares the next start the warm-up: a file of the folder another process holds this moment (a
        # scan of the state just written) never fails the warm-up itself (it was told to the App as a model that did
        # not start).
        try:
            kept.unlink(missing_ok=True)  # the facts are written last: a state cut halfway is never restored
            saved = int(self._post("/slots/0?action=save", {"filename": state.name}, 120).get("n_saved") or 0) > 0
            if saved:
                kept.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError, http.client.HTTPException):
            saved = False
        keep = {state.name, kept.name} if saved else set()
        earlier = [other for other in self.slot_dir.glob(f"{PREFIX}*.json")
                   if other.name != kept.name and other.with_suffix(".slot").is_file()]
        if earlier:
            last = max(earlier, key=lambda other: (_stamp(str(other)) or [0, 0])[1])
            keep |= {last.name, last.with_suffix(".slot").name}
        for stale in self.slot_dir.glob(f"{PREFIX}*"):
            if stale.name not in keep:
                try:
                    stale.unlink(missing_ok=True)
                except OSError:
                    pass  # held this moment: the next save removes it
        return saved

    def forget_set_aside(self) -> bool:
        """Every slot state a vision question set aside (*.bin, which holds the person's conversation) is removed; the
        kept prefix (PREFIX, saved before any turn) stays. Whether none is left. At start, and when the person had BAXY
        forget everything or deleted every conversation (trace.forget): a question under way then loses its state and
        the next decision reads the conversation again."""
        left = False
        for stale in self.slot_dir.glob("*.bin"):
            try:
                stale.unlink(missing_ok=True)
            except OSError:
                left = True  # held by the server this moment
        return not left

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(5)
            except subprocess.TimeoutExpired:
                self._process.kill()


# The kept prefix's files in the slot folder: its state (.slot, never *.bin: start() removes those) and its facts (.json).
PREFIX = "baxy_prefix_"

# w6-lat (2026-10-23): the KV cache's types, an option for an A/B and never the default (q8_0 for K and V). BAXY_RENEW_KV
# is one type for both («q4_0») or «K,V» («q8_0,q4_0»). Expected, not measured (no GPU run): Qwen3.5-4B keeps K and V in
# its 8 full-attention layers of 32 (4 KV heads × 256), 17 KiB per token at q8_0 (llama_kv_cache: 136 MiB for 8,192
# cells); at q4_0 ~9 KiB. With the ~44k tokens of a turn in the slot, each decoded token reads ~0.73 GiB of KV beside the
# ~2.55 GiB of Q4_K_M weights: q4_0 for both reads ~0.35 GiB less (−11 % of the bytes; decode up to ~8-10 % faster where
# it is bound by memory: predicted 487 ms → ~440-450 ms per turn.continue) and frees ~0.4 GiB of VRAM at 53,248 cells;
# «q8_0,q4_0» half of that. Risk: K at 4 bits is the part that moves attention most (llama.cpp's perplexity reports: q8_0
# close to f16, q4_0 K clearly worse than q4_0 V), on a 4B whose decisions were tuned at q8_0; the prompt may read no
# faster (dequantized in the flash-attention kernel); a new type is a new prefix key (Mind.warm reads the prefix once
# more, ~18 s, then keeps it). Needs decision2, falsedades and e2e A/B on the GPU before any default changes.
KV_TYPES = ("f16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0")


def kv_types(setting: str) -> tuple[str, str]:
    """The KV cache's (K, V) types from BAXY_RENEW_KV's text: empty, q8_0 and q8_0; one type, both; «K,V», each. Any
    other text fails the start with its cause (RuntimeError, as a pinned port in use)."""
    parts = [part.strip().lower() for part in setting.split(",")] if setting.strip() else ["q8_0"]
    if len(parts) == 1:
        parts *= 2
    if len(parts) != 2 or any(part not in KV_TYPES for part in parts):
        raise RuntimeError(f"BAXY_RENEW_KV {setting!r}: one of {', '.join(KV_TYPES)}, or two of them as «K,V»")
    return parts[0], parts[1]


def _vision_args() -> list[str]:
    """PLAN_GENERAL A5 (measured 2026-10-21): the model's own projector, on the CPU (no VRAM; ~0.7 GB of RAM), so the
    click's last stage can ask this server where a control is on a window without an accessible tree; the one slot's
    state is set aside meanwhile in the slot folder (_slot_dir). A question on the slot evicted the conversation,
    whose state (2 GB) the RAM prompt cache refused, and the next decision re-read it for 25 s; a second slot on a
    unified KV cache lost it too with this hybrid model (21 s). Saved and restored around the question: 1.35 s and
    0.74 s for 42,910 tokens, then 17 tokens re-read."""
    projector = os.environ.get("BAXY_MIND_MMPROJ", "").strip()
    if not projector or not Path(projector).is_file():
        return []
    return ["--mmproj", projector, "--no-mmproj-offload"]


def _slot_dir() -> Path:
    """The server's --slot-save-path: BAXY_VISION_SLOT_DIR, where the App's vision sets the slot's state aside, or the
    same folder the App gives it (MindRuntimeDiscovery) when the vision is off."""
    held = os.environ.get("BAXY_VISION_SLOT_DIR", "").strip()
    return Path(held) if held else Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "slots"


def _stamp(path: str) -> list[int] | None:
    """A file's size and modification time, or None when it is not there."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return [status.st_size, status.st_mtime_ns]


# The llama-server builds the mind may start, by the SHA-256 of their files (00_IDENTIDAD: no piece changes in silence).
BUILDS = Path(__file__).with_name("data") / "llama_server.v1.json"


def declared_build(server: str, builds: Path = BUILDS) -> str:
    """The name of the declared build (data/llama_server.v1.json) that ``server`` is: each file the declaration names,
    in the folder of the given llama-server.exe, with that build's SHA-256. w11-llama (2026-10-25): the product ran
    whatever BAXY_MIND_LLAMA_SERVER named, unhashed; the registration's hash (MindRuntimeDiscovery) was of a server the
    launcher overrode, and of the 10 KB launcher only, while llama.cpp's code lives in its DLLs. RuntimeError names
    the files that match no build, or says the folder mixes builds."""
    declaration = json.loads(builds.read_text(encoding="utf-8"))
    path = Path(server)
    if path.name.lower() != "llama-server.exe":
        raise RuntimeError(f"BAXY_MIND_LLAMA_SERVER is not a llama-server.exe: {server}")
    actual: dict[str, str | None] = {}
    for name in declaration["files"]:
        try:
            actual[name] = hashlib.sha256((path.parent / name).read_bytes()).hexdigest()
        except OSError:
            actual[name] = None
    for build, entry in declaration["builds"].items():
        if entry["sha256"] == actual:
            return build
    unknown = [f"{name} {digest[:12] if digest else 'missing'}" for name, digest in actual.items()
               if digest is None or all(entry["sha256"][name] != digest for entry in declaration["builds"].values())]
    detail = ", ".join(unknown) if unknown else "its files belong to different builds"
    raise RuntimeError(f"llama-server not declared in {builds.name}: {server} ({detail})")


def _pinned_port() -> int | None:
    """BAXY_MIND_LLAMA_PORT when set; None when not (a free port is taken). Review 2026-10-22: a pinned port in use
    fails the start with its cause; another port taken in silence left the core's vision pointing at the pinned one."""
    try:
        port = int(os.environ.get("BAXY_MIND_LLAMA_PORT", ""))
    except ValueError:
        return None
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"BAXY_MIND_LLAMA_PORT {port} is in use on the loopback: {error}") from error
    return port


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
