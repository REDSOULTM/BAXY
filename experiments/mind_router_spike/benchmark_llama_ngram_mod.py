"""Physical, effect-free A/B for llama.cpp ngram-mod speculation.

The benchmark keeps BAXY's official b9980 server, Gemma 4 model, q8 KV,
Flash Attention, prompts, schemas, seeds, scheduling and payloads fixed.  The
only server-profile difference is:

* ``none``: ``--spec-type none``;
* ``ngram-mod``: ``--spec-type ngram-mod`` with either b9980's documented
  defaults or one explicitly supplied, predeclared dense-model profile.

Structured calls request raw generated token ids in both arms.  Drafted and
accepted token counts are collected from response timings whenever b9980
exposes them.  Core is never started and no external effect is executed.
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


_SPEC_TYPES = {
    "none": "none",
    "ngram-mod": "ngram-mod",
}


class NgramRuntime(KvQuantRuntime):
    def __init__(
        self,
        profile: str,
        run_id: str,
        ngram_tuning: dict[str, int] | None = None,
    ) -> None:
        if profile not in _SPEC_TYPES:
            raise ValueError(f"unknown speculative profile: {profile}")
        self._spec_profile = profile
        self._ngram_tuning = ngram_tuning
        super().__init__("q8", run_id)

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        if "--spec-type" in command:
            raise AssertionError("production command unexpectedly sets spec type")
        command.extend(["--spec-type", _SPEC_TYPES[self._spec_profile]])
        if self._spec_profile == "ngram-mod" and self._ngram_tuning is not None:
            command.extend(
                [
                    "--spec-ngram-mod-n-match",
                    str(self._ngram_tuning["match"]),
                    "--spec-ngram-mod-n-min",
                    str(self._ngram_tuning["min"]),
                    "--spec-ngram-mod-n-max",
                    str(self._ngram_tuning["max"]),
                ]
            )
        return command

    def _record_profile(self) -> str:
        return self._spec_profile

    def _extra_response_record(
        self,
        response: dict[str, Any],
        timings: dict[str, Any],
    ) -> dict[str, Any]:
        del response
        drafted = timings.get("draft_n")
        accepted = timings.get("draft_n_accepted")
        return {
            "draft_n": drafted,
            "draft_n_accepted": accepted,
            "draft_acceptance": (
                float(accepted) / float(drafted)
                if isinstance(drafted, (int, float))
                and not isinstance(drafted, bool)
                and drafted > 0
                and isinstance(accepted, (int, float))
                and not isinstance(accepted, bool)
                else None
            ),
        }


def _draft_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for stage in (*TARGET_STAGES, "chat", "other"):
        selected = [record for record in records if record["stage"] == stage]
        if not selected:
            continue
        drafted = sum(
            float(record["draft_n"])
            for record in selected
            if isinstance(record.get("draft_n"), (int, float))
            and not isinstance(record.get("draft_n"), bool)
        )
        accepted = sum(
            float(record["draft_n_accepted"])
            for record in selected
            if isinstance(record.get("draft_n_accepted"), (int, float))
            and not isinstance(record.get("draft_n_accepted"), bool)
        )
        summary[stage] = {
            "calls": len(selected),
            "calls_with_drafts": sum(
                isinstance(record.get("draft_n"), (int, float))
                and not isinstance(record.get("draft_n"), bool)
                and float(record["draft_n"]) > 0.0
                for record in selected
            ),
            "draft_n_total": drafted,
            "draft_n_accepted_total": accepted,
            "acceptance": accepted / drafted if drafted > 0.0 else None,
        }
    total_drafted = sum(
        float(item["draft_n_total"]) for item in summary.values()
    )
    total_accepted = sum(
        float(item["draft_n_accepted_total"]) for item in summary.values()
    )
    return {
        "by_stage": summary,
        "draft_n_total": total_drafted,
        "draft_n_accepted_total": total_accepted,
        "acceptance": (
            total_accepted / total_drafted if total_drafted > 0.0 else None
        ),
    }


def _run_arm(
    profile: str,
    run_id: str,
    ngram_tuning: dict[str, int] | None,
) -> dict[str, Any]:
    runtime = NgramRuntime(profile, run_id, ngram_tuning)
    cases: list[dict[str, Any]] = []
    server_pid: int | None = None
    started = time.perf_counter()
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        process = runtime._process
        if process is None or process.poll() is not None:
            raise RuntimeError("fresh llama-server child is not alive")
        server_pid = process.pid
        ready_seconds = time.perf_counter() - started
        for case in CASES:
            cases.append(_run_case(runtime, case))
    finally:
        owned_process = runtime._process
        runtime.close()
        if owned_process is not None and owned_process.poll() is None:
            raise RuntimeError("llama-server child survived runtime.close()")

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
        "spec_type": _SPEC_TYPES[profile],
        "server_ready_seconds": ready_seconds,
        "cases": cases,
        "case_projection": [_case_projection(case) for case in cases],
        "decision_projection": [
            _case_decision_projection(case) for case in cases
        ],
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "draft_summary": _draft_summary(runtime._benchmark_records),
        "structured_elapsed_total_seconds": sum(
            float(record["elapsed_seconds"]) for record in targeted
        ),
        "case_elapsed_total_seconds": sum(elapsed),
        "case_elapsed_p50_seconds": statistics.median(elapsed),
        "case_elapsed_p95_seconds": _quantile(elapsed, 0.95),
        "case_elapsed_max_seconds": max(elapsed),
    }


def _arm_plan(order: str) -> list[tuple[str, str]]:
    if order == "none-ngram":
        return [
            ("order1-none", "none"),
            ("order1-ngram", "ngram-mod"),
        ]
    if order == "ngram-none":
        return [
            ("order2-ngram", "ngram-mod"),
            ("order2-none", "none"),
        ]
    if order == "both":
        return [
            ("order1-none", "none"),
            ("order1-ngram", "ngram-mod"),
            ("order2-ngram", "ngram-mod"),
            ("order2-none", "none"),
        ]
    raise ValueError(f"unknown order: {order}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("both", "none-ngram", "ngram-none"),
        default="both",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--ngram-match", type=int)
    parser.add_argument("--ngram-min", type=int)
    parser.add_argument("--ngram-max", type=int)
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
    tuning_values = (args.ngram_match, args.ngram_min, args.ngram_max)
    if any(value is not None for value in tuning_values) and not all(
        value is not None for value in tuning_values
    ):
        parser.error(
            "--ngram-match, --ngram-min and --ngram-max must be supplied "
            "together"
        )
    if all(value is not None for value in tuning_values):
        if any(value <= 0 for value in tuning_values):
            parser.error("all ngram tuning values must be positive")
        ngram_tuning: dict[str, int] | None = {
            "match": args.ngram_match,
            "min": args.ngram_min,
            "max": args.ngram_max,
        }
    else:
        ngram_tuning = None

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ.pop("GGML_CUDA_GRAPH_OPT", None)
    os.environ.pop("CUDA_MODULE_LOADING", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server.resolve())
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model.resolve())
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    if args.validate_only:
        validations = {}
        for profile in ("none", "ngram-mod"):
            runtime = NgramRuntime(
                profile,
                f"validate-{profile}",
                ngram_tuning,
            )
            try:
                command = runtime._server_command()
            finally:
                runtime.close()
            validations[profile] = {
                "spec_type": command[command.index("--spec-type") + 1],
                "cache_type_k": command[command.index("-ctk") + 1],
                "cache_type_v": command[command.index("-ctv") + 1],
                "flash_attention": command[command.index("-fa") + 1],
                "explicit_ngram_tuning_flags": [
                    item
                    for item in command
                    if item.startswith("--spec-ngram-")
                ],
            }
        print(json.dumps(validations, ensure_ascii=False, indent=2))
        return 0

    arms = [
        _run_arm(profile, run_id, ngram_tuning)
        for run_id, profile in _arm_plan(args.arm_order)
    ]
    by_id = {arm["run_id"]: arm for arm in arms}
    comparisons: list[dict[str, Any]] = []
    exact_case_outputs: list[dict[str, Any]] = []
    if args.arm_order in {"both", "none-ngram"}:
        baseline = by_id["order1-none"]
        candidate = by_id["order1-ngram"]
        comparisons.append(
            _compare_pair(
                pair_id="none-then-ngram",
                baseline=baseline,
                candidate=candidate,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "none-then-ngram",
                "equal": (
                    baseline["case_projection"]
                    == candidate["case_projection"]
                ),
            }
        )
    if args.arm_order in {"both", "ngram-none"}:
        candidate = by_id["order2-ngram"]
        baseline = by_id["order2-none"]
        comparisons.append(
            _compare_pair(
                pair_id="ngram-then-none",
                baseline=baseline,
                candidate=candidate,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "ngram-then-none",
                "equal": (
                    baseline["case_projection"]
                    == candidate["case_projection"]
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
    candidate_drafted = all(
        arm["draft_summary"]["draft_n_total"] > 0.0
        for arm in arms
        if arm["profile"] == "ngram-mod"
    )
    opposite_order_improvement = len(comparisons) == 2 and all(
        comparison["candidate_minus_baseline_case_p50_seconds"] < 0.0
        and comparison["candidate_minus_baseline_case_total_seconds"] < 0.0
        for comparison in comparisons
    )
    promotion_gate_passed = (
        stage_coverage
        and mode_contracts
        and exact_equivalence
        and candidate_drafted
        and opposite_order_improvement
    )
    result = {
        "schema": "baxy.llama-ngram-mod-ab.v1",
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
        "candidate": {
            "spec_type": "ngram-mod",
            "configuration": (
                "b9980 documented defaults"
                if ngram_tuning is None
                else "predeclared conservative dense-model profile"
            ),
            "ngram_min": (
                48 if ngram_tuning is None else ngram_tuning["min"]
            ),
            "ngram_max": (
                64 if ngram_tuning is None else ngram_tuning["max"]
            ),
            "ngram_match": (
                24 if ngram_tuning is None else ngram_tuning["match"]
            ),
            "explicit_tuning_flags": (
                []
                if ngram_tuning is None
                else [
                    "--spec-ngram-mod-n-match",
                    "--spec-ngram-mod-n-min",
                    "--spec-ngram-mod-n-max",
                ]
            ),
        },
        "control": {
            "only_variable": (
                "--spec-type none versus --spec-type ngram-mod"
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
            "draft_metrics": [
                "timings.draft_n",
                "timings.draft_n_accepted",
            ],
            "end_to_end_case_latency": True,
        },
        "stage_coverage": stage_coverage,
        "mode_contracts": mode_contracts,
        "exact_case_outputs": exact_case_outputs,
        "exact_equivalence": exact_equivalence,
        "candidate_drafted": candidate_drafted,
        "opposite_order_improvement": opposite_order_improvement,
        "comparisons": comparisons,
        "arms": arms,
        "promotion_gate_passed": promotion_gate_passed,
        "promotion_rule": (
            "Require generated drafts, exact raw tokens, outputs and final "
            "decisions in both orders, plus lower turn p50 and turn total in "
            "both opposite-order pairs. Reject a profile that does not draft, "
            "changes any output, or fails to improve both latency measures "
            "repeatably."
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
                    "candidate_drafted",
                    "opposite_order_improvement",
                    "promotion_gate_passed",
                    "comparisons",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if stage_coverage and mode_contracts and exact_equivalence else 2


if __name__ == "__main__":
    raise SystemExit(main())
