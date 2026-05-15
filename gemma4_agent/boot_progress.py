"""Tail llama-server.{out,err}.log while the model is loading and translate
log lines into BUS `boot_stage` events so the UI can show what's actually
happening — instead of a single opaque "loading…" placeholder.

This file is intentionally decoupled from llama_server.py and agent_runner.py
so the constraint about NOT touching agent.py / tool_retrieval.py /
verifier_orchestrator.py keeps holding. We only read the log file; we never
modify what llama-server prints.

The parser is best-effort. llama.cpp doesn't emit a clean percentage during
load_tensors, so we map known marker lines to human-readable stages:

    "main: loading model"                       → llama_metadata
    "load_tensors: loading model tensors"       → llama_layers
    "load_tensors: offloaded N/M layers to GPU" → llama_offload (with %)
    "main: server is listening on http..."      → llama_listening

The PROGRESS extracted from "offloaded N/M" gives a real percent (layer
offload progress) — that's the only honest % we have from llama.cpp's output.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


# Stage names are part of the WS contract — the UI matches against them.
STAGE_SPAWN = "llama_spawn"
STAGE_METADATA = "llama_metadata"
STAGE_LAYERS = "llama_layers"
STAGE_OFFLOAD = "llama_offload"
STAGE_LISTENING = "llama_listening"
STAGE_HEALTH = "llama_health"


_RE_OFFLOAD = re.compile(r"offloaded\s+(\d+)\s*/\s*(\d+)\s+layers? to GPU", re.IGNORECASE)


def _emit(publish: Callable[[dict], None], stage: str, label: str,
          progress: float | None = None, error: str | None = None) -> None:
    publish({
        "type": "boot_stage",
        "stage": stage,
        "label": label,
        "progress": progress,
        "error": error,
    })


class LlamaLogTail:
    """Tails a llama-server log file in a daemon thread, publishing boot_stage
    events as it recognises known marker lines. Stops on its own as soon as it
    sees `server is listening` (or when stop() is called by the caller).

    Designed to be one-shot per llama-server startup: create it, call start(),
    and let it self-terminate when the model is ready.
    """

    def __init__(self, log_path: Path, publish: Callable[[dict], None]) -> None:
        self._log_path = log_path
        self._publish = publish
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_stage: str | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="gemma4-llama-tail", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        # poll for the log file to exist (llama-server may not have spawned
        # the first time we check). cap the wait so we don't loop forever.
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline and not self._stop.is_set():
            if self._log_path.is_file():
                break
            time.sleep(0.25)
        else:
            return  # log never appeared or we were stopped

        try:
            with self._log_path.open("r", encoding="utf-8", errors="replace") as fh:
                # seek to end so we only see fresh boot output. The log is
                # opened in append mode by LlamaServerManager so all the prior
                # runs are already in it; we don't want to replay them.
                fh.seek(0, 2)
                while not self._stop.is_set():
                    line = fh.readline()
                    if not line:
                        time.sleep(0.15)
                        continue
                    self._handle_line(line)
                    # auto-terminate once the server is listening — the agent
                    # builder will take over from here with its own events.
                    if self._last_stage == STAGE_LISTENING:
                        return
        except OSError as exc:
            logger.debug("LlamaLogTail read error: %s", exc)

    def _handle_line(self, line: str) -> None:
        # Order matters: more specific patterns first.
        m = _RE_OFFLOAD.search(line)
        if m:
            n = int(m.group(1))
            total = int(m.group(2))
            pct = round(100.0 * n / max(1, total), 1)
            self._emit(STAGE_OFFLOAD, f"offloaded {n}/{total} layers to GPU", progress=pct)
            return
        if "server is listening" in line:
            self._emit(STAGE_LISTENING, "llama-server listening · running health check")
            return
        if "load_tensors: loading model tensors" in line:
            self._emit(STAGE_LAYERS, "loading model tensors")
            return
        if "main: loading model" in line or "srv    load_model" in line:
            self._emit(STAGE_METADATA, "reading model metadata")
            return

    def _emit(self, stage: str, label: str, progress: float | None = None) -> None:
        # de-duplicate: don't spam the bus with the same stage. progress
        # updates are an exception — they can repeat with a moving value.
        if stage == self._last_stage and progress is None:
            return
        self._last_stage = stage
        _emit(self._publish, stage, label, progress=progress)


def emit_stage(publish: Callable[[dict], None], stage: str, label: str,
               progress: float | None = None, error: str | None = None) -> None:
    """Public helper for callers that want to publish boot_stage events
    without instantiating a tail (e.g. the agent build phase)."""
    _emit(publish, stage, label, progress=progress, error=error)
