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
    # One slot: every request (the person's turns and the heartbeat, which keeps the same system prompt and tools)
    # starts from the same cached prefix. A second slot only served the composition and the forced arguments, which
    # the native loop no longer makes; it cost 950 MiB of VRAM (measured on the notebook, 2026-10-15).
    DECIDE = 0

    def __init__(self, gguf: str, server: str, gpu_layers: str = "99", context: int = 32768,
                 extra_args: list[str] | None = None, log_name: str = "llama-server.log") -> None:
        self.gguf = gguf
        self.extra_args = list(extra_args or [])
        self.log_name = log_name
        self.server = server
        self.gpu_layers = gpu_layers
        self.context = context
        self.port = _free_port()
        self._process: subprocess.Popen | None = None
        self._ready = threading.Event()
        self._failure: str | None = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return Path(self.gguf).name

    def start(self) -> None:
        command = [
            self.server, "-m", self.gguf, "--host", "127.0.0.1", "--port", str(self.port),
            "-ngl", self.gpu_layers, "-c", str(self.context), "-np", "1", "-fa", "on",
            "-ctk", "q8_0", "-ctv", "q8_0", "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
            # Read the GGUF into the GPU without mapping it: a mapped model keeps its pages in the working set after
            # they reach the GPU (measured on the PC 2026-10-15: RAM 3237 → 1132 MiB, same VRAM 3905 MiB and speed).
            "--load-mode", "none",
        ] + self.extra_args
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

    def chat(self, body: dict[str, Any], *, slot: int, timeout: float = 120.0) -> dict[str, Any]:
        """One chat completion on a pinned slot, so each slot keeps its own prefix cached between turns."""
        if self._process is not None and self._process.poll() is not None:
            # The model server died: the sidecar exits, so the App sees the mind close and relaunches it.
            os._exit(70)
        self.wait_ready(timeout)
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({**body, "id_slot": slot, "cache_prompt": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            return json.loads(reply.read())

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(5)
            except subprocess.TimeoutExpired:
                self._process.kill()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
