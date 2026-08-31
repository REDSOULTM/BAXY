"""Single-campaign cursor for Goal 09.5.3 code_tests checkpoints.

Migrates the 09.5.1 v1 queue in place: 477 lots become recoverable units of
one campaign. Unit ledgers must not point back at the human prompt.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.campaign.v1"
CAMPAIGN_ID = "code_tests"
KIND = "code_tests"
OWNER_PROMPT = "documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md"
CAMPAIGN_CONTINUE = "campaign:code_tests"
DOCS_PROMPT = "documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md"
EVIDENCE_PROMPT = "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def campaign_path(repo: Path) -> Path:
    return repo / "artifacts" / "goal095" / "campaigns" / "code_tests.json"


def counts_for(queue_ledger: dict[str, Any]) -> dict[str, int]:
    pending = claimed = complete = 0
    total = 0
    for item in queue_ledger.get("batches") or []:
        if item.get("kind") != KIND:
            continue
        total += 1
        status = item.get("status")
        if status == "pending":
            pending += 1
        elif status == "claimed":
            claimed += 1
        elif status == "complete":
            complete += 1
    return {
        "pending": pending,
        "claimed": claimed,
        "complete": complete,
        "total": total,
    }


def next_human_prompt(queue_ledger: dict[str, Any]) -> str | None:
    code = counts_for(queue_ledger)
    if code["pending"] or code["claimed"]:
        return None
    docs_open = any(
        item.get("kind") == "docs" and item.get("status") in {"pending", "claimed"}
        for item in queue_ledger.get("batches") or []
    )
    return DOCS_PROMPT if docs_open else EVIDENCE_PROMPT


def write_campaign(
    repo: Path,
    queue_ledger: dict[str, Any],
    cursor_batch_id: str | None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = counts_for(queue_ledger)
    complete_ids = [
        item["batch_id"]
        for item in queue_ledger.get("batches") or []
        if item.get("kind") == KIND and item.get("status") == "complete"
    ]
    claimed_ids = [
        item["batch_id"]
        for item in queue_ledger.get("batches") or []
        if item.get("kind") == KIND and item.get("status") == "claimed"
    ]
    cursor = claimed_ids[0] if claimed_ids else cursor_batch_id
    payload = {
        "schema": SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "kind": KIND,
        "required_human_launches": 1,
        "owner_prompt": OWNER_PROMPT,
        "migrated_from": "artifacts/goal095/queue v1; 477 code_tests lots",
        "cursor_batch_id": cursor,
        "cursor_status": (
            "claimed"
            if claimed_ids
            else "complete"
            if counts["pending"] == 0
            else "pending"
        ),
        "counts": counts,
        "preserved_complete": complete_ids,
        "next_human_prompt": next_human_prompt(queue_ledger),
        "updated_utc": now,
    }
    dump_json(campaign_path(repo), payload)
    return payload
