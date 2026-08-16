"""Combine the opened R1 development replay across its real product owners.

This is post-holdout development evidence.  It never upgrades the opened R1
population back to blind status and never executes a provider or physical
effect.  Mind-owned rows come from a turn-only replay; memory-owned rows come
from the App's private parser TRX.
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


CORPUS = REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl"
SIDECAR_REPORT = (
    REPO
    / "artifacts/development/generalization_surface_r1_replay_after_systemic_fix.v3.json"
)
MEMORY_TRX = (
    REPO
    / "artifacts/development/generalization_surface_memory_app_r1_after_systemic_fix.v1.trx"
)
OUTPUT = (
    REPO
    / "artifacts/development/generalization_surface_product_ownership_r1_after_systemic_fix.v1.json"
)
APP_PARSER = REPO / "src/Baxy.App/NaturalMemoryRequestParser.cs"
APP_PARSER_TESTS = (
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs"
)
CATALOG_CONTRACT = REPO / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
CLARIFICATION_TESTS = REPO / "tests/test_effect_intent.py"
LABEL_CORRECTION_CASE_ID = "message-03-plain"
TRX_NAMESPACE = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _duration_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":", maxsplit=2)
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(quantile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def _trx_memory_results(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    namespace = {"t": TRX_NAMESPACE}
    counters = root.find(".//t:ResultSummary/t:Counters", namespace)
    if counters is None:
        raise RuntimeError("memory TRX has no result counters")
    expected_counters = {"total": "10", "executed": "10", "passed": "10", "failed": "0"}
    if any(counters.get(key) != value for key, value in expected_counters.items()):
        raise RuntimeError(f"memory TRX is not a clean 10/10 pass: {counters.attrib}")

    rows: list[dict[str, Any]] = []
    for result in root.findall(".//t:UnitTestResult", namespace):
        test_name = str(result.get("testName") or "")
        prefix = 'RoutesGeneralizationSurfaceStatusRequests("'
        if not test_name.startswith(prefix) or not test_name.endswith('")'):
            raise RuntimeError(f"unexpected test in memory TRX: {test_name}")
        rows.append(
            {
                "text": test_name[len(prefix) : -2],
                "outcome": result.get("outcome"),
                "seconds": _duration_seconds(str(result.get("duration"))),
            }
        )
    if len(rows) != 10 or any(row["outcome"] != "Passed" for row in rows):
        raise RuntimeError("memory TRX result rows are not exactly ten passes")
    return rows


def analyze(sidecar_path: Path, memory_trx_path: Path) -> dict[str, Any]:
    cases = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) != 310:
        raise RuntimeError("opened R1 population shape changed")
    case_by_id = {str(case["case_id"]): case for case in cases}
    memory_cases = [case for case in cases if case["family"] == "memory"]
    mind_cases = [case for case in cases if case["family"] != "memory"]

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if sidecar.get("blind_holdout") is not False:
        raise RuntimeError("sidecar input is not explicitly development-only")
    if sidecar.get("effects_executed") != 0:
        raise RuntimeError("sidecar development replay executed effects")
    if sidecar.get("runtime_manifest_changed") is not False:
        raise RuntimeError("sidecar development replay changed its runtime manifest")
    population = sidecar.get("population") or {}
    if population.get("measured_cases") != 300:
        raise RuntimeError("sidecar development replay did not measure 300 rows")
    if population.get("excluded_families") != ["memory"]:
        raise RuntimeError("sidecar development replay has the wrong ownership exclusion")
    rows = list(sidecar.get("rows") or [])
    if len(rows) != 300 or {row["case_id"] for row in rows} != {
        case["case_id"] for case in mind_cases
    }:
        raise RuntimeError("sidecar rows do not match the 300 Mind-owned cases")

    memory_results = _trx_memory_results(memory_trx_path)
    if {row["text"] for row in memory_results} != {
        str(case["text"]) for case in memory_cases
    }:
        raise RuntimeError("App parser TRX does not match all ten memory-owned texts")

    original_failures = [row for row in rows if not row["exact_turn_correct"]]
    if [row["case_id"] for row in original_failures] != [LABEL_CORRECTION_CASE_ID]:
        raise RuntimeError(f"unexpected residual failures: {original_failures}")
    residual = original_failures[0]
    residual_case = case_by_id[LABEL_CORRECTION_CASE_ID]
    channel_tokens = ("whatsapp", "discord", "wsp")
    channel_absent = not any(
        token in str(residual_case["text"]).casefold() for token in channel_tokens
    )
    safe_clarification = (
        channel_absent
        and residual.get("final_kind") == "clarify"
        and residual.get("final_intent_operations") == ["message.send"]
        and residual.get("final_effect_operations") == []
        and residual.get("stage_names") == ["explicit_clarification"]
        and residual.get("unsafe_effect") is False
    )
    if not safe_clarification:
        raise RuntimeError("the single label correction is not a safe missing-channel clarification")

    mind_exact = sum(bool(row["exact_turn_correct"]) for row in rows)
    memory_exact = len(memory_results)
    original_exact = mind_exact + memory_exact
    memory_latencies = [float(row["seconds"]) for row in memory_results]
    report = {
        "schema": "baxy.generalization-surface-product-ownership-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_r1_population_post_holdout_development_only",
        "blind_holdout": False,
        "certification_claim": False,
        "effects_executed": 0,
        "ownership": {
            "mind_sidecar": {
                "families": 30,
                "cases": 300,
                "authority": "turn.decide_only_no_plan_no_core_no_provider",
            },
            "app_private_memory_parser": {
                "families": 1,
                "cases": 10,
                "authority": "parser_test_only_no_core_no_provider",
            },
        },
        "metrics": {
            "original_preregistered_oracle": {
                "cases": 310,
                "exact": original_exact,
                "failed": 310 - original_exact,
                "accuracy": original_exact / 310,
                "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in rows),
            },
            "contract_audited_product_behavior": {
                "cases": 310,
                "correct": original_exact + int(safe_clarification),
                "accuracy": (original_exact + int(safe_clarification)) / 310,
                "label_corrections": 1,
                "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in rows),
            },
            "mind_sidecar": sidecar["metrics"],
            "app_private_memory_parser": {
                "cases": 10,
                "passed": 10,
                "accuracy": 1.0,
                "seconds_p50": statistics.median(memory_latencies),
                "seconds_p95": _percentile(memory_latencies, 0.95),
                "seconds_max": max(memory_latencies),
            },
        },
        "label_audit": [
            {
                "case_id": LABEL_CORRECTION_CASE_ID,
                "original_outcome": residual_case["outcome"],
                "contract_audited_outcome": "clarify_missing_channel",
                "channel_absent": channel_absent,
                "observed_kind": residual["final_kind"],
                "observed_intent_operations": residual["final_intent_operations"],
                "observed_effect_operations": residual["final_effect_operations"],
                "safe_product_behavior": safe_clarification,
                "reason": (
                    "message.recipient.resolve requires channel and recipient; the text names "
                    "Ana but provides neither Discord nor WhatsApp"
                ),
            }
        ],
        "sources": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "sidecar_report": str(sidecar_path.relative_to(REPO)),
            "sidecar_report_sha256": sha256(sidecar_path),
            "memory_trx": str(memory_trx_path.relative_to(REPO)),
            "memory_trx_sha256": sha256(memory_trx_path),
            "app_parser_sha256": sha256(APP_PARSER),
            "app_parser_tests_sha256": sha256(APP_PARSER_TESTS),
            "catalog_contract_sha256": sha256(CATALOG_CONTRACT),
            "clarification_tests_sha256": sha256(CLARIFICATION_TESTS),
            "analyzer_sha256": sha256(Path(__file__).resolve()),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar-report", type=Path, default=SIDECAR_REPORT)
    parser.add_argument("--memory-trx", type=Path, default=MEMORY_TRX)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    sidecar_path = args.sidecar_report.resolve()
    memory_trx_path = args.memory_trx.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise RuntimeError(f"refusing to overwrite development evidence: {output_path}")
    report = analyze(sidecar_path, memory_trx_path)
    write_json_atomic(output_path, report)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
