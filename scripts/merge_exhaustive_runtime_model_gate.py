"""Merge disjoint exhaustive model-gate shards into one canonical ledger."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_exhaustive_runtime_model_gate import (
    APP_ROUTES,
    CASES,
    HARD_FAILURE_STATUSES,
    LANGUAGE_SCOPE,
    ORACLE,
    OUTPUT,
    SUMMARY,
    file_sha256,
    is_runtime,
    read_jsonl,
    runtime_fingerprint,
    write_json,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--oracle", type=Path, default=ORACLE)
    parser.add_argument("--language-scope", type=Path, default=LANGUAGE_SCOPE)
    parser.add_argument("--app-routes", type=Path, default=APP_ROUTES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=SUMMARY)
    args = parser.parse_args()

    cases = [case for case in read_jsonl(args.cases) if is_runtime(case)]
    case_by_id = {case["case_id"]: case for case in cases}
    language_scope = {row["case_id"]: row for row in read_jsonl(args.language_scope)}
    if set(language_scope) != set(case_by_id):
        raise RuntimeError("runtime cases and language scope do not match exactly")
    fingerprint = runtime_fingerprint(args.oracle, args.app_routes, args.language_scope)
    rows: list[dict] = []
    for path in args.inputs:
        rows.extend(read_jsonl(path))
    ids = [str(row.get("case_id") or "") for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("model gate shards contain duplicate case IDs")
    if set(ids) != set(case_by_id):
        missing = len(set(case_by_id).difference(ids))
        extra = len(set(ids).difference(case_by_id))
        raise RuntimeError(f"model gate shards are not exhaustive (missing={missing}, extra={extra})")
    for row in rows:
        case = case_by_id[row["case_id"]]
        if (
            row.get("runtime_fingerprint") != fingerprint
            or row.get("text_sha256") != case["text_sha256"]
            or row.get("completed") is not True
            or row.get("tools_executed") != 0
        ):
            raise RuntimeError(f"invalid shard evidence for {row.get('case_id')}")

    row_by_id = {row["case_id"]: row for row in rows}
    ordered = [row_by_id[case["case_id"]] for case in cases]
    write_jsonl(args.output, ordered)
    statuses = Counter(row["status"] for row in ordered)
    hard_failures = [
        row for row in ordered if row["status"] in HARD_FAILURE_STATUSES
    ]
    latencies = sorted(float(row["total_seconds"]) for row in ordered)
    summary = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "every_exact_runtime_message_real_desktop_route_and_persistent_sidecar_no_effect",
        "source_case_sha256": file_sha256(args.cases),
        "source_oracle_sha256": file_sha256(args.oracle),
        "source_language_scope_sha256": file_sha256(args.language_scope),
        "runtime_fingerprint": fingerprint,
        "unique_runtime_cases": len(cases),
        "target_language_cases": sum(
            row["scope"] == "target" for row in language_scope.values()),
        "out_of_scope_language_cases": sum(
            row["scope"] == "out_of_scope_language" for row in language_scope.values()),
        "completed_cases": len(ordered),
        "remaining_cases": 0,
        "runtime_occurrences_covered": sum(
            int(row["runtime_occurrence_count"]) for row in ordered
        ),
        "status_counts": dict(sorted(statuses.items())),
        "latency_seconds": {
            "maximum": max(latencies, default=0),
            "p50": latencies[len(latencies) // 2] if latencies else 0,
            "p95": latencies[int((len(latencies) - 1) * 0.95)] if latencies else 0,
        },
        "all_cases_completed": True,
        "hard_failures": len(hard_failures),
        "hard_failure_cases": [row["case_id"] for row in hard_failures[:100]],
        "shards_merged": len(args.inputs),
        "tools_executed": 0,
    }
    write_json(args.summary_output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 3 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
