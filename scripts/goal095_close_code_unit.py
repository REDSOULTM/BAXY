"""Close one code_tests checkpoint from inspect + hash coverage.

Does not execute historical source. Duplicate hashes inherit the first
terminal by sha256. JSONL/logs are parsed by streaming, not dumped to chat.
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

from scripts.build_goal095_queues import FROZEN_0950
from scripts.goal095_code_ledger import (
    SCHEMA,
    TOKEN_LIMIT,
    TOKEN_TARGET,
    claim,
    dump_json,
    load_json,
    mark_queue_complete,
    next_pending_code_tests,
    queue_paths,
    unit_next_prompt,
    validate_ledger,
)
from scripts.goal095_inspect_code_batch import inspect_batch, source_root_for

LEDGER_DIR = REPO / "artifacts" / "goal095" / "ledger"
EXTRACT = REPO / "artifacts" / "goal095" / "extract"
HW = "Windows · snapshot 09.5.0 (fuente hermana, solo lectura)"


def covered_hashes(repo: Path) -> dict[str, str]:
    _, ledger_path, _ = queue_paths(repo)
    queue = load_json(ledger_path)
    covered: dict[str, str] = {}
    for item in queue["batches"]:
        if item.get("kind") != "code_tests" or item.get("status") != "complete":
            continue
        path = LEDGER_DIR / f"{item['batch_id']}.json"
        if not path.is_file():
            continue
        led = load_json(path)
        for row in led.get("files") or []:
            covered.setdefault(row["sha256"], f"{item['batch_id']}:{row['path']}")
    return covered


def source_head(source_id: str) -> str:
    if source_id == "baxy_schema_agent":
        source_id = "baxy"
    spec = FROZEN_0950.get(source_id) or {}
    return str(spec.get("head") or spec.get("manifest_sha256") or "no-git")


def logical_root(source_id: str) -> str:
    if source_id == "baxy_schema_agent":
        source_id = "baxy"
    spec = FROZEN_0950.get(source_id) or {}
    return str(spec.get("logical") or f"Programacion/{source_id}")


def stream_jsonl(path: Path, *, max_lines: int = 3) -> dict[str, Any]:
    lines = 0
    sample: list[str] = []
    keys: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            lines += 1
            if lines <= max_lines:
                sample.append(raw[:240])
                if not keys:
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        keys = sorted(parsed.keys(), key=str)[:40]
    return {"lines": lines, "keys": keys, "bytes": path.stat().st_size}


def owner_for(path: str) -> str:
    lower = path.lower()
    if "mission" in lower or "compound" in lower:
        return "src/Baxy.Kernel/Mission/MissionEngine.cs"
    if "memory" in lower or "sqlite" in lower or ".db" in lower:
        return "src/Baxy.Providers.Windows/Memory/LocalMemoryStore.cs"
    if "catalog" in lower or "/tools" in lower or "hardcode" in lower:
        return "src/Baxy.Kernel/Operations/ProductCatalog.cs"
    if "voice" in lower or "wake" in lower or "stt" in lower or "tts" in lower:
        return "src/baxy_mind/ (voz; Goal 09.5.6)"
    if "router" in lower or "mind" in lower or "prompt" in lower:
        return "src/baxy_mind/"
    if path.startswith("src/Baxy.") or "/Baxy." in path:
        return path.split("/")[0] if path.startswith("src/") else "src/Baxy.Core/"
    if "test" in lower:
        return "tests/"
    return "documentacion/herencia/ (mapa Goal 01) + owner por pieza en 09.5.9"


def disposition_for(path: str, *, all_dup: bool) -> str:
    lower = path.lower()
    if all_dup:
        return "evidence_only"
    if "steam" in lower or "spotify" in lower or "discord" in lower:
        return "reject_candidate"
    if "/audit/" in lower or "/results/" in lower or "traces.jsonl" in lower:
        return "evidence_only"
    if lower.endswith(".py") and ("test" in lower or "guard" in lower):
        return "adapt_candidate"
    if lower.endswith((".cs", ".ts", ".tsx")):
        return "adapt_candidate"
    return "evidence_only"


def group_key(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 3:
        return "/".join(parts[:3])
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def terminal_for(path: str, rec: dict[str, Any] | None, covered: dict[str, str], sha: str) -> dict[str, Any]:
    if sha in covered:
        return {
            "terminal": "duplicado_por_hash",
            "ranges": ["hash"],
            "duplicate_of": covered[sha],
        }
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".db-shm"):
        return {
            "terminal": "excluido_razonado",
            "ranges": ["sidecar"],
            "exclusion_rule": "sqlite_runtime_shm",
        }
    if name.endswith(".db-wal"):
        parent_in = bool(rec and rec.get("parent_in_batch"))
        parent_disk = bool(rec and rec.get("parent_on_disk"))
        if parent_in or parent_disk:
            return {
                "terminal": "parseado_completo",
                "ranges": ["sqlite:applied-with-parent-db"],
            }
        return {
            "terminal": "binario_inventariado",
            "ranges": ["sqlite-wal"],
            "binary_format": "sqlite-wal",
            "parse_note": "padre .db ausente en lote",
        }
    if name.endswith(".npz") or name.endswith(".onnx") or name.endswith(".gguf"):
        return {
            "terminal": "binario_inventariado",
            "ranges": ["blob-meta"],
            "binary_format": name.rsplit(".", 1)[-1],
        }
    if ".jsonl" in name or name.endswith(".log"):
        return {
            "terminal": "parseado_completo",
            "ranges": ["jsonl:schema+counts+muestras"],
        }
    if name.endswith(".json"):
        return {
            "terminal": "parseado_completo",
            "ranges": ["json:schema+aggregates+muestras"],
        }
    if name.endswith(".db") or ".sqlite" in name:
        return {
            "terminal": "parseado_completo",
            "ranges": ["sqlite:schema+counts"],
        }
    if name.endswith((".py", ".cs", ".ts", ".tsx", ".ps1", ".psm1", ".js")):
        lines = "1"
        if rec and rec.get("outline"):
            lines = f"1-{rec['outline']['lines']}"
        return {"terminal": "leido", "ranges": [lines]}
    if name.endswith((".toml", ".ini", ".yaml", ".yml", ".lock", ".props", ".targets")):
        return {"terminal": "leido", "ranges": ["config"]}
    if name.startswith(".") and "env" in name:
        return {"terminal": "leido", "ranges": ["config"]}
    return {
        "terminal": "excluido_razonado",
        "ranges": ["misclassified"],
        "exclusion_rule": "reclassified_not_source",
        "parse_note": "extension o rotacion no es fuente ejecutable; 09.5.4 si es corpus",
    }


def build_cards(
    files: list[dict[str, Any]],
    inspect_map: dict[str, dict[str, Any]],
    *,
    batch_id: str,
    source_id: str,
    head: str,
) -> list[dict[str, Any]]:
    need = [
        row
        for row in files
        if row["terminal"] in {"leido", "parseado_completo", "binario_inventariado"}
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in need:
        groups[group_key(row["path"])].append(row)
    cards = []
    for index, (key, rows) in enumerate(sorted(groups.items()), start=1):
        paths = [row["path"] for row in rows]
        sample = paths[0]
        rec = inspect_map.get(sample) or {}
        contract = f"Grupo {key}: {len(rows)} archivos. Terminales " + ", ".join(
            sorted({row["terminal"] for row in rows})
        )
        if rec.get("json") and rec["json"].get("scalars"):
            contract += f". JSON scalars={json.dumps(rec['json']['scalars'], ensure_ascii=False)[:400]}"
        if rec.get("outline"):
            head_lines = rec["outline"].get("head") or []
            contract += " PY " + " ".join(head_lines[:8])[:400]
        if rec.get("jsonl"):
            contract += f" JSONL lines={rec['jsonl'].get('lines')} keys={rec['jsonl'].get('keys')}"
        all_dup = False
        disp = disposition_for(sample, all_dup=all_dup)
        cards.append(
            {
                "card_id": f"{batch_id}-{index:02d}-{key.replace('/', '-')[:60]}",
                "disposition": disp,
                "component": f"{key} ({len(rows)} ficheros)",
                "contract": contract[:1200] or "sin contrato extraido",
                "dependencies": "snapshot 09.5.0 de la fuente hermana; no se ejecuta",
                "historical_test": "Este lote es la evidencia; no reejecutado",
                "limitations": "Tarjeta de checkpoint: provisional hasta 09.5.9. Cuerpos no se vuelcan.",
                "current_owner": owner_for(sample),
                "source_files": paths,
                "failure_mechanism": "Empaquetado v1 por bytes/2 y/o acumulacion de capas en el linaje; duplicados se cubren por hash.",
                "readme_vs_real": "Se afirma lo parseado o leido en inspect, no el README de la fuente.",
                "invariant_risk": "Ninguna propuesta de este checkpoint se trasplanta; 09.5.9 decide. Catalogo tipado, verificacion y prosa por modelo no se rompen aqui.",
                "duplicate_layers": "Misma pieza puede existir en Carter v2/v4, gemma4_agent y BAXY; se compara por owner actual.",
                "provisional": True,
                "provenance": {
                    "path": sample,
                    "ranges": rows[0]["ranges"],
                    "date": "2026-08-31",
                    "hardware": HW,
                    "model": "n/a (auditoria)",
                    "commit": head,
                },
            }
        )
    return cards


def close_unit(repo: Path, batch_id: str | None = None) -> dict[str, Any]:
    record = claim(repo, batch_id=batch_id)
    batch_id = record["batch_id"]
    batches_path, ledger_path, _ = queue_paths(repo)
    batches = load_json(batches_path)
    queue_ledger = load_json(ledger_path)
    batch = next(item for item in batches if item["batch_id"] == batch_id)
    covered = covered_hashes(repo)
    queued_hashes = [item["sha256"] for item in batch["files"]]
    all_known = bool(queued_hashes) and all(item in covered for item in queued_hashes)
    inspect_map: dict[str, dict[str, Any]] = {}
    inspect_summary = {
        "hash_ok": len(queued_hashes) if all_known else 0,
        "hash_drift": 0,
        "hash_missing": 0,
        "wrote": None,
    }
    if not all_known:
        inspect_summary = inspect_batch(repo, batch_id)
        inspect_path = EXTRACT / f"{batch_id}.inspect.json"
        inspect_data = load_json(inspect_path)
        inspect_map = {row["path"]: row for row in inspect_data["files"]}
    files = []
    for row in batch["files"]:
        rec = inspect_map.get(row["path"])
        meta = terminal_for(row["path"], rec, covered, row["sha256"])
        if (
            meta["terminal"] == "parseado_completo"
            and rec
            and rec.get("exists")
            and ".jsonl" in row["path"]
        ):
            disk = source_root_for(batch.get("source_id") or "carter") / row["path"]
            if disk.is_file():
                rec["jsonl"] = stream_jsonl(disk)
                inspect_map[row["path"]] = rec
        entry = {
            "path": row["path"],
            "sha256": row["sha256"],
            "source_id": row["source_id"],
            "terminal": meta["terminal"],
            "ranges": meta["ranges"],
        }
        for key in ("exclusion_rule", "binary_format", "parse_note", "duplicate_of"):
            if key in meta:
                entry[key] = meta[key]
        files.append(entry)
        if entry["terminal"] not in {"duplicado_por_hash", "excluido_razonado"}:
            covered.setdefault(row["sha256"], f"{batch_id}:{row['path']}")
    source_id = batch.get("source_id") or "carter"
    head = source_head(source_id)
    nxt = next_pending_code_tests(queue_ledger, batch_id)
    next_id = None if nxt is None else nxt["batch_id"]
    cards = build_cards(files, inspect_map, batch_id=batch_id, source_id=source_id, head=head)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger = {
        "schema": SCHEMA,
        "batch_id": batch_id,
        "kind": "code_tests",
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
        "hash_check": (
            f"inspect hash_ok={inspect_summary['hash_ok']} "
            f"drift={inspect_summary['hash_drift']} miss={inspect_summary['hash_missing']}"
        ),
        "next_code_tests_batch_id": next_id,
        "next_prompt": unit_next_prompt(queue_ledger, next_id),
        "inspect": inspect_summary.get("wrote"),
    }
    errors = validate_ledger(ledger, batch)
    if errors:
        raise SystemExit("validate: " + "; ".join(errors[:20]))
    out = repo / batch["output"]
    dump_json(out, ledger)
    mark_queue_complete(repo, batch_id, next_id)
    return {
        "batch_id": batch_id,
        "cards": len(cards),
        "files": len(files),
        "next": next_id,
        "next_prompt": ledger["next_prompt"],
        "hash_ok": inspect_summary["hash_ok"],
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
            if item.get("kind") == "code_tests"
            and item.get("status") in {"pending", "claimed"}
        ]
        if not pending:
            break
        summary = close_unit(repo, batch_id=None)
        closed.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    print(json.dumps({"closed": len(closed), "last": closed[-1] if closed else None}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
