"""Measure the inherited command splitter on the sealed 15-mission bank.

This is a structural measurement only: it checks whether the inherited splitter
produces the preregistered number of clauses and identifies which currently
failed missions would reach more than one decision turn.  It neither executes
providers nor assumes that a correct clause count implies correct operations.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
INHERITED = REPO.parent / "Probando Gemma 4"
SOURCE = INHERITED / "gemma4_agent/routing/command_splitter.py"
ENCODER = INHERITED / "gemma4_agent/data/router_encoder_ft/model_int8.onnx"
BANK = REPO / "artifacts/development/goal03b_compound_missions.v1.jsonl"
CURRENT = REPO / "artifacts/development/goal03b_compound_after_final.json"
OUTPUT = REPO / "artifacts/development/goal03_inherited_command_splitter_v20.json"
EXPECTED_BANK_SHA256 = (
    "f66e981c454415999e1f1304b030dabde8e137300c48a237887f8b054bf3c724"
)
EXPECTED_ENCODER_SHA256 = (
    "987091a86e004caafcbcc9d61148dc5d5851b9cac3d2a5700db810e578e4f026"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _latency(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    p90_index = min(len(ordered) - 1, int(0.9 * len(ordered)))
    return {
        "rows": len(ordered),
        "p50": statistics.median(ordered),
        "p90": ordered[p90_index],
        "max": ordered[-1],
        "total": sum(ordered),
    }


def main() -> int:
    if _sha256(BANK) != EXPECTED_BANK_SHA256:
        raise RuntimeError("sealed compound mission bank identity changed")
    if _sha256(ENCODER) != EXPECTED_ENCODER_SHA256:
        raise RuntimeError("coordinated inherited encoder identity changed")

    os.environ["GEMMA4_ENCODER_ONNX"] = "1"
    os.environ["GEMMA4_LEAN_TOOLS"] = "1"
    os.environ["GEMMA4_SEMANTIC_COLD_LOAD"] = "1"
    os.environ["GEMMA4_SPLIT_MULTILANG"] = "1"
    sys.path.insert(0, str(INHERITED))

    from gemma4_agent.routing.command_splitter import (
        _ensure_action_centroids,
        has_back_reference,
        split_command,
    )

    if not _ensure_action_centroids():
        raise RuntimeError("the inherited multilingual action centroids did not load")
    split_command("open Spotify and then turn down the volume")

    current_payload = json.loads(CURRENT.read_text(encoding="utf-8"))
    current_by_id = {row["case_id"]: row for row in current_payload["rows"]}
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for source in _jsonl(BANK):
        started = time.perf_counter()
        clauses = split_command(source["text"])
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        expected_count = len(source["steps"])
        current = current_by_id[source["case_id"]]
        rows.append(
            {
                **source,
                "expected_clause_count": expected_count,
                "clauses": clauses,
                "clause_count": len(clauses),
                "count_correct": len(clauses) == expected_count,
                "back_reference_by_clause": [
                    has_back_reference(clause) for clause in clauses
                ],
                "current_whole": bool(current["whole"]),
                "current_step_named": list(current["step_named"]),
                "currently_failed_and_split": (
                    not current["whole"] and len(clauses) > 1
                ),
                "seconds": elapsed,
            }
        )

    result = {
        "schema": "baxy.goal03-inherited-command-splitter.v1",
        "source": {
            "checkout": str(INHERITED),
            "source_path": str(SOURCE),
            "source_sha256": _sha256(SOURCE),
            "encoder_sha256": _sha256(ENCODER),
            "bank_sha256": _sha256(BANK),
            "current_result_sha256": _sha256(CURRENT),
            "policy": {
                "max_clauses": 3,
                "action_margin": 0.05,
                "multilingual": True,
            },
        },
        "population": {
            "missions": len(rows),
            "expected_steps": sum(len(row["steps"]) for row in rows),
        },
        "structural": {
            "exact_clause_count": sum(row["count_correct"] for row in rows),
            "split_more_than_one": sum(row["clause_count"] > 1 for row in rows),
            "under_split": [
                row["case_id"]
                for row in rows
                if row["clause_count"] < row["expected_clause_count"]
            ],
            "over_split": [
                row["case_id"]
                for row in rows
                if row["clause_count"] > row["expected_clause_count"]
            ],
            "already_whole_and_split": [
                row["case_id"]
                for row in rows
                if row["current_whole"] and row["clause_count"] > 1
            ],
            "currently_failed_and_split": [
                row["case_id"] for row in rows if row["currently_failed_and_split"]
            ],
        },
        "current_product": {
            "whole_missions": sum(row["current_whole"] for row in rows),
            "named_steps": sum(
                sum(bool(value) for value in row["current_step_named"])
                for row in rows
            ),
        },
        "steady_state_seconds": _latency(latencies),
        "limits": [
            "Clause-count agreement is not operation accuracy.",
            "No clause was sent to the BAXY mind in this measurement.",
            "No provider, dispatcher, or external effect was enabled.",
        ],
        "rows": rows,
    }
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: result[key] for key in (
        "population", "structural", "current_product", "steady_state_seconds",
        "limits",
    )}, ensure_ascii=False, indent=2))
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
