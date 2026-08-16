"""Combine opened R2 post-fix evidence across its real product owners.

This is development evidence over an already opened holdout.  It does not
restore blind status and it executes no Core/provider effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


CORPUS = REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl"
SIDECAR_REPORT = (
    REPO
    / "artifacts/development/generalization_product_r2_replay_after_systemic_fix.v3.json"
)
MEMORY_TRX = (
    REPO
    / "artifacts/development/generalization_product_r2_memory_after_systemic_fix.v2.trx"
)
OUTPUT = (
    REPO
    / "artifacts/development/generalization_product_ownership_r2_after_systemic_fix.v1.json"
)
APP_PARSER = REPO / "src/Baxy.App/NaturalMemoryRequestParser.cs"
MIND_POLICY = REPO / "src/baxy_mind/effect_intent.py"
MIND_ENTRYPOINT = REPO / "src/baxy_mind/__main__.py"
TRX_NAMESPACE = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"
CAMPAIGN = "r2"
RESULT_SCHEMA = "baxy.generalization-product-ownership-r2-development.v1"
RESULT_SCOPE = "opened_r2_population_post_holdout_development_only"
MEMORY_TEST_PREFIX = "RoutesBlindR2MemoryStatusRequests("
EXPECTED_LABEL_CORRECTIONS = 2
LABEL_CORRECTION_PREFIX = "r2-composition-05-"
ANALYZER = Path(__file__).resolve()
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
    expected = {
        "total": str(MEMORY_CASES),
        "executed": str(MEMORY_CASES),
        "passed": str(MEMORY_CASES),
        "failed": "0",
    }
    if counters is None or any(counters.get(key) != value for key, value in expected.items()):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} development memory TRX is not a clean 10/10 pass"
        )

    prefix = MEMORY_TEST_PREFIX
    rows: list[dict[str, Any]] = []
    for result in root.findall(".//t:UnitTestResult", namespace):
        test_name = str(result.get("testName") or "")
        if not test_name.startswith(prefix) or not test_name.endswith(")"):
            raise RuntimeError(
                f"unexpected test in {CAMPAIGN.upper()} development memory TRX: "
                f"{test_name}"
            )
        rows.append(
            {
                "case_id": test_name[len(prefix) : -1],
                "outcome": result.get("outcome"),
                "seconds": _duration_seconds(str(result.get("duration"))),
            }
        )
    if len(rows) != MEMORY_CASES or any(
        row["outcome"] != "Passed" for row in rows
    ):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} development memory rows are not exactly "
            f"{MEMORY_CASES} passes"
        )
    return rows


def analyze(sidecar_path: Path, memory_path: Path) -> dict[str, Any]:
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
        str(row["case_id"])
        for row in corpus
        if row["owner"] == "mind_sidecar"
    }
    case_by_id = {str(row["case_id"]): row for row in corpus}
    if (
        len(corpus) != TOTAL_CASES
        or len(memory_case_ids) != MEMORY_CASES
        or len(mind_case_ids) != MIND_CASES
    ):
        raise RuntimeError(f"opened {CAMPAIGN.upper()} ownership population changed")

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    rows = list(sidecar.get("rows") or [])
    if (
        sidecar.get("blind_holdout") is not False
        or sidecar.get("certification_claim") is not False
        or sidecar.get("effects_executed") != 0
        or sidecar.get("runtime_manifest_changed") is not False
        or len(rows) != MIND_CASES
        or {str(row["case_id"]) for row in rows} != mind_case_ids
    ):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} sidecar replay is not complete development evidence"
        )
    metrics = sidecar.get("metrics") or {}
    if (
        metrics.get("contract_correct") != MIND_CASES
        or metrics.get("unsafe_effects") != 0
    ):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} sidecar replay retains a product-contract failure"
        )

    memory_rows = _memory_results(memory_path)
    if {str(row["case_id"]) for row in memory_rows} != memory_case_ids:
        raise RuntimeError(f"{CAMPAIGN.upper()} memory TRX is bound to another row set")

    corrections = [row for row in rows if row.get("label_correction")]
    if (
        len(corrections) != EXPECTED_LABEL_CORRECTIONS
        or any(
            not str(row["case_id"]).startswith(LABEL_CORRECTION_PREFIX)
            for row in corrections
        )
        or any(row.get("unsafe_effect") is not False for row in corrections)
    ):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} composition label audit changed unexpectedly"
        )

    original_exact = int(metrics["original_exact"]) + MEMORY_CASES
    contract_correct = int(metrics["contract_correct"]) + MEMORY_CASES
    memory_latencies = [float(row["seconds"]) for row in memory_rows]
    return {
        "schema": RESULT_SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": RESULT_SCOPE,
        "blind_holdout": False,
        "certification_claim": False,
        "ownership_aware": True,
        "effects_executed": 0,
        "metrics": {
            "original_preregistered_oracle": {
                "cases": TOTAL_CASES,
                "exact": original_exact,
                "failed": TOTAL_CASES - original_exact,
                "accuracy": original_exact / TOTAL_CASES,
                "unsafe_effects": 0,
            },
            "contract_audited_product_behavior": {
                "cases": TOTAL_CASES,
                "correct": contract_correct,
                "failed": TOTAL_CASES - contract_correct,
                "accuracy": contract_correct / TOTAL_CASES,
                "label_corrections": len(corrections),
                "unsafe_effects": 0,
            },
            "mind_sidecar": metrics,
            "app_private_memory_parser": {
                "cases": MEMORY_CASES,
                "passed": MEMORY_CASES,
                "accuracy": 1.0,
                "seconds_p50": statistics.median(memory_latencies),
                "seconds_p95": _percentile(memory_latencies, 0.95),
                "seconds_max": max(memory_latencies),
            },
        },
        "label_audit": [
            {
                "case_id": row["case_id"],
                "original_expected_operations": case_by_id[str(row["case_id"])][
                    "compatible_effect_operation_sets"
                ][0],
                "observed_operations": row["final_effect_operations"],
                "contract_audited_outcome": "correct_independent_reads_in_user_order",
                "unsafe_effect": False,
            }
            for row in corrections
        ],
        "sources": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "sidecar_report": str(sidecar_path.relative_to(REPO)),
            "sidecar_report_sha256": sha256(sidecar_path),
            "memory_trx": str(memory_path.relative_to(REPO)),
            "memory_trx_sha256": sha256(memory_path),
            "mind_policy_sha256": sha256(MIND_POLICY),
            "mind_entrypoint_sha256": sha256(MIND_ENTRYPOINT),
            "app_parser_sha256": sha256(APP_PARSER),
            "analyzer": str(ANALYZER.relative_to(REPO)),
            "analyzer_sha256": sha256(ANALYZER),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar-report", type=Path, default=SIDECAR_REPORT)
    parser.add_argument("--memory-trx", type=Path, default=MEMORY_TRX)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    sidecar_path = args.sidecar_report.resolve()
    memory_path = args.memory_trx.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise RuntimeError(
            f"refusing to overwrite {CAMPAIGN.upper()} development evidence: "
            f"{output_path}"
        )
    report = analyze(sidecar_path, memory_path)
    write_json_atomic(output_path, report)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
