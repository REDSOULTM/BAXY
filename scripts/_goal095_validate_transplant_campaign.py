"""Validate the 09.5.9/09.5.10 transplant campaign against the shipped matrix."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_0959_matrix import (
    campaign_counts,
    campaign_path,
    index_audit_card_ids,
    index_synthesis_responsibility_ids,
    load_assignment,
    load_campaign,
    load_matrix,
    validate_campaign,
    validate_matrix,
)


def main() -> int:
    matrix = load_matrix(REPO)
    assignment = load_assignment(REPO)
    campaign = load_campaign(REPO)
    card_ids = index_audit_card_ids(REPO)
    synthesis_ids = index_synthesis_responsibility_ids(REPO)
    errors = validate_matrix(matrix, card_ids, synthesis_ids, assignment, repo=REPO)
    errors.extend(validate_campaign(campaign, matrix))
    counts = campaign_counts(campaign)
    summary = {
        "campaign_id": campaign.get("campaign_id"),
        "counts": counts,
        "declared": campaign.get("counts"),
        "lots": [lot.get("responsibility_id") for lot in campaign.get("lots") or []],
        "empty_reason": campaign.get("empty_reason") or "",
        "next_human_prompt": campaign.get("next_human_prompt"),
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
