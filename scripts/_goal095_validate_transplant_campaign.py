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
    index_orphan_transplant_claims,
    index_synthesis_responsibility_ids,
    load_assignment,
    load_campaign,
    load_matrix,
    load_transplant_ledger,
    transplant_ledger_path,
    validate_matrix,
    validate_transplant_closeout,
)


def main() -> int:
    matrix = load_matrix(REPO)
    assignment = load_assignment(REPO)
    campaign = load_campaign(REPO)
    card_ids = index_audit_card_ids(REPO)
    synthesis_ids = index_synthesis_responsibility_ids(REPO)
    errors = validate_matrix(matrix, card_ids, synthesis_ids, assignment, repo=REPO)
    errors.extend(validate_transplant_closeout(campaign, matrix, repo=REPO))
    counts = campaign_counts(campaign)
    ledger_path = transplant_ledger_path(REPO)
    ledger = load_transplant_ledger(REPO) if ledger_path.is_file() else {}
    summary = {
        "campaign_id": campaign.get("campaign_id"),
        "counts": counts,
        "declared": campaign.get("counts"),
        "lots": [lot.get("responsibility_id") for lot in campaign.get("lots") or []],
        "empty_reason": campaign.get("empty_reason") or "",
        "required_human_launches": campaign.get("required_human_launches"),
        "owner_prompt": campaign.get("owner_prompt"),
        "next_human_prompt": campaign.get("next_human_prompt"),
        "matrix_next_human_prompt": matrix.get("next_human_prompt"),
        "ledger_next_prompt": ledger.get("next_prompt"),
        "orphan_claims": index_orphan_transplant_claims(REPO),
        "errors": errors,
        "campaign_path": str(campaign_path(REPO).relative_to(REPO)).replace("\\", "/"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
