"""Exact historical intent hints without arguments or execution authority."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "historical_runtime_intents.jsonl"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_FAMILY = re.compile(r"^[a-z][a-z0-9_]*$")
_EFFECTS = frozenset({"none", "operation", "unsupported"})


@dataclass(frozen=True, slots=True)
class HistoricalIntentHint:
    effect: str
    families: tuple[str, ...]


class HistoricalIntentRegistry:
    def __init__(self, rows: Iterable[dict]) -> None:
        hints: dict[str, HistoricalIntentHint] = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "effect",
                "families",
                "text_sha256",
            }:
                raise ValueError("historical intent hint has a non-canonical shape")
            key = row["text_sha256"]
            effect = row["effect"]
            families = row["families"]
            if (
                not isinstance(key, str)
                or _HASH.fullmatch(key) is None
                or key in hints
                or effect not in _EFFECTS
                or not isinstance(families, list)
                or families != sorted(set(families))
                or any(not isinstance(value, str) or _FAMILY.fullmatch(value) is None for value in families)
                or effect != "operation" and families
            ):
                raise ValueError("historical intent hint is invalid or duplicated")
            hints[key] = HistoricalIntentHint(effect, tuple(families))
        self._hints = hints

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> HistoricalIntentRegistry:
        if not path.is_file():
            return cls(())
        with path.open(encoding="utf-8") as handle:
            return cls(json.loads(line) for line in handle if line.strip())

    def lookup(self, text: str) -> HistoricalIntentHint | None:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return self._hints.get(key)

    def __len__(self) -> int:
        return len(self._hints)


FAMILY_EXPANSIONS = {
    "app": frozenset({"app", "window"}),
    "browser": frozenset({"browser", "web"}),
    "media": frozenset({"media", "streaming"}),
    "network": frozenset({"network", "wifi"}),
    "note_task": frozenset({"note", "task"}),
    "notification": frozenset({"notification", "reminder"}),
    "system_settings": frozenset({"system"}),
    "vision": frozenset({"capture", "ocr", "vision"}),
    "web": frozenset({"browser", "web"}),
}


def operation_allowed_by_hint(operation: str, hint: HistoricalIntentHint | None) -> bool:
    if hint is None or hint.effect != "operation":
        return False
    actual = operation.split(".", 1)[0]
    allowed = set(hint.families)
    for family in hint.families:
        allowed.update(FAMILY_EXPANSIONS.get(family, ()))
    return actual in allowed
