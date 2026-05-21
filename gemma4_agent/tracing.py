"""JSONL trace logging for offline agent evaluation."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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

    def __post_init__(self) -> None:
        if self.enabled:
            # Tracing is DIAGNOSTICS — it must never break the agent. If the
            # path is unwritable (parent is a file, no permission, full disk),
            # disable instead of raising out of the agent constructor.
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                self.enabled = False
                return
            # Rotate on startup so a previous session that grew past the
            # cap rolls over cleanly without an extra big-file event.
            self._maybe_rotate()

    def new_turn_id(self) -> str:
        return f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def event(self, turn_id: str, kind: str, **payload: Any) -> None:
        if not self.enabled:
            return
        # Cheap rotation throttle: stat() every ROTATE_CHECK_EVERY events.
        self._event_counter += 1
        if self._event_counter >= ROTATE_CHECK_EVERY:
            self._event_counter = 0
            self._maybe_rotate()
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "turn_id": turn_id,
            "kind": kind,
            **_json_safe(payload),
        }
        # event() is called dozens of times per turn from the agent loop. A
        # write failure (full disk, locked file, parent removed mid-session)
        # must NEVER crash the turn — tracing is diagnostics. Swallow IO/encode
        # errors; the turn continues without this trace line.
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except (OSError, TypeError, ValueError):
            pass

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
