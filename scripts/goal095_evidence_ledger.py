"""Claim, schema and validation for Goal 09.5.4 evidence_assets ledgers.

Live claims resume without resetting claimed_utc. Expired leases return
the unit to pending. Terminals are the four evidence terminals only —
`leido` is rejected. next_prompt must not relaunch 09.5.4.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_docs_ledger import (
    TOKEN_LIMIT,
    TOKEN_TARGET,
    batch_from_batches,
    dump_json,
    load_json,
    queue_paths,
)
from scripts.goal095_evidence_campaign import (
    CAMPAIGN_CONTINUE,
    MODELS_PROMPT,
    OWNER_PROMPT,
    write_campaign,
)

SCHEMA = "baxy.goal095.evidence-ledger.v1"
KIND = "evidence_assets"
LEASE_SECONDS = 6 * 3600
ALLOWED_NEXT_PROMPTS = frozenset({CAMPAIGN_CONTINUE, MODELS_PROMPT})
TERMINALS = frozenset(
    {
        "parseado_completo",
        "binario_inventariado",
        "duplicado_por_hash",
        "excluido_razonado",
    }
)
CARD_KINDS = frozenset(
    {"metric", "asset", "run", "contamination", "negative", "corpus"}
)
OUTCOMES = frozenset({"exito", "fracaso", "inconcluso", "contexto", "negativo"})
QUEUE_STATUSES = frozenset({"pending", "claimed", "complete"})
RANKING_NEEDLES = ("best model", "modelo mejor", "mejor modelo")

LEDGER_REQUIRED = (
    "schema",
    "batch_id",
    "kind",
    "status",
    "claimed_utc",
    "closed_utc",
    "estimated_tokens",
    "token_limit",
    "token_target",
    "source_id",
    "source_head",
    "source_root",
    "files",
    "cards",
    "missing",
    "overlaps",
    "next_evidence_assets_batch_id",
    "next_prompt",
)
FILE_REQUIRED = ("path", "sha256", "source_id", "terminal", "ranges")
CARD_REQUIRED = (
    "card_id",
    "card_kind",
    "corpus",
    "denominator",
    "version",
    "hardware",
    "limitations",
    "identity",
    "consumers",
    "associated_benchmark",
    "source_files",
    "provisional",
    "ranking_claim",
    "equivalent_comparison",
    "measurement",
    "outcome",
    "works",
    "provenance",
    "current_owner",
)
PROVENANCE_REQUIRED = ("path", "ranges", "date", "hardware", "model", "commit")


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def first_pending_evidence(queue_ledger: dict[str, Any]) -> dict[str, Any] | None:
    for item in queue_ledger["batches"]:
        if item.get("kind") == KIND and item.get("status") == "pending":
            return item
    return None


def claimed_evidence(queue_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in queue_ledger["batches"]
        if item.get("kind") == KIND and item.get("status") == "claimed"
    ]


def unit_next_prompt(queue_ledger: dict[str, Any], next_id: str | None) -> str:
    if next_id:
        return CAMPAIGN_CONTINUE
    return MODELS_PROMPT


def expire_stale_claims(
    repo: Path,
    *,
    now: datetime | None = None,
    lease_seconds: int = LEASE_SECONDS,
) -> list[str]:
    """Return expired batch ids to pending. Does not claim a replacement."""
    _batches_path, ledger_path, _summary = queue_paths(repo)
    if not ledger_path.is_file():
        return []
    queue_ledger = load_json(ledger_path)
    clock = now or datetime.now(timezone.utc)
    expired_ids: list[str] = []
    claims_dir = repo / "artifacts" / "goal095" / "claims"
    for item in queue_ledger.get("batches") or []:
        if item.get("kind") != KIND or item.get("status") != "claimed":
            continue
        expires = _parse_utc(item.get("lease_expires_utc"))
        claimed_at = _parse_utc(item.get("claimed_utc"))
        if expires is None and claimed_at is not None:
            expires = claimed_at + timedelta(seconds=lease_seconds)
        if expires is None or expires > clock:
            continue
        item["status"] = "pending"
        item["claimed_utc"] = None
        item["lease_expires_utc"] = None
        expired_ids.append(item["batch_id"])
        claim_path = claims_dir / f"{item['batch_id']}.json"
        if claim_path.is_file():
            record = load_json(claim_path)
            record["status"] = "expired"
            record["expired_utc"] = clock.strftime("%Y-%m-%dT%H:%M:%SZ")
            dump_json(claim_path, record)
    if expired_ids:
        dump_json(ledger_path, queue_ledger)
        write_campaign(repo, queue_ledger, None)
    return expired_ids


def claim(
    repo: Path,
    batch_id: str | None = None,
    source_root: Path | None = None,
    source_head: str | None = None,
    *,
    now: datetime | None = None,
    lease_seconds: int = LEASE_SECONDS,
) -> dict[str, Any]:
    expire_stale_claims(repo, now=now, lease_seconds=lease_seconds)
    batches_path, ledger_path, _summary_path = queue_paths(repo)
    batches = load_json(batches_path)
    queue_ledger = load_json(ledger_path)
    claimed = claimed_evidence(queue_ledger)
    claim_path_dir = repo / "artifacts" / "goal095" / "claims"
    clock = now or datetime.now(timezone.utc)
    if claimed:
        ids = [item["batch_id"] for item in claimed]
        if batch_id is None:
            batch_id = ids[0]
        if ids != [batch_id]:
            raise RuntimeError(f"another batch already claimed: {ids}")
        existing = claim_path_dir / f"{batch_id}.json"
        if existing.is_file():
            record = load_json(existing)
            if record.get("status") == "claimed":
                write_campaign(repo, queue_ledger, batch_id)
                return record
    else:
        pending = first_pending_evidence(queue_ledger)
        if pending is None:
            raise RuntimeError("no pending evidence_assets batch")
        if batch_id is None:
            batch_id = pending["batch_id"]
        if pending["batch_id"] != batch_id:
            raise RuntimeError(
                f"first pending evidence_assets is {pending['batch_id']}, not {batch_id}"
            )
    batch = batch_from_batches(batches, batch_id)
    if batch["estimated_tokens"] > TOKEN_LIMIT:
        raise RuntimeError("batch exceeds token limit")
    claimed_utc = clock.strftime("%Y-%m-%dT%H:%M:%SZ")
    lease_expires = (clock + timedelta(seconds=lease_seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    for item in queue_ledger["batches"]:
        if item["batch_id"] == batch_id:
            item["status"] = "claimed"
            item["claimed_utc"] = item.get("claimed_utc") or claimed_utc
            claimed_utc = item["claimed_utc"]
            item["lease_expires_utc"] = lease_expires
    dump_json(ledger_path, queue_ledger)
    claim_record = {
        "schema": SCHEMA,
        "batch_id": batch_id,
        "kind": KIND,
        "status": "claimed",
        "claimed_utc": claimed_utc,
        "lease_expires_utc": lease_expires,
        "estimated_tokens": batch["estimated_tokens"],
        "token_limit": batch.get("token_limit", TOKEN_LIMIT),
        "token_target": batch.get("token_target", TOKEN_TARGET),
        "file_count": batch["file_count"],
        "source_id": batch.get("source_id"),
        "source_root": (
            None
            if source_root is None
            else source_root.as_posix()
            if not source_root.is_absolute()
            else f"Programacion/{source_root.name}"
        ),
        "source_head": source_head,
        "output": batch["output"],
    }
    dump_json(claim_path_dir / f"{batch_id}.json", claim_record)
    write_campaign(repo, queue_ledger, batch_id)
    return claim_record


def _require(obj: dict[str, Any], keys: tuple[str, ...], where: str) -> list[str]:
    errors = []
    for key in keys:
        if key not in obj:
            errors.append(f"{where} missing {key}")
    return errors


def _blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).casefold()


def validate_ledger(
    ledger: dict[str, Any],
    batch: dict[str, Any],
    *,
    allow_open: bool = False,
) -> list[str]:
    errors = _require(ledger, LEDGER_REQUIRED, "ledger")
    if ledger.get("schema") != SCHEMA:
        errors.append("schema")
    if ledger.get("kind") != KIND:
        errors.append("kind")
    if ledger.get("batch_id") != batch["batch_id"]:
        errors.append("batch_id mismatch")
    if ledger.get("status") not in {"claimed", "complete"}:
        errors.append("status")
    if ledger.get("status") != "complete" and not allow_open:
        errors.append("ledger not complete")
    if int(ledger.get("estimated_tokens", -1)) != int(batch["estimated_tokens"]):
        errors.append("estimated_tokens")
    if int(ledger.get("token_limit", -1)) > TOKEN_LIMIT:
        errors.append("token_limit")
    if int(batch["estimated_tokens"]) > TOKEN_LIMIT:
        errors.append("batch over budget")
    assigned = {
        (item["path"], item["sha256"], item["source_id"]) for item in batch["files"]
    }
    seen: set[tuple[str, str, str]] = set()
    terminals_ok = True
    for index, row in enumerate(ledger.get("files") or []):
        where = f"files[{index}]"
        errors.extend(_require(row, FILE_REQUIRED, where))
        key = (row.get("path"), row.get("sha256"), row.get("source_id"))
        if key in seen:
            errors.append(f"{where} duplicate")
        seen.add(key)
        if key not in assigned:
            errors.append(f"{where} outside batch")
        terminal = row.get("terminal")
        if terminal == "leido":
            errors.append(f"{where} leido is not a terminal for evidence_assets")
            terminals_ok = False
        elif terminal not in TERMINALS:
            errors.append(f"{where} terminal")
            terminals_ok = False
        ranges = row.get("ranges")
        if not isinstance(ranges, list) or not ranges:
            errors.append(f"{where} ranges")
        if terminal == "duplicado_por_hash" and not row.get("duplicate_of"):
            errors.append(f"{where} duplicate_of")
        if terminal == "excluido_razonado" and not row.get("exclusion_rule"):
            errors.append(f"{where} exclusion_rule")
        if terminal == "binario_inventariado":
            if not row.get("binary_format"):
                errors.append(f"{where} binary_format")
            if not row.get("extract_ref"):
                errors.append(f"{where} extract_ref")
        if terminal == "parseado_completo" and not row.get("extract_ref"):
            errors.append(f"{where} extract_ref")
    next_prompt = ledger.get("next_prompt")
    if next_prompt not in ALLOWED_NEXT_PROMPTS:
        errors.append("next_prompt must not relaunch 09.5.4")
    if OWNER_PROMPT in str(next_prompt):
        errors.append("next_prompt relaunches owner prompt")
    if "09.5.4_AUDITAR_EVIDENCIA_LOTE.md" in str(next_prompt):
        errors.append("next_prompt relaunches 09.5.4")
    if seen != assigned:
        missing = assigned - seen
        extra = seen - assigned
        if missing:
            errors.append(f"uncovered {len(missing)}")
        if extra:
            errors.append(f"extra {len(extra)}")
    if ledger.get("missing") not in (0, []):
        errors.append("missing must stay 0")
    if ledger.get("overlaps") not in (0, []):
        errors.append("overlaps must stay 0")
    card_ids: set[str] = set()
    covered_by_cards: set[str] = set()
    for index, card in enumerate(ledger.get("cards") or []):
        where = f"cards[{index}]"
        errors.extend(_require(card, CARD_REQUIRED, where))
        card_id = card.get("card_id")
        if not card_id or card_id in card_ids:
            errors.append(f"{where} card_id")
        card_ids.add(card_id)
        if card.get("card_kind") not in CARD_KINDS:
            errors.append(f"{where} card_kind")
        if card.get("outcome") not in OUTCOMES:
            errors.append(f"{where} outcome")
        if card.get("provisional") is not True:
            errors.append(f"{where} must stay provisional until 09.5.9")
        if card.get("works") is True:
            errors.append(f"{where} works must not follow from existence")
        ranking = card.get("ranking_claim")
        comparison = card.get("equivalent_comparison")
        blob = _blob(card)
        if ranking is True and not comparison:
            errors.append(f"{where} ranking without equivalent comparison")
        if any(needle in blob for needle in RANKING_NEEDLES) and not comparison:
            errors.append(f"{where} ranking phrase without equivalent comparison")
        for field in (
            "corpus",
            "denominator",
            "version",
            "hardware",
            "limitations",
            "identity",
            "consumers",
            "measurement",
        ):
            if not card.get(field):
                errors.append(f"{where} empty {field}")
        prov = card.get("provenance") or {}
        errors.extend(_require(prov, PROVENANCE_REQUIRED, f"{where}.provenance"))
        sources = card.get("source_files") or []
        if not sources:
            errors.append(f"{where} source_files")
        for path in sources:
            covered_by_cards.add(path)
    assigned_paths = {item["path"] for item in batch["files"]}
    if terminals_ok:
        need_card = {
            row["path"]
            for row in ledger.get("files") or []
            if row.get("terminal")
            in {"parseado_completo", "binario_inventariado"}
        }
        orphan = need_card - covered_by_cards
        if orphan:
            errors.append(f"covered file without card {sorted(orphan)[:8]}")
        unknown = covered_by_cards - assigned_paths
        if unknown:
            errors.append(f"card sources outside batch {sorted(unknown)[:8]}")
    raw = _blob(ledger)
    if "c:\\users\\" in raw or "d:\\perfil\\" in raw:
        errors.append("personal path leaked into ledger")
    return errors


def mark_queue_complete(
    repo: Path, batch_id: str, next_evidence_assets_batch_id: str | None
) -> None:
    _batches_path, ledger_path, _summary_path = queue_paths(repo)
    queue_ledger = load_json(ledger_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = False
    for item in queue_ledger["batches"]:
        if item["batch_id"] == batch_id:
            item["status"] = "complete"
            item["closed_utc"] = now
            found = True
    if not found:
        raise RuntimeError(batch_id)
    queue_ledger["first_evidence_assets_batch_id"] = next_evidence_assets_batch_id
    dump_json(ledger_path, queue_ledger)
    claim_path = repo / "artifacts" / "goal095" / "claims" / f"{batch_id}.json"
    if claim_path.is_file():
        claim_record = load_json(claim_path)
        claim_record["status"] = "complete"
        claim_record["closed_utc"] = now
        dump_json(claim_path, claim_record)
    write_campaign(repo, queue_ledger, next_evidence_assets_batch_id)


def next_pending_evidence(
    queue_ledger: dict[str, Any], current_id: str
) -> dict[str, Any] | None:
    for item in queue_ledger["batches"]:
        if item.get("kind") != KIND:
            continue
        if item["batch_id"] == current_id:
            continue
        if item.get("status") == "pending":
            return item
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("action", choices=("claim", "validate", "expire"))
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--source-head", default=None)
    parser.add_argument("--ledger", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    if args.action == "expire":
        expired = expire_stale_claims(repo)
        print(json.dumps({"expired": expired}, indent=2), flush=True)
        return 0
    if args.action == "claim":
        record = claim(
            repo,
            batch_id=args.batch_id,
            source_root=args.source_root,
            source_head=args.source_head,
        )
        print(json.dumps(record, indent=2, sort_keys=True), flush=True)
        return 0
    batches_path, _ledger_path, _summary = queue_paths(repo)
    batches = load_json(batches_path)
    ledger_path = args.ledger
    if ledger_path is None:
        raise SystemExit("--ledger required")
    ledger = load_json(ledger_path)
    batch = batch_from_batches(batches, ledger["batch_id"])
    errors = validate_ledger(ledger, batch)
    if errors:
        print("\n".join(errors), flush=True)
        return 1
    print("ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
