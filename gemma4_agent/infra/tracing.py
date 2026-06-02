"""JSONL trace logging for offline agent evaluation."""

from __future__ import annotations

import atexit
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO


# Sprint 7.3: rotation thresholds. The defaults give ~150MB worth of
# history across the active file + 3 archives before the oldest is
# discarded.
DEFAULT_MAX_SIZE_MB = 50
DEFAULT_KEEP_FILES = 3
ROTATE_CHECK_EVERY = 100  # only stat() the file every N events


@dataclass
class TraceLogger:
    path: Path
    enabled: bool = True
    max_size_mb: int = DEFAULT_MAX_SIZE_MB
    keep_files: int = DEFAULT_KEEP_FILES
    _event_counter: int = field(default=0, init=False, repr=False, compare=False)
    # Latency fix (2026-06-02): keep a PERSISTENT append handle instead of
    # open()/write()/close() on every event(). With ~150 events/turn the
    # per-event open/close syscalls cost ~22ms/turn; a held handle + flush
    # drops that to ~1.6ms (micro-bench: 22.4ms -> 1.6ms, ~21ms/turn saved).
    # The handle is opened LAZILY on the first successful write and keyed to
    # the CURRENT self.path so callers/tests that repoint .path still work.
    _fh: TextIO | None = field(default=None, init=False, repr=False, compare=False)
    _fh_path: Path | None = field(default=None, init=False, repr=False, compare=False)
    # event() runs on the single agent-turn thread today (turns are serialized
    # through the AgentWorker queue; ambient_observer/health threads do NOT
    # touch this logger). The lock is cheap insurance: an uncontended lock is
    # ~sub-microsecond and it guarantees no interleaved write / handle-vs-
    # rotation race if any future caller emits from another thread.
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.enabled:
            # Tracing is DIAGNOSTICS — it must never break the agent. If the
            # path is unwritable (parent is a file, no permission, full disk ->
            # OSError) or malformed (embedded null byte / bad chars -> ValueError
            # from the OS layer), disable instead of raising out of the agent
            # constructor. The exception class is irrelevant: at this filesystem
            # boundary ANY failure to prepare the path means "can't trace", and
            # diagnostics must never crash what they trace. event() already
            # swallows the same (OSError, TypeError, ValueError) on write.
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, ValueError):
                self.enabled = False
                return
            # Rotate on startup so a previous session that grew past the
            # cap rolls over cleanly without an extra big-file event.
            self._maybe_rotate()
            # Ensure the held handle is flushed/closed on interpreter exit so
            # the tail of the last turn is never lost. atexit is best-effort
            # and self-cleaning; close() is idempotent and swallows errors.
            atexit.register(self.close)

    def new_turn_id(self) -> str:
        return f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def _close_handle(self) -> None:
        """Close the persistent handle if open (best-effort, never raises)."""
        fh, self._fh, self._fh_path = self._fh, None, None
        if fh is not None:
            try:
                fh.close()
            except (OSError, ValueError):
                pass

    def close(self) -> None:
        """Flush and release the persistent handle. Idempotent + fail-safe.

        Called from atexit and before rotation. Holding the lock keeps it safe
        against a concurrent event() (defensive — see _lock docstring).
        """
        with self._lock:
            self._close_handle()

    def _handle(self) -> TextIO | None:
        """Return a writable handle bound to the CURRENT self.path.

        Opens lazily on first use and reopens transparently if self.path was
        repointed (callers/tests mutate .path directly) or after rotation
        closed the handle. Any open failure (unwritable path, full disk, bad
        chars) is swallowed and returns None so event() simply skips the line
        — tracing must never crash the agent. Must be called under _lock.
        """
        if self._fh is not None and self._fh_path == self.path:
            return self._fh
        # Path changed or no handle yet: drop any stale handle, open fresh.
        self._close_handle()
        try:
            self._fh = self.path.open("a", encoding="utf-8")
            self._fh_path = self.path
            return self._fh
        except (OSError, ValueError):
            self._fh = None
            self._fh_path = None
            return None

    def event(self, turn_id: str, kind: str, **payload: Any) -> None:
        if not self.enabled:
            return
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "turn_id": turn_id,
            "kind": kind,
            **_json_safe(payload),
        }
        # event() is called dozens of times per turn from the agent loop. A
        # write failure (full disk, locked file, parent removed mid-session)
        # or a non-serializable payload must NEVER crash the turn — tracing is
        # diagnostics. Swallow IO/encode errors; the turn continues without
        # this trace line. The lock serializes the rotation->reopen->write
        # sequence so a concurrent caller can't write through a half-rotated
        # handle (defensive; today event() is single-threaded).
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            # Encoding failed before we ever touched the filesystem.
            return
        with self._lock:
            # Cheap rotation throttle: stat() every ROTATE_CHECK_EVERY events.
            # _maybe_rotate() closes the handle before renaming the active file
            # (Windows can't rename an open file), so the next _handle() reopens
            # the fresh active file.
            self._event_counter += 1
            if self._event_counter >= ROTATE_CHECK_EVERY:
                self._event_counter = 0
                self._maybe_rotate()
            fh = self._handle()
            if fh is None:
                return
            try:
                fh.write(line + "\n")
                # Flush so consumers (and tests) see the line immediately and a
                # crash doesn't drop the in-flight buffer. Flushing is cheap;
                # the win came from dropping the open/close, not the flush.
                fh.flush()
            except (OSError, ValueError):
                # The held handle went bad (disk full, file deleted/locked
                # mid-session). Drop it so the next event() retries a fresh
                # open; never propagate.
                self._close_handle()

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def _rotated_path(self, index: int) -> Path:
        """Return the path of the N-th rotated file (e.g. traces.jsonl.1).

        We append ``.N`` to the *full* filename instead of replacing the
        suffix so a path like ``traces.jsonl`` becomes ``traces.jsonl.1``
        rather than ``traces.1`` (which would lose the format hint).
        """
        return self.path.with_name(f"{self.path.name}.{index}")

    def _maybe_rotate(self) -> None:
        """Rotate the trace file when it exceeds ``max_size_mb``.

        Scheme: active file → .1, .1 → .2, …, .keep_files → discarded.
        Defensive: any IO error during rotation is swallowed so a full
        disk or a locked archive never breaks the agent.
        """
        try:
            if not self.path.exists():
                return
            max_bytes = self.max_size_mb * 1024 * 1024
            if self.path.stat().st_size < max_bytes:
                return
            # The persistent append handle holds the active file open. On
            # Windows you cannot rename a file that is open in this process,
            # and even on POSIX the next event() must write to the NEW active
            # file, not the (now-rotated) old inode. Close the handle first;
            # the next _handle() call reopens the fresh active file lazily.
            self._close_handle()
            # Cascade: oldest archive drops off the end, others shift +1.
            for i in range(self.keep_files, 0, -1):
                src = self._rotated_path(i)
                if i == self.keep_files:
                    if src.exists():
                        src.unlink()
                    continue
                dst = self._rotated_path(i + 1)
                if src.exists():
                    src.rename(dst)
            # Move the active file into slot .1; the next event() call
            # will create a fresh active file.
            self.path.rename(self._rotated_path(1))
        except Exception:
            # Rotation must never break the agent.
            pass


def summarize_content(content: str | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(content, str):
        return {"type": "text", "chars": len(content), "preview": content[:500]}
    parts: list[dict[str, Any]] = []
    for part in content:
        kind = str(part.get("type") or "unknown")
        summary: dict[str, Any] = {"type": kind}
        if kind == "text":
            text = str(part.get("text") or "")
            summary.update(chars=len(text), preview=text[:500])
        elif kind == "image_url":
            url = str((part.get("image_url") or {}).get("url") or "")
            summary.update(data_uri=url.startswith("data:"), chars=len(url))
        elif kind == "input_audio":
            audio = part.get("input_audio") or {}
            summary.update(format=audio.get("format"), chars=len(str(audio.get("data") or "")))
        parts.append(summary)
    return {"type": "multimodal", "parts": parts}


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(v) for v in value]
        return str(value)
