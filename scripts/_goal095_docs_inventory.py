"""One-shot inventory of docs batches. Not imported by product code."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_goal095_queues import FROZEN_0950, PROGRAMACION


def main() -> int:
    batches = json.loads(
        (REPO / "artifacts/goal095/queue/batches.json").read_text(encoding="utf-8")
    )
    ledger = json.loads(
        (REPO / "artifacts/goal095/queue/ledger.json").read_text(encoding="utf-8")
    )
    status = {
        item["batch_id"]: item.get("status")
        for item in ledger["batches"]
        if item.get("kind") == "docs"
    }
    docs = [batch for batch in batches if batch.get("kind") == "docs"]
    print("docs batches", len(docs))
    extensions: Counter[str] = Counter()
    for batch in docs:
        print(
            f"{batch['batch_id']}\t{status.get(batch['batch_id'])}\t"
            f"files={batch['file_count']}\ttok={batch['estimated_tokens']}\t"
            f"src={batch.get('source_id')}\tsub={batch.get('subsystem')}"
        )
        for row in batch["files"]:
            name = row["path"].replace("\\", "/").rsplit("/", 1)[-1]
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else "(none)"
            extensions[ext] += 1
    print("---EXTS---")
    for key, count in extensions.most_common():
        print(key, count)
    print("---SOURCES---")
    for source_id, spec in FROZEN_0950.items():
        root = PROGRAMACION / spec["folder"]
        print(source_id, root, "exists" if root.is_dir() else "MISSING")
    sample = next(item for item in docs if item["batch_id"] == "docs-002-carter")
    print("---002 first 20---")
    for row in sample["files"][:20]:
        print(row["path"], row["size"])
    print("---002 last 8---")
    for row in sample["files"][-8:]:
        print(row["path"], row["size"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
