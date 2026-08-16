"""A/B exact cross-request reuse of validated G/L/V/C inferences.

Each arm starts a fresh canonical sidecar and submits the same frozen,
effect-free ``turn.decide`` messages three times.  The baseline disables only
the owned-runtime verifier reuse cache; the candidate is the product default. No
Core operation is dispatched.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    build_workload,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    validate_reply,
    write_json_atomic,
)


DEFAULT_OUTPUT = (
    REPO
    / "artifacts"
    / "fixes"
    / "validated_inference_reuse_ab_20260730.json"
)
DEFAULT_CASES = frozenset({"turn-00", "turn-28"})


def _canonical_sha256(value: object) -> str:
    wire = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


def _decision_projection(reply: dict[str, Any]) -> dict[str, Any]:
    plan = reply.get("plan")
    operations: list[str] = []
    if isinstance(plan, dict) and isinstance(plan.get("steps"), list):
        operations = [
            str(step.get("operation"))
            for step in plan["steps"]
            if isinstance(step, dict)
            and isinstance(step.get("operation"), str)
        ]
    return {
        "kind": reply.get("kind"),
        "operation": reply.get("operation"),
        "plan_operations": operations,
        "conversation_kind": reply.get("conversation_kind"),
        "effect_verification": reply.get("effect_verification"),
        "response_language": reply.get("response_language"),
        "turn_attempts": reply.get("turn_attempts"),
    }


def _effect_projection(reply: dict[str, Any]) -> dict[str, Any]:
    decision = _decision_projection(reply)
    operations = list(decision["plan_operations"])
    operation = decision["operation"]
    if isinstance(operation, str) and operation:
        operations.append(operation)
    effect_operations = reply.get("effectOperations")
    if isinstance(effect_operations, list):
        operations.extend(
            item
            for item in effect_operations
            if isinstance(item, str) and item
        )
    return {
        "kind": decision["kind"],
        "operations": sorted(set(operations)),
    }


def _semantic_reply_sha256(reply: dict[str, Any]) -> str:
    ignored = {
        "id",
        "turn_attempts",
        "turn_recovery",
        "recovery_attempts",
    }
    return _canonical_sha256(
        {key: value for key, value in reply.items() if key not in ignored}
    )


def _visible_reply_sha256(reply: dict[str, Any]) -> str | None:
    field = "question" if reply.get("kind") == "clarify" else "reply"
    value = reply.get(field)
    if not isinstance(value, str):
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sidecar_without_reuse() -> int:
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__

    def initialize_without_reuse(self: LlmRuntime) -> None:
        original_init(self)
        self._validated_classifier_reuse_enabled = False

    LlmRuntime.__init__ = initialize_without_reuse
    return sidecar_module.main()


def _run_arm(
    arm: str,
    *,
    selected_cases: frozenset[str],
    repetitions: int,
) -> dict[str, Any]:
    resolved = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        resolved,
        gpu_layers=resolved.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    command = [str(resolved.python), "-u", "-X", "utf8"]
    if arm == "baseline":
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-without-reuse",
            ]
        )
    else:
        command.extend(["-m", "baxy_mind"])

    workload = [
        item
        for item in build_workload()
        if item.request_type == "turn.decide"
        and item.case_id in selected_cases
    ]
    if {item.case_id for item in workload} != set(selected_cases):
        raise ValueError("faltan casos congelados para el A/B")

    client = JsonLineProcess(command, environment=environment, cwd=REPO)
    observations: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar hello rejected")
        catalog = client.request(
            {
                "type": "catalog.configure",
                "id": f"catalog-classifier-reuse-{arm}",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if catalog.get("type") != "catalog.ready":
            raise RuntimeError("catalog handshake rejected")

        for item in workload:
            for repetition in range(1, repetitions + 1):
                started = time.perf_counter()
                reply = client.request(item.message, limits["turn.decide"])
                elapsed = time.perf_counter() - started
                observations.append(
                    {
                        "case_id": item.case_id,
                        "repetition": repetition,
                        "elapsed_seconds": round(elapsed, 4),
                        "validation_error": validate_reply(item, reply) or None,
                        "decision": _decision_projection(reply),
                        "effect_projection_sha256": _canonical_sha256(
                            _effect_projection(reply)
                        ),
                        "semantic_reply_sha256": _semantic_reply_sha256(reply),
                        "visible_reply_sha256": _visible_reply_sha256(reply),
                    }
                )
                print(
                    f"{arm} {item.case_id} #{repetition}: "
                    f"{elapsed:.4f}s {reply.get('kind')}",
                    flush=True,
                )
    finally:
        client.close(
            graceful_message={
                "type": "shutdown",
                "id": f"shutdown-classifier-reuse-{arm}",
            },
            timeout=limits["shutdown"],
        )

    warm = [
        float(row["elapsed_seconds"])
        for row in observations
        if int(row["repetition"]) > 1
    ]
    return {
        "arm": arm,
        "observations": observations,
        "warm_latency_seconds": {
            "count": len(warm),
            "p50": round(statistics.median(warm), 4),
            "max": round(max(warm), 4),
            "total": round(sum(warm), 4),
        },
        "validation_errors": sum(
            row["validation_error"] is not None for row in observations
        ),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    order = tuple(part.strip() for part in args.arm_order.split(","))
    if sorted(order) != ["baseline", "candidate"]:
        raise ValueError("--arm-order debe contener baseline,candidate")
    cases = frozenset(args.case or DEFAULT_CASES)
    resolved = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    arms = [
        _run_arm(
            arm,
            selected_cases=cases,
            repetitions=args.repetitions,
        )
        for arm in order
    ]
    by_arm = {str(arm["arm"]): arm for arm in arms}
    baseline_rows = {
        (str(row["case_id"]), int(row["repetition"])): row
        for row in by_arm["baseline"]["observations"]
    }
    candidate_rows = {
        (str(row["case_id"]), int(row["repetition"])): row
        for row in by_arm["candidate"]["observations"]
    }
    shared = sorted(set(baseline_rows) & set(candidate_rows))
    exact = all(
        baseline_rows[key]["decision"] == candidate_rows[key]["decision"]
        and baseline_rows[key]["effect_projection_sha256"]
        == candidate_rows[key]["effect_projection_sha256"]
        and baseline_rows[key]["semantic_reply_sha256"]
        == candidate_rows[key]["semantic_reply_sha256"]
        and baseline_rows[key]["visible_reply_sha256"]
        == candidate_rows[key]["visible_reply_sha256"]
        for key in shared
    )
    baseline_warm = by_arm["baseline"]["warm_latency_seconds"]
    candidate_warm = by_arm["candidate"]["warm_latency_seconds"]
    return {
        "schema": "baxy.validated-inference-reuse-ab.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "arm_order": list(order),
        "runtime": public_runtime_identity(resolved),
        "effect_free": True,
        "core_operations_dispatched": 0,
        "cases": sorted(cases),
        "repetitions": args.repetitions,
        "control": {
            "only_variable": "owned-runtime exact G/L/V/C reuse cache",
            "fresh_server_per_arm": True,
            "baseline_reuse_enabled": False,
            "candidate_reuse_enabled": True,
        },
        "arms": arms,
        "comparison": {
            "all_rows_paired": len(shared)
            == len(baseline_rows)
            == len(candidate_rows),
            "exact_outputs": exact,
            "candidate_minus_baseline_warm_p50_seconds": round(
                float(candidate_warm["p50"]) - float(baseline_warm["p50"]),
                4,
            ),
            "candidate_minus_baseline_warm_max_seconds": round(
                float(candidate_warm["max"]) - float(baseline_warm["max"]),
                4,
            ),
            "candidate_minus_baseline_warm_total_seconds": round(
                float(candidate_warm["total"])
                - float(baseline_warm["total"]),
                4,
            ),
            "validation_clean": (
                by_arm["baseline"]["validation_errors"] == 0
                and by_arm["candidate"]["validation_errors"] == 0
            ),
        },
        "candidate_status": "requires_opposite_order",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--arm-order",
        default="baseline,candidate",
    )
    parser.add_argument("--case", action="append")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--sidecar-without-reuse",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sidecar_without_reuse:
        return _sidecar_without_reuse()
    if not 2 <= args.repetitions <= 5:
        raise SystemExit("--repetitions debe estar entre 2 y 5")
    report = run(args)
    write_json_atomic(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "comparison": report["comparison"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
