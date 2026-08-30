"""Claim, schema and validation for Goal 09.5.2 docs ledgers.

Does not read source bodies. Workers write condensed cards; this module
checks budget, exact batch membership, terminals and card fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.docs-ledger.v1"
KIND = "docs"
TOKEN_LIMIT = 350000
TOKEN_TARGET = 300000
TERMINALS = frozenset({"leido", "duplicado_por_hash", "excluido_razonado"})
CLAIM_KINDS = frozenset({"documental", "reproducido"})
OUTCOMES = frozenset({"exito", "fracaso", "inconcluso", "contexto"})
VALIDITIES = frozenset(
    {
        "historica",
        "mecanismo_reutilizable",
        "caducada",
        "requiere_remeidir",
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
    "next_docs_batch_id",
    "next_prompt",
)
FILE_REQUIRED = ("path", "sha256", "source_id", "terminal", "ranges")
CARD_REQUIRED = (
    "card_id",
    "claim_kind",
    "problem",
    "outcome",
    "solution_or_failure",
    "causal_mechanism",
    "measurement",
    "provenance",
    "limitations",
    "validity",
    "current_piece",
    "source_files",
    "repeats",
)
PROVENANCE_REQUIRED = ("path", "ranges", "date", "hardware", "model", "commit")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def queue_paths(repo: Path) -> tuple[Path, Path, Path]:
    queue = repo / "artifacts" / "goal095" / "queue"
    return queue / "batches.json", queue / "ledger.json", queue / "summary.json"


def first_pending_docs(queue_ledger: dict[str, Any]) -> dict[str, Any] | None:
    for item in queue_ledger["batches"]:
        if item.get("kind") == KIND and item.get("status") == "pending":
            return item
    return None


def batch_from_batches(batches: list[dict[str, Any]], batch_id: str) -> dict[str, Any]:
    matches = [item for item in batches if item.get("batch_id") == batch_id]
    if len(matches) != 1:
        raise ValueError(f"expected one {batch_id}, got {len(matches)}")
    return matches[0]


def claim(
    repo: Path,
    batch_id: str | None = None,
    source_root: Path | None = None,
    source_head: str | None = None,
) -> dict[str, Any]:
    batches_path, ledger_path, _summary_path = queue_paths(repo)
    batches = load_json(batches_path)
    queue_ledger = load_json(ledger_path)
    pending = first_pending_docs(queue_ledger)
    if pending is None:
        raise RuntimeError("no pending docs batch")
    if batch_id is None:
        batch_id = pending["batch_id"]
    if pending["batch_id"] != batch_id:
        raise RuntimeError(
            f"first pending docs is {pending['batch_id']}, not {batch_id}"
        )
    claimed = [item for item in queue_ledger["batches"] if item.get("status") == "claimed"]
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
    dump_json(repo / "artifacts" / "goal095" / "claims" / f"{batch_id}.json", claim_record)
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
    assigned = {(item["path"], item["sha256"], item["source_id"]) for item in batch["files"]}
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
        if terminal == "leido" and not row.get("ranges"):
            errors.append(f"{where} leido without ranges")
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
        if card.get("claim_kind") not in CLAIM_KINDS:
            errors.append(f"{where} claim_kind")
        if card.get("outcome") not in OUTCOMES:
            errors.append(f"{where} outcome")
        if card.get("validity") not in VALIDITIES:
            errors.append(f"{where} validity")
        if card.get("claim_kind") == "reproducido" and card.get("validity") == "historica":
            errors.append(f"{where} reproduced marked only historical")
        if card.get("validity") != "historica" and card.get("claim_kind") != "reproducido":
            if card.get("validity") in {"mecanismo_reutilizable"}:
                pass
            elif card.get("claim_kind") == "documental" and card.get("validity") not in {
                "historica",
                "caducada",
                "requiere_remeidir",
                "mecanismo_reutilizable",
            }:
                errors.append(f"{where} documental presented as current")
        prov = card.get("provenance") or {}
        errors.extend(_require(prov, PROVENANCE_REQUIRED, f"{where}.provenance"))
        sources = card.get("source_files") or []
        if not sources:
            errors.append(f"{where} source_files")
        for path in sources:
            covered_by_cards.add(path)
        if not card.get("problem") or not card.get("causal_mechanism"):
            errors.append(f"{where} empty core fields")
        measurement = card.get("measurement")
        if measurement in (None, "", []):
            errors.append(f"{where} measurement")
    assigned_paths = {item["path"] for item in batch["files"]}
    if terminals_ok:
        read_paths = {
            row["path"]
            for row in ledger.get("files") or []
            if row.get("terminal") == "leido"
        }
        orphan = read_paths - covered_by_cards
        if orphan:
            errors.append(f"leido without card {sorted(orphan)[:8]}")
        unknown = covered_by_cards - assigned_paths
        if unknown:
            errors.append(f"card sources outside batch {sorted(unknown)[:8]}")
    return errors


def mark_queue_complete(repo: Path, batch_id: str, next_docs_batch_id: str | None) -> None:
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
    queue_ledger["first_docs_batch_id"] = next_docs_batch_id
    dump_json(ledger_path, queue_ledger)


def next_pending_docs(queue_ledger: dict[str, Any], current_id: str) -> dict[str, Any] | None:
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
