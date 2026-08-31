"""Close the 09.5.10 transplant campaign.

Empty-queue and last-lot share apply_transplant_closeout: pending=0 and
claimed=0 names 09.5.11A. Does not invent lots, does not walk source trees,
and does not write src/.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.goal095_0959_matrix import (
    LEDGER_REL,
    MARKDOWN_09510_REL,
    PROTECTED_REJECTS,
    REVALIDATE_PROMPT,
    TRANSPLANT_PROMPT,
    apply_transplant_closeout,
    campaign_counts,
    campaign_path,
    dump_json,
    index_orphan_transplant_claims,
    load_campaign,
    load_json,
    load_matrix,
    lots_from_matrix,
    matrix_path,
    transplant_ledger_path,
    validate_transplant_closeout,
)

LEASE_SECONDS = 6 * 3600


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def expire_or_resume_claims(
    repo: Path,
    campaign: dict[str, Any],
    *,
    now: datetime | None = None,
    lease_seconds: int = LEASE_SECONDS,
) -> tuple[list[str], list[str]]:
    """Live claims resume; expired leases return to pending. No terminals dropped."""
    clock = now or datetime.now(timezone.utc)
    claims_dir = repo / "artifacts" / "goal095" / "claims"
    expired: list[str] = []
    resumed: list[str] = []
    for lot in campaign.get("lots") or []:
        if lot.get("status") != "claimed":
            continue
        lot_id = str(lot.get("lot_id") or "")
        claim_path = claims_dir / f"{lot_id}.json"
        if not claim_path.is_file():
            lot["status"] = "pending"
            expired.append(lot_id)
            continue
        rec = load_json(claim_path)
        expires = _parse_utc(rec.get("lease_expires_utc"))
        claimed_at = _parse_utc(rec.get("claimed_utc"))
        if expires is None and claimed_at is not None:
            expires = claimed_at + timedelta(seconds=lease_seconds)
        if expires is not None and expires <= clock:
            lot["status"] = "pending"
            rec["status"] = "expired"
            rec["expired_utc"] = clock.strftime("%Y-%m-%dT%H:%M:%SZ")
            dump_json(claim_path, rec)
            expired.append(lot_id)
            continue
        resumed.append(lot_id)
    return expired, resumed


def _patch_json_next(path: Path, field: str, new_value: str, *, previous: str) -> None:
    """Change one string field without rewriting an unrelated JSON body."""
    text = path.read_text(encoding="utf-8")
    old = f'"{field}": "{previous}"'
    new = f'"{field}": "{new_value}"'
    if old not in text:
        data = load_json(path)
        if str(data.get(field) or "") == new_value:
            return
        raise RuntimeError(f"{path}: {field} is not {previous}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def close_campaign(repo: Path) -> dict[str, Any]:
    matrix = load_matrix(repo)
    campaign = load_campaign(repo)
    expected_ids = [lot["responsibility_id"] for lot in lots_from_matrix(matrix)]
    actual_ids = [str(lot.get("responsibility_id") or "") for lot in campaign.get("lots") or []]
    if actual_ids != expected_ids:
        raise RuntimeError(f"lots != matrix transplant rows {actual_ids} vs {expected_ids}")
    expired, resumed = expire_or_resume_claims(repo, campaign)
    pending = [
        lot.get("lot_id")
        for lot in campaign.get("lots") or []
        if lot.get("status") == "pending"
    ]
    if pending:
        raise RuntimeError(
            "pending lots exist; 09.5.10 processes them before closeout: "
            + ", ".join(str(item) for item in pending[:12])
        )
    claimed = [
        lot.get("lot_id")
        for lot in campaign.get("lots") or []
        if lot.get("status") == "claimed"
    ]
    if claimed:
        raise RuntimeError(
            "live claims remain after expire/resume: "
            + ", ".join(str(item) for item in claimed[:12])
        )
    updated = _now_utc()
    closed = apply_transplant_closeout(campaign, updated_utc=updated)
    dump_json(campaign_path(repo), closed)
    next_prompt = closed["next_human_prompt"]
    _patch_json_next(
        matrix_path(repo),
        "next_human_prompt",
        next_prompt,
        previous=TRANSPLANT_PROMPT,
    )
    s9 = repo / LEDGER_REL
    if s9.is_file():
        _patch_json_next(
            s9,
            "next_prompt",
            next_prompt,
            previous=TRANSPLANT_PROMPT,
        )
    counts = campaign_counts(closed)
    ledger = {
        "schema": "baxy.goal095.09510-ledger.v1",
        "batch_id": "transplant-09.5.10",
        "kind": "transplant",
        "status": "complete",
        "goal": "09.5.10",
        "closed_utc": updated,
        "campaign_ref": str(campaign_path(repo).relative_to(repo)).replace("\\", "/"),
        "matrix_ref": str(matrix_path(repo).relative_to(repo)).replace("\\", "/"),
        "markdown_ref": MARKDOWN_09510_REL.replace("\\", "/"),
        "required_human_launches": 1,
        "owner_prompt": TRANSPLANT_PROMPT,
        "empty_reason": closed.get("empty_reason") or "",
        "lots_applied": [lot.get("responsibility_id") for lot in closed.get("lots") or []],
        "live_src_changed": False,
        "estado_del_arte_added": False,
        "fallo_de_ambiente": [],
        "expired_claims": expired,
        "resumed_claims": resumed,
        "orphan_claims": index_orphan_transplant_claims(repo),
        "protected_rejects_blocked": list(PROTECTED_REJECTS),
        "campaigns_remain_closed": {
            "docs": "25/25 pending=0 claimed=0",
            "code_tests": "477/477 pending=0 claimed=0",
            "evidence_assets": "132/132 pending=0 claimed=0",
        },
        "counts": counts,
        "next_prompt": next_prompt,
    }
    dump_json(transplant_ledger_path(repo), ledger)
    matrix_after = load_matrix(repo)
    errors = validate_transplant_closeout(closed, matrix_after, repo=repo)
    return {
        "counts": counts,
        "next_human_prompt": next_prompt,
        "expired_claims": expired,
        "resumed_claims": resumed,
        "orphan_claims": index_orphan_transplant_claims(repo),
        "errors": errors,
    }


def main() -> int:
    summary = close_campaign(_REPO)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
