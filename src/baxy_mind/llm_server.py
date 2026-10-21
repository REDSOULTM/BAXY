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
            # The prompt cache in RAM holds a prompt the slot set aside (a heartbeat between two turns): at most 1.5 GB
            # instead of 8 GB, so the harness stays under 4 GB of RAM (one 37k prompt with its state is ~0.7 GB).
            # Checkpoints stay at llama.cpp's spacing: every 512 tokens cost ~46 ms per decision and 55 MiB of VRAM
            # (decision2 d6 vs d6b, 2026-10-15) once the last answer of a turn keeps the tools and the prefix.
            "-cram", "1536",
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

    def chat(self, body: dict[str, Any], *, timeout: float = 120.0) -> dict[str, Any]:
        """One chat completion on the one slot, whose prefix stays cached between turns."""
        if self._process is not None and self._process.poll() is not None:
            # The model server died: the sidecar exits, so the App sees the mind close and relaunches it.
            os._exit(70)
        self.wait_ready(timeout)
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({**body, "id_slot": 0, "cache_prompt": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            return json.loads(reply.read())

    def tokenize(self, text: str) -> list[int]:
        """The model's tokens for a text, special tokens included (<tool_call> is one)."""
        self.wait_ready(600)
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/tokenize",
            data=json.dumps({"content": text, "parse_special": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as reply:
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
    """BAXY_MIND_LLAMA_PORT when set and free on the loopback; None otherwise (a free port is taken)."""
    try:
        port = int(os.environ.get("BAXY_MIND_LLAMA_PORT", ""))
    except ValueError:
        return None
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return None
    return port


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
