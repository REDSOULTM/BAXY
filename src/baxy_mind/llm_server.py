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
    # Two pinned slots: slot 0 always holds the decision prefix (system + whole catalog, ~23k tokens), slot 1 the
    # short prompts (composition, forced arguments). One shared slot evicted the catalog after every composition and
    # the next turn re-read it whole (7,5 s on 2026-10-15). The context is per slot.
    DECIDE, SHORT = 0, 1

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
            "-ngl", self.gpu_layers, "-c", str(self.context * 2), "-np", "2", "-fa", "on",
            "-ctk", "q8_0", "-ctv", "q8_0", "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
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
        if not self._ready.wait(timeout):
            raise RuntimeError(self._failure or "llama-server is not ready")

    def chat(self, body: dict[str, Any], *, slot: int, timeout: float = 120.0) -> dict[str, Any]:
        """One chat completion on a pinned slot, so each slot keeps its own prefix cached between turns."""
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
