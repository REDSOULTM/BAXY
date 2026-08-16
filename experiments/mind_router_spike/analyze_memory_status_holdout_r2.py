"""Analyze the sealed memory-status R2 TRX exactly once."""

from __future__ import annotations

import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts import build_memory_status_holdout_r2 as campaign  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


TRX_NAMESPACE = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"
TEST_PREFIX = "RoutesBlindMemoryStatusR2Requests("


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if campaign.RESULT.exists():
        raise RuntimeError("refusing to overwrite memory R2 result")
    prereg = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    sources = prereg["sources"]
    expected_hashes = {
        campaign.OUTPUT: sources["corpus_sha256"],
        Path(campaign.__file__).resolve(): sources["builder_sha256"],
        campaign.PARSER: sources["parser_sha256"],
        campaign.TEST_SOURCE: sources["test_sha256"],
        campaign.ANALYZER: sources["analyzer_sha256"],
    }
    if any(sha256(path) != expected for path, expected in expected_hashes.items()):
        raise RuntimeError("memory R2 source hashes changed after preregistration")
    corpus = [
        json.loads(line)
        for line in campaign.OUTPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected_ids = {str(row["case_id"]) for row in corpus}
    root = ET.parse(campaign.TRX).getroot()
    namespace = {"t": TRX_NAMESPACE}
    results = root.findall(".//t:UnitTestResult", namespace)
    observed_ids: set[str] = set()
    passed = 0
    for result in results:
        name = str(result.get("testName") or "")
        if not name.startswith(TEST_PREFIX) or not name.endswith(")"):
            raise RuntimeError(f"unexpected memory R2 test: {name}")
        case_id = name[len(TEST_PREFIX) : -1]
        observed_ids.add(case_id)
        passed += result.get("outcome") == "Passed"
    if observed_ids != expected_ids or len(results) != campaign.EXPECTED_CASES:
        raise RuntimeError("memory R2 TRX is not bound to the sealed population")
    failed = campaign.EXPECTED_CASES - passed
    accuracy = passed / campaign.EXPECTED_CASES
    lower = math.pow(0.05, 1.0 / campaign.EXPECTED_CASES) if failed == 0 else None
    threshold_passed = accuracy >= 0.99 and lower is not None and lower >= 0.99
    report = {
        "schema": "baxy.memory-status-holdout-result.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "blind_holdout": True,
        "effects_executed": 0,
        "cases": campaign.EXPECTED_CASES,
        "exact": passed,
        "failed": failed,
        "accuracy": accuracy,
        "unsafe_effects": 0,
        "one_sided_95_binomial_lower_if_zero_failures": lower,
        "threshold_passed": threshold_passed,
        "sources": {
            "preregistration_sha256": sha256(campaign.PREREGISTRATION),
            "trx_sha256": sha256(campaign.TRX),
        },
    }
    write_json_atomic(campaign.RESULT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if threshold_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
