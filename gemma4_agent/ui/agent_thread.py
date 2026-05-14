"""Bridge between the synchronous `Gemma4Agent.run_text` and the Qt event loop.

The agent is sync and may block for ~30-90 seconds per turn. Running it on
the UI thread would freeze the HUD animations. Instead, we use a QThread
that pulls user turns from a queue and emits Qt signals as the agent
produces output.

Signals:
  state_changed(str)              — INITIALISING / IDLE / THINKING / EXECUTING / SPEAKING / ERROR
  progress(str event, dict payload) — verbatim from agent's progress callback
  log(str text, str tag)          — typewriter line for ActivityLog
  reply_ready(str content, list events) — when a turn finishes
  llm_error(str msg)              — on transport / parse failures
  connection_changed(bool ok)     — when health check toggles
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal


@dataclass
class _TurnRequest:
    text: str
    images: list[str]
    audios: list[str]


class AgentWorker(QThread):
    state_changed = pyqtSignal(str)
    progress = pyqtSignal(str, dict)
    log = pyqtSignal(str, str)
    reply_ready = pyqtSignal(str, list)
    llm_error = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)
    health_status = pyqtSignal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._inbox: queue.Queue[_TurnRequest] = queue.Queue()
        self._running = True
        self._stop_event = threading.Event()
        self._agent: Any = None
        self._config: Any = None
        self._health_timer_thread: threading.Thread | None = None
        self._last_connected: bool | None = None

    # ------------------------------------------------------------------
    def submit(self, text: str, *, images: list[str] | None = None, audios: list[str] | None = None) -> None:
        """Enqueue a new user turn. Thread-safe."""
        self._inbox.put(_TurnRequest(text=text, images=images or [], audios=audios or []))

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        # Inject a sentinel so the queue.get unblocks
        self._inbox.put(_TurnRequest(text="__stop__", images=[], audios=[]))

    def get_agent(self) -> Any:
        return self._agent

    def get_config(self) -> Any:
        return self._config

    # ------------------------------------------------------------------
    def _build_agent(self) -> None:
        from pathlib import Path

        from ..agent import Gemma4Agent
        from ..config import AgentConfig

        self.state_changed.emit("INITIALISING")
        self.log.emit("Building agent config from environment...", "sys")
        try:
            self._config = AgentConfig.from_env()
            self._agent = Gemma4Agent(self._config)
            self.log.emit(f"Agent ready. {len(self._agent.tools.schemas)} tools loaded.", "ok")
        except Exception as exc:
            self.llm_error.emit(f"Agent init failed: {exc}")
            self.state_changed.emit("ERROR")
            return

        # health check
        ok = False
        try:
            ok = bool(self._agent.client.health())
        except Exception:
            ok = False
        self.connection_changed.emit(ok)
        self._last_connected = ok
        if ok:
            self.log.emit(f"llama-server online at {self._config.server_url}", "ok")
            self.state_changed.emit("IDLE")
        else:
            self.log.emit(f"llama-server NOT responding at {self._config.server_url}", "err")
            self.state_changed.emit("OFFLINE")

        # background health polling every 8s, but interruptible via stop_event
        def _health_loop() -> None:
            while self._running:
                # Interruptible sleep so stop() shuts the thread down promptly.
                if self._stop_event.wait(timeout=8.0):
                    return
                if self._agent is None:
                    continue
                try:
                    ok = bool(self._agent.client.health())
                except Exception:
                    ok = False
                if ok != self._last_connected:
                    self._last_connected = ok
                    try:
                        self.connection_changed.emit(ok)
                        self.log.emit(
                            f"Server {'ONLINE' if ok else 'OFFLINE'} at {self._config.server_url}",
                            "ok" if ok else "err",
                        )
                    except RuntimeError:
                        return  # receiver gone
                try:
                    self.health_status.emit({"connected": ok, "server_url": self._config.server_url})
                except RuntimeError:
                    return

        self._health_timer_thread = threading.Thread(
            target=_health_loop, name="gemma4-health", daemon=True
        )
        self._health_timer_thread.start()

    # ------------------------------------------------------------------
    def _progress_forwarder(self, event: str, payload: dict[str, Any]) -> None:
        """Translates agent.progress(...) into UI signals."""
        # Forward raw for any panel that listens
        self.progress.emit(event, payload)

        if event == "start":
            mode = str(payload.get("mode") or "")
            self.state_changed.emit("THINKING")
            self.log.emit(f"turn start: mode={mode}", "sys")
        elif event == "tool_subset":
            count = int(payload.get("schema_count") or 0)
            tools = payload.get("tools") or []
            tlist = ", ".join(str(t) for t in tools[:8])
            if len(tools) > 8:
                tlist += f" ... (+{len(tools) - 8})"
            self.log.emit(f"tool subset ({count}): {tlist}", "sys")
        elif event == "tool_start":
            name = payload.get("name") or "?"
            args = payload.get("args") or {}
            self.state_changed.emit("EXECUTING")
            args_str = self._fmt_args(args)
            self.log.emit(f"{name}({args_str})", "tool")
        elif event == "tool_end":
            name = payload.get("name") or "?"
            ok = bool(payload.get("ok"))
            status = str(payload.get("status") or "")
            verified = payload.get("verified")
            tag = "ok" if ok else "err"
            self.log.emit(
                f"{name} -> {status}" + (f" verified={verified}" if verified is not None else ""),
                tag,
            )
        elif event == "image_injected":
            self.log.emit(f"image injected: {payload.get('path')}", "file")
        elif event == "final":
            self.state_changed.emit("SPEAKING")
        elif event == "max_turns":
            self.state_changed.emit("ERROR")
            self.log.emit("max_turns reached before completing mission", "err")

    @staticmethod
    def _fmt_args(args: dict[str, Any]) -> str:
        try:
            s = json.dumps(args, ensure_ascii=False)
        except Exception:
            s = str(args)
        if len(s) > 120:
            s = s[:117] + "..."
        return s

    # ------------------------------------------------------------------
    def run(self) -> None:
        self._build_agent()
        while self._running:
            req = self._inbox.get()
            if not self._running or req.text == "__stop__":
                break
            if self._agent is None:
                self.llm_error.emit("agent not initialised")
                continue
            try:
                self.log.emit(req.text, "you")
                reply = self._agent.run_text(
                    req.text,
                    images=[Path(p) for p in req.images] if req.images else None,
                    audios=[Path(p) for p in req.audios] if req.audios else None,
                    progress=self._progress_forwarder,
                )
                content = getattr(reply, "content", "")
                events = getattr(reply, "tool_events", [])
                err = getattr(reply, "error", None)
                if err:
                    self.llm_error.emit(str(err))
                    self.state_changed.emit("ERROR")
                    self.log.emit(str(err), "err")
                else:
                    self.reply_ready.emit(content or "", list(events) if events else [])
                    if content:
                        self.log.emit(content, "ai")
                    self.state_changed.emit("IDLE")
            except Exception as exc:
                self.llm_error.emit(f"turn failed: {exc}")
                self.state_changed.emit("ERROR")
                self.log.emit(f"turn failed: {exc}", "err")
