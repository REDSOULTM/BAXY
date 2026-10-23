"""System One, layer 2: a small decision model (Laya, tuned on BAXY's requests) beside Qwen, on the CPU.

It answers one typed question — which of Qwen's own candidates the person asked for — with calibrated probabilities, in
one pass (llama-server's /v1/systemone). Phase 0 (scripts/renew/system_one, 2026-10-21): tuned laya-multilingual 322M,
on the 152 held-out real requests, 94.1 % against Qwen's 92.1 %; when Qwen doubted (< 0.6) and Laya disagreed, asking
instead held 6 of 9 wrong actions with no extra question. 576 MiB of RAM, ~140 ms per question on a laptop CPU.

The question is written here, once: training (build_kev_data.py) and serving read the same words.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ANSWER = "responder_con_palabras"
ASK = "ask_user"
KINDS = {"actuar": "hacer algo en el PC con una herramienta",
         "preguntar": "preguntar a la persona porque falta un dato o el pedido es ambiguo",
         "responder": "contestar con palabras, sin herramientas (charla, conocimiento, texto que no pide nada)",
         "no_se_puede": "decir que eso no lo hace: no hay una herramienta para ese pedido"}
OPTION_TEXT = {ANSWER: "contestar con palabras, sin usar herramientas",
               ASK: "preguntar a la persona lo que falta o lo que no está claro"}
QUESTION = "¿Qué debe hacer el asistente con este pedido?"
STATE_CHARS = 1200


def short(text: str, limit: int = 220) -> str:
    """A tool's description as an option: its first sentence, cut at a word."""
    text = " ".join(str(text).split())
    cut = text.find(". ")
    text = text[:cut + 1] if 0 < cut < limit else text
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def state_text(text: str, history: list[dict[str, Any]] | None) -> str:
    """The state as plain text (kev.train serializes a dict as JSON; llama-server renders it with its own template)."""
    previous = " | ".join(f'{m["role"]}: {m["content"]}' for m in (history or [])[-4:]) or "ninguna"
    # An encoder reads at most ~1k tokens (laya-multilingual's default): a pasted text keeps its start, as does history.
    text, previous = str(text)[:STATE_CHARS], previous[-STATE_CHARS // 2:]
    return (f"Pedido de la persona: {text}\nConversación previa: {previous}\n"
            "Lugar: asistente de escritorio BAXY en el PC Windows de la persona")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class SystemOne:
    """Its own llama-server on the CPU (no VRAM: Qwen holds the 4 GB). A turn never waits for it to load."""

    def __init__(self, gguf: str, server: str, threads: int = 4) -> None:
        self.gguf, self.server, self.threads = gguf, server, threads
        self.port = _free_port()
        self._process: subprocess.Popen | None = None
        self._ready = threading.Event()

    def start(self) -> None:
        log_dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = open(log_dir / "system-one.log", "w", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # An encoder reads its whole input in one batch: -b/-ub cover the longest state plus its options. No device at
        # all (-dev none): with only -ngl 0 the CUDA build still made a context and offloaded its big batches, and the
        # product's VRAM went 3902 → 4091 MiB with System One on (Renew al máximo, palanca 3.1).
        self._process = subprocess.Popen(
            [self.server, "-m", self.gguf, "--host", "127.0.0.1", "--port", str(self.port), "-ngl", "0", "-dev", "none",
             "-t", str(self.threads), "-c", "4096", "-np", "1", "-b", "2048", "-ub", "2048"],
            stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        threading.Thread(target=self._wait_health, daemon=True).start()

    def _wait_health(self) -> None:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline and self._process is not None and self._process.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as reply:
                    if reply.status == 200:
                        self._ready.set()
                        return
            except Exception:  # noqa: BLE001 - still loading
                time.sleep(0.3)

    @property
    def ready(self) -> bool:
        return self._ready.is_set() and self._process is not None and self._process.poll() is None

    def choose(self, text: str, history: list[dict[str, Any]] | None, options: dict[str, str],
               timeout: float = 2.0) -> dict[str, Any] | None:
        """Which option the person asked for: {choice, p, probabilities, ms}; None when it is not up or fails (the turn
        goes on as Qwen decided)."""
        if not self.ready or len(options) < 2:
            return None
        started = time.monotonic()
        # The order of the options moves the answer («cierra el spotify»: close the app 0.52 listed second, 0.94 first;
        # 2026-10-21): asked in both orders, the probabilities averaged. One after the other: both at once on two slots
        # (-np 2) took the same time with the same answers (w6-lat, scripts/renew/system_one/medir_ordenes.py: the CPU
        # pass is the cost), and an encoder has no prompt prefix to keep between the two.
        totals: dict[str, float] = {}
        try:
            for order in (list(options), list(reversed(options))):
                answer = self._ask(text, history, {k: options[k] for k in order}, timeout)
                if answer is None:
                    return None
                for key, value in (answer.get("probabilities") or {}).items():
                    totals[key] = totals.get(key, 0.0) + float(value) / 2
        except Exception:  # noqa: BLE001 - review 2026-10-22: an answer not of its shape is no answer, never a failed turn
            return None
        choice = max(totals, key=lambda key: totals[key]) if totals else None
        if choice not in options:
            return None
        return {"choice": choice, "p": round(totals[choice], 4),
                "probabilities": {k: round(v, 4) for k, v in totals.items()},
                "ms": round((time.monotonic() - started) * 1000)}

    def _ask(self, text: str, history: list[dict[str, Any]] | None, options: dict[str, str],
             timeout: float) -> dict[str, Any] | None:
        body = {"state": state_text(text, history),
                "questions": {"operacion": {"type": "choice", "instructions": QUESTION, "criteria": options}}}
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/systemone",
                                             data=json.dumps(body).encode("utf-8"),
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as reply:
                return (json.loads(reply.read()).get("answers") or {}).get("operacion") or {}
        except (OSError, urllib.error.URLError, ValueError):
            return None

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(5)
            except subprocess.TimeoutExpired:
                self._process.kill()
