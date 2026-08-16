"""Join Mind and App routing evidence for all 169 MVP catalogue operations."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SCENARIOS = (
    REPO
    / "artifacts"
    / "development"
    / "catalog_seen_scenarios_r2_dependency_complete.jsonl"
)
MIND_REPORT = REPO / "artifacts" / "mvp" / "catalog_functional_matrix_mind_v1.json"
MEMORY_TRX = (
    REPO
    / "artifacts"
    / "mvp"
    / "catalog_functional_matrix_memory_v1"
    / "catalog_memory_v1.trx"
)
OUTPUT = REPO / "artifacts" / "mvp" / "catalog_routing_matrix_v1.json"
EXPECTED_CATALOG_SHA256 = (
    "67c82b61bc661bdf35478a1ae2139e2b609dcbb861e0c59ab5d05dfa0a41fd41"
)
MEMORY_TEST_NAME = re.compile(
    r"^RoutesEveryReviewedCatalogMemoryOperation\((?P<case_id>[^)]+)\)$"
)
TRX_NAMESPACE = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duration_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":", 2)
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def load_scenarios() -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in SCENARIOS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if (
        len(rows) != 169
        or len({row.get("target_operation") for row in rows}) != 169
        or any(row.get("catalog_sha256") != EXPECTED_CATALOG_SHA256 for row in rows)
    ):
        raise RuntimeError("the authenticated 169-operation scenario matrix changed")
    return rows


def load_memory_results(path: Path) -> dict[str, dict[str, Any]]:
    root = ET.parse(path).getroot()
    results: dict[str, dict[str, Any]] = {}
    for node in root.findall(".//t:UnitTestResult", TRX_NAMESPACE):
        name = node.attrib.get("testName", "")
        match = MEMORY_TEST_NAME.fullmatch(name)
        if match is None:
            continue
        case_id = match.group("case_id")
        results[case_id] = {
            "outcome": node.attrib.get("outcome"),
            "seconds": duration_seconds(node.attrib.get("duration", "00:00:00")),
        }
    return results


def build_report(mind_report: Path, memory_trx: Path) -> dict[str, Any]:
    scenarios = load_scenarios()
    by_case = {str(row["case_id"]): row for row in scenarios}
    mind = json.loads(mind_report.read_text(encoding="utf-8"))
    if (
        mind.get("schema") != "baxy.mvp-catalog-functional-matrix-mind.v1"
        or mind.get("development_gate_passed") is not True
        or mind.get("effects_executed") != 0
        or mind.get("metrics", {}).get("exact") != 158
        or mind.get("metrics", {}).get("cases") != 158
    ):
        raise RuntimeError("the Mind routing report did not pass 158/158 safely")

    matrix_rows: list[dict[str, Any]] = []
    mind_targets: set[str] = set()
    for row in mind.get("rows") or []:
        target = str(row.get("target_operation"))
        case_id = str(row.get("case_id"))
        scenario = by_case.get(case_id)
        if (
            scenario is None
            or scenario.get("owner") != "mind_sidecar"
            or target != scenario.get("target_operation")
            or row.get("exact_turn_correct") is not True
            or row.get("unsafe_effect") is not False
        ):
            raise RuntimeError(f"invalid Mind matrix row: {case_id}")
        mind_targets.add(target)
        matrix_rows.append(
            {
                "case_id": case_id,
                "family": target.split(".", 1)[0],
                "operation": target,
                "language": scenario["language"],
                "text": scenario["text"],
                "routing_owner": "mind_sidecar",
                "routing_seconds": row["seconds"],
                "routing_passed": True,
                "unsafe_effect": False,
                "provider_execution": "pending_separate_safe_execution_gate",
                "independent_verification": "pending_separate_safe_execution_gate",
            }
        )

    memory_results = load_memory_results(memory_trx)
    memory_scenarios = [row for row in scenarios if row["owner"] == "app_memory_parser"]
    expected_memory_ids = {str(row["case_id"]) for row in memory_scenarios}
    if set(memory_results) != expected_memory_ids:
        raise RuntimeError("the App memory TRX does not cover exactly its eleven rows")
    for scenario in memory_scenarios:
        case_id = str(scenario["case_id"])
        result = memory_results[case_id]
        if result["outcome"] != "Passed":
            raise RuntimeError(f"App memory routing failed: {case_id}")
        target = str(scenario["target_operation"])
        matrix_rows.append(
            {
                "case_id": case_id,
                "family": target.split(".", 1)[0],
                "operation": target,
                "language": scenario["language"],
                "text": scenario["text"],
                "routing_owner": "app_memory_parser",
                "routing_seconds": result["seconds"],
                "routing_passed": True,
                "unsafe_effect": False,
                "provider_execution": "pending_separate_safe_execution_gate",
                "independent_verification": "pending_separate_safe_execution_gate",
            }
        )

    operations = {str(row["operation"]) for row in matrix_rows}
    expected_operations = {str(row["target_operation"]) for row in scenarios}
    if (
        len(matrix_rows) != 169
        or operations != expected_operations
        or len(mind_targets) != 158
    ):
        raise RuntimeError(
            "the joined MVP routing matrix is not exactly 169 operations"
        )

    by_language = collections.Counter(str(row["language"]) for row in matrix_rows)
    by_family = collections.Counter(str(row["family"]) for row in matrix_rows)
    return {
        "schema": "baxy.mvp-catalog-routing-matrix.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "reviewed_seen_routes_not_blind_provider_execution",
        "program_sha256": file_sha256(Path(__file__)),
        "sources": {
            "scenarios": str(SCENARIOS.relative_to(REPO)),
            "scenarios_sha256": file_sha256(SCENARIOS),
            "mind_report": str(mind_report.relative_to(REPO)),
            "mind_report_sha256": file_sha256(mind_report),
            "memory_trx": str(memory_trx.relative_to(REPO)),
            "memory_trx_sha256": file_sha256(memory_trx),
            "catalog_sha256": EXPECTED_CATALOG_SHA256,
        },
        "metrics": {
            "operations": 169,
            "routing_passed": 169,
            "routing_failed": 0,
            "unsafe_effects": 0,
            "mind_routes": 158,
            "app_memory_routes": 11,
            "by_language": dict(sorted(by_language.items())),
            "by_family": dict(sorted(by_family.items())),
        },
        "rows": sorted(matrix_rows, key=lambda row: str(row["operation"])),
        "effects_executed": 0,
        "routing_gate_passed": True,
        "provider_execution_gate_passed": False,
        "overall_mvp_gate_passed": False,
        "status": "routing_passed_provider_execution_pending",
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite existing evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mind-report", type=Path, default=MIND_REPORT)
    parser.add_argument("--memory-trx", type=Path, default=MEMORY_TRX)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.mind_report.resolve(), args.memory_trx.resolve())
    write_json_atomic(args.output.resolve(), report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "routing_passed": report["metrics"]["routing_passed"],
                "provider_execution_pending": not report[
                    "provider_execution_gate_passed"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
