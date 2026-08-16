"""Build an evidence-indexed operation coverage report for the night audit."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def iter_documents(path: Path) -> list[Any]:
    try:
        if path.suffix.lower() == ".jsonl":
            return [
                json.loads(line)
                for line in path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
        return [json.loads(path.read_text(encoding="utf-8-sig"))]
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []


def terminal_record(
    operation: str,
    response: dict[str, Any],
    source: str,
    kind: str,
) -> dict[str, Any] | None:
    status = response.get("status")
    if status not in {"completed", "failed", "pending", "rejected"}:
        return None
    return {
        "operation": operation,
        "status": status,
        "verified": response.get("verified"),
        "error": response.get("errorCode"),
        "source": source,
        "kind": kind,
    }


def scan_node(
    node: Any,
    source: str,
    records: list[dict[str, Any]],
) -> None:
    if isinstance(node, list):
        for item in node:
            scan_node(item, source, records)
        return
    if not isinstance(node, dict):
        return

    response_groups = {
        "capture_responses": "capture.screenshot",
        "ocr_responses_sanitized": "ocr.read",
        "vision_responses_sanitized": "vision.describe",
    }
    for key, mapped_operation in response_groups.items():
        responses = node.get(key)
        if isinstance(responses, list) and responses:
            response = responses[-1]
            if isinstance(response, dict):
                record = terminal_record(
                    mapped_operation,
                    response,
                    source,
                    "named-response-group",
                )
                if record is not None:
                    records.append(record)

    core_operation = node.get("core_operation")
    core_status = node.get("core_status")
    if isinstance(core_operation, str) and core_status in {
        "completed",
        "failed",
        "pending",
        "rejected",
    }:
        records.append(
            {
                "operation": core_operation,
                "status": core_status,
                "verified": node.get("core_verified"),
                "error": node.get("core_error"),
                "source": source,
                "kind": "portable-core-summary",
            }
        )

    operation = node.get("operation")
    if isinstance(operation, str):
        if node.get("terminal_status") in {
            "completed",
            "failed",
            "pending",
            "rejected",
        }:
            records.append(
                {
                    "operation": operation,
                    "status": node["terminal_status"],
                    "verified": node.get("terminal_verified"),
                    "error": node.get("terminal_error"),
                    "source": source,
                    "kind": "sanitized-terminal-summary",
                }
            )
        responses = node.get("responses")
        if isinstance(responses, list) and responses:
            response = responses[-1]
            if isinstance(response, dict):
                record = terminal_record(operation, response, source, "operation-responses")
                if record is not None:
                    records.append(record)
        response = node.get("response")
        if isinstance(response, dict):
            record = terminal_record(operation, response, source, "operation-response")
            if record is not None:
                records.append(record)

    payload = node.get("payload")
    if (
        isinstance(payload, dict)
        and payload.get("phase") == "completed"
        and isinstance(payload.get("operation"), str)
        and isinstance(payload.get("response"), dict)
    ):
        record = terminal_record(
            payload["operation"],
            payload["response"],
            source,
            "authenticated-journal",
        )
        if record is not None:
            records.append(record)

    for value in node.values():
        scan_node(value, source, records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit_root = args.audit_root.resolve(strict=True)
    output = args.output.resolve()

    catalog_report = json.loads(
        (audit_root / "installed_catalog_smoke.json").read_text(encoding="utf-8-sig")
    )
    catalog = [case["operation"] for case in catalog_report["cases"]]
    risks = {case["operation"]: case["risk"] for case in catalog_report["cases"]}
    records: list[dict[str, Any]] = []

    for path in sorted(audit_root.iterdir()):
        if path == output or path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        documents = iter_documents(path)
        for document in documents:
            scan_node(document, path.name, records)

        if path.name == "installed_catalog_smoke.json":
            document = documents[0]
            for case in document.get("cases", []):
                provider = case.get("provider")
                if not isinstance(provider, dict):
                    continue
                records.append(
                    {
                        "operation": case["operation"],
                        "status": provider.get("status"),
                        "verified": provider.get("verified"),
                        "error": provider.get("error"),
                        "source": path.name,
                        "kind": "catalog-provider-probe",
                    }
                )

        if path.name == "overnight_soak_installed.json":
            document = documents[0]
            for operation, aggregate in document.get("aggregate", {}).items():
                for status, count in aggregate.get("statuses", {}).items():
                    records.append(
                        {
                            "operation": operation,
                            "status": status,
                            "verified": status == "completed",
                            "error": None,
                            "source": path.name,
                            "kind": "soak-aggregate",
                            "count": count,
                        }
                    )
                for error, count in aggregate.get("errors", {}).items():
                    records.append(
                        {
                            "operation": operation,
                            "status": "failed",
                            "verified": False,
                            "error": error,
                            "source": path.name,
                            "kind": "soak-error-aggregate",
                            "count": count,
                        }
                    )

    by_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["operation"] in risks:
            by_operation[record["operation"]].append(record)

    operations: list[dict[str, Any]] = []
    for operation in catalog:
        evidence = by_operation.get(operation, [])
        statuses = sorted({record["status"] for record in evidence if record["status"]})
        errors = sorted({record["error"] for record in evidence if record["error"]})
        sources = sorted({record["source"] for record in evidence})
        operations.append(
            {
                "operation": operation,
                "risk": risks[operation],
                "functionally_exercised": bool(evidence),
                "has_verified_success": any(
                    record["status"] == "completed" and record["verified"] is True
                    for record in evidence
                ),
                "has_safe_failure": any(
                    record["status"] in {"failed", "rejected"}
                    and record["verified"] is False
                    for record in evidence
                ),
                "statuses": statuses,
                "errors": errors,
                "sources": sources,
            }
        )

    exercised = [item for item in operations if item["functionally_exercised"]]
    verified = [item for item in operations if item["has_verified_success"]]
    unexercised = [item for item in operations if not item["functionally_exercised"]]
    report = {
        "schema": "baxy.audit.operation-coverage.v1",
        "catalog_count": len(catalog),
        "functional_exercised_count": len(exercised),
        "verified_success_count": len(verified),
        "unexercised_count": len(unexercised),
        "unexercised_by_risk": {
            risk: [
                item["operation"]
                for item in unexercised
                if item["risk"] == risk
            ]
            for risk in sorted({item["risk"] for item in unexercised})
        },
        "operations": operations,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "catalog_count": report["catalog_count"],
                "functional_exercised_count": report["functional_exercised_count"],
                "verified_success_count": report["verified_success_count"],
                "unexercised_count": report["unexercised_count"],
                "unexercised_by_risk": report["unexercised_by_risk"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
