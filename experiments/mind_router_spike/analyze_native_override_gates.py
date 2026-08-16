"""Enumerate conservative native-selector override gates on opened R4 data."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "artifacts/research/mdeberta_native_selector_mtop_r1.json"
V1 = ROOT / "artifacts/research/operation_shortlist_mtop_r4_v1.json"
V2 = ROOT / "artifacts/research/operation_shortlist_mtop_r4_v2.json"
REPORT = ROOT / "artifacts/research/native_override_gates_r1.json"
NO_ACTION = "__none__"


def _family(operation: str) -> str:
    return operation.split(".", 1)[0]


def analyze() -> dict[str, Any]:
    native_source = json.loads(NATIVE.read_text(encoding="utf-8"))
    v1_source = json.loads(V1.read_text(encoding="utf-8"))
    v2_source = json.loads(V2.read_text(encoding="utf-8"))
    native = {str(row["source_id"]): row for row in native_source["records"]}
    v2 = {str(row["source_id"]): row for row in v2_source["rows"]}
    rows = []
    for lexical in v1_source["rows"]:
        source_id = str(lexical["source_id"])
        specialist = native[source_id]
        selected = (
            str(specialist["selected_operations"][0])
            if specialist["selected_operations"]
            else NO_ACTION
        )
        rows.append(
            {
                "source_id": source_id,
                "expected": frozenset(str(value) for value in lexical["expected"]),
                "specialist": [str(value) for value in specialist["specialist_top"]],
                "native": selected,
                "v1": [str(value) for value in lexical["top_5"]],
                "v2": [str(value) for value in v2[source_id]["top_5"]],
            }
        )

    predicates: dict[str, Callable[[dict[str, Any]], bool]] = {
        "native_effect": lambda row: row["native"] != NO_ACTION,
        "native_is_specialist_second": lambda row: row["native"] == row["specialist"][1],
        "native_in_specialist_top2": lambda row: row["native"] in row["specialist"][:2],
        "native_in_specialist_top3": lambda row: row["native"] in row["specialist"][:3],
        "native_is_v1_top1": lambda row: row["native"] == row["v1"][0],
        "native_is_v2_top1": lambda row: row["native"] == row["v2"][0],
        "native_in_v1_top2": lambda row: row["native"] in row["v1"][:2],
        "native_in_v2_top2": lambda row: row["native"] in row["v2"][:2],
        "lexical_top1_agreement": lambda row: row["v1"][0] == row["v2"][0],
        "specialist_is_no_action": lambda row: row["specialist"][0] == NO_ACTION,
        "specialist_is_effect": lambda row: row["specialist"][0] != NO_ACTION,
        "same_effect_family": lambda row: (
            row["native"] != NO_ACTION
            and row["specialist"][0] != NO_ACTION
            and _family(row["native"]) == _family(row["specialist"][0])
        ),
    }
    baseline_correct = sum(
        row["specialist"][0] in row["expected"] for row in rows
    )
    gates = []
    names = sorted(predicates)
    for count in range(1, 5):
        for selected_predicates in itertools.combinations(names, count):
            overridden = [
                row
                for row in rows
                if row["native"] != row["specialist"][0]
                and all(predicates[name](row) for name in selected_predicates)
            ]
            corrections = sum(
                row["specialist"][0] not in row["expected"]
                and row["native"] in row["expected"]
                for row in overridden
            )
            regressions = sum(
                row["specialist"][0] in row["expected"]
                and row["native"] not in row["expected"]
                for row in overridden
            )
            if not overridden:
                continue
            gates.append(
                {
                    "predicates": list(selected_predicates),
                    "overrides": len(overridden),
                    "corrections": corrections,
                    "regressions": regressions,
                    "result_correct": baseline_correct + corrections - regressions,
                    "result_accuracy": round(
                        (baseline_correct + corrections - regressions) / len(rows),
                        6,
                    ),
                }
            )
    gates.sort(
        key=lambda row: (
            -int(row["result_correct"]),
            int(row["regressions"]),
            int(row["overrides"]),
            len(row["predicates"]),
        )
    )
    report = {
        "schema": "baxy.native-override-gate-analysis.v1",
        "scope": "opened_r4_development_only_no_promotion",
        "cases": len(rows),
        "specialist_correct": baseline_correct,
        "specialist_accuracy": round(baseline_correct / len(rows), 6),
        "best": gates[:50],
        "best_zero_regression": next(
            (row for row in gates if row["regressions"] == 0),
            None,
        ),
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
