"""Physical, effect-free A/B for a small speculative-L launch stagger.

The control and candidate execute identical P/G/L/V/C/E/chat requests.  The
candidate delays only the speculative L worker by ``--delay-ms`` so P and G can
prefill first; authoritative language calls outside the parallel scheduler are
never delayed.  This explores the continuum between eager P+G+L and fully
guard-gated L without changing any model contract or final validator.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from benchmark_guard_gated_language import (  # type: ignore[import-not-found]
    ScheduleRuntime,
    _latency_deltas,
    _latency_summary,
    _selected_cases,
)
from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    _case_projection,
    _run_case,
    _stage_summary,
)


class StaggerRuntime(ScheduleRuntime):
    def __init__(self, profile: str, delay_seconds: float) -> None:
        if profile not in {"eager", "stagger"}:
            raise ValueError(f"unknown stagger profile: {profile}")
        self._stagger_profile = profile
        self._stagger_seconds = delay_seconds if profile == "stagger" else 0.0
        super().__init__("eager")

    def detect_response_language(
        self,
        text: str,
        *,
        cancellation: Any = None,
        cache_result: bool = True,
    ) -> str:
        if cancellation is not None and self._stagger_seconds > 0:
            deadline = time.monotonic() + self._stagger_seconds
            while True:
                cancellation.raise_if_cancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(0.01, remaining))
        return super().detect_response_language(
            text,
            cancellation=cancellation,
            cache_result=cache_result,
        )


def _run_arm(
    profile: str,
    delay_seconds: float,
    cases_to_run: tuple[Any, ...],
) -> dict[str, Any]:
    runtime = StaggerRuntime(profile, delay_seconds)
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
        for case in cases_to_run:
            cases.append(_run_case(runtime, case))
    finally:
        owned_process = runtime._process
        runtime.close()
        if owned_process is not None and owned_process.poll() is None:
            raise RuntimeError("llama-server child survived runtime.close()")
    return {
        "profile": profile,
        "delay_seconds": runtime._stagger_seconds,
        "server_pid": server_pid,
        "server_ready_seconds": ready_seconds,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "timeline": runtime.timeline,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "latency": _latency_summary(cases),
    }


def _strict_projection(case: dict[str, Any]) -> dict[str, Any]:
    projection = _case_projection(case)
    projection.pop("reply", None)
    return projection


def _post_projection(arm: dict[str, Any]) -> dict[str, list[list[Any]]]:
    grouped: dict[str, list[list[Any]]] = {}
    for record in arm["posts"]:
        key = f"{record['case']}::{record['stage']}"
        grouped.setdefault(key, []).append(
            [
                record.get("payload_sha256"),
                record.get("content"),
            ]
        )
    return grouped


def _language_start_offsets(arm: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for case in arm["cases"]:
        records = [
            record
            for record in arm["timeline"]
            if record["case"] == case["case"]
        ]
        policy = next(
            (record for record in records if record["stage"] == "P"),
            None,
        )
        guard = next(
            (record for record in records if record["stage"] == "G"),
            None,
        )
        language = next(
            (record for record in records if record["stage"] == "L"),
            None,
        )
        result.append(
            {
                "case": case["case"],
                "language_after_policy_start_seconds": (
                    float(language["started"]) - float(policy["started"])
                    if language and policy
                    else None
                ),
                "language_finished_before_guard": (
                    bool(language and guard)
                    and float(language["finished"]) <= float(guard["finished"])
                ),
                "language_finished_before_policy": (
                    bool(language and policy)
                    and float(language["finished"]) <= float(policy["finished"])
                ),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("eager-stagger", "stagger-eager"),
        default="eager-stagger",
    )
    parser.add_argument("--delay-ms", type=float, required=True)
    parser.add_argument("--smoke", action="store_true")
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
    if (
        not args.server.is_file()
        or not args.model.is_file()
        or not 0.0 < args.delay_ms <= 2_000.0
    ):
        raise ValueError("invalid assets or delay")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    delay_seconds = args.delay_ms / 1_000.0
    cases_to_run = _selected_cases(args.smoke)
    arm_order = args.arm_order.split("-")
    arms = [
        _run_arm(profile, delay_seconds, cases_to_run)
        for profile in arm_order
    ]
    by_profile = {arm["profile"]: arm for arm in arms}
    eager = by_profile["eager"]
    stagger = by_profile["stagger"]
    strict_final_exact = [
        _strict_projection(case) for case in eager["cases"]
    ] == [_strict_projection(case) for case in stagger["cases"]]
    reply_exact = [
        case.get("reply") for case in eager["cases"]
    ] == [case.get("reply") for case in stagger["cases"]]
    all_posts_exact = _post_projection(eager) == _post_projection(stagger)
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    quality_gate = strict_final_exact and mode_contracts
    result = {
        "schema": "baxy.language-stagger-ab.v1",
        "arm_order": arm_order,
        "delay_ms": args.delay_ms,
        "smoke": args.smoke,
        "safety": {
            "core_started": False,
            "external_effects_executed": False,
        },
        "control": {
            "only_variable": "speculative L launch delay",
            "identical_requests_prompts_schemas": True,
            "authoritative_L_never_delayed": True,
            "fresh_server_per_arm": True,
        },
        "quality": {
            "strict_final_without_free_reply_exact": strict_final_exact,
            "free_reply_exact": reply_exact,
            "all_post_wire_and_content_exact": all_posts_exact,
            "mode_contracts": mode_contracts,
            "passed": quality_gate,
        },
        "latency_delta_stagger_minus_eager": _latency_deltas(eager, stagger),
        "language_timeline": {
            profile: _language_start_offsets(arm)
            for profile, arm in by_profile.items()
        },
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require final exactness and both physical orders to improve "
            "all/action/conversation p50 and tails, with every staggered L "
            "finishing before G on conversation cases."
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
                "arm_order": arm_order,
                "delay_ms": args.delay_ms,
                "smoke": args.smoke,
                "quality": result["quality"],
                "latency_delta_stagger_minus_eager": result[
                    "latency_delta_stagger_minus_eager"
                ],
                "language_timeline": result["language_timeline"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if quality_gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
