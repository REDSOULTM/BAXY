"""Single-campaign cursor for Goal 09.5.4 evidence_assets checkpoints.

Wraps the 09.5.1 v1 queue in place: 132 lots become recoverable units of
one campaign. Unit ledgers must not point back at the human prompt.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.campaign.v1"
CAMPAIGN_ID = "evidence_assets"
KIND = "evidence_assets"
OWNER_PROMPT = "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"
CAMPAIGN_CONTINUE = "campaign:evidence_assets"
MODELS_PROMPT = "documentacion/sprints/09.5.5_MODELOS_ROUTER_IDIOMAS.md"
VOICE_PROMPT = "documentacion/sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md"
TOOLS_PROMPT = "documentacion/sprints/09.5.7_TOOLS_SKILLS_MISIONES.md"
RUNTIME_PROMPT = "documentacion/sprints/09.5.8_RUNTIME_UI_RECURSOS.md"
DOCS_PROMPT = "documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md"
CODE_PROMPT = "documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md"


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def campaign_path(repo: Path) -> Path:
    return repo / "artifacts" / "goal095" / "campaigns" / "evidence_assets.json"


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
    evidence = counts_for(queue_ledger)
    if evidence["pending"] or evidence["claimed"]:
        return None
    return RUNTIME_PROMPT


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
    pending_ids = [
        item["batch_id"]
        for item in queue_ledger.get("batches") or []
        if item.get("kind") == KIND and item.get("status") == "pending"
    ]
    cursor = claimed_ids[0] if claimed_ids else cursor_batch_id
    if cursor is None and pending_ids:
        cursor = pending_ids[0]
    payload = {
        "schema": SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "kind": KIND,
        "required_human_launches": 1,
        "owner_prompt": OWNER_PROMPT,
        "migrated_from": "artifacts/goal095/queue v1; 132 evidence_assets lots",
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
        "smoke": (
            "skipped; historical results recovered from artifacts. "
            "existence is not works. physical re-test only if 09.5.9 "
            "chooses reuse — exact requirement in 09.5.10."
        ),
        "updated_utc": now,
    }
    dump_json(campaign_path(repo), payload)
    return payload


def wrap_v1(repo: Path) -> dict[str, Any]:
    queue_path = repo / "artifacts" / "goal095" / "queue" / "ledger.json"
    queue_ledger = load_json(queue_path)
    claimed = [
        item["batch_id"]
        for item in queue_ledger.get("batches") or []
        if item.get("kind") == KIND and item.get("status") == "claimed"
    ]
    pending = [
        item["batch_id"]
        for item in queue_ledger.get("batches") or []
        if item.get("kind") == KIND and item.get("status") == "pending"
    ]
    cursor = claimed[0] if claimed else (pending[0] if pending else None)
    return write_campaign(repo, queue_ledger, cursor)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("action", choices=("wrap", "status"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    if args.action == "wrap":
        payload = wrap_v1(repo)
    else:
        queue = load_json(repo / "artifacts" / "goal095" / "queue" / "ledger.json")
        payload = write_campaign(repo, queue, None)
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
