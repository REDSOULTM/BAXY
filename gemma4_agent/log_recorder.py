"""Per-session log recorder. Subscribes synchronously to the EventBus and
writes two files per session into `~/.gemma4/logs/<session_id>/`:

- `full.log`  — JSON line per published event. Captures EVERYTHING the
  agent / voice / server emits: state changes, tool calls, errors, raw
  BUS payloads. This is the debug feed.
- `chat.log`  — human-readable transcript of only what the user sees on
  screen: YOU / GEMMA / TOOL / SYSTEM / CONTEXT / THOUGHT / MEMORY /
  TRIGGER / BOOT entries from the activity panel.

Why a separate file: when the user reports "gemma did X weird thing",
chat.log lets us reconstruct the visible conversation without sifting
through hundreds of telemetry events.

Session lifecycle: the recorder watches `{type: 'session', id, label}`
events to switch which directory it writes into. Before the first
session event arrives we write to `_pre_session/` so boot output is
still captured. The file handles roll over on session change.

Threading: writes are guarded by an RLock because BUS.publish() runs
under the bus lock but invokes listeners while still holding it — so
nested re-entry from the same thread must work. Each line is flushed
so a crash leaves the log on disk."""

from __future__ import annotations

import datetime
import json
import logging
import threading
from pathlib import Path
from typing import Any, TextIO

from .events_bus import BUS

logger = logging.getLogger(__name__)

# only these activity sources end up in chat.log. anything else is
# internal noise from the perspective of "what the user saw".
_CHAT_SOURCES = {
    "YOU", "GEMMA", "TOOL", "SYSTEM", "CONTEXT",
    "THOUGHT", "MEMORY", "TRIGGER", "BOOT",
}


def _logs_root() -> Path:
    """Root of the logs tree. Mirrors `sessions_dir()` layout so logs
    live next to the sessions they describe."""
    import os
    override = os.environ.get("GEMMA4_AGENT_LOGS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".gemma4" / "logs"


def _iso_now() -> str:
    return datetime.datetime.now().isoformat(timespec="milliseconds")


class LogRecorder:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session_id: str | None = None
        self._session_label: str | None = None
        self._dir: Path | None = None
        self._full: TextIO | None = None
        self._chat: TextIO | None = None
        self._installed = False
        # start under _pre_session so events emitted during server boot
        # (RUNNER.start, VOICE.enable) are still captured. they'll move
        # to the real session dir as soon as one is created.
        self._switch_to("_pre_session", label="(pre-session boot)")

    def install(self) -> None:
        """Register on the BUS. Idempotent — calling twice is a no-op."""
        with self._lock:
            if self._installed:
                return
            BUS.add_listener(self._on_event)
            self._installed = True
            self._write_full({"type": "_recorder", "event": "installed", "ts": _iso_now()})
            self._write_chat("BOOT", "log recorder online")

    def uninstall(self) -> None:
        with self._lock:
            if not self._installed:
                return
            BUS.remove_listener(self._on_event)
            self._installed = False
            self._close_handles()

    def current_session(self) -> str | None:
        with self._lock:
            return self._session_id

    # ---------- internals ----------

    def _switch_to(self, session_id: str, *, label: str | None = None) -> None:
        """Close current handles and open new ones for the given session id.
        `_pre_session` is a special sentinel used before the first real
        session event arrives."""
        # caller already holds _lock when this is invoked from _on_event,
        # but RLock makes the constructor path safe too.
        with self._lock:
            if session_id == self._session_id:
                # same session — just record the label change.
                if label and label != self._session_label:
                    self._session_label = label
                    self._write_chat("SYSTEM", f"session label · {label}")
                return
            self._close_handles()
            self._session_id = session_id
            self._session_label = label
            safe = "".join(c for c in session_id if c.isalnum() or c == "_")[:48] or "_unknown"
            self._dir = _logs_root() / safe
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning("log recorder: cannot create %s: %s", self._dir, exc)
                self._dir = None
                return
            try:
                # append so reopening the same session id keeps history.
                self._full = (self._dir / "full.log").open("a", encoding="utf-8", buffering=1)
                self._chat = (self._dir / "chat.log").open("a", encoding="utf-8", buffering=1)
            except OSError as exc:
                logger.warning("log recorder: cannot open log files: %s", exc)
                self._close_handles()
                return
            self._write_full({
                "type": "_recorder",
                "event": "session_open",
                "session_id": session_id,
                "label": label,
                "ts": _iso_now(),
            })
            if label:
                self._write_chat("SYSTEM", f"session · {session_id[:8]} · {label}")
            else:
                self._write_chat("SYSTEM", f"session · {session_id[:8]}")

    def _close_handles(self) -> None:
        for handle in (self._full, self._chat):
            if handle is None:
                continue
            try:
                handle.flush()
                handle.close()
            except OSError:
                pass
        self._full = None
        self._chat = None

    def _write_full(self, payload: dict[str, Any]) -> None:
        if self._full is None:
            return
        try:
            line = json.dumps(payload, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            # last resort: stringify so a bad payload never silently kills
            # the recorder.
            line = json.dumps({"_unserializable": str(payload), "error": str(exc)})
        try:
            self._full.write(line + "\n")
        except OSError as exc:
            logger.debug("log recorder full.log write failed: %s", exc)

    def _write_chat(self, src: str, msg: str, *, ts: str | None = None) -> None:
        if self._chat is None:
            return
        stamp = ts or _stamp_short()
        try:
            self._chat.write(f"[{stamp}] {src}: {msg}\n")
        except OSError as exc:
            logger.debug("log recorder chat.log write failed: %s", exc)

    def _on_event(self, event: dict[str, Any]) -> None:
        # exceptions get swallowed by the bus but we still don't want to
        # propagate them up the call chain. wrap the whole thing.
        try:
            self._handle(event)
        except Exception as exc:
            logger.debug("log recorder failed to handle event: %s", exc)

    def _handle(self, event: dict[str, Any]) -> None:
        with self._lock:
            etype = str(event.get("type") or "")

            # always record the raw event to full.log first so even
            # session-switch events appear in the previous session's tail
            # before the handle rolls over. that's the "audit" guarantee.
            stamped = {"_ts": _iso_now(), **event}
            self._write_full(stamped)

            if etype == "session":
                sid = event.get("id")
                if isinstance(sid, str) and sid:
                    self._switch_to(sid, label=str(event.get("label") or "") or None)
                return

            if etype == "activity":
                entry = event.get("entry") or {}
                if not isinstance(entry, dict):
                    return
                src = str(entry.get("src") or "").strip().upper()
                msg = str(entry.get("msg") or "")
                ts = str(entry.get("ts") or "") or None
                if src in _CHAT_SOURCES and msg:
                    self._write_chat(src, msg, ts=ts)


def _stamp_short() -> str:
    n = datetime.datetime.now()
    return f"{n.hour:02d}:{n.minute:02d}:{n.second:02d}"


# module-level singleton. Importing `RECORDER` installs it lazily — the
# server calls .install() during create_app so it survives reimports and
# starts capturing immediately when the FastAPI app comes up.
RECORDER = LogRecorder()
