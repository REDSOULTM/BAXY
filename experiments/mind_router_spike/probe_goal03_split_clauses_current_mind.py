"""Send the four justified inherited splits through the current BAXY mind.

V20 identified four currently failed compound missions with exactly two
inherited clauses.  This probe measures those eight clauses independently at
the existing ``turn.decide`` boundary.  It combines declared operations only;
providers remain disabled and no first-step result is fabricated for dependent
second clauses.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for root in (REPO, REPO / "src"):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from experiments.mind_router_spike.run_goal03_comprehension import (  # noqa: E402
    _final_operations,
    measure,
)


SPLITTER_RESULT = (
    REPO / "artifacts/development/goal03_inherited_command_splitter_v20.json"
)
CURRENT_RESULT = REPO / "artifacts/development/goal03b_compound_after_final.json"
AUDIT = REPO / "artifacts/development/goal03_split_clauses_v21.turn-audit.jsonl"
TELEMETRY = REPO / "artifacts/development/goal03_split_clauses_v21.telemetry.jsonl"
OUTPUT = REPO / "artifacts/development/goal03_split_clauses_v21.json"
CASE_IDS = ("cmp-b04", "cmp-b05", "cmp-b10", "cmp-b15")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    splitter = json.loads(SPLITTER_RESULT.read_text(encoding="utf-8"))
    current = json.loads(CURRENT_RESULT.read_text(encoding="utf-8"))
    split_by_id = {row["case_id"]: row for row in splitter["rows"]}
    current_by_id = {row["case_id"]: row for row in current["rows"]}
    if tuple(splitter["structural"]["currently_failed_and_split"]) != CASE_IDS:
        raise RuntimeError("V20 justified split population changed")

    clause_rows: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        row = split_by_id[case_id]
        if len(row["clauses"]) != len(row["steps"]) or current_by_id[case_id]["whole"]:
            raise RuntimeError(f"{case_id} no longer belongs in the split probe")
        for index, (clause, expected) in enumerate(
            zip(row["clauses"], row["steps"]), start=1
        ):
            clause_rows.append(
                {
                    "case_id": f"{case_id}-s{index}",
                    "mission_id": case_id,
                    "step_index": index,
                    "language": row["language"],
                    "text": clause,
                    "expected_operations": expected,
                    "in_catalog": True,
                }
            )

    telemetry = measure(
        clause_rows,
        label="compound-split-v21",
        audit_path=AUDIT,
    )
    TELEMETRY.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in telemetry
        ),
        encoding="utf-8",
        newline="\n",
    )

    scored_clauses: list[dict[str, Any]] = []
    for row in telemetry:
        final = _final_operations(row)
        named = bool(set(final) & set(row["expected_operations"]))
        scored_clauses.append(
            {
                "case_id": row["case_id"],
                "mission_id": row["mission_id"],
                "step_index": row["step_index"],
                "text": row["text"],
                "expected_operations": row["expected_operations"],
                "final_operations": final,
                "named": named,
                "kind": row["kind"],
                "decision_path": row["decision_path"],
                "retrieval": row["retrieval"],
                "seconds": row["seconds"],
            }
        )

    missions: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        clauses = [row for row in scored_clauses if row["mission_id"] == case_id]
        missions.append(
            {
                "case_id": case_id,
                "clause_named": [row["named"] for row in clauses],
                "whole": all(row["named"] for row in clauses),
                "current_whole": bool(current_by_id[case_id]["whole"]),
                "current_step_named": list(current_by_id[case_id]["step_named"]),
            }
        )

    result = {
        "schema": "baxy.goal03-split-clauses-current-mind.v1",
        "source": {
            "splitter_result_sha256": _sha256(SPLITTER_RESULT),
            "current_compound_result_sha256": _sha256(CURRENT_RESULT),
            "audit_sha256": _sha256(AUDIT),
            "telemetry_sha256": _sha256(TELEMETRY),
        },
        "population": {
            "missions": len(missions),
            "clauses": len(scored_clauses),
        },
        "before": {
            "whole_missions": sum(row["current_whole"] for row in missions),
            "named_steps": sum(
                sum(bool(value) for value in row["current_step_named"])
                for row in missions
            ),
        },
        "after_independent_clauses": {
            "whole_missions": sum(row["whole"] for row in missions),
            "named_steps": sum(row["named"] for row in scored_clauses),
        },
        "latency_seconds": _latency([row["seconds"] for row in scored_clauses]),
        "three_zeros": {
            "providers_enabled": False,
            "effects_executed": 0,
        },
        "limits": [
            "Each clause has empty history, matching a recognition probe rather than execution.",
            "No result or success of an earlier clause is fabricated.",
            "A named dependent clause does not prove that its runtime arguments are grounded.",
        ],
        "missions": missions,
        "clauses": scored_clauses,
    }
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({key: result[key] for key in (
        "population", "before", "after_independent_clauses", "latency_seconds",
        "three_zeros", "limits", "missions",
    )}, ensure_ascii=False, indent=2))
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
