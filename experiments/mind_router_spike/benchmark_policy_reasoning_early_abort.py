"""ABBA preflight for aborting reasoning-first primary P streams.

Each arm reuses the frozen 30-turn diagnostic, starts a fresh sidecar and
llama-server, configures the authenticated Core catalog, and executes no
effects.  The candidate remains research-only even if this preflight passes:
reasoning-first is an empirical tail discriminator, not a proof that the
constrained decode cannot still finish with a valid decision.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "fixes"
    / "policy_reasoning_early_abort_ab_20260730.json"
)


def _gpu_snapshot() -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,pstate,clocks.current.sm,"
                "clocks.max.sm,power.draw,memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        values = [value.strip() for value in completed.stdout.split(",")]
        if len(values) != 6:
            return None
        return {
            "temperature_c": float(values[0]),
            "pstate": values[1],
            "sm_clock_mhz": float(values[2]),
            "sm_clock_max_mhz": float(values[3]),
            "power_w": float(values[4]),
            "memory_used_mib": float(values[5]),
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _decision_without_diagnostics(observation: dict[str, Any]) -> dict[str, Any]:
    decision = observation.get("decision")
    if not isinstance(decision, dict):
        return {}
    return {
        key: value
        for key, value in decision.items()
        if key not in {"turn_attempts", "policy_reasoning_early_aborts"}
    }


def _effect_identity(observation: dict[str, Any]) -> tuple[str, ...]:
    decision = observation.get("decision")
    if not isinstance(decision, dict):
        return ()
    operations: list[str] = []
    operation = decision.get("operation")
    if isinstance(operation, str) and operation:
        operations.append(operation)
    plan_operations = decision.get("plan_operations")
    if isinstance(plan_operations, list):
        operations.extend(
            item for item in plan_operations if isinstance(item, str) and item
        )
    return tuple(sorted(set(operations)))


def _is_effect(observation: dict[str, Any]) -> bool:
    decision = observation.get("decision")
    kind = decision.get("kind") if isinstance(decision, dict) else None
    return kind in {"action", "plan"} or bool(_effect_identity(observation))


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1),
    )
    return ordered[index]


def _compare(
    pair_id: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    base = {
        row["case_id"]: row
        for row in baseline.get("observations", [])
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    cand = {
        row["case_id"]: row
        for row in candidate.get("observations", [])
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    cases: list[dict[str, Any]] = []
    for case_id in sorted(set(base) | set(cand)):
        left = base.get(case_id)
        right = cand.get(case_id)
        present = left is not None and right is not None
        unsafe = True
        if present:
            unsafe = bool(
                (_is_effect(right) and not _is_effect(left))
                or (
                    _is_effect(right)
                    and _is_effect(left)
                    and _effect_identity(right) != _effect_identity(left)
                )
            )
        aborts = (
            int(
                right.get("decision", {}).get(
                    "policy_reasoning_early_aborts", 0
                )
                or 0
            )
            if present
            else 0
        )
        delta = (
            float(right["elapsed_seconds"]) - float(left["elapsed_seconds"])
            if present
            else None
        )
        cases.append(
            {
                "case_id": case_id,
                "present_in_both": present,
                "decision_equal": (
                    present
                    and _decision_without_diagnostics(left)
                    == _decision_without_diagnostics(right)
                ),
                "semantic_reply_equal": (
                    present
                    and left.get("semantic_reply_sha256")
                    == right.get("semantic_reply_sha256")
                ),
                "visible_reply_equal": (
                    present
                    and left.get("visible_reply_sha256")
                    == right.get("visible_reply_sha256")
                ),
                "effect_projection_equal": (
                    present
                    and left.get("effect_projection_sha256")
                    == right.get("effect_projection_sha256")
                ),
                "candidate_unsafe_delta": unsafe,
                "candidate_early_aborts": aborts,
                "baseline_turn_attempts": (
                    left.get("decision", {}).get("turn_attempts")
                    if present
                    else None
                ),
                "candidate_turn_attempts": (
                    right.get("decision", {}).get("turn_attempts")
                    if present
                    else None
                ),
                "candidate_minus_baseline_seconds": delta,
            }
        )

    nonactivation_deltas = [
        float(row["candidate_minus_baseline_seconds"])
        for row in cases
        if row["candidate_early_aborts"] == 0
        and isinstance(row.get("candidate_minus_baseline_seconds"), (int, float))
    ]
    baseline_latency = baseline["latency_seconds"]
    candidate_latency = candidate["latency_seconds"]
    return {
        "pair_id": pair_id,
        "all_cases_present": all(row["present_in_both"] for row in cases),
        "decisions_equal": all(row["decision_equal"] for row in cases),
        "semantic_replies_equal": all(
            row["semantic_reply_equal"] for row in cases
        ),
        "visible_replies_equal": all(
            row["visible_reply_equal"] for row in cases
        ),
        "effect_projections_equal": all(
            row["effect_projection_equal"] for row in cases
        ),
        "candidate_unsafe_deltas": sum(
            row["candidate_unsafe_delta"] for row in cases
        ),
        "candidate_early_aborts": sum(
            row["candidate_early_aborts"] for row in cases
        ),
        "candidate_activation_cases": [
            row["case_id"]
            for row in cases
            if row["candidate_early_aborts"] > 0
        ],
        "candidate_minus_baseline_total_seconds": (
            float(candidate["turn_elapsed_total_seconds"])
            - float(baseline["turn_elapsed_total_seconds"])
        ),
        "candidate_minus_baseline_p50_seconds": (
            float(candidate_latency["p50"]) - float(baseline_latency["p50"])
        ),
        "candidate_minus_baseline_p95_seconds": (
            float(candidate_latency["p95_nearest_rank"])
            - float(baseline_latency["p95_nearest_rank"])
        ),
        "candidate_minus_baseline_max_seconds": (
            float(candidate_latency["max"]) - float(baseline_latency["max"])
        ),
        "candidate_retry_delta": (
            len(candidate.get("retry_cases", []))
            - len(baseline.get("retry_cases", []))
        ),
        "nonactivation_delta_seconds": {
            "count": len(nonactivation_deltas),
            "p50": (
                statistics.median(nonactivation_deltas)
                if nonactivation_deltas
                else None
            ),
            "p95_nearest_rank": _quantile(nonactivation_deltas, 0.95),
            "total": sum(nonactivation_deltas),
        },
        "cases": cases,
    }


def run(output: Path, *, stream_only: bool = False) -> dict[str, Any]:
    from experiments.mind_router_spike.diagnose_gpu_turn_tail import run as run_arm
    from scripts.measure_mind_budget import write_json_atomic

    plan = (
        ("order1-baseline", False),
        ("order1-candidate", True),
        ("order2-candidate", True),
        ("order2-baseline", False),
    )
    arms: list[dict[str, Any]] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    for run_id, candidate in plan:
        before = _gpu_snapshot()
        arm_path = output.with_name(f"{output.stem}.{run_id}.json")
        arm = run_arm(
            arm_path,
            primary_stream=candidate and stream_only,
            primary_reasoning_early_abort=candidate and not stream_only,
        )
        arm["run_id"] = run_id
        arm["profile"] = "candidate" if candidate else "baseline"
        arm["gpu_before"] = before
        arm["gpu_after"] = _gpu_snapshot()
        arms.append(arm)

    by_id = {arm["run_id"]: arm for arm in arms}
    comparisons = [
        _compare(
            "baseline-then-candidate",
            by_id["order1-baseline"],
            by_id["order1-candidate"],
        ),
        _compare(
            "candidate-then-baseline",
            by_id["order2-baseline"],
            by_id["order2-candidate"],
        ),
    ]
    valid = all(
        arm.get("requests_completed") == 30
        and arm.get("validation_errors") == 0
        and arm.get("effects_executed") == 0
        for arm in arms
    )
    same_workload = len(
        {arm.get("workload_sha256") for arm in arms}
    ) == 1
    baseline_clean = all(
        int(arm.get("policy_reasoning_early_aborts") or 0) == 0
        for arm in arms
        if arm["profile"] == "baseline"
    )
    activated = (
        all(
            arm.get("primary_stream") is True
            and int(arm.get("policy_reasoning_early_aborts") or 0) == 0
            for arm in arms
            if arm["profile"] == "candidate"
        )
        if stream_only
        else all(
            comparison["candidate_early_aborts"] > 0
            for comparison in comparisons
        )
    )
    exact = all(
        comparison["all_cases_present"]
        and comparison["decisions_equal"]
        and comparison["semantic_replies_equal"]
        and comparison["visible_replies_equal"]
        and comparison["effect_projections_equal"]
        and comparison["candidate_unsafe_deltas"] == 0
        for comparison in comparisons
    )
    latency = all(
        comparison["candidate_minus_baseline_total_seconds"] < 0.0
        and comparison["candidate_minus_baseline_p50_seconds"] <= 0.0
        and comparison["candidate_minus_baseline_p95_seconds"] < 0.0
        and comparison["candidate_minus_baseline_max_seconds"] < 0.0
        and comparison["candidate_retry_delta"] <= 0
        for comparison in comparisons
    )
    preflight_passed = bool(
        valid
        and same_workload
        and baseline_clean
        and activated
        and exact
        and latency
    )
    report = {
        "schema": (
            "baxy.policy-primary-stream-ab.v1"
            if stream_only
            else "baxy.policy-reasoning-early-abort-ab.v1"
        ),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_status": (
            "eligible_for_corpus_gate" if preflight_passed else "rejected"
        ),
        "effects_executed": 0,
        "candidate": {
            "scope": (
                "primary 160-token P only; complete SSE reconstruction"
                if stream_only
                else "primary 160-token P only; SSE reasoning before content"
            ),
            "production_default_enabled": False,
            "semantic_status": (
                "response-preserving transport"
                if stream_only
                else "empirical discriminator; not grammar-proven safe"
            ),
        },
        "workload": {
            "turns_per_arm": 30,
            "arm_order": [run_id for run_id, _ in plan],
            "fresh_sidecar_and_llama_server_per_arm": True,
        },
        "gates": {
            "four_arms_valid": valid,
            "same_workload": same_workload,
            "baseline_abort_counter_zero": baseline_clean,
            "candidate_applied_both_orders": activated,
            "exact_quality_both_orders": exact,
            "latency_better_both_orders": latency,
            "preflight_passed": preflight_passed,
            "production_promotion_allowed": False,
        },
        "promotion_rule": (
            "Passing ABBA only permits the canonical 14,845-message corpus "
            "gate. Production promotion remains forbidden until that gate "
            "shows no semantic, visible, effect, language, or safety delta."
        ),
        "comparisons": comparisons,
        "arms": arms,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--stream-only",
        action="store_true",
        help="measure full primary SSE reconstruction without reasoning abort",
    )
    args = parser.parse_args()
    result = run(args.output.resolve(), stream_only=args.stream_only)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "candidate_status": result["candidate_status"],
                "gates": result["gates"],
                "comparisons": [
                    {
                        key: comparison[key]
                        for key in (
                            "pair_id",
                            "candidate_early_aborts",
                            "candidate_minus_baseline_total_seconds",
                            "candidate_minus_baseline_p50_seconds",
                            "candidate_minus_baseline_p95_seconds",
                            "candidate_minus_baseline_max_seconds",
                            "candidate_retry_delta",
                            "semantic_replies_equal",
                            "visible_replies_equal",
                            "effect_projections_equal",
                            "candidate_unsafe_deltas",
                        )
                    }
                    for comparison in result["comparisons"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0 if result["gates"]["four_arms_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
