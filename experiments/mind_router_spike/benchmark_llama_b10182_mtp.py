"""Physical, effect-free b10182 A/B for Gemma 4 MTP decoding.

Both arms use the same temporary official b10182 server, BAXY's registered
Gemma 4 E2B model, Q8 KV cache, Flash Attention, three slots, prompts,
schemas, seeds, payloads and six-case workload.  The only profile difference
is:

* ``none``: ``--spec-type none``;
* ``draft-mtp``: ``--spec-type draft-mtp --spec-draft-n-max 1``.

Structured calls request raw generated token ids.  Drafted and accepted token
counts are captured from b10182 response timings.  Core is never started and
no external effect is executed.
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
from benchmark_llama_ngram_mod import (  # type: ignore[import-not-found]
    _draft_summary,
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
    "draft-mtp": "draft-mtp",
}


class MtpRuntime(KvQuantRuntime):
    def __init__(self, profile: str, run_id: str) -> None:
        if profile not in _SPEC_TYPES:
            raise ValueError(f"unknown MTP profile: {profile}")
        self._spec_profile = profile
        self._server_log_path = (
            Path("artifacts/fixes")
            / f"llama_b10182_mtp_{run_id}_{time.time_ns()}.log"
        ).resolve()
        super().__init__("q8", run_id)

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        if "--spec-type" in command:
            raise AssertionError("production command unexpectedly sets spec type")
        command.extend(["--log-file", str(self._server_log_path)])
        command.extend(["--spec-type", _SPEC_TYPES[self._spec_profile]])
        if self._spec_profile == "draft-mtp":
            command.extend(["--spec-draft-n-max", "1"])
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


def _run_arm(profile: str, run_id: str) -> dict[str, Any]:
    runtime = MtpRuntime(profile, run_id)
    cases: list[dict[str, Any]] = []
    server_pid: int | None = None
    started = time.perf_counter()
    try:
        # Keep startup synchronous in this standalone benchmark so a b10182
        # load/CLI error is surfaced instead of being swallowed by the
        # product warmup thread's intentionally fail-closed boundary.
        runtime._ensure_started()
        if not runtime.wait_warmup(0.0):
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
        "spec_draft_n_max": 1 if profile == "draft-mtp" else None,
        "server_log": str(runtime._server_log_path),
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
    if order == "none-mtp":
        return [
            ("order1-none", "none"),
            ("order1-mtp", "draft-mtp"),
        ]
    if order == "mtp-none":
        return [
            ("order2-mtp", "draft-mtp"),
            ("order2-none", "none"),
        ]
    if order == "both":
        return [
            ("order1-none", "none"),
            ("order1-mtp", "draft-mtp"),
            ("order2-mtp", "draft-mtp"),
            ("order2-none", "none"),
        ]
    raise ValueError(f"unknown order: {order}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("both", "none-mtp", "mtp-none"),
        default="both",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--server",
        type=Path,
        default=Path(
            r"C:\Users\usuario\AppData\Local\Temp"
            r"\baxy-llama-b10182-audit-20260729"
            r"\runtime\llama-server.exe"
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
        raise FileNotFoundError("official b10182/model audit assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ.pop("GGML_CUDA_GRAPH_OPT", None)
    os.environ.pop("CUDA_MODULE_LOADING", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server.resolve())
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model.resolve())
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    if args.validate_only:
        validations = {}
        for profile in ("none", "draft-mtp"):
            runtime = MtpRuntime(profile, f"validate-{profile}")
            try:
                command = runtime._server_command()
            finally:
                runtime.close()
            validations[profile] = {
                "spec_type": command[command.index("--spec-type") + 1],
                "spec_draft_n_max": (
                    command[command.index("--spec-draft-n-max") + 1]
                    if "--spec-draft-n-max" in command
                    else None
                ),
                "cache_type_k": command[command.index("-ctk") + 1],
                "cache_type_v": command[command.index("-ctv") + 1],
                "flash_attention": command[command.index("-fa") + 1],
                "parallel": command[command.index("-np") + 1],
            }
        print(json.dumps(validations, ensure_ascii=False, indent=2))
        return 0

    arms = [
        _run_arm(profile, run_id)
        for run_id, profile in _arm_plan(args.arm_order)
    ]
    by_id = {arm["run_id"]: arm for arm in arms}
    comparisons: list[dict[str, Any]] = []
    exact_case_outputs: list[dict[str, Any]] = []
    if args.arm_order in {"both", "none-mtp"}:
        baseline = by_id["order1-none"]
        candidate = by_id["order1-mtp"]
        comparisons.append(
            _compare_pair(
                pair_id="none-then-mtp",
                baseline=baseline,
                candidate=candidate,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "none-then-mtp",
                "equal": (
                    baseline["case_projection"]
                    == candidate["case_projection"]
                ),
            }
        )
    if args.arm_order in {"both", "mtp-none"}:
        candidate = by_id["order2-mtp"]
        baseline = by_id["order2-none"]
        comparisons.append(
            _compare_pair(
                pair_id="mtp-then-none",
                baseline=baseline,
                candidate=candidate,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "mtp-then-none",
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
        if arm["profile"] == "draft-mtp"
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
        "schema": "baxy.llama-b10182-mtp-ab.v1",
        "candidate_status": "research_only",
        "arm_order": args.arm_order,
        "runtime": {
            "release": "b10182",
            "commit": "afeebe1",
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
            "spec_type": "draft-mtp",
            "spec_draft_n_max": 1,
        },
        "control": {
            "only_variable": (
                "--spec-type none versus --spec-type draft-mtp "
                "--spec-draft-n-max 1"
            ),
            "fresh_server_per_arm": True,
            "same_payloads": True,
            "case_count_per_arm": len(CASES),
            "core_started": False,
            "external_effects_executed": False,
            "installed": False,
            "runtime_manifest_changed": False,
        },
        "measurement": {
            "raw_structured_tokens": (
                "llama.cpp b10182 __verbose.tokens via identical "
                "verbose=true and return_tokens=true"
            ),
            "draft_metrics": [
                "timings.draft_n",
                "timings.draft_n_accepted",
            ],
            "server_ready_seconds": True,
            "end_to_end_case_latency": True,
            "stage_latency": list(TARGET_STAGES),
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
            "Require generated drafts; exact raw tokens, raw and visible "
            "content, operations and final decisions in both orders; and "
            "lower turn p50 and total in both opposite-order pairs."
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
