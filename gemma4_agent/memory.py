"""Explicit persistent memory for the Gemma 4 agent."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class MemoryStore:
    path: Path
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

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
        from .state import atomic_write_json
        atomic_write_json(self.path, data)

    def save(self, key: str, value: str) -> dict[str, Any]:
        key = key.strip()
        if not key:
            return {"ok": False, "error": "empty key"}
        with self._lock:
            data = self._load()
            data["items"][key] = {
                "value": value,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._save(data)
            return {"ok": True, "key": key, "value": value}

    def auto_save(self, facts: list[dict[str, str]], *, max_total: int = 50) -> dict[str, Any]:
        """Persist facts extracted automatically (without explicit user request).

        Each fact is dict {key, value}. We prefix the key with 'auto:' so the
        user can tell auto-learned facts from explicit ones, and we cap the
        total auto-saved facts at `max_total` (FIFO eviction of oldest).
        """
        with self._lock:
            data = self._load()
            items = data.setdefault("items", {})
            added: list[str] = []
            skipped: list[dict[str, Any]] = []
            for fact in facts:
                key = str(fact.get("key", "")).strip()
                value = str(fact.get("value", "")).strip()
                if not key or not value:
                    skipped.append({"reason": "empty_key_or_value", "fact": fact})
                    continue
                stamped_key = key if key.startswith("auto:") else f"auto:{key}"
                items[stamped_key] = {
                    "value": value,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "source": "auto_extracted",
                }
                added.append(stamped_key)
            # Evict oldest auto:* entries if we exceed the cap. Explicit (non-auto)
            # entries are never touched.
            auto_keys = [k for k in items if k.startswith("auto:")]
            if len(auto_keys) > max_total:
                sorted_auto = sorted(
                    ((k, items[k].get("updated_at", "")) for k in auto_keys),
                    key=lambda pair: pair[1],
                )
                to_drop = len(auto_keys) - max_total
                for k, _ in sorted_auto[:to_drop]:
                    items.pop(k, None)
            self._save(data)
            return {"ok": True, "added": added, "skipped": skipped, "total_auto": sum(1 for k in items if k.startswith("auto:"))}

    def recall(self, query: str | None = None) -> dict[str, Any]:
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            items = self._load().get("items", {})
        if not items:
            return "No persistent memory saved."
        lines = []
        for key, entry in sorted(items.items()):
            lines.append(f"- {key}: {entry.get('value', '')}")
        return "\n".join(lines)
