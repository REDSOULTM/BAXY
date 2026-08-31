"""Claim, schema and validation for Goal 09.5.3 code_tests ledgers.

Does not read source bodies. Workers write condensed component cards; this
module checks budget, exact batch membership, terminals and dispositions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
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

SCHEMA = "baxy.goal095.code-ledger.v1"
KIND = "code_tests"
TERMINALS = frozenset(
    {
        "leido",
        "parseado_completo",
        "duplicado_por_hash",
        "binario_inventariado",
        "excluido_razonado",
    }
)
DISPOSITIONS = frozenset(
    {
        "reuse_exact",
        "adapt_candidate",
        "evidence_only",
        "reject_candidate",
    }
)
QUEUE_STATUSES = frozenset({"pending", "claimed", "complete"})

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
    "next_code_tests_batch_id",
    "next_prompt",
)
FILE_REQUIRED = ("path", "sha256", "source_id", "terminal", "ranges")
CARD_REQUIRED = (
    "card_id",
    "disposition",
    "component",
    "contract",
    "dependencies",
    "historical_test",
    "limitations",
    "current_owner",
    "source_files",
    "failure_mechanism",
    "readme_vs_real",
    "invariant_risk",
    "duplicate_layers",
    "provisional",
)
PROVENANCE_REQUIRED = ("path", "ranges", "date", "hardware", "model", "commit")


def first_pending_code_tests(queue_ledger: dict[str, Any]) -> dict[str, Any] | None:
    for item in queue_ledger["batches"]:
        if item.get("kind") == KIND and item.get("status") == "pending":
            return item
    return None


def claim(
    repo: Path,
    batch_id: str | None = None,
    source_root: Path | None = None,
    source_head: str | None = None,
) -> dict[str, Any]:
    batches_path, ledger_path, _summary_path = queue_paths(repo)
    batches = load_json(batches_path)
    queue_ledger = load_json(ledger_path)
    pending = first_pending_code_tests(queue_ledger)
    if pending is None:
        raise RuntimeError("no pending code_tests batch")
    if batch_id is None:
        batch_id = pending["batch_id"]
    if pending["batch_id"] != batch_id:
        raise RuntimeError(
            f"first pending code_tests is {pending['batch_id']}, not {batch_id}"
        )
    claimed = [
        item for item in queue_ledger["batches"] if item.get("status") == "claimed"
    ]
    if claimed:
        ids = [item["batch_id"] for item in claimed]
        if ids != [batch_id]:
            raise RuntimeError(f"another batch already claimed: {ids}")
    batch = batch_from_batches(batches, batch_id)
    if batch["estimated_tokens"] > TOKEN_LIMIT:
        raise RuntimeError("batch exceeds token limit")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for item in queue_ledger["batches"]:
        if item["batch_id"] == batch_id:
            item["status"] = "claimed"
            item["claimed_utc"] = now
    dump_json(ledger_path, queue_ledger)
    claim_record = {
        "schema": SCHEMA,
        "batch_id": batch_id,
        "kind": KIND,
        "status": "claimed",
        "claimed_utc": now,
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
    dump_json(
        repo / "artifacts" / "goal095" / "claims" / f"{batch_id}.json",
        claim_record,
    )
    return claim_record


def _require(obj: dict[str, Any], keys: tuple[str, ...], where: str) -> list[str]:
    errors = []
    for key in keys:
        if key not in obj:
            errors.append(f"{where} missing {key}")
    return errors


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
        if terminal not in TERMINALS:
            errors.append(f"{where} terminal")
            terminals_ok = False
        ranges = row.get("ranges")
        if not isinstance(ranges, list) or not ranges:
            errors.append(f"{where} ranges")
        if terminal == "duplicado_por_hash" and not row.get("duplicate_of"):
            errors.append(f"{where} duplicate_of")
        if terminal == "excluido_razonado" and not row.get("exclusion_rule"):
            errors.append(f"{where} exclusion_rule")
        if terminal == "binario_inventariado" and not row.get("binary_format"):
            errors.append(f"{where} binary_format")
        if terminal in {"leido", "parseado_completo"} and not row.get("ranges"):
            errors.append(f"{where} {terminal} without ranges")
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
        if card.get("disposition") not in DISPOSITIONS:
            errors.append(f"{where} disposition")
        if card.get("provisional") is not True:
            errors.append(f"{where} must stay provisional until 09.5.9")
        for field in (
            "contract",
            "dependencies",
            "historical_test",
            "limitations",
            "current_owner",
            "failure_mechanism",
            "readme_vs_real",
            "invariant_risk",
            "duplicate_layers",
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
            in {"leido", "parseado_completo", "binario_inventariado"}
        }
        orphan = need_card - covered_by_cards
        if orphan:
            errors.append(f"covered file without card {sorted(orphan)[:8]}")
        unknown = covered_by_cards - assigned_paths
        if unknown:
            errors.append(f"card sources outside batch {sorted(unknown)[:8]}")
    return errors


def mark_queue_complete(
    repo: Path, batch_id: str, next_code_tests_batch_id: str | None
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
    queue_ledger["first_code_tests_batch_id"] = next_code_tests_batch_id
    dump_json(ledger_path, queue_ledger)


def next_pending_code_tests(
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
    parser.add_argument("action", choices=("claim", "validate"))
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--source-head", default=None)
    parser.add_argument("--ledger", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
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
