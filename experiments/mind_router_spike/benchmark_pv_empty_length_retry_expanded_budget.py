"""A/B for a larger P/V budget only after an empty length-limited result.

The first internal attempt remains byte-for-byte identical to production.
When that exact P or V attempt returns empty content with
``finish_reason=length``, the candidate raises only the immediately following
internal retry budget: P from 160 to 256 tokens and V from 24 to 64 tokens.
Prompts, response formats, sampling, seeds, validators and full-turn recovery
remain unchanged. No Core operation is dispatched.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from experiments.mind_router_spike import (  # noqa: E402
    benchmark_pv_empty_length_retry_direct_gbnf as shared_benchmark,
)


DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "fixes"
    / "pv_empty_length_retry_expanded_budget_ab_20260730.json"
)


def _candidate_budget_scope_exact(arm: dict[str, Any]) -> bool:
    for post in arm["posts"]:
        stage = post.get("stage")
        eligible = post.get("eligible_empty_length_retry") is True
        applied = post.get("candidate_applied") is True
        source = post.get("source_max_tokens")
        wire = post.get("wire_max_tokens")
        if eligible and stage in {"P", "V"}:
            expected_source = 160 if stage == "P" else 24
            expected_wire = 256 if stage == "P" else 64
            if (
                not applied
                or source != expected_source
                or wire != expected_wire
                or post.get("wire_constraint") != "response_format"
            ):
                return False
        elif applied or source != wire:
            return False
    return True


def _baseline_budget_unchanged(arm: dict[str, Any]) -> bool:
    return all(
        post.get("candidate_applied") is not True
        and post.get("source_max_tokens") == post.get("wire_max_tokens")
        for post in arm["posts"]
    )


def _run(output: Path) -> int:
    from scripts.baxy_runtime_config import (
        DEFAULT_RUNTIME_MANIFEST,
        public_runtime_identity,
        resolve_runtime,
    )
    from scripts.measure_mind_budget import (
        current_core_capabilities,
        discover_core,
    )

    user_dotnet = Path.home() / ".dotnet"
    if (user_dotnet / "dotnet.exe").is_file():
        os.environ["DOTNET_ROOT"] = str(user_dotnet)
        os.environ["DOTNET_ROOT_X64"] = str(user_dotnet)

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(discover_core(None))
    arm_plan = (
        ("order1-baseline", shared_benchmark.PROFILE_BASELINE),
        ("order1-candidate", shared_benchmark.PROFILE_EXPANDED_BUDGET),
        ("order2-candidate", shared_benchmark.PROFILE_EXPANDED_BUDGET),
        ("order2-baseline", shared_benchmark.PROFILE_BASELINE),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pv-empty-length-budget-ab-",
        dir=str(output.parent),
    ) as temporary:
        temp_root = Path(temporary).resolve()
        arms = [
            shared_benchmark._run_arm(
                profile=profile,
                run_id=run_id,
                log_path=temp_root / f"{run_id}.jsonl",
                runtime=runtime,
                capabilities=capabilities,
            )
            for run_id, profile in arm_plan
        ]

    by_id = {arm["run_id"]: arm for arm in arms}
    comparisons = [
        shared_benchmark._compare_pair(
            "baseline-then-candidate",
            by_id["order1-baseline"],
            by_id["order1-candidate"],
        ),
        shared_benchmark._compare_pair(
            "candidate-then-baseline",
            by_id["order2-baseline"],
            by_id["order2-candidate"],
        ),
    ]
    for comparison in comparisons:
        comparison["arm_roles"] = {
            "baseline": shared_benchmark.PROFILE_BASELINE,
            "candidate": shared_benchmark.PROFILE_EXPANDED_BUDGET,
        }

    candidate_arms = [
        arm
        for arm in arms
        if arm["profile"] == shared_benchmark.PROFILE_EXPANDED_BUDGET
    ]
    baseline_arms = [
        arm
        for arm in arms
        if arm["profile"] == shared_benchmark.PROFILE_BASELINE
    ]
    workload_complete = all(len(arm["observations"]) == 30 for arm in arms)
    workload_identical = (
        len({arm["workload_sha256"] for arm in arms}) == 1
        and len({tuple(arm["workload_case_ids"]) for arm in arms}) == 1
    )
    validation_clean = all(arm["validation_errors"] == 0 for arm in arms)
    first_attempts_preserved = all(
        arm["first_attempt_response_format_violations"] == 0 for arm in arms
    )
    response_format_preserved = all(
        all(
            post.get("wire_constraint") != "direct_gbnf"
            for post in arm["posts"]
        )
        for arm in arms
    )
    sampling_unchanged = all(
        arm["seed_or_temperature_mutations"] == 0 for arm in arms
    )
    candidate_triggered = all(
        arm["eligible_retry_posts"] > 0
        and arm["candidate_applied_posts"] == arm["eligible_retry_posts"]
        for arm in candidate_arms
    )
    candidate_budget_scope_exact = all(
        _candidate_budget_scope_exact(arm) for arm in candidate_arms
    )
    baseline_budget_unchanged = all(
        _baseline_budget_unchanged(arm) for arm in baseline_arms
    )
    exact_decisions_replies_effects = all(
        comparison["all_cases_present"]
        and comparison["decision_projections_equal"]
        and comparison["semantic_replies_equal"]
        and comparison["visible_replies_equal"]
        and comparison["effect_projections_equal"]
        for comparison in comparisons
    )
    zero_unsafe_deltas = all(
        comparison["candidate_unsafe_deltas"] == 0 for comparison in comparisons
    )
    retries_lower_both_orders = all(
        comparison["candidate_retry_reduction"] > 0
        for comparison in comparisons
    )
    retry_tail_faster_both_orders = all(
        comparison["tail_cases"] > 0
        and comparison["candidate_minus_baseline_tail_total_seconds"] < 0.0
        for comparison in comparisons
    )
    total_faster_both_orders = all(
        comparison["candidate_minus_baseline_turn_total_seconds"] < 0.0
        for comparison in comparisons
    )
    measurement_valid = (
        workload_complete
        and workload_identical
        and validation_clean
        and first_attempts_preserved
        and response_format_preserved
        and sampling_unchanged
        and candidate_triggered
        and candidate_budget_scope_exact
        and baseline_budget_unchanged
        and exact_decisions_replies_effects
        and zero_unsafe_deltas
    )
    hypothesis_supported = (
        measurement_valid
        and retries_lower_both_orders
        and retry_tail_faster_both_orders
        and total_faster_both_orders
    )

    result = {
        "schema": "baxy.pv-empty-length-retry-expanded-budget-ab.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_status": "research_only",
        "measurement_outcome": (
            "hypothesis_supported"
            if hypothesis_supported
            else (
                "valid_but_hypothesis_not_supported"
                if measurement_valid
                else "invalid_measurement"
            )
        ),
        "effects_executed": 0,
        "candidate": {
            "scope": "only the immediate P/V retry after empty+length",
            "budget_delta": {"P": [160, 256], "V": [24, 64]},
            "unchanged": [
                "first internal attempt",
                "messages and prompts",
                "response_format and JSON schemas",
                "temperature and seeds",
                "validators and full-turn recovery",
            ],
        },
        "workload": {
            "turns_per_arm": 30,
            "arms": [run_id for run_id, _ in arm_plan],
            "fresh_sidecar_and_llama_server_per_arm": True,
            "both_orders": True,
            "core_effect_requests_sent": 0,
            "catalog_operations": len(capabilities),
        },
        "runtime": public_runtime_identity(runtime),
        "gates": {
            "workload_complete": workload_complete,
            "workload_identical_across_arms": workload_identical,
            "validation_clean": validation_clean,
            "first_attempt_response_format_preserved": first_attempts_preserved,
            "response_format_preserved_on_all_posts": response_format_preserved,
            "temperature_and_seeds_unchanged": sampling_unchanged,
            "candidate_triggered_both_orders": candidate_triggered,
            "candidate_budget_scope_exact": candidate_budget_scope_exact,
            "baseline_budget_unchanged": baseline_budget_unchanged,
            "exact_decisions_replies_effects": exact_decisions_replies_effects,
            "zero_unsafe_deltas": zero_unsafe_deltas,
            "retries_lower_both_orders": retries_lower_both_orders,
            "retry_tail_faster_both_orders": retry_tail_faster_both_orders,
            "total_faster_both_orders": total_faster_both_orders,
            "measurement_valid": measurement_valid,
            "hypothesis_supported": hypothesis_supported,
        },
        "evaluation_rule": (
            "Require four fresh opposite-order arms, exact scope and wire "
            "invariants, 30/30 valid replies, exact decision/reply/effect "
            "projections, zero unsafe deltas, fewer full-turn retries and "
            "lower retry-tail plus total time in both orders."
        ),
        "comparisons": comparisons,
        "arms": arms,
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "measurement_outcome": result["measurement_outcome"],
                "gates": result["gates"],
                "comparisons": [
                    {
                        key: comparison[key]
                        for key in (
                            "pair_id",
                            "decision_projections_equal",
                            "semantic_replies_equal",
                            "visible_replies_equal",
                            "effect_projections_equal",
                            "candidate_unsafe_deltas",
                            "baseline_retry_cases",
                            "candidate_retry_cases",
                            "candidate_retry_reduction",
                            "candidate_minus_baseline_tail_total_seconds",
                            "candidate_minus_baseline_turn_total_seconds",
                        )
                    }
                    for comparison in comparisons
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if hypothesis_supported else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    fixes = (ROOT / "artifacts" / "fixes").resolve()
    if output.parent != fixes or output.suffix.casefold() != ".json":
        parser.error("--output must be a JSON directly below artifacts/fixes")
    return _run(output)


if __name__ == "__main__":
    raise SystemExit(main())
