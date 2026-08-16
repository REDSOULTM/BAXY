"""Build the shipped, no-authority regression hint bank from the oracle.

Only the exact text hash, expected effect shape, and broad operation families
are retained. The bank contains no user text, arguments, permissions, tool
results, or confirmations and therefore cannot authorize an effect.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
ORACLE = REPO / "artifacts" / "historical_exhaustive" / "runtime_oracle.jsonl"
OUTPUT = REPO / "src" / "baxy_mind" / "data" / "historical_runtime_intents.jsonl"
ALLOWED_EFFECTS = frozenset({"none", "operation", "unsupported"})


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def hint_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    hints = []
    seen: set[str] = set()
    for row in rows:
        effect = str(row.get("expected_effect") or "")
        text_sha256 = str(row.get("text_sha256") or "")
        if effect not in ALLOWED_EFFECTS or len(text_sha256) != 64:
            continue
        if text_sha256 in seen:
            raise ValueError(f"duplicate historical text hash: {text_sha256}")
        seen.add(text_sha256)
        hints.append(
            {
                "effect": effect,
                "families": sorted(set(row.get("expected_families") or ())),
                "text_sha256": text_sha256,
            }
        )
    hints.sort(key=lambda item: item["text_sha256"])
    return hints


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", type=Path, default=ORACLE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    rows = hint_rows(read_jsonl(args.oracle))
    write_jsonl(args.output, rows)
    counts = Counter(row["effect"] for row in rows)
    print(
        json.dumps(
            {
                "hints": len(rows),
                "by_effect": dict(sorted(counts.items())),
                "contains_user_text": False,
                "contains_arguments_or_authority": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
