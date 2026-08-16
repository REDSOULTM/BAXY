"""Attribute R4 perfect-nomination failures to product pipeline stages."""

from __future__ import annotations

import argparse
import collections
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = (
    REPO
    / "artifacts"
    / "research"
    / "mtop_product_validation_development_r10_operation_oracle.json"
)
DEFAULT_AUDIT = (
    REPO
    / "artifacts"
    / "research"
    / "mtop_product_validation_development_r10_operation_oracle.raw.jsonl"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts"
    / "research"
    / "mtop_operation_oracle_pipeline_analysis_r1.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def _load_terminal_audits(path: Path) -> dict[str, dict[str, Any]]:
    terminal_by_request: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid audit JSONL line {line_number}") from error
            if not isinstance(row, dict) or row.get("phase") not in {
                "final",
                "recovery",
            }:
                continue
            request_id = row.get("request_id")
            if not isinstance(request_id, str):
                raise ValueError(f"invalid final audit request id at line {line_number}")
            terminal_by_request[request_id] = row
    return terminal_by_request


def _first_removed_stage(audit: dict[str, Any]) -> str | None:
    raw = audit.get("raw_decision")
    if not isinstance(raw, dict) or not raw.get("effect_operations"):
        return None
    previous = list(raw["effect_operations"])
    for stage in audit.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        current = list(stage.get("effect_operations") or [])
        if previous and not current:
            return str(stage.get("name") or "unknown")
        previous = current
    return None


def _counter_rows(counter: collections.Counter[str]) -> list[dict[str, Any]]:
    return [
        {"name": name, "cases": count}
        for name, count in counter.most_common()
    ]


def analyze(*, report_path: Path, audit_path: Path) -> dict[str, Any]:
    report = _load_json(report_path)
    samples = report.get("samples")
    if not isinstance(samples, list) or len(samples) != 198:
        raise ValueError("the operation-oracle report must contain exactly 198 rows")
    audits = _load_terminal_audits(audit_path)
    rows: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError("the operation-oracle report contains an invalid row")
        request_id = f"mtop-validation-{index}"
        audit = audits.get(request_id)
        if audit is None:
            raise ValueError(f"missing final audit for {request_id}")
        assessment = sample.get("assessment")
        expected = sample.get("expected")
        projection = sample.get("projection")
        final = audit.get("final")
        if not all(
            isinstance(value, dict)
            for value in (assessment, expected, projection, final)
        ):
            raise ValueError(f"invalid report or audit structure for {request_id}")
        if (
            assessment["observed_kind"] != final["kind"]
            or assessment["observed_intent_operations"]
            != final["intent_operations"]
            or assessment["observed_effect_operations"]
            != final["effect_operations"]
        ):
            raise ValueError(f"report/audit mismatch for {request_id}")
        operation = (
            str(expected["intent_operations"][0])
            if expected["intent_operations"]
            else "__none__"
        )
        removed_stage = _first_removed_stage(audit)
        disposition = str(projection["disposition"])
        observed_kind = str(assessment["observed_kind"])
        if bool(assessment["exact"]):
            cause = "correct"
        elif audit.get("phase") == "recovery":
            recovery = audit.get("recovery")
            failure_kinds = (
                recovery.get("failure_kinds")
                if isinstance(recovery, dict)
                else None
            )
            suffix = (
                "+".join(str(value) for value in failure_kinds)
                if isinstance(failure_kinds, list) and failure_kinds
                else "unknown"
            )
            cause = f"runtime_recovery:{suffix}"
        elif removed_stage is not None:
            cause = f"effect_removed:{removed_stage}"
        elif disposition == "candidate_missing_information" and observed_kind in {
            "action",
            "plan",
        }:
            cause = "missing_information_overgrounded"
        elif not bool(assessment["intent_exact"]):
            cause = "intent_identity_lost"
        elif not bool(assessment["kind_exact"]):
            cause = f"kind_mismatch:{observed_kind}"
        elif not bool(assessment["effect_exact"]):
            cause = "effect_mismatch"
        else:
            cause = "other"
        rows.append(
            {
                "request_id": request_id,
                "source_id": sample["source_id"],
                "locale": sample["locale"],
                "text": sample["text"],
                "disposition": disposition,
                "operation": operation,
                "cause": cause,
                "audit_terminal_phase": audit.get("phase"),
                "first_effect_removal_stage": removed_stage,
                "expected_kinds": expected["kinds"],
                "observed_kind": observed_kind,
                "intent_exact": assessment["intent_exact"],
                "effect_exact": assessment["effect_exact"],
                "kind_exact": assessment["kind_exact"],
                "exact": assessment["exact"],
            }
        )
    causes = collections.Counter(str(row["cause"]) for row in rows)
    removal_stages = collections.Counter(
        str(row["first_effect_removal_stage"])
        for row in rows
        if row["first_effect_removal_stage"] is not None
    )
    failures_by_operation = collections.Counter(
        str(row["operation"]) for row in rows if not row["exact"]
    )
    by_disposition: dict[str, Any] = {}
    for disposition in sorted({str(row["disposition"]) for row in rows}):
        subset = [row for row in rows if row["disposition"] == disposition]
        exact = sum(bool(row["exact"]) for row in subset)
        by_disposition[disposition] = {
            "cases": len(subset),
            "exact": exact,
            "exact_accuracy": round(exact / len(subset), 6),
            "causes": _counter_rows(
                collections.Counter(str(row["cause"]) for row in subset)
            ),
        }
    return {
        "schema": "baxy.mtop-operation-oracle-pipeline-analysis.v1",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "side_effect_free": True,
        "source": {
            "report": str(report_path.resolve()),
            "audit": str(audit_path.resolve()),
            "cases": len(rows),
        },
        "summary": {
            "exact": sum(bool(row["exact"]) for row in rows),
            "causes": _counter_rows(causes),
            "first_effect_removal_stages": _counter_rows(removal_stages),
            "failures_by_operation": _counter_rows(failures_by_operation),
        },
        "by_disposition": by_disposition,
        "failures": [row for row in rows if not row["exact"]],
        "samples": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = analyze(report_path=args.report, audit_path=args.audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "summary": result["summary"],
                "by_disposition": result["by_disposition"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
