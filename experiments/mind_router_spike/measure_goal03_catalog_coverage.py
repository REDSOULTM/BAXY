"""Goal 03: the coverage ledger, so consolidating can be told from amputating.

The identity fixes two numbers and their order: coverage must not drop, and with
coverage intact the smaller count wins. That is only checkable if coverage is
enumerated **before** the catalogue is touched, so this publishes it as data.

Coverage here is the enumerated set of distinct things the person can ask the
machine to do, one entry per authenticated operation the planner can reach,
identified by name and by the SHA-256 of its contract (description plus argument
schema). Two catalogues cover the same ground when every entry of the first is
still reachable in the second — directly, or as a named action of a parametric
tool, or as a step of a chain. That last clause is what lets a smaller catalogue
keep its coverage instead of losing it.

Reads the core's authenticated ``hello`` catalogue. Starts no model and executes
no effect.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)

SCHEMA = "baxy.goal03-catalog-coverage.v1"
RESULT_DIR = REPO / "artifacts" / "development"
# El planner nunca planifica memoria privada, y ``app.status`` es interno.
UNREACHABLE_PREFIXES = ("memory.",)
UNREACHABLE_NAMES = {"app.status"}


def _contract_sha256(capability: dict[str, Any]) -> str:
    payload = json.dumps(
        [capability["description"], capability["argumentsSchema"]],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build(capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for capability in sorted(capabilities, key=lambda item: item["name"]):
        name = capability["name"]
        entries.append(
            {
                "operation": name,
                "family": name.split(".", 1)[0],
                "risk": capability["risk"],
                "planner_reachable": name not in UNREACHABLE_NAMES
                and not name.startswith(UNREACHABLE_PREFIXES),
                "contract_sha256": _contract_sha256(capability),
                "description": capability["description"],
            }
        )
    reachable = [entry for entry in entries if entry["planner_reachable"]]
    ledger = hashlib.sha256(
        "\n".join(
            f"{entry['operation']}\t{entry['contract_sha256']}" for entry in entries
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "count": {
            "operations": len(entries),
            "planner_reachable": len(reachable),
            "families": len({entry["family"] for entry in entries}),
        },
        "coverage_ledger_sha256": ledger,
        "by_family": dict(
            sorted(collections.Counter(entry["family"] for entry in entries).items())
        ),
        "by_risk": dict(
            sorted(collections.Counter(entry["risk"] for entry in entries).items())
        ),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03 catalogue coverage ledger")
    parser.add_argument("--label", required=True)
    arguments = parser.parse_args()

    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    report = build(capabilities)
    destination = RESULT_DIR / f"goal03_catalog_coverage_{arguments.label}.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("count", "coverage_ledger_sha256", "by_family")
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
