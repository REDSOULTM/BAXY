"""Cold physical A/B for CUDA lazy versus eager module loading.

Both arms use BAXY's exact b9980/q8 production inference profile and differ
only in the fresh llama-server child's ``CUDA_MODULE_LOADING`` environment:

* ``lazy``: explicitly ``CUDA_MODULE_LOADING=LAZY``;
* ``eager``: explicitly ``CUDA_MODULE_LOADING=EAGER``.

The benchmark includes launch-to-ready, the first real turn,
launch-to-first-response and launch-to-workload-complete.  Structured calls
request raw generated token ids in both arms.  Core is never started and no
external effect is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from benchmark_llama_kv_q4 import (  # type: ignore[import-not-found]
    KvQuantRuntime,
)
from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    _case_projection,
    _run_case,
)
from benchmark_structured_top_k1 import (  # type: ignore[import-not-found]
    TARGET_STAGES,
    _case_decision_projection,
    _compare_pair,
    _file_sha256,
    _quantile,
    _stage_summary,
)


_CUDA_MODULE_LOADING = {
    "lazy": "LAZY",
    "eager": "EAGER",
}


def _run_arm(profile: str, run_id: str) -> dict[str, Any]:
    try:
        environment_value = _CUDA_MODULE_LOADING[profile]
    except KeyError as exc:
        raise ValueError(f"unknown module-loading profile: {profile}") from exc

    os.environ["CUDA_MODULE_LOADING"] = environment_value
    runtime = KvQuantRuntime("q8", run_id)
    cases: list[dict[str, Any]] = []
    started = time.perf_counter()
    ready_seconds: float | None = None
    server_pid: int | None = None
    startup_to_first_response_seconds: float | None = None
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        process = runtime._process
        if process is None or process.poll() is not None:
            raise RuntimeError("fresh llama-server child is not alive")
        server_pid = process.pid
        ready_seconds = time.perf_counter() - started
        for index, case in enumerate(CASES):
            cases.append(_run_case(runtime, case))
            if index == 0:
                startup_to_first_response_seconds = (
                    time.perf_counter() - started
                )
        startup_to_workload_complete_seconds = time.perf_counter() - started
    finally:
        owned_process = runtime._process
        runtime.close()
        if owned_process is not None and owned_process.poll() is None:
            raise RuntimeError("llama-server child survived runtime.close()")

    if ready_seconds is None or startup_to_first_response_seconds is None:
        raise AssertionError("cold timing boundaries were not reached")
    for record in runtime._benchmark_records:
        record["module_loading_profile"] = profile
        record["cuda_module_loading"] = environment_value

    elapsed = [float(case["elapsed_seconds"]) for case in cases]
    targeted = [
        record
        for record in runtime._benchmark_records
        if record["stage"] in TARGET_STAGES
    ]
    return {
        "run_id": run_id,
        "profile": profile,
        "server_pid": server_pid,
        "environment": {
            "CUDA_MODULE_LOADING": environment_value,
        },
        "server_ready_seconds": ready_seconds,
        "first_turn_seconds": elapsed[0],
        "first_turn_case": cases[0]["case"],
        "startup_to_first_response_seconds": (
            startup_to_first_response_seconds
        ),
        "startup_to_workload_complete_seconds": (
            startup_to_workload_complete_seconds
        ),
        "cases": cases,
        "case_projection": [_case_projection(case) for case in cases],
        "decision_projection": [
            _case_decision_projection(case) for case in cases
        ],
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "structured_elapsed_total_seconds": sum(
            float(record["elapsed_seconds"]) for record in targeted
        ),
        "case_elapsed_total_seconds": sum(elapsed),
        "case_elapsed_p50_seconds": statistics.median(elapsed),
        "case_elapsed_p95_seconds": _quantile(elapsed, 0.95),
        "case_elapsed_max_seconds": max(elapsed),
    }


def _arm_plan(order: str) -> list[tuple[str, str]]:
    if order == "lazy-eager":
        return [
            ("order1-lazy", "lazy"),
            ("order1-eager", "eager"),
        ]
    if order == "eager-lazy":
        return [
            ("order2-eager", "eager"),
            ("order2-lazy", "lazy"),
        ]
    if order == "both":
        return [
            ("order1-lazy", "lazy"),
            ("order1-eager", "eager"),
            ("order2-eager", "eager"),
            ("order2-lazy", "lazy"),
        ]
    raise ValueError(f"unknown order: {order}")


def _cold_delta(
    *,
    pair_id: str,
    lazy: dict[str, Any],
    eager: dict[str, Any],
) -> dict[str, Any]:
    metrics = (
        "server_ready_seconds",
        "first_turn_seconds",
        "startup_to_first_response_seconds",
        "startup_to_workload_complete_seconds",
        "case_elapsed_p50_seconds",
        "case_elapsed_total_seconds",
    )
    return {
        "pair_id": pair_id,
        "eager_minus_lazy": {
            metric: float(eager[metric]) - float(lazy[metric])
            for metric in metrics
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("both", "lazy-eager", "eager-lazy"),
        default="both",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--server",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe"
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\assets\models"
            r"\gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
        ),
    )
    args = parser.parse_args()
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("official b9980 runtime assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ.pop("GGML_CUDA_GRAPH_OPT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server.resolve())
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model.resolve())
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    if args.validate_only:
        runtime = KvQuantRuntime("q8", "validate")
        try:
            command = runtime._server_command()
        finally:
            runtime.close()
        result = {
            "profiles": _CUDA_MODULE_LOADING,
            "cache_type_k": command[command.index("-ctk") + 1],
            "cache_type_v": command[command.index("-ctv") + 1],
            "flash_attention": command[command.index("-fa") + 1],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    arms = [
        _run_arm(profile, run_id)
        for run_id, profile in _arm_plan(args.arm_order)
    ]
    by_id = {arm["run_id"]: arm for arm in arms}
    comparisons: list[dict[str, Any]] = []
    cold_deltas: list[dict[str, Any]] = []
    exact_case_outputs: list[dict[str, Any]] = []
    if args.arm_order in {"both", "lazy-eager"}:
        lazy = by_id["order1-lazy"]
        eager = by_id["order1-eager"]
        comparisons.append(
            _compare_pair(
                pair_id="lazy-then-eager",
                baseline=lazy,
                candidate=eager,
            )
        )
        cold_deltas.append(
            _cold_delta(
                pair_id="lazy-then-eager",
                lazy=lazy,
                eager=eager,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "lazy-then-eager",
                "equal": (
                    lazy["case_projection"] == eager["case_projection"]
                ),
            }
        )
    if args.arm_order in {"both", "eager-lazy"}:
        eager = by_id["order2-eager"]
        lazy = by_id["order2-lazy"]
        comparisons.append(
            _compare_pair(
                pair_id="eager-then-lazy",
                baseline=lazy,
                candidate=eager,
            )
        )
        cold_deltas.append(
            _cold_delta(
                pair_id="eager-then-lazy",
                lazy=lazy,
                eager=eager,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "eager-then-lazy",
                "equal": (
                    lazy["case_projection"] == eager["case_projection"]
                ),
            }
        )

    stage_coverage = all(
        arm["stage_summary"][stage]["calls"] > 0
        for arm in arms
        for stage in TARGET_STAGES
    )
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    exact_equivalence = (
        all(item["equal"] for item in exact_case_outputs)
        and all(
            comparison["payloads_equal"]
            and comparison["contents_equal"]
            and comparison["raw_contents_equal"]
            and comparison["raw_tokens_available"]
            and comparison["tokens_equal"]
            and comparison["final_decisions_equal"]
            for comparison in comparisons
        )
    )
    cold_total_improvement = len(cold_deltas) == 2 and all(
        item["eager_minus_lazy"]["startup_to_first_response_seconds"] < 0.0
        and item["eager_minus_lazy"][
            "startup_to_workload_complete_seconds"
        ]
        < 0.0
        for item in cold_deltas
    )
    no_turn_regression = len(cold_deltas) == 2 and all(
        item["eager_minus_lazy"]["first_turn_seconds"] <= 0.0
        and item["eager_minus_lazy"]["case_elapsed_p50_seconds"] <= 0.0
        for item in cold_deltas
    )
    promotion_gate_passed = (
        stage_coverage
        and mode_contracts
        and exact_equivalence
        and cold_total_improvement
        and no_turn_regression
    )
    result = {
        "schema": "baxy.cuda-module-loading-ab.v1",
        "candidate_status": "research_only",
        "arm_order": args.arm_order,
        "runtime": {
            "server": str(args.server.resolve()),
            "server_sha256": _file_sha256(args.server),
            "model": str(args.model.resolve()),
            "cache_type_k": "q8_0",
            "cache_type_v": "q8_0",
            "flash_attention": "on",
            "parallel": 3,
            "context_per_slot": 4_096,
        },
        "control": {
            "only_variable": (
                "CUDA_MODULE_LOADING=LAZY versus CUDA_MODULE_LOADING=EAGER"
            ),
            "fresh_server_per_arm": True,
            "same_payloads": True,
            "case_count_per_arm": len(CASES),
            "core_started": False,
            "external_effects_executed": False,
        },
        "measurement": {
            "raw_structured_tokens": (
                "llama.cpp b9980 __verbose.tokens via identical "
                "verbose=true and return_tokens=true"
            ),
            "startup_boundaries": [
                "launch_to_health_ready",
                "first_real_turn",
                "launch_to_first_response",
                "launch_to_workload_complete",
            ],
        },
        "stage_coverage": stage_coverage,
        "mode_contracts": mode_contracts,
        "exact_case_outputs": exact_case_outputs,
        "exact_equivalence": exact_equivalence,
        "cold_deltas": cold_deltas,
        "cold_total_improvement": cold_total_improvement,
        "no_turn_regression": no_turn_regression,
        "comparisons": comparisons,
        "arms": arms,
        "promotion_gate_passed": promotion_gate_passed,
        "promotion_rule": (
            "Require exact raw tokens, outputs and final decisions in both "
            "orders; lower launch-to-first-response and "
            "launch-to-workload-complete in both orders; and no first-turn or "
            "turn-p50 regression. Moving cost from first turn into readiness "
            "without improving the complete startup-to-response balance is a "
            "rejection."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "schema",
                    "stage_coverage",
                    "mode_contracts",
                    "exact_equivalence",
                    "cold_deltas",
                    "cold_total_improvement",
                    "no_turn_regression",
                    "promotion_gate_passed",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if stage_coverage and mode_contracts and exact_equivalence else 2


if __name__ == "__main__":
    raise SystemExit(main())
