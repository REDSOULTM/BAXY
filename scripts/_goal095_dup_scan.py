"""Count remaining code_tests batches that are hash-duplicates of earlier units."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "artifacts" / "goal095" / "queue"
LEDGER_DIR = REPO / "artifacts" / "goal095" / "ledger"


def main() -> int:
    batches = json.loads((QUEUE / "batches.json").read_text(encoding="utf-8"))
    queue = json.loads((QUEUE / "ledger.json").read_text(encoding="utf-8"))
    idmap = {item["batch_id"]: item for item in batches}
    seen: dict[str, str] = {}
    for item in queue["batches"]:
        if item.get("kind") != "code_tests" or item.get("status") != "complete":
            continue
        path = LEDGER_DIR / f"{item['batch_id']}.json"
        if not path.is_file():
            continue
        led = json.loads(path.read_text(encoding="utf-8"))
        for row in led["files"]:
            seen[row["sha256"]] = item["batch_id"]
    all_dup = 0
    partial = 0
    fresh = 0
    examples: list[str] = []
    for item in queue["batches"]:
        if item.get("kind") != "code_tests" or item.get("status") == "complete":
            continue
        batch = idmap[item["batch_id"]]
        hashes = [row["sha256"] for row in batch["files"]]
        if hashes and all(h in seen for h in hashes):
            all_dup += 1
            if len(examples) < 8:
                examples.append(item["batch_id"])
        elif any(h in seen for h in hashes):
            partial += 1
            for h in hashes:
                seen.setdefault(h, item["batch_id"])
        else:
            fresh += 1
            for h in hashes:
                seen.setdefault(h, item["batch_id"])
    print(json.dumps({"all_dup": all_dup, "partial": partial, "fresh": fresh, "examples": examples}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
