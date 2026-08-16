"""Freeze an honest audit of historical compound planner missions."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSIONS = ROOT / "tests/data/historical_missions.jsonl"
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
DEFAULT_OUT = ROOT / "artifacts/planner_recovery/historical_compound_audit.json"

CONTAMINATION = re.compile(
    r"(?:<task-notification>|<codex_internal_context|# Context from my IDE|"
    r"\b(?:Grep|Read|Edit|Bash|AskUserQuestion|OUT|IN)\b.*(?:\.py|lines?|output)|"
    r"\bpytest\b|\bSKILL\.md\b|\btool-use-id\b|\boutput-file\b|"
    r"\b(?:commit|branch|router|planner|benchmark|gate|test_[a-z])\b|"
    r"(?:^|\n)\s*C\d{2}-\d{2}:|```|\{\s*\"(?:ok|status|result)\")",
    re.IGNORECASE | re.MULTILINE,
)


def clean_candidate(value: str) -> bool:
    value = value.strip()
    return (
        3 <= len(value) <= 512
        and "\x00" not in value
        and CONTAMINATION.search(value) is None
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in MISSIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    compounds = [
        row
        for row in rows
        if row.get("class") == "user_mission"
        and len(row.get("operations") or []) >= 2
    ]
    catalog_names = set(
        re.findall(
            r'Descriptor\(\s*"([a-z0-9.]+)"',
            CATALOG.read_text(encoding="utf-8"),
        )
    )
    catalog_families = {name.split(".", 1)[0] for name in catalog_names}

    audited = []
    for row in compounds:
        operations = tuple(row.get("operations") or ())
        private = any(operation.startswith("memory.") for operation in operations)
        candidates = [
            example.strip()
            for example in row.get("examples") or []
            if clean_candidate(example)
        ]
        if private:
            classification = "private_boundary"
            reason = "memory branch must be isolated before public planning"
        elif candidates:
            classification = "natural_evaluable"
            reason = "contains at least one bounded natural user objective"
        else:
            classification = "contaminated_trace"
            reason = "only logs, code, notifications, evaluation prose, or oversized traces"
        missing_families = sorted(
            {
                operation.split(".", 1)[0]
                for operation in operations
                if not operation.startswith("memory.")
                and operation.split(".", 1)[0] not in catalog_families
            }
        )
        audited.append(
            {
                "mission_id": row["canonical_mission_id"],
                "classification": classification,
                "reason": reason,
                "representative_objective": candidates[0] if candidates else None,
                "historical_operations": list(operations),
                "operation_count": len(operations),
                "missing_public_families": missing_families,
            }
        )

    counts = Counter(item["classification"] for item in audited)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(MISSIONS.relative_to(ROOT)).replace("\\", "/"),
        "policy": {
            "natural_evaluable": "may enter no-effect model planner evaluation",
            "contaminated_trace": "coverage/provenance only; never replayed as a user objective",
            "private_boundary": "tested through private envelope; memory text never enters the LLM",
        },
        "summary": {
            "compound_historical_missions": len(compounds),
            "max_steps": max(len(row["operations"]) for row in compounds),
            "classification_counts": dict(sorted(counts.items())),
            "missions_missing_public_family": sum(
                bool(item["missing_public_families"]) for item in audited
            ),
            "all_within_planner_limit": all(
                len(row["operations"]) <= 16 for row in compounds
            ),
        },
        "missions": audited,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
