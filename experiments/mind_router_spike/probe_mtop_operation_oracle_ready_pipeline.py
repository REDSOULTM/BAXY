"""Measure perfect R4 nomination through the final pre-Core grounding stage.

The probe is side-effect-free.  It sends ``turn.decide`` and then, only when
the turn preserves a requested effect, sends either ``arguments`` or ``plan``.
It never sends a plan or an operation to Core.  A case is ``ready`` only after
the real mind returns schema-validated literal arguments or a complete plan;
otherwise it must clarify or abstain according to the development oracle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
for path in (REPO, SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
from experiments.mind_router_spike.probe_mtop_product_validation import (  # noqa: E402
    expected_turn,
    select_validation_rows,
    terminal_user_operations,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


DEFAULT_ORACLE = (
    REPO
    / "artifacts"
    / "research"
    / "mtop_product_validation_development_r4_operation_oracle.json"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts"
    / "research"
    / "mtop_operation_oracle_ready_pipeline_r1.json"
)
ORACLE_ENV = "BAXY_EXPERIMENT_MTOP_OPERATION_ORACLE"
VERIFICATION_ENV = "BAXY_EXPERIMENT_MTOP_ORACLE_VERIFICATION"


def _percentile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    return round(ordered[round((len(ordered) - 1) * probability)], 6)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _logical_expected(disposition: str) -> str:
    if disposition == "candidate":
        return "ready"
    if disposition == "candidate_missing_information":
        return "clarify"
    return "conversation"


def _terminal_plan_operations(reply: dict[str, Any]) -> list[str]:
    steps = reply.get("steps")
    if not isinstance(steps, list):
        return []
    operations = [
        str(step.get("operation") or "")
        for step in steps
        if isinstance(step, dict)
    ]
    if len(operations) != len(steps) or any(not value for value in operations):
        return []
    return list(terminal_user_operations(operations))


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    exact = sum(bool(row["exact"]) for row in rows)
    turn_latencies = [float(row["turn_seconds"]) for row in rows]
    total_latencies = [float(row["total_seconds"]) for row in rows]
    outcomes: dict[str, int] = {}
    for row in rows:
        outcome = str(row["observed_outcome"])
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return {
        "cases": total,
        "exact": exact,
        "exact_accuracy": round(exact / total, 6),
        "observed_outcomes": dict(sorted(outcomes.items())),
        "turn_latency_seconds": {
            "p50": _percentile(turn_latencies, 0.50),
            "p95": _percentile(turn_latencies, 0.95),
        },
        "ready_pipeline_latency_seconds": {
            "p50": _percentile(total_latencies, 0.50),
            "p95": _percentile(total_latencies, 0.95),
            "maximum": round(max(total_latencies), 6),
        },
    }


def run(
    *,
    oracle: Path,
    output: Path,
    groups_per_stratum: int,
    mind_module: str,
    audit: Path | None,
) -> dict[str, Any]:
    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    selected = select_validation_rows(rows, groups_per_stratum=groups_per_stratum)
    if len(selected) != 198:
        raise ValueError("the R4 ready-pipeline population is not exactly 198")
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = {str(item.get("name") or "") for item in capabilities}
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment[ORACLE_ENV] = str(oracle.resolve(strict=True))
    environment[VERIFICATION_ENV] = "recovered"
    if audit is not None:
        if audit.exists():
            raise RuntimeError(f"refusing to append to existing audit: {audit}")
        environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(audit.resolve())
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", mind_module],
        environment=environment,
        cwd=REPO,
    )
    measured: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("mind sidecar did not publish hello")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "mtop-ready-pipeline-catalog",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("mind sidecar rejected the authenticated catalog")
        client.request(
            {
                "type": "turn.decide",
                "id": "mtop-ready-pipeline-warmup",
                "text": "hola, responde brevemente",
                "history": [],
            },
            limits["turn.decide"],
        )
        for index, row in enumerate(selected):
            expected = expected_turn(row)
            expected_operations = list(expected["intent_operations"])
            if any(operation not in catalog_names for operation in expected_operations):
                raise ValueError("R4 references an operation absent from the catalog")
            started = time.perf_counter()
            turn_started = time.perf_counter()
            turn = client.request(
                {
                    "type": "turn.decide",
                    "id": f"mtop-validation-{index}",
                    "text": row["text"],
                    "history": [],
                },
                limits["turn.decide"],
            )
            turn_seconds = time.perf_counter() - turn_started
            turn_kind = str(turn.get("kind") or "")
            turn_intents = list(turn.get("intentOperations") or [])
            turn_effects = list(turn.get("effectOperations") or [])
            observed_outcome = "invalid_turn"
            downstream: dict[str, Any] | None = None
            terminal_operations: list[str] = []
            if turn_kind == "conversation":
                observed_outcome = "conversation"
            elif turn_kind == "clarify":
                observed_outcome = "clarify"
            elif turn_kind == "action" and isinstance(turn.get("operation"), str):
                operation = str(turn["operation"])
                downstream = client.request(
                    {
                        "type": "arguments",
                        "id": f"mtop-ready-arguments-{index}",
                        "operation": operation,
                        "text": row["text"],
                    },
                    limits["arguments"],
                )
                if downstream.get("type") == "arguments.result":
                    if downstream.get("ok") is True and isinstance(
                        downstream.get("arguments"), dict
                    ):
                        observed_outcome = "ready"
                        terminal_operations = [operation]
                    elif downstream.get("ok") is False and isinstance(
                        downstream.get("question"), str
                    ) and str(downstream["question"]).strip():
                        observed_outcome = "clarify"
                    else:
                        observed_outcome = "invalid_arguments_result"
                else:
                    observed_outcome = "arguments_error"
            elif turn_kind == "plan" and turn_effects:
                downstream = client.request(
                    {
                        "type": "plan",
                        "id": f"mtop-ready-plan-{index}",
                        "text": row["text"],
                        "history": [],
                        "expectedOperations": turn_effects,
                    },
                    60.0,
                )
                if downstream.get("type") == "plan.result":
                    plan_kind = str(downstream.get("kind") or "")
                    if plan_kind == "plan":
                        terminal_operations = _terminal_plan_operations(downstream)
                        observed_outcome = "ready"
                    elif plan_kind == "clarify" and isinstance(
                        downstream.get("question"), str
                    ) and str(downstream["question"]).strip():
                        observed_outcome = "clarify"
                    else:
                        observed_outcome = f"plan_{plan_kind or 'invalid'}"
                else:
                    observed_outcome = "plan_error"
            expected_outcome = _logical_expected(str(row["projection"]["disposition"]))
            operation_conserved = (
                terminal_operations == expected_operations
                if observed_outcome == "ready"
                else turn_intents == expected_operations
                if expected_operations
                else not turn_intents and not turn_effects
            )
            exact = observed_outcome == expected_outcome and operation_conserved
            measured.append(
                {
                    "source_id": row["source_id"],
                    "mission_id": row["mission_id"],
                    "locale": row["locale"],
                    "text": row["text"],
                    "semantic": row["semantic"],
                    "projection": row["projection"],
                    "expected_operations": expected_operations,
                    "expected_outcome": expected_outcome,
                    "observed_outcome": observed_outcome,
                    "operation_conserved": operation_conserved,
                    "turn": {
                        "kind": turn_kind,
                        "intent_operations": turn_intents,
                        "effect_operations": turn_effects,
                    },
                    "downstream": downstream,
                    "turn_seconds": round(turn_seconds, 6),
                    "total_seconds": round(time.perf_counter() - started, 6),
                    "exact": exact,
                }
            )
    finally:
        client.close(
            graceful_message={
                "type": "shutdown",
                "id": "mtop-ready-pipeline-shutdown",
            },
            timeout=limits["shutdown"],
        )
    mtop._assert_input_identity_stable(identity)
    summary = _summarize(measured)
    by_disposition = {
        disposition: _summarize(
            [
                item
                for item in measured
                if item["projection"]["disposition"] == disposition
            ]
        )
        for disposition in sorted(
            {str(item["projection"]["disposition"]) for item in measured}
        )
    }
    report = {
        "schema": "baxy.mtop-operation-oracle-ready-pipeline.development.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_validation_only_mtop_test_remains_sealed",
        "side_effect_free": True,
        "core_or_provider_requests_sent": 0,
        "source": {
            "corpus_sha256": identity.corpus.sha256,
            "manifest_sha256": identity.manifest.sha256,
            "map_sha256": manifest["source"]["map_sha256"],
            "oracle_sha256": _sha256(oracle),
            "groups_per_stratum": groups_per_stratum,
            "selected_rows": len(selected),
            "test_content_read": False,
            "mind_module": mind_module,
        },
        "runtime": public_runtime_identity(runtime),
        "summary": summary,
        "by_disposition": by_disposition,
        "failures": [item for item in measured if not item["exact"]],
        "samples": measured,
        "status": "passed" if summary["exact_accuracy"] >= 0.99 else "failed",
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--groups-per-stratum", type=int, default=8)
    parser.add_argument(
        "--mind-module",
        default="experiments.mind_router_spike.oracle_operation_mind_entrypoint",
    )
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    report = run(
        oracle=args.oracle,
        output=args.output,
        groups_per_stratum=args.groups_per_stratum,
        mind_module=args.mind_module,
        audit=args.audit,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                **report["summary"],
                "failures": len(report["failures"]),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
