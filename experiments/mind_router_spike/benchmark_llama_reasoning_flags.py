"""Physical A/B for llama.cpp's overlapping reasoning-disable controls.

The registered b9980 profile currently passes both ``--reasoning off`` and
``--reasoning-budget 0``.  Recent llama.cpp reports indicate that the sampler
budget override can interfere with the native reasoning switch for hybrid
models.  This effect-free experiment removes only the budget override in the
candidate arm.  Prompts, model, schemas, seeds, temperatures and every other
server option remain unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
from typing import Any

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    InstrumentedRuntime,
    _case_projection,
    _run_case,
    _stage_summary,
)


class ReasoningFlagsRuntime(InstrumentedRuntime):
    def __init__(self, profile: str) -> None:
        self._reasoning_flags_profile = profile
        super().__init__(profile)

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        if self._reasoning_flags_profile == "off-only":
            index = command.index("--reasoning-budget")
            del command[index : index + 2]
        return command


def _run_arm(profile: str) -> dict[str, Any]:
    runtime = ReasoningFlagsRuntime(profile)
    cases: list[dict[str, Any]] = []
    command = runtime._server_command()
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        for case in CASES:
            cases.append(_run_case(runtime, case))
    finally:
        runtime.close()
    elapsed = [float(case["elapsed_seconds"]) for case in cases]
    return {
        "profile": profile,
        "server_command": command,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "elapsed_p50_seconds": statistics.median(elapsed),
        "elapsed_p95_seconds": max(elapsed),
        "elapsed_total_seconds": sum(elapsed),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("both-off-only", "off-only-both"),
        default="both-off-only",
    )
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
        raise FileNotFoundError("official runtime assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server.resolve())
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model.resolve())
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    # The profile contains a hyphen, so recover the two legal orderings
    # explicitly instead of treating every separator as an arm boundary.
    profiles = (
        ["both", "off-only"]
        if args.arm_order == "both-off-only"
        else ["off-only", "both"]
    )
    arms = [_run_arm(profile) for profile in profiles]
    by_profile = {arm["profile"]: arm for arm in arms}
    baseline = by_profile["both"]
    candidate = by_profile["off-only"]
    baseline_projection = [
        _case_projection(case) for case in baseline["cases"]
    ]
    candidate_projection = [
        _case_projection(case) for case in candidate["cases"]
    ]
    exact_outputs = baseline_projection == candidate_projection
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    baseline_command = baseline["server_command"]
    candidate_command = candidate["server_command"]
    command_scope_exact = (
        baseline_command.count("--reasoning-budget") == 1
        and baseline_command[
            baseline_command.index("--reasoning-budget") + 1
        ]
        == "0"
        and "--reasoning-budget" not in candidate_command
        and candidate_command[
            candidate_command.index("--reasoning") + 1
        ]
        == "off"
        and [
            item
            for index, item in enumerate(baseline_command)
            if index
            not in {
                baseline_command.index("--reasoning-budget"),
                baseline_command.index("--reasoning-budget") + 1,
            }
        ]
        == candidate_command
    )
    result = {
        "schema": "baxy.llama-reasoning-flags-ab.v1",
        "arm_order": arm_order,
        "profiles": profiles,
        "runtime": {
            "server": str(args.server.resolve()),
            "model": str(args.model.resolve()),
            "parallel": 3,
            "context_per_slot": 4096,
        },
        "gates": {
            "command_scope_exact": command_scope_exact,
            "exact_outputs": exact_outputs,
            "mode_contracts": mode_contracts,
            "candidate_faster_p50": (
                candidate["elapsed_p50_seconds"]
                < baseline["elapsed_p50_seconds"]
            ),
            "candidate_faster_p95": (
                candidate["elapsed_p95_seconds"]
                < baseline["elapsed_p95_seconds"]
            ),
            "candidate_faster_total": (
                candidate["elapsed_total_seconds"]
                < baseline["elapsed_total_seconds"]
            ),
        },
        "latency_delta_off_only_minus_both": {
            "p50_seconds": (
                candidate["elapsed_p50_seconds"]
                - baseline["elapsed_p50_seconds"]
            ),
            "p95_seconds": (
                candidate["elapsed_p95_seconds"]
                - baseline["elapsed_p95_seconds"]
            ),
            "total_seconds": (
                candidate["elapsed_total_seconds"]
                - baseline["elapsed_total_seconds"]
            ),
        },
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require exact normalized outputs and opposite-order physical "
            "replication with lower p50, tail and total latency."
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
                "schema": result["schema"],
                "profiles": profiles,
                "gates": result["gates"],
                "latency_delta_off_only_minus_both": result[
                    "latency_delta_off_only_minus_both"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0 if exact_outputs and mode_contracts and command_scope_exact else 2


if __name__ == "__main__":
    raise SystemExit(main())
