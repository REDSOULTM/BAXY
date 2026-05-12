"""Explicit persistent memory for the Gemma 4 agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class MemoryStore:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"items": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": {}}
        if not isinstance(data, dict):
            return {"items": {}}
        data.setdefault("items", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save(self, key: str, value: str) -> dict[str, Any]:
        key = key.strip()
        if not key:
            return {"ok": False, "error": "empty key"}
        data = self._load()
        data["items"][key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save(data)
        return {"ok": True, "key": key, "value": value}

    def recall(self, query: str | None = None) -> dict[str, Any]:
        data = self._load()
        items = data.get("items", {})
        if not query:
            return {"ok": True, "items": items}
        q = query.casefold()
        matches = {
            k: v for k, v in items.items()
            if q in k.casefold() or q in str(v.get("value", "")).casefold()
        }
        return {"ok": True, "query": query, "items": matches}

    def delete(self, key: str) -> dict[str, Any]:
        data = self._load()
        items = data.get("items", {})
        if key == "*":
            count = len(items)
            data["items"] = {}
            self._save(data)
            return {"ok": True, "deleted": count}
        existed = key in items
        items.pop(key, None)
        self._save(data)
        return {"ok": True, "key": key, "existed": existed}

    def prompt_summary(self) -> str:
        items = self._load().get("items", {})
        if not items:
            return "No persistent memory saved."
        lines = []
        for key, entry in sorted(items.items()):
            lines.append(f"- {key}: {entry.get('value', '')}")
        return "\n".join(lines)
