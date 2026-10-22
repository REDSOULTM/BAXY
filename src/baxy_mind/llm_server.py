"""The local model server: one llama-server process owned by the mind, one slot, its prompt prefix kept in cache."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any


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
                 extra_args: list[str] | None = None, log_name: str = "llama-server.log") -> None:
        self.gguf = gguf
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

    @property
    def name(self) -> str:
        return Path(self.gguf).name

    def start(self) -> None:
        vision = _vision_args()
        command = [
            self.server, "-m", self.gguf, "--host", "127.0.0.1", "--port", str(self.port),
            "-ngl", self.gpu_layers, "-c", str(self.context), "-np", "1", "-fa", "on",
            "-ctk", "q8_0", "-ctv", "q8_0", "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
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
        ] + vision + self.extra_args
        # A state a vision question set aside and never put back holds the person's conversation: none is kept.
        if held := os.environ.get("BAXY_VISION_SLOT_DIR", "").strip():
            for stale in Path(held).glob("*.bin"):
                stale.unlink(missing_ok=True)
        log_dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = open(log_dir / self.log_name, "w", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
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

    def chat(self, body: dict[str, Any], *, timeout: float = 120.0) -> dict[str, Any]:
        """One chat completion on the one slot, whose prefix stays cached between turns."""
        self.wait_ready(self._within(timeout))
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({**body, "id_slot": 0, "cache_prompt": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self._within(timeout)) as reply:
            return json.loads(reply.read())

    def fill_call(self, body: dict[str, Any], wire: str, timeout: float = 30.0) -> dict[str, Any] | None:
        """The model's arguments for one tool another layer chose (System One, piece A): the same chat, with the call
        already started as the assistant's last message, so the prompt and its cached prefix stay the same and only the
        arguments are written. tool_choice «required» keeps the call grammar active from that prefix on, inside this
        tool's own parameters (llama.cpp b11609: common/sampling.cpp, common/chat.cpp, common/parsers/qwen3-coder.cpp).
        Returns the parsed call {"name", "arguments"} or None."""
        messages = [*body["messages"], {"role": "assistant", "content": f"<tool_call>\n<function={wire}>\n"}]
        request = {**{k: v for k, v in body.items() if k not in ("logit_bias", "tool_choice", "max_tokens")},
                   "messages": messages, "tool_choice": "required", "parallel_tool_calls": False,
                   "continue_final_message": True, "add_generation_prompt": False, "max_tokens": 300,
                   "temperature": 0.0, "id_slot": 0, "cache_prompt": True}
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

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(5)
            except subprocess.TimeoutExpired:
                self._process.kill()


def _vision_args() -> list[str]:
    """PLAN_GENERAL A5 (measured 2026-10-21): the model's own projector, on the CPU (no VRAM; ~0.7 GB of RAM), so the
    click's last stage can ask this server where a control is on a window without an accessible tree; and where the
    one slot's state is set aside meanwhile (BAXY_VISION_SLOT_DIR). A question on the slot evicted the conversation,
    whose state (2 GB) the RAM prompt cache refused, and the next decision re-read it for 25 s; a second slot on a
    unified KV cache lost it too with this hybrid model (21 s). Saved and restored around the question: 1.35 s and
    0.74 s for 42,910 tokens, then 17 tokens re-read."""
    projector = os.environ.get("BAXY_MIND_MMPROJ", "").strip()
    if not projector or not Path(projector).is_file():
        return []
    held = os.environ.get("BAXY_VISION_SLOT_DIR", "").strip()
    if held:
        Path(held).mkdir(parents=True, exist_ok=True)
    return ["--mmproj", projector, "--no-mmproj-offload"] + (["--slot-save-path", held] if held else [])


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
