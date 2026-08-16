#!/usr/bin/env python3
"""Replay explicitly named turn-policy cases for bounded diagnostics.

This tool never sends plans to Core or providers.  It exists so a failed full
gate can be diagnosed without paying for hundreds of unrelated model calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_turn_policy_gate as gate  # noqa: E402


def _load_specs(case_ids: list[str]) -> list[dict[str, Any]]:
    requested = set(case_ids)
    specs = {
        str(spec["case_id"]): spec
        for spec in gate.contextual_cases()
        if str(spec["case_id"]) in requested
    }
    with gate.DEFAULT_HOLDOUT.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            row = json.loads(raw_line)
            case_id = "holdout:" + str(row.get("source_id") or "")
            if case_id in requested:
                specs[case_id] = gate.holdout_case(row)
    missing = sorted(requested - set(specs))
    if missing:
        raise ValueError("case_id desconocido: " + ", ".join(missing))
    return [specs[case_id] for case_id in case_ids]


def _failure_stages(
    audit_path: Path,
    request_ids: set[str],
) -> dict[str, list[dict[str, str]]]:
    stages = {request_id: [] for request_id in request_ids}
    if not audit_path.is_file():
        return stages
    with audit_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            record = json.loads(raw_line)
            request_id = str(record.get("request_id") or "")
            if (
                request_id in stages
                and record.get("phase") == "attempt_failure"
            ):
                stages[request_id].append(
                    {
                        "failure_kind": str(record.get("failure_kind") or ""),
                        "failure_stage": str(record.get("failure_stage") or ""),
                        "failure_reason": str(record.get("failure_reason") or ""),
                        "error_type": str(record.get("error_type") or ""),
                    }
                )
    return stages


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe focal de casos concretos de turn.decide.",
    )
    parser.add_argument("--case-id", action="append", required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, default=gate.DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--arm", choices=("baseline", "evidence"), default="baseline")
    parser.add_argument("--request-timeout", type=float, default=75.0)
    parser.add_argument("--startup-timeout", type=float, default=240.0)
    parser.add_argument("--evidence-ready-timeout", type=float, default=900.0)
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output = args.output.resolve()
    audit = output.with_suffix(".raw.jsonl")
    if args.fresh:
        gate.remove_file_if_present(output)
        gate.remove_file_if_present(audit)
    elif output.exists() or audit.exists():
        raise FileExistsError("la salida ya existe; usa --fresh o una ruta nueva")

    specs = _load_specs(args.case_id)
    runtime_manifest = gate.read_runtime_manifest(args.runtime_manifest)
    gguf = Path(str(runtime_manifest.get("gguf") or "")).resolve(strict=True)
    llama_server = Path(
        str(runtime_manifest.get("llama_server") or "")
    ).resolve(strict=True)
    ngl = int(runtime_manifest.get("ngl") or 99)
    policy_identity = gate.load_one_sided_policy_identity(gate.DEFAULT_POLICY)
    catalog_configuration = gate.core_catalog_configuration(args.core)
    capabilities = catalog_configuration["capabilities"]
    evidence_cache = (
        Path(os.environ.get("LOCALAPPDATA", REPO))
        / "BAXYRuntime"
        / "turn-evidence"
    )
    overrides = {
        "BAXY_MIND_TURN_CORPUS": str(gate.DEFAULT_RUNTIME),
        "BAXY_MIND_TURN_EVIDENCE_CACHE": str(evidence_cache),
        "BAXY_MIND_TURN_EVIDENCE_POLICY": str(gate.DEFAULT_POLICY),
        "BAXY_MIND_TURN_AUDIT_PATH": str(audit),
        "BAXY_MIND_TURN_EVIDENCE_DISABLED": (
            "1" if args.arm == "baseline" else "0"
        ),
    }
    results: list[dict[str, Any]] = []
    with gate.MindClient(
        capabilities,
        application_catalog=catalog_configuration["applicationCatalog"],
        game_catalog=catalog_configuration["gameCatalog"],
        gguf=gguf,
        llama_server=llama_server,
        ngl=ngl,
        endpoint=None,
        environment_overrides=overrides,
        startup_timeout=args.startup_timeout,
    ) as client:
        gate.warm_sidecar(
            client,
            arm=args.arm,
            corpus_sha256=gate.file_sha256(gate.DEFAULT_RUNTIME),
            policy_identity=policy_identity,
            timeout=args.request_timeout,
            evidence_ready_timeout=args.evidence_ready_timeout,
        )
        for spec in specs:
            result = gate.measure_case(
                client,
                args.arm,
                spec,
                args.request_timeout,
            )
            results.append(
                {
                    "case_id": spec["case_id"],
                    "expected_modes": spec["expected_modes"],
                    "expected_families": spec["expected_families"],
                    "result": result,
                }
            )

    request_ids = {
        str(row["result"].get("audit_request_id") or "") for row in results
    }
    failures = _failure_stages(audit, request_ids)
    for row in results:
        request_id = str(row["result"].get("audit_request_id") or "")
        row["attempt_failures"] = failures.get(request_id, [])
    report = {
        "schema": "baxy.turn-policy-case-probe.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "status": "diagnostic_completed",
        "scope": "turn.decide_only_no_core_operations_or_provider_effects",
        "arm": args.arm,
        "effects_executed": 0,
        "cases": results,
        "summary": {
            "cases": len(results),
            "runtime_errors": sum(bool(row["result"]["error"]) for row in results),
            "recovery_cases": sum(
                int(row["result"]["recovery_attempts"] > 0) for row in results
            ),
            "attempt_failures": sum(len(row["attempt_failures"]) for row in results),
        },
        "audit": {
            "path": gate.repo_relative(audit),
            "sha256": gate.file_sha256(audit) if audit.is_file() else "",
            "contains_input_text": False,
        },
    }
    gate.write_json_atomic(output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"status={report['status']} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
