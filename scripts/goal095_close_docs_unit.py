"""Close one docs checkpoint from inspect extracts and hash coverage.

Does not implement product code. Duplicate hashes inherit the first
terminal by sha256. Condensed cards cite path+ranges, not full bodies.
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
from scripts.goal095_docs_ledger import (
    SCHEMA,
    TOKEN_LIMIT,
    TOKEN_TARGET,
    claim,
    dump_json,
    load_json,
    mark_queue_complete,
    next_docs_in_order,
    queue_paths,
    unit_next_prompt,
    validate_ledger,
)
from scripts.goal095_inspect_docs_batch import inspect_batch

LEDGER_DIR = REPO / "artifacts" / "goal095" / "ledger"
EXTRACT = REPO / "artifacts" / "goal095" / "extract"
HW = "Windows · snapshot 09.5.0 (fuente hermana, solo lectura)"


def covered_hashes(repo: Path) -> dict[str, str]:
    _, ledger_path, _ = queue_paths(repo)
    queue = load_json(ledger_path)
    covered: dict[str, str] = {}
    for item in queue["batches"]:
        if item.get("kind") != "docs" or item.get("status") != "complete":
            continue
        path = LEDGER_DIR / f"{item['batch_id']}.json"
        if not path.is_file():
            continue
        led = load_json(path)
        for row in led.get("files") or []:
            covered.setdefault(row["sha256"], f"{item['batch_id']}:{row['path']}")
    return covered


def source_head(source_id: str) -> str:
    spec = FROZEN_0950.get(source_id) or {}
    return str(spec.get("head") or spec.get("manifest_sha256") or "no-git")


def logical_root(source_id: str) -> str:
    spec = FROZEN_0950.get(source_id) or {}
    return str(spec.get("logical") or f"Programacion/{source_id}")


def group_key(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return "/".join(parts[:-1])
    return parts[0]


def owner_for(path: str) -> str:
    lower = path.lower()
    if any(key in lower for key in ("wake", "stt", "tts", "voice", "audio", "piper")):
        return "src/baxy_mind/ (voz; Goal 09.5.6) + 09.5.9"
    if any(key in lower for key in ("router", "prompt", "mind", "llm", "gemma")):
        return "src/baxy_mind/ + Goal 09.5.5"
    if any(key in lower for key in ("catalog", "tool", "hardcode", "skill", "mission")):
        return "src/Baxy.Kernel/ + Goal 09.5.7"
    if any(key in lower for key in ("memory", "sqlite", "jarvis")):
        return "src/Baxy.Providers.Windows/Memory/ + Goal 09.5.8"
    if any(key in lower for key in ("ui", "field", "overlay", "presence")):
        return "src/Baxy.FieldUi/ + Goal 09.5.8"
    if any(key in lower for key in ("identidad", "tesis", "razon", "invarian")):
        return "documentacion/00_IDENTIDAD.md"
    return "documentacion/herencia/ (mapa Goal 01) + owner por pieza en 09.5.9"


def _outcome(extracts: list[dict[str, Any]]) -> str:
    blob = " ".join(
        (item.get("lead") or "")
        + " "
        + " ".join(head.get("text", "") for head in item.get("headings") or [])
        for item in extracts
    ).lower()
    fail = ("fail", "fracaso", "rejected", "blocker", "no sirve", "falso")
    success = ("pass", "exito", "green", "resolved", "listo")
    if any(word in blob for word in fail) and not any(
        word in blob for word in ("gate green",)
    ):
        return "fracaso"
    if any(word in blob for word in success) and "fail" not in blob:
        return "exito"
    if any(word in blob for word in ("inconclus", "pending", "TODO", "no medido")):
        return "inconcluso"
    return "contexto"


def _validity(path: str, extract: dict[str, Any]) -> str:
    blob = (
        (extract.get("lead") or "")
        + " "
        + " ".join(head.get("text", "") for head in extract.get("headings") or [])
        + " "
        + path
    ).lower()
    if any(
        key in blob
        for key in (
            "verific",
            "catalogo tipado",
            "confirmacion",
            "fake success",
            "prosa por modelo",
            "local y privado",
        )
    ):
        return "mecanismo_reutilizable"
    if any(key in blob for key in ("qwen3:4b", "ollama default", "hasta 2026-05-08")):
        return "caducada"
    if extract.get("measures"):
        return "requiere_remeidir"
    return "historica"


def _clip(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def build_cards(
    files: list[dict[str, Any]],
    inspect_map: dict[str, dict[str, Any]],
    *,
    batch_id: str,
    head: str,
) -> list[dict[str, Any]]:
    need = [row for row in files if row["terminal"] == "leido"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in need:
        groups[group_key(row["path"])].append(row)
    cards = []
    for index, (key, rows) in enumerate(sorted(groups.items()), start=1):
        paths = [row["path"] for row in rows]
        sample = paths[0]
        extracts = [
            (inspect_map.get(path) or {}).get("extract") or {} for path in paths
        ]
        primary = extracts[0] if extracts else {}
        headings = []
        for extract in extracts:
            for heading in extract.get("headings") or []:
                text = heading.get("text") or ""
                if text and text not in headings:
                    headings.append(text)
                if len(headings) >= 8:
                    break
        measures = []
        for extract in extracts:
            for item in extract.get("measures") or []:
                text = item.get("text") or ""
                if text and text not in measures:
                    measures.append(text)
                if len(measures) >= 10:
                    break
        mechanisms = []
        for extract in extracts:
            for item in extract.get("mechanisms") or []:
                text = item.get("text") or ""
                if text and text not in mechanisms:
                    mechanisms.append(text)
                if len(mechanisms) >= 4:
                    break
        lead = next((item.get("lead") for item in extracts if item.get("lead")), "")
        dates = []
        models = []
        hardware = []
        for extract in extracts:
            for found in extract.get("dates") or []:
                if found not in dates:
                    dates.append(found)
            for found in extract.get("models") or []:
                if found not in models:
                    models.append(found)
            for found in extract.get("hardware") or []:
                if found not in hardware:
                    hardware.append(found)
        problem = headings[0] if headings else key
        if lead:
            problem = _clip(f"{problem}: {lead}", 280)
        measurement = (
            _clip(" | ".join(measures), 400)
            if measures
            else "Sin cifra extraible en titulos/fragmentos; afirmacion documental, no reproducida."
        )
        mechanism = (
            _clip(" | ".join(mechanisms), 400)
            if mechanisms
            else (
                "Afirmacion documental del snapshot 09.5.0. No se reejecuto. "
                "Repeticion entre agentes del mismo directorio no es evidencia independiente."
            )
        )
        solution = _clip(
            lead or "Documento de contexto del linaje; veredicto pendiente de 09.5.9.",
            400,
        )
        date = dates[0] if dates else "2026-08-31"
        model = models[0] if models else "n/a (auditoria documental)"
        hardware_s = hardware[0] if hardware else HW
        ranges = rows[0].get("ranges") or ["1-1"]
        cards.append(
            {
                "card_id": f"{batch_id}-{index:02d}-{key.replace('/', '-')[:50]}",
                "claim_kind": "documental",
                "problem": problem or key,
                "outcome": _outcome(extracts),
                "solution_or_failure": solution,
                "causal_mechanism": mechanism,
                "measurement": measurement,
                "provenance": {
                    "path": sample,
                    "ranges": ranges,
                    "date": date,
                    "hardware": hardware_s,
                    "model": model,
                    "commit": head,
                },
                "limitations": (
                    "Lectura de snapshot hermana; no es prueba contemporanea de BAXY. "
                    f"Grupo {key}: {len(rows)} archivos. Cuerpos no se pegan al ledger."
                ),
                "validity": _validity(sample, primary),
                "current_piece": owner_for(sample),
                "source_files": paths,
                "repeats": paths[1:12],
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
        if inspect_summary["hash_missing"]:
            raise SystemExit(
                "FALLO_DE_AMBIENTE hash_missing="
                f"{inspect_summary['hash_missing']} batch={batch_id}"
            )
    files = []
    for row in batch["files"]:
        rec = inspect_map.get(row["path"]) or {}
        extract = rec.get("extract") or {}
        if row["sha256"] in covered:
            entry = {
                "path": row["path"],
                "sha256": row["sha256"],
                "source_id": row["source_id"],
                "terminal": "duplicado_por_hash",
                "ranges": ["hash"],
                "duplicate_of": covered[row["sha256"]],
            }
        elif extract.get("binary") and extract.get("missing"):
            raise SystemExit(f"FALLO_DE_AMBIENTE missing {row['path']}")
        elif extract.get("binary"):
            entry = {
                "path": row["path"],
                "sha256": row["sha256"],
                "source_id": row["source_id"],
                "terminal": "excluido_razonado",
                "ranges": ["not-text"],
                "exclusion_rule": "not_text_document",
            }
        else:
            ranges = extract.get("ranges") or ["1-1"]
            entry = {
                "path": row["path"],
                "sha256": row["sha256"],
                "source_id": row["source_id"],
                "terminal": "leido",
                "ranges": ranges,
            }
            covered.setdefault(row["sha256"], f"{batch_id}:{row['path']}")
        files.append(entry)
    source_id = batch.get("source_id") or "carter"
    head = source_head(source_id)
    nxt = next_docs_in_order(batches, batch_id)
    next_id = nxt
    cards = build_cards(files, inspect_map, batch_id=batch_id, head=head)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger = {
        "schema": SCHEMA,
        "batch_id": batch_id,
        "kind": "docs",
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
        "files": files,
        "cards": cards,
        "missing": 0,
        "overlaps": 0,
        "hash_check": (
            f"inspect hash_ok={inspect_summary['hash_ok']} "
            f"drift={inspect_summary['hash_drift']} miss={inspect_summary['hash_missing']}"
        ),
        "next_docs_batch_id": next_id,
        "next_prompt": unit_next_prompt(queue_ledger, next_id),
        "inspect": inspect_summary.get("wrote"),
        "notes": (
            "Afirmaciones son documentales salvo que claim_kind=reproducido. "
            "Ninguna cifra se presenta como vigente de BAXY actual."
        ),
    }
    errors = validate_ledger(ledger, batch)
    if errors:
        raise SystemExit("validate: " + "; ".join(errors[:20]))
    out = repo / batch["output"]
    dump_json(out, ledger)
    mark_queue_complete(repo, batch_id, next_id)
    claim_path = repo / "artifacts" / "goal095" / "claims" / f"{batch_id}.json"
    if claim_path.is_file():
        sealed = load_json(claim_path)
        sealed["status"] = "complete"
        sealed["closed_utc"] = now
        dump_json(claim_path, sealed)
    return {
        "batch_id": batch_id,
        "cards": len(cards),
        "files": len(files),
        "leido": sum(1 for row in files if row["terminal"] == "leido"),
        "duplicado_por_hash": sum(
            1 for row in files if row["terminal"] == "duplicado_por_hash"
        ),
        "excluido_razonado": sum(
            1 for row in files if row["terminal"] == "excluido_razonado"
        ),
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
            if item.get("kind") == "docs"
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
