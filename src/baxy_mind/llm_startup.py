"""Why the local llama-server could not start, said as a stable cause.

r22 (2026-10-09): with another llama-server holding ~4 GB of a 6 GB GPU the
mind's server died while warming up, its stderr went to DEVNULL and the App
retried forever in silence. This piece owns the startup diagnosis only: a
bounded tail of the server's own startup lines (paths scrubbed, nothing of the
person: they are written before any request exists), the cause read from them,
and the free-VRAM check that fails fast before a launch that cannot fit.
"""

from __future__ import annotations

import collections
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

STARTUP_CAUSES = frozenset(
    {"vram_insuficiente", "ram_insuficiente", "proceso_salio", "tiempo"}
)
TAIL_LINES = 12
TAIL_LINE_CHARACTERS = 160
NVIDIA_QUERY_SECONDS = 2.0
# Compute buffers and the CUDA context beside the weights (-ngl 99, --no-mmap).
VRAM_MARGIN_BYTES = 256 * 1024 * 1024

_VRAM_EXHAUSTED = re.compile(
    r"(?i)cudamalloc failed|cuda error: out of memory|out of memory.*(?:cuda|gpu|vram)"
    r"|(?:failed|unable) to allocate (?:cuda|vulkan|gpu)\w* buffer"
    r"|erroroutofdevicememory"
)
_RAM_EXHAUSTED = re.compile(
    r"(?i)(?:failed|unable) to allocate cpu\w* buffer|bad_alloc|insufficient memory"
    r"|not enough memory|paging file"
)
# A path may hold spaces («C:/Users/Nombre Apellido/…»): a quoted one is erased up to its quote, an
# unquoted one up to the end of the line, so no part of the account name survives.
_PATH_START = r"(?:[A-Za-z]:[\\/]|\\\\|/(?:home|users|mnt)/)"
_QUOTED_PATH = re.compile(r"(['\"])" + _PATH_START + r"[^'\"\n]*\1", re.IGNORECASE)
_PATH = re.compile(_PATH_START + r".*$", re.IGNORECASE)


class LlmStartupFailure(RuntimeError):
    """A llama-server startup that failed for a known cause."""

    def __init__(
        self,
        cause: str,
        message: str,
        *,
        exit_code: int | None = None,
        tail: tuple[str, ...] = (),
    ) -> None:
        if cause not in STARTUP_CAUSES:
            raise ValueError("causa de arranque desconocida")
        super().__init__(message)
        self.cause = cause
        self.exit_code = exit_code
        self.tail = tuple(tail)

    def report(self) -> dict[str, Any]:
        """The protocol shape: stable cause, exit code, scrubbed server lines."""

        return {"cause": self.cause, "exitCode": self.exit_code, "tail": list(self.tail)}


def scrub_line(raw: str) -> str:
    """One server line without paths (they carry the person's account name)."""

    line = _PATH.sub("<ruta>", _QUOTED_PATH.sub("<ruta>", raw.strip()))
    return line[:TAIL_LINE_CHARACTERS]


def cause_from_tail(tail: tuple[str, ...] | list[str]) -> str:
    """vram/ram exhaustion when the server said so, else the bare exit."""

    text = "\n".join(tail)
    if _VRAM_EXHAUSTED.search(text):
        return "vram_insuficiente"
    if _RAM_EXHAUSTED.search(text):
        return "ram_insuficiente"
    return "proceso_salio"


def exit_failure(exit_code: int | None, tail: tuple[str, ...]) -> LlmStartupFailure:
    return LlmStartupFailure(
        cause_from_tail(tail),
        f"llama-server terminó (exit {exit_code})",
        exit_code=exit_code,
        tail=tail,
    )


def failure_of(error: BaseException) -> LlmStartupFailure:
    """Any startup exception as a cause: a timeout is ``tiempo``."""

    if isinstance(error, LlmStartupFailure):
        return error
    if isinstance(error, TimeoutError):
        return LlmStartupFailure("tiempo", str(error))
    return LlmStartupFailure("proceso_salio", type(error).__name__)


class StderrTail:
    """Drains a child's stderr; keeps a bounded tail only until it is ready."""

    def __init__(self, stream: Any) -> None:
        self._lines: collections.deque[str] = collections.deque(maxlen=TAIL_LINES)
        self._lock = threading.Lock()
        self._recording = True
        self._thread = threading.Thread(
            target=self._drain, args=(stream,), name="baxy-llm-stderr", daemon=True
        )
        self._thread.start()

    def _drain(self, stream: Any) -> None:
        try:
            for raw in stream:
                with self._lock:
                    if not self._recording:
                        continue
                    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
                    line = scrub_line(text)
                    if line:
                        self._lines.append(line)
        except Exception:  # noqa: BLE001 - a closed pipe ends the drain
            return

    def stop_recording(self) -> None:
        """After readiness the server's lines may describe requests: not kept."""

        with self._lock:
            self._recording = False
            self._lines.clear()

    def tail(self, wait_seconds: float = 0.5) -> tuple[str, ...]:
        """The startup lines, after the dead child's last ones were read."""

        self._thread.join(timeout=wait_seconds)
        with self._lock:
            return tuple(self._lines)


def free_vram_bytes() -> int | None:
    """Free memory of GPU 0 by nvidia-smi; None when it cannot be read."""

    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=NVIDIA_QUERY_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    first = completed.stdout.strip().splitlines()[:1]
    try:
        return int(first[0].strip()) * 1024 * 1024 if first else None
    except ValueError:
        return None


def require_vram_for(gguf: str | None, *, cpu_only: bool) -> None:
    """Fail fast when the full-offload model cannot fit in the free VRAM.

    An unknown reading (no nvidia-smi, no model file, partial offload) never
    blocks: only a measured shortage does.
    """

    if cpu_only or not gguf:
        return
    layers = os.environ.get("BAXY_MIND_NGL", "99").strip()
    try:
        if int(layers) < 99:
            return
    except ValueError:
        return
    try:
        model_bytes = Path(gguf).stat().st_size
    except OSError:
        return
    free = free_vram_bytes()
    if free is None:
        return
    required = model_bytes + VRAM_MARGIN_BYTES
    if free < required:
        raise LlmStartupFailure(
            "vram_insuficiente",
            "VRAM libre insuficiente para el modelo",
            tail=(f"vram_libre_mib={free // (1024 * 1024)} requerida_mib={required // (1024 * 1024)}",),
        )
