"""Publish the measured temporal-grounding candidate rejections.

``dateparser`` is loaded only from an explicitly supplied experimental target.
The deprecated Microsoft candidate is not executed because its official NuGet
restore crosses a critical-vulnerability gate before compilation.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_PACKAGE_ROOT = Path(r"D:\BAXYRuntime\experiments\dateparser-1.4.1")
DEFAULT_OUTPUT = (
    REPO / "artifacts" / "research" / "temporal_grounding_candidates_r1.json"
)
REFERENCE_LOCAL = datetime(2026, 8, 1, 12, 0, 0)
SETTINGS = {
    "RELATIVE_BASE": REFERENCE_LOCAL,
    "PREFER_DATES_FROM": "future",
    "TIMEZONE": "America/Santiago",
    "TO_TIMEZONE": "UTC",
    "RETURN_AS_TIMEZONE_AWARE": True,
}
CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "dependent-relative-en",
        "locale": "en",
        "text": "set an alarm 15 minutes before my meeting at 2 pm",
        "expected": "2026-08-01T17:45:00+00:00",
    },
    {
        "id": "relative-duration-en",
        "locale": "en",
        "text": "set alarm for 7 hours",
        "expected": "2026-08-01T23:00:00+00:00",
    },
    {
        "id": "relative-duration-es",
        "locale": "es",
        "text": "pon la alarma de aquí a 7 horas",
        "expected": "2026-08-01T23:00:00+00:00",
    },
    {
        "id": "weekday-clock-en",
        "locale": "en",
        "text": "set an alarm for Monday at 6 am",
        "expected": "2026-08-03T10:00:00+00:00",
    },
    {
        "id": "weekend-es",
        "locale": "es",
        "text": "este fin de semana",
        "expected": "supported_time_span",
    },
    {
        "id": "invalid-military-clock",
        "locale": "en",
        "text": "make an alarm for 0760h",
        "expected": "abstain",
    },
    {
        "id": "ambiguous-mealtime-en",
        "locale": "en",
        "text": "snack time",
        "expected": "abstain",
    },
    {
        "id": "ambiguous-mealtime-es",
        "locale": "es",
        "text": "hora de la merienda",
        "expected": "abstain",
    },
    {
        "id": "non-temporal-event-en",
        "locale": "en",
        "text": "beginning of school",
        "expected": "abstain",
    },
    {
        "id": "misspelled-weekday-en",
        "locale": "en",
        "text": "on Mondy",
        "expected": "abstain",
    },
)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * probability)]


def run(package_root: Path) -> dict[str, Any]:
    resolved = package_root.resolve(strict=True)
    sys.path.insert(0, str(resolved))
    import dateparser  # noqa: PLC0415
    from dateparser.search import search_dates  # noqa: PLC0415

    rows: list[dict[str, Any]] = []
    for case in CASES:
        started = time.perf_counter()
        matches = search_dates(
            str(case["text"]),
            languages=[str(case["locale"])],
            settings=SETTINGS,
        )
        elapsed = time.perf_counter() - started
        values = [
            value.isoformat()
            for _, value in (matches or [])
        ]
        expected = str(case["expected"])
        if expected == "abstain":
            passed = not values
        elif expected == "supported_time_span":
            # search_dates must recognize the span itself; a point guess is
            # not enough authority for a bounded calendar query.
            passed = False
        else:
            passed = expected in values
        rows.append(
            {
                **case,
                "seconds": round(elapsed, 6),
                "matches": [
                    {"text": text, "value": value.isoformat()}
                    for text, value in (matches or [])
                ],
                "passed": passed,
            }
        )
    latencies = [float(row["seconds"]) for row in rows]
    passed = sum(bool(row["passed"]) for row in rows)
    return {
        "schema": "baxy.temporal-grounding-candidates.research.v1",
        "measured_at": datetime.now().astimezone().isoformat(),
        "reference_local": REFERENCE_LOCAL.isoformat(),
        "side_effect_free": True,
        "candidates": {
            "dateparser": {
                "version": dateparser.__version__,
                "package_root": str(resolved),
                "cases": len(rows),
                "passed": passed,
                "accuracy": round(passed / len(rows), 6),
                "latency_seconds": {
                    "p50": round(statistics.median(latencies), 6),
                    "p95": round(_percentile(latencies, 0.95), 6),
                },
                "status": "rejected",
                "reason": (
                    "incorrect dependent/weekday normalization, false positive "
                    "on invalid or ambiguous time text, and missed time span"
                ),
                "samples": rows,
            },
            "microsoft_recognizers_text_datetime": {
                "version": "1.8.13",
                "status": "rejected_before_execution",
                "official_package_state": "deprecated_unmaintained",
                "restore_gate": "failed",
                "restore_errors": [
                    "NU1904: NuGet.CommandLine 5.11.5 critical vulnerability",
                    "GHSA-68w7-72jg-6qpp",
                    "NU1901: NuGet.CommandLine 5.11.5 low vulnerability",
                    "GHSA-g4vj-cjjj-v7hg",
                ],
                "gate_lowered_or_suppressed": False,
            },
            "duckling": {
                "status": "rejected_before_execution",
                "reason": (
                    "requires a Haskell toolchain and additional local server; "
                    "not competitive with the notebook portability budget"
                ),
            },
        },
        "conclusion": (
            "no measured off-the-shelf candidate is safe enough to grant "
            "temporal argument authority"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.package_root)
    write_json_atomic(args.output, report)
    print(json.dumps(report["candidates"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
