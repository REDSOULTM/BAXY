"""Reopen one complete docs unit so it can be closed again. Data-only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_docs_campaign import write_campaign
from scripts.goal095_docs_ledger import dump_json, load_json, queue_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args()
    _batches, ledger_path, _ = queue_paths(REPO)
    queue = load_json(ledger_path)
    found = False
    for item in queue["batches"]:
        if item["batch_id"] == args.batch_id:
            item["status"] = "pending"
            item.pop("claimed_utc", None)
            item.pop("closed_utc", None)
            found = True
    if not found:
        raise SystemExit(args.batch_id)
    dump_json(ledger_path, queue)
    claim = REPO / "artifacts" / "goal095" / "claims" / f"{args.batch_id}.json"
    if claim.is_file():
        claim.unlink()
    write_campaign(REPO, queue, args.batch_id)
    print(args.batch_id, "pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
