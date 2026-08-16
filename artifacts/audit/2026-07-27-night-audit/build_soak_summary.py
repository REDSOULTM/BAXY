"""Build compact final metrics from the completed core and mind soaks."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def resource_summary(
    samples: list[dict[str, Any]], segment_key: str = "segment"
) -> dict[str, Any]:
    by_segment: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_segment[int(sample[segment_key])].append(sample)
    fields = ("rssBytes", "privateBytes", "handles", "threads")
    overall = {
        field: {
            "minimum": min(float(sample[field]) for sample in samples),
            "maximum": max(float(sample[field]) for sample in samples),
        }
        for field in fields
    }
    segments = []
    for segment, values in sorted(by_segment.items()):
        segments.append(
            {
                "segment": segment,
                "samples": len(values),
                "first": {field: values[0][field] for field in fields},
                "last": {field: values[-1][field] for field in fields},
                "maximum": {
                    field: max(float(value[field]) for value in values)
                    for field in fields
                },
            }
        )
    return {"samples": len(samples), "overall": overall, "segments": segments}


def core_summary(core: dict[str, Any]) -> dict[str, Any]:
    aggregate = core["aggregate"]
    operation_calls = sum(int(item["calls"]) for item in aggregate.values())
    weighted_seconds = sum(
        int(item["calls"]) * float(item["meanSeconds"])
        for item in aggregate.values()
    )
    statuses: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    for item in aggregate.values():
        statuses.update({key: int(value) for key, value in item["statuses"].items()})
        errors.update({key: int(value) for key, value in item["errors"].items()})
    return {
        "running": core["running"],
        "startedUtc": core["startedUtc"],
        "checkpointUtc": core["checkpointUtc"],
        "deadline": core["deadline"],
        "elapsedSeconds": core["elapsedSeconds"],
        "coreVersion": core["coreVersion"],
        "catalogCount": core["catalogCount"],
        "calls": core["calls"],
        "aggregateOperationCalls": operation_calls,
        "operationsSampled": len(aggregate),
        "statuses": dict(statuses),
        "expectedErrors": dict(errors),
        "weightedMeanSeconds": weighted_seconds / operation_calls,
        "maximumSeconds": max(
            float(item["maxSeconds"]) for item in aggregate.values()
        ),
        "anomalies": core["anomalies"],
        "segments": core["segments"],
        "resources": resource_summary(core["resourceSamples"]),
        "finalError": core["finalError"],
    }


def mind_summary(mind: dict[str, Any]) -> dict[str, Any]:
    calls = mind["calls"]
    elapsed = [float(call["elapsedSeconds"]) for call in calls]
    by_text: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call in calls:
        by_text[str(call["text"])].append(call)
    cases = []
    for text, values in by_text.items():
        matched = sum(bool(value["matched"]) for value in values)
        case_elapsed = [float(value["elapsedSeconds"]) for value in values]
        cases.append(
            {
                "text": text,
                "runs": len(values),
                "matched": matched,
                "mismatched": len(values) - matched,
                "matchRate": matched / len(values),
                "meanSeconds": statistics.fmean(case_elapsed),
                "p95Seconds": percentile(case_elapsed, 0.95),
                "maximumSeconds": max(case_elapsed),
            }
        )
    cases.sort(key=lambda item: item["text"])
    return {
        "running": mind["running"],
        "startedUtc": mind["startedUtc"],
        "checkpointUtc": mind["checkpointUtc"],
        "deadline": mind["deadline"],
        "coreVersion": mind["coreVersion"],
        "catalogCount": mind["catalogCount"],
        "intervalSeconds": mind["intervalSeconds"],
        "decisions": len(calls),
        "matched": mind["aggregate"]["matched"],
        "mismatched": mind["aggregate"]["mismatched"],
        "matchRate": mind["aggregate"]["matched"] / len(calls),
        "protocolAnomalies": mind["aggregate"]["protocolAnomalies"],
        "meanSeconds": statistics.fmean(elapsed),
        "p95Seconds": percentile(elapsed, 0.95),
        "maximumSeconds": max(elapsed),
        "cases": cases,
        "segments": mind["segments"],
        "resources": resource_summary(mind["resourceSamples"]),
        "finalError": mind["finalError"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--mind", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-running", action="store_true")
    args = parser.parse_args()
    core = json.loads(args.core.read_text(encoding="utf-8"))
    mind = json.loads(args.mind.read_text(encoding="utf-8"))
    if not args.allow_running and (core["running"] or mind["running"]):
        raise SystemExit("both soaks must be complete unless --allow-running is used")
    report = {
        "schema": "baxy.audit.soak-summary.v1",
        "core": core_summary(core),
        "mind": mind_summary(mind),
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "coreCalls": report["core"]["calls"],
                "coreAnomalies": len(report["core"]["anomalies"]),
                "coreSegments": len(report["core"]["segments"]),
                "mindDecisions": report["mind"]["decisions"],
                "mindMatchRate": report["mind"]["matchRate"],
                "mindProtocolAnomalies": report["mind"]["protocolAnomalies"],
                "mindSegments": len(report["mind"]["segments"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
