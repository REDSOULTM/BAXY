"""Close one evidence_assets checkpoint: parse/inventory, terminals, cards.

Does not retrain or re-run expensive campaigns. Duplicate hashes inherit
the first terminal. Structured files are parsed by streaming tools.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_goal095_queues import (
    FROZEN_0950,
    PROGRAMACION,
    SCHEMA_AGENT_REFS,
    hash_git_blob,
)
from scripts.goal095_docs_ledger import dump_json, load_json, queue_paths
from scripts.goal095_evidence_ledger import (
    SCHEMA,
    TOKEN_LIMIT,
    TOKEN_TARGET,
    claim,
    mark_queue_complete,
    next_pending_evidence,
    unit_next_prompt,
    validate_ledger,
)
from scripts.goal095_evidence_parse import (
    owner_for,
    process_file,
    strip_personal,
)

LEDGER_DIR = REPO / "artifacts" / "goal095" / "ledger"
EXTRACT = REPO / "artifacts" / "goal095" / "extract"
HASH_INDEX = EXTRACT / "_evidence_hash_index.json"
HW = "Windows · snapshot 09.5.0 (fuente hermana, solo lectura)"
SCHEMA_KEEP = (
    REPO / "artifacts" / "goal095" / "sources" / "baxy_schema_agent.keep.sha256.jsonl"
)


def _clip(value: str, limit: int) -> str:
    value = " ".join(str(value).split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def source_head(source_id: str) -> str:
    if source_id == "baxy_schema_agent":
        return SCHEMA_AGENT_REFS.get(
            "origin/Tools-Reduce", "schema-agent-git-blob"
        )
    spec = FROZEN_0950.get(source_id) or {}
    return str(spec.get("head") or spec.get("manifest_sha256") or "no-git")


def logical_root(source_id: str) -> str:
    if source_id == "baxy_schema_agent":
        return "Programacion/BAXY (Schema Agent git blobs)"
    spec = FROZEN_0950.get(source_id) or {}
    return str(spec.get("logical") or f"Programacion/{source_id}")


def _schema_keep_map() -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    if not SCHEMA_KEEP.is_file():
        return mapping
    for line in SCHEMA_KEEP.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        mapping[row["path"]] = row
    return mapping


def resolve_disk(repo: Path, source_id: str, rel: str) -> Path | None:
    posix = rel.replace("\\", "/")
    if source_id == "baxy_schema_agent":
        keep = _schema_keep_map().get(posix)
        if keep is None:
            return None
        dest_dir = EXTRACT / "_schema_agent_blobs"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / posix.replace("/", "__")
        if dest.is_file() and dest.stat().st_size == int(keep.get("size") or dest.stat().st_size):
            return dest
        baxy = PROGRAMACION / "BAXY"
        data, digest = hash_git_blob(baxy, keep["git_blob"])
        if digest != keep.get("sha256"):
            dest.write_bytes(data)
        else:
            dest.write_bytes(data)
        return dest
    spec = FROZEN_0950.get(source_id)
    if spec is None:
        return None
    path = PROGRAMACION / spec["folder"] / posix
    return path if path.is_file() else None


def load_hash_index(repo: Path) -> dict[str, str]:
    if HASH_INDEX.is_file():
        return load_json(HASH_INDEX)
    covered: dict[str, str] = {}
    _, ledger_path, _ = queue_paths(repo)
    queue = load_json(ledger_path)
    for item in queue["batches"]:
        if item.get("status") != "complete":
            continue
        path = LEDGER_DIR / f"{item['batch_id']}.json"
        if not path.is_file():
            continue
        led = load_json(path)
        for row in led.get("files") or []:
            sha = row.get("sha256")
            if sha:
                covered.setdefault(sha, f"{item['batch_id']}:{row['path']}")
    HASH_INDEX.parent.mkdir(parents=True, exist_ok=True)
    dump_json(HASH_INDEX, covered)
    return covered


def save_hash_index(covered: dict[str, str]) -> None:
    dump_json(HASH_INDEX, covered)


def group_key(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 3:
        return "/".join(parts[:3])
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _card_kind(paths: list[str], extracts: list[dict[str, Any]]) -> str:
    blob = " ".join(paths).lower()
    if "false_positive" in blob or "negativ" in blob:
        return "negative"
    if "contamin" in blob or ("train" in blob and "eval" in blob):
        return "contamination"
    if any((item or {}).get("parser") == "binary_inventory" for item in extracts):
        return "asset"
    dist = {}
    for item in extracts:
        dist.update((item or {}).get("distribution") or {})
    if any(key in dist for key in ("status", "fail_like", "error_rows")):
        return "metric"
    if any((item or {}).get("parser") in {"jsonl", "json", "sqlite"} for item in extracts):
        return "run"
    return "corpus"


def _outcome(kind: str, extracts: list[dict[str, Any]]) -> str:
    if kind == "negative":
        return "negativo"
    blob = json.dumps([item.get("distribution") for item in extracts], ensure_ascii=False).lower()
    if "fail" in blob or "error" in blob:
        return "fracaso"
    return "contexto"


def _measurement(extracts: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for extract, row in zip(extracts, rows):
        parser = (extract or {}).get("parser")
        n = (extract or {}).get("rows")
        nbytes = (extract or {}).get("bytes")
        dist = (extract or {}).get("distribution") or {}
        parts.append(
            f"{row['path'].rsplit('/', 1)[-1]} parser={parser} rows={n} bytes={nbytes} dist={_clip(json.dumps(dist, ensure_ascii=False), 180)}"
        )
        if len(parts) >= 6:
            break
    if not parts:
        return "No extract; denominator unpublished — do not treat as a rate."
    return _clip(" | ".join(parts), 800)


def build_cards(
    files: list[dict[str, Any]],
    extracts: dict[str, dict[str, Any]],
    *,
    batch_id: str,
    head: str,
    source_id: str,
) -> list[dict[str, Any]]:
    need = [
        row
        for row in files
        if row["terminal"] in {"parseado_completo", "binario_inventariado"}
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in need:
        groups[group_key(row["path"])].append(row)
    cards = []
    for index, (key, rows) in enumerate(sorted(groups.items()), start=1):
        paths = [row["path"] for row in rows]
        sample = paths[0]
        recs = [extracts.get(path) or {} for path in paths]
        kind = _card_kind(paths, recs)
        identity = f"{source_id}:{key}"
        consumers = (
            recs[0].get("consumers")
            if recs and recs[0].get("consumers")
            else "historical artifact; consumers pending 09.5.9"
        )
        bench = recs[0].get("associated_benchmark") if recs else "none recovered in this campaign"
        cards.append(
            strip_personal(
                {
                    "card_id": f"{batch_id}-{index:02d}-{key.replace('/', '-')[:60]}",
                    "card_kind": kind,
                    "corpus": key,
                    "denominator": (
                        f"{len(rows)} files in group {key}; per-file rows/bytes in measurement. "
                        "Do not promote a ratio without this denominator."
                    ),
                    "version": f"snapshot 09.5.0 {source_id} head={head[:12]}",
                    "hardware": HW,
                    "limitations": (
                        "Recovered metadata/results; not a contemporary rerun. "
                        "Train/eval contamination, false positives and failed runs stay as records. "
                        "Existence is not works. Provisional until 09.5.9."
                    ),
                    "identity": identity,
                    "consumers": consumers,
                    "associated_benchmark": bench or "none recovered in this campaign",
                    "source_files": paths,
                    "provisional": True,
                    "ranking_claim": False,
                    "equivalent_comparison": "",
                    "measurement": _measurement(recs, rows),
                    "outcome": _outcome(kind, recs),
                    "works": False,
                    "current_owner": owner_for(sample),
                    "provenance": {
                        "path": sample,
                        "ranges": rows[0]["ranges"],
                        "date": "2026-08-31",
                        "hardware": HW,
                        "model": "n/a (auditoria evidencia)",
                        "commit": head,
                    },
                }
            )
        )
    return cards


def close_unit(repo: Path, batch_id: str | None = None) -> dict[str, Any]:
    record = claim(repo, batch_id=batch_id)
    batch_id = record["batch_id"]
    batches_path, ledger_path, _ = queue_paths(repo)
    batches = load_json(batches_path)
    queue_ledger = load_json(ledger_path)
    batch = next(item for item in batches if item["batch_id"] == batch_id)
    covered = load_hash_index(repo)
    source_id = batch.get("source_id") or "carter"
    extract_map: dict[str, dict[str, Any]] = {}
    compact_extracts: dict[str, Any] = {}
    files: list[dict[str, Any]] = []
    hash_ok = hash_drift = hash_miss = 0
    extract_rel = f"artifacts/goal095/extract/{batch_id}.parse.json"
    for row in batch["files"]:
        rel = row["path"]
        sha = row["sha256"]
        if sha in covered:
            files.append(
                {
                    "path": rel,
                    "sha256": sha,
                    "source_id": row["source_id"],
                    "terminal": "duplicado_por_hash",
                    "ranges": ["hash"],
                    "duplicate_of": covered[sha],
                }
            )
            continue
        disk = resolve_disk(repo, source_id, rel)
        if disk is None or not disk.is_file():
            raise SystemExit(
                f"FALLO_DE_AMBIENTE missing {source_id}:{rel} batch={batch_id}"
            )
        try:
            result = process_file(disk, source_id=source_id, rel=rel)
        except Exception as exc:  # noqa: BLE001 — one corrupt blob must not abort the campaign
            from scripts.goal095_evidence_parse import classify_action, sha256_and_size

            digest, size = sha256_and_size(disk)
            decision = classify_action(rel)
            extract = strip_personal(
                {
                    "parser": "failed",
                    "bytes": size,
                    "sha256": digest,
                    "rows": 0,
                    "schema": {},
                    "distribution": {},
                    "extremes": {
                        "first_offset": 0,
                        "last_offset": max(size - 1, 0),
                    },
                    "errors": [
                        {
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    ],
                    "samples": {
                        "head": [],
                        "tail": [
                            {
                                "offset": max(size - 1, 0),
                                "line": 0,
                                "text": "eof",
                            }
                        ],
                    },
                }
            )
            if decision.get("action") == "inventory":
                result = {
                    "terminal": "binario_inventariado",
                    "ranges": ["blob-meta"],
                    "binary_format": Path(rel).suffix.lstrip(".") or "unknown",
                    "extract": extract,
                }
            else:
                result = {
                    "terminal": "parseado_completo",
                    "ranges": ["parse-error"],
                    "extract": extract,
                }
        extract = result.get("extract") or {}
        disk_sha = extract.get("sha256")
        if disk_sha and disk_sha == sha:
            hash_ok += 1
        elif disk_sha:
            hash_drift += 1
        else:
            hash_ok += 1
        extract_map[rel] = extract
        compact_extracts[rel] = strip_personal(extract)
        entry: dict[str, Any] = {
            "path": rel,
            "sha256": sha,
            "source_id": row["source_id"],
            "terminal": result["terminal"],
            "ranges": result["ranges"],
            "extract_ref": f"{extract_rel}#{rel}",
        }
        if result["terminal"] == "excluido_razonado":
            entry["exclusion_rule"] = result["exclusion_rule"]
            entry.pop("extract_ref", None)
        if result["terminal"] == "binario_inventariado":
            entry["binary_format"] = result.get("binary_format") or (
                extract.get("format") or "unknown"
            )
        if disk_sha and disk_sha != sha:
            entry["parse_note"] = f"disk_sha256={disk_sha} queued={sha}"
        files.append(entry)
        if result["terminal"] not in {"duplicado_por_hash", "excluido_razonado"}:
            covered.setdefault(sha, f"{batch_id}:{rel}")
        elif result["terminal"] == "excluido_razonado":
            covered.setdefault(sha, f"{batch_id}:{rel}")
    head = source_head(source_id)
    nxt = next_pending_evidence(queue_ledger, batch_id)
    next_id = None if nxt is None else nxt["batch_id"]
    cards = build_cards(
        files, extract_map, batch_id=batch_id, head=head, source_id=source_id
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parse_payload = {
        "batch_id": batch_id,
        "source_id": source_id,
        "file_count": len(files),
        "hash_ok": hash_ok,
        "hash_drift": hash_drift,
        "hash_missing": hash_miss,
        "files": compact_extracts,
    }
    dump_json(repo / extract_rel, parse_payload)
    ledger = {
        "schema": SCHEMA,
        "batch_id": batch_id,
        "kind": "evidence_assets",
        "status": "complete",
        "claimed_utc": record["claimed_utc"],
        "closed_utc": now,
        "estimated_tokens": batch["estimated_tokens"],
        "token_limit": TOKEN_LIMIT,
        "token_target": TOKEN_TARGET,
        "source_id": source_id,
        "source_head": head,
        "source_root": logical_root(source_id),
        "file_count": batch["file_count"],
        "subsystem": batch.get("subsystem"),
        "subsystems": batch.get("subsystems"),
        "files": files,
        "cards": cards,
        "missing": 0,
        "overlaps": 0,
        "hash_check": f"inspect hash_ok={hash_ok} drift={hash_drift} miss={hash_miss}",
        "next_evidence_assets_batch_id": next_id,
        "next_prompt": unit_next_prompt(queue_ledger, next_id),
        "inspect": extract_rel,
        "smoke": "skipped; results recovered; existence is not works",
    }
    ledger = strip_personal(ledger)
    errors = validate_ledger(ledger, batch)
    if errors:
        raise SystemExit("validate: " + "; ".join(errors[:20]))
    out = repo / batch["output"]
    dump_json(out, ledger)
    mark_queue_complete(repo, batch_id, next_id)
    save_hash_index(covered)
    return {
        "batch_id": batch_id,
        "cards": len(cards),
        "files": len(files),
        "next": next_id,
        "next_prompt": ledger["next_prompt"],
        "hash_ok": hash_ok,
        "hash_drift": hash_drift,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--max-units", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    closed = []
    for _ in range(max(1, args.max_units)):
        _, ledger_path, _ = queue_paths(repo)
        queue = load_json(ledger_path)
        pending = [
            item
            for item in queue["batches"]
            if item.get("kind") == "evidence_assets"
            and item.get("status") in {"pending", "claimed"}
        ]
        if not pending:
            break
        summary = close_unit(repo, batch_id=None)
        closed.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    print(
        json.dumps({"closed": len(closed), "last": closed[-1] if closed else None}),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
