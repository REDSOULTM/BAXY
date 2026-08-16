"""Aggregate the sealed R2 Mind and App-memory evidence without reopening it."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.build_generalization_product_holdout_r2 import (  # noqa: E402
    MEASUREMENT_SOURCES,
    MEMORY_TRX,
    MIND_OUTPUT,
    OUTPUT as CORPUS,
    POLICY_SOURCES,
    PREREGISTRATION,
    PRODUCT_OUTPUT as OUTPUT,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


TRX_NAMESPACE = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"
CAMPAIGN = "r2"
RESULT_SCHEMA = "baxy.generalization-product-holdout-r2-result.v1"
RESULT_SCOPE = "sealed_blind_generalization_product_r2_population"
MEMORY_TEST_PREFIX = "RoutesBlindR2MemoryStatusRequests("
TOTAL_CASES = 340
MIND_CASES = 330
MEMORY_CASES = 10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _duration_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":", maxsplit=2)
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(quantile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def _memory_results(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    namespace = {"t": TRX_NAMESPACE}
    counters = root.find(".//t:ResultSummary/t:Counters", namespace)
    if counters is None:
        raise RuntimeError(f"{CAMPAIGN.upper()} memory TRX has no counters")
    expected = str(MEMORY_CASES)
    if counters.get("total") != expected or counters.get("executed") != expected:
        raise RuntimeError(
            f"{CAMPAIGN.upper()} memory TRX did not execute exactly "
            f"{MEMORY_CASES} rows: {counters.attrib}"
        )

    prefix = MEMORY_TEST_PREFIX
    rows: list[dict[str, Any]] = []
    for result in root.findall(".//t:UnitTestResult", namespace):
        test_name = str(result.get("testName") or "")
        if not test_name.startswith(prefix) or not test_name.endswith(")"):
            raise RuntimeError(
                f"unexpected test in {CAMPAIGN.upper()} memory TRX: {test_name}"
            )
        rows.append(
            {
                "case_id": test_name[len(prefix) : -1],
                "outcome": result.get("outcome"),
                "passed": result.get("outcome") == "Passed",
                "seconds": _duration_seconds(str(result.get("duration"))),
            }
        )
    if (
        len(rows) != MEMORY_CASES
        or len({row["case_id"] for row in rows}) != MEMORY_CASES
    ):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} memory TRX rows are incomplete or duplicated"
        )
    return rows


def analyze(mind_path: Path, memory_path: Path) -> dict[str, Any]:
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    if (
        preregistration.get("blind_holdout") is not True
        or preregistration.get("measurement_status") != "unopened"
        or preregistration["output"]["sha256"] != sha256(CORPUS)
    ):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} preregistration is not sealed and unopened"
        )
    actual_policy = {
        str(path.relative_to(REPO)): sha256(path) for path in POLICY_SOURCES
    }
    actual_measurement = {
        str(path.relative_to(REPO)): sha256(path) for path in MEASUREMENT_SOURCES
    }
    if preregistration["sources"]["policy_sha256"] != actual_policy:
        raise RuntimeError(f"{CAMPAIGN.upper()} policy changed after preregistration")
    if preregistration["sources"]["measurement_sha256"] != actual_measurement:
        raise RuntimeError(
            f"{CAMPAIGN.upper()} measurement code changed after preregistration"
        )

    corpus = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    memory_case_ids = {
        str(row["case_id"])
        for row in corpus
        if row["owner"] == "app_private_memory_parser"
    }
    mind_case_ids = {
        str(row["case_id"]) for row in corpus if row["owner"] == "mind_sidecar"
    }
    if (
        len(corpus) != TOTAL_CASES
        or len(memory_case_ids) != MEMORY_CASES
        or len(mind_case_ids) != MIND_CASES
    ):
        raise RuntimeError(f"{CAMPAIGN.upper()} corpus ownership split changed")

    mind = json.loads(mind_path.read_text(encoding="utf-8"))
    mind_rows = list(mind.get("rows") or [])
    if (
        mind.get("blind_holdout") is not True
        or mind.get("owner") != "mind_sidecar"
        or mind.get("effects_executed") != 0
        or mind.get("runtime_manifest_changed") is not False
        or len(mind_rows) != MIND_CASES
        or {str(row["case_id"]) for row in mind_rows} != mind_case_ids
    ):
        raise RuntimeError(f"{CAMPAIGN.upper()} Mind evidence is invalid")
    if mind["source"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} Mind evidence is bound to another corpus"
        )

    memory_rows = _memory_results(memory_path)
    if {str(row["case_id"]) for row in memory_rows} != memory_case_ids:
        raise RuntimeError(
            f"{CAMPAIGN.upper()} memory evidence is bound to another row set"
        )

    mind_exact = sum(bool(row["exact_turn_correct"]) for row in mind_rows)
    memory_exact = sum(bool(row["passed"]) for row in memory_rows)
    total_exact = mind_exact + memory_exact
    total_cases = len(corpus)
    unsafe = sum(bool(row["unsafe_effect"]) for row in mind_rows)
    threshold = float(preregistration["method"]["minimum_exact_turn_accuracy"])
    passed = total_exact / total_cases >= threshold and unsafe == 0
    memory_latencies = [float(row["seconds"]) for row in memory_rows]
    report = {
        "schema": RESULT_SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": RESULT_SCOPE,
        "blind_holdout": True,
        "ownership_aware": True,
        "effects_executed": 0,
        "thresholds": {
            "minimum_exact_turn_accuracy": threshold,
            "maximum_unsafe_effects": 0,
        },
        "metrics": {
            "cases": total_cases,
            "exact": total_exact,
            "failed": total_cases - total_exact,
            "exact_turn_accuracy": total_exact / total_cases,
            "unsafe_effects": unsafe,
            "threshold_passed": passed,
            "one_sided_95_binomial_lower_if_zero_failures": (
                math.pow(0.05, 1.0 / total_cases)
                if total_exact == total_cases
                else None
            ),
            "mind_sidecar": mind["metrics"],
            "app_private_memory_parser": {
                "cases": MEMORY_CASES,
                "exact": memory_exact,
                "failed": MEMORY_CASES - memory_exact,
                "accuracy": memory_exact / MEMORY_CASES,
                "seconds_p50": statistics.median(memory_latencies),
                "seconds_p95": _percentile(memory_latencies, 0.95),
                "seconds_max": max(memory_latencies),
            },
        },
        "failures": {
            "mind_sidecar": [
                {
                    "case_id": row["case_id"],
                    "failure_cause": row["failure_cause"],
                    "final_kind": row["final_kind"],
                    "final_intent_operations": row["final_intent_operations"],
                    "final_effect_operations": row["final_effect_operations"],
                    "unsafe_effect": row["unsafe_effect"],
                }
                for row in mind_rows
                if not row["exact_turn_correct"]
            ],
            "app_private_memory_parser": [
                {"case_id": row["case_id"], "outcome": row["outcome"]}
                for row in memory_rows
                if not row["passed"]
            ],
        },
        "sources": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "preregistration": str(PREREGISTRATION.relative_to(REPO)),
            "preregistration_sha256": sha256(PREREGISTRATION),
            "mind_result": str(mind_path.relative_to(REPO)),
            "mind_result_sha256": sha256(mind_path),
            "mind_raw_audit": mind["source"]["raw_audit"],
            "mind_raw_audit_sha256": mind["source"]["raw_audit_sha256"],
            "memory_trx": str(memory_path.relative_to(REPO)),
            "memory_trx_sha256": sha256(memory_path),
            "tree_frozen_against_preregistered_hashes": True,
        },
        "memory_rows": memory_rows,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mind-result", type=Path, default=MIND_OUTPUT)
    parser.add_argument("--memory-trx", type=Path, default=MEMORY_TRX)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    mind_path = args.mind_result.resolve()
    memory_path = args.memory_trx.resolve()
    output_path = args.output.resolve()
    if (
        mind_path != MIND_OUTPUT.resolve()
        or memory_path != MEMORY_TRX.resolve()
        or output_path != OUTPUT.resolve()
    ):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} aggregate evidence paths are preregistered and immutable"
        )
    if output_path.exists():
        raise RuntimeError(
            f"refusing to overwrite {CAMPAIGN.upper()} product evidence: {output_path}"
        )
    report = analyze(mind_path, memory_path)
    write_json_atomic(output_path, report)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0 if report["metrics"]["threshold_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
