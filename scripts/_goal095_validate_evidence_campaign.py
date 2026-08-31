"""Validate the closed evidence_assets campaign: counts, terminals, next_prompt."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_evidence_campaign import campaign_path, counts_for
from scripts.goal095_evidence_ledger import (
    OWNER_PROMPT,
    TERMINALS,
    load_json,
    queue_paths,
    validate_ledger,
)

RANKING_NEEDLES = ("best model", "modelo mejor", "mejor modelo")


def main() -> int:
    batches_path, ledger_path, _ = queue_paths(REPO)
    batches = load_json(batches_path)
    queue = load_json(ledger_path)
    counts = counts_for(queue)
    errors: list[str] = []
    if counts["pending"] != 0:
        errors.append(f"pending={counts['pending']}")
    if counts["claimed"] != 0:
        errors.append(f"claimed={counts['claimed']}")
    if counts["complete"] != counts["total"] or counts["total"] != 132:
        errors.append(f"complete={counts}")
    idmap = {item["batch_id"]: item for item in batches}
    relaunch = 0
    invalid = 0
    terminals: Counter[str] = Counter()
    ranking_bad = 0
    metric_missing = 0
    orphan_claims = []
    claims_dir = REPO / "artifacts" / "goal095" / "claims"
    for path in claims_dir.glob("evidence_assets-*.json"):
        rec = load_json(path)
        if rec.get("status") == "claimed":
            orphan_claims.append(path.name)
    for item in queue["batches"]:
        if item.get("kind") != "evidence_assets":
            continue
        if item.get("status") != "complete":
            errors.append(f"not complete {item['batch_id']}")
            continue
        path = REPO / "artifacts" / "goal095" / "ledger" / f"{item['batch_id']}.json"
        if not path.is_file():
            errors.append(f"missing ledger {item['batch_id']}")
            continue
        led = load_json(path)
        if OWNER_PROMPT in str(led.get("next_prompt")):
            relaunch += 1
        if "09.5.4_AUDITAR_EVIDENCIA_LOTE.md" in str(led.get("next_prompt")):
            relaunch += 1
        batch = idmap[item["batch_id"]]
        found = validate_ledger(led, batch)
        if found:
            invalid += 1
            if len(errors) < 12:
                errors.append(f"{item['batch_id']}: {found[:3]}")
        for row in led.get("files") or []:
            terminals[row.get("terminal") or "?"] += 1
            if row.get("terminal") not in TERMINALS:
                errors.append(f"bad terminal {item['batch_id']} {row.get('path')}")
        for card in led.get("cards") or []:
            blob = json.dumps(card, ensure_ascii=False).casefold()
            if any(needle in blob for needle in RANKING_NEEDLES) and not card.get(
                "equivalent_comparison"
            ):
                ranking_bad += 1
            for field in ("corpus", "denominator", "version", "hardware", "limitations"):
                if not card.get(field):
                    metric_missing += 1
                    break
    campaign = (
        load_json(campaign_path(REPO)) if campaign_path(REPO).is_file() else {}
    )
    if campaign.get("required_human_launches") != 1:
        errors.append("required_human_launches")
    if campaign.get("next_human_prompt") == OWNER_PROMPT:
        errors.append("campaign relaunches 09.5.4")
    if campaign.get("next_human_prompt") != (
        "documentacion/sprints/09.5.7_TOOLS_SKILLS_MISIONES.md"
    ):
        if counts["pending"] == 0 and counts["claimed"] == 0:
            errors.append(f"next_human={campaign.get('next_human_prompt')}")
    payload = {
        "counts": counts,
        "pending": counts["pending"],
        "claimed": counts["claimed"],
        "complete": counts["complete"],
        "relaunch_09_5_4": relaunch,
        "invalid_ledgers": invalid,
        "next_human": campaign.get("next_human_prompt"),
        "required_human_launches": campaign.get("required_human_launches"),
        "orphan_claimed": orphan_claims,
        "terminals": dict(terminals),
        "ranking_without_comparison": ranking_bad,
        "metric_cards_missing_fields": metric_missing,
        "errors": errors[:20],
    }
    print(json.dumps(payload, indent=2), flush=True)
    return 1 if errors or relaunch or invalid or orphan_claims or ranking_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
