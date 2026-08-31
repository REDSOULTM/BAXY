"""Validate the docs campaign: counts, terminals, no relaunch of 09.5.2."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_docs_campaign import campaign_path, counts_for
from scripts.goal095_docs_ledger import OWNER_PROMPT, load_json, queue_paths, validate_ledger


def main() -> int:
    batches_path, ledger_path, _ = queue_paths(REPO)
    batches = load_json(batches_path)
    queue = load_json(ledger_path)
    counts = counts_for(queue)
    errors: list[str] = []
    idmap = {item["batch_id"]: item for item in batches}
    relaunch = 0
    invalid = 0
    for item in queue["batches"]:
        if item.get("kind") != "docs":
            continue
        if item.get("status") != "complete":
            continue
        path = REPO / "artifacts" / "goal095" / "ledger" / f"{item['batch_id']}.json"
        if not path.is_file():
            errors.append(f"missing ledger {item['batch_id']}")
            continue
        led = load_json(path)
        if OWNER_PROMPT in str(led.get("next_prompt")):
            relaunch += 1
        batch = idmap[item["batch_id"]]
        found = validate_ledger(led, batch)
        if found:
            invalid += 1
            if len(errors) < 12:
                errors.append(f"{item['batch_id']}: {found[:3]}")
    campaign = load_json(campaign_path(REPO)) if campaign_path(REPO).is_file() else {}
    if campaign.get("required_human_launches") != 1:
        errors.append("required_human_launches")
    if campaign.get("next_human_prompt") == OWNER_PROMPT:
        errors.append("campaign relaunches 09.5.2")
    print(
        json.dumps(
            {
                "counts": counts,
                "relaunch_09_5_2": relaunch,
                "invalid_ledgers": invalid,
                "next_human": campaign.get("next_human_prompt"),
                "errors": errors[:20],
            },
            indent=2,
        )
    )
    return 1 if errors or relaunch or invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
