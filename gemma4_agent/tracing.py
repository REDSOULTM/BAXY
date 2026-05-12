"""JSONL trace logging for offline agent evaluation."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TraceLogger:
    path: Path
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def new_turn_id(self) -> str:
        return f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def event(self, turn_id: str, kind: str, **payload: Any) -> None:
        if not self.enabled:
            return
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "turn_id": turn_id,
            "kind": kind,
            **_json_safe(payload),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


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
