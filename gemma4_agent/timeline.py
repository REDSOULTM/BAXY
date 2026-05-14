"""Tool timeline export.

Writes every progress event from `Gemma4Agent.run_text` to a JSONL file under
`~/.gemma4/timeline/<session_id>-<turn>.jsonl`. The agent already emits
events like `tool_start`, `tool_end`, `tool_subset`, `final`, etc. We just
serialize them with a timestamp so they can be inspected later or rendered by
an external UI.

Disable via env `GEMMA4_AGENT_TIMELINE=false` (default ON).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ProgressCallback = Callable[[str, dict[str, Any]], None]


def is_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_AGENT_TIMELINE") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def timeline_dir() -> Path:
    override = os.environ.get("GEMMA4_AGENT_TIMELINE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".gemma4" / "timeline"


class TimelineWriter:
    """Forward every progress event to JSONL while still calling `inner`.

    Usage:

        writer = TimelineWriter(session_id="abc123", turn_index=4, inner=progress.update)
        reply = agent.run_text(user, progress=writer)
        writer.close()

    The writer is itself callable, so `progress=writer` works as the agent's
    progress callback. On `close()`, the file is flushed.
    """

    def __init__(
        self,
        *,
        session_id: str,
        turn_index: int,
        inner: ProgressCallback | None = None,
        root: Path | None = None,
    ) -> None:
        self.session_id = session_id
        self.turn_index = turn_index
        self.inner = inner
        self.root = root or timeline_dir()
        self.path: Path | None = None
        self._fh: Any = None
        self._opened = False

    def _ensure_open(self) -> None:
        if self._opened:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._opened = True
            return
        safe_id = "".join(c for c in self.session_id if c.isalnum())[:32] or "anon"
        self.path = self.root / f"{safe_id}-turn{self.turn_index:03d}.jsonl"
        try:
            self._fh = self.path.open("w", encoding="utf-8")
        except OSError:
            self._fh = None
        self._opened = True

    def __call__(self, event: str, payload: dict[str, Any]) -> None:
        self._ensure_open()
        if self._fh is not None:
            record = {
                "ts": datetime.now().isoformat(timespec="milliseconds"),
                "event": event,
                "payload": _safe_payload(payload),
            }
            try:
                self._fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                self._fh.flush()
            except (OSError, TypeError, ValueError):
                pass
        if self.inner is not None:
            try:
                self.inner(event, payload)
            except Exception:
                pass

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None


def _safe_payload(payload: Any, *, depth: int = 0) -> Any:
    """Recursive truncation that preserves JSON structure.

    - Strings > 600 chars: tail-trim with `...[trunc]`.
    - Lists/tuples: first 20 items, each recursed.
    - Dicts: every value recursed (up to depth 5 — beyond that, stringify).
    - Other scalars: passthrough.

    The point of preserving structure (vs the prior aggressive str() flattening)
    is so tools-aware consumers can still pretty-print nested tool_calls,
    args, and results from the JSONL.
    """
    if depth > 5:
        s = str(payload)
        return s if len(s) <= 300 else s[:300] + "...[trunc]"
    if payload is None or isinstance(payload, (bool, int, float)):
        return payload
    if isinstance(payload, str):
        return payload if len(payload) <= 600 else payload[:600] + "...[trunc]"
    if isinstance(payload, (list, tuple)):
        return [_safe_payload(item, depth=depth + 1) for item in list(payload)[:20]]
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            out[str(key)] = _safe_payload(value, depth=depth + 1)
        return out
    s = str(payload)
    return s if len(s) <= 300 else s[:300] + "...[trunc]"
