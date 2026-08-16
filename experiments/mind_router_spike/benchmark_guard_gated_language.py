"""Physical, effect-free A/B for scheduling L only after G.

Both arms use the registered BAXY runtime, unchanged prompts, schemas, model,
three-slot server profile and validators.  The sole variable is the private
``_guard_gated_language`` scheduler flag:

* ``eager`` starts P, G and L together (the previous product schedule).
* ``gated`` starts P and G, then gives G's released slot to L for no-effect
  turns or to V for effect-shaped turns.

Every arm owns a fresh llama-server process.  Core is never started and no
provider/effect is executed.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import threading
import time
from pathlib import Path
from typing import Any

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    InstrumentedRuntime,
    _case_projection,
    _run_case,
    _stage,
    _stage_summary,
)


_PROFILES = ("eager", "gated")
_SMOKE_CASE_NAMES = frozenset({"task_create_a", "knowledge_a"})


class ScheduleRuntime(InstrumentedRuntime):
    def __init__(self, profile: str) -> None:
        if profile not in _PROFILES:
            raise ValueError(f"unknown scheduling profile: {profile}")
        self._schedule_profile = profile
        self.timeline: list[dict[str, Any]] = []
        self._timeline_lock = threading.Lock()
        # "auto" keeps request-local slot selection identical in both arms.
        super().__init__("auto")
        self._guard_gated_language = profile == "gated"
        self._speculative_count_after_guard = True
        self._speculative_knowledge_enabled = True

    def _post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        stage = _stage(payload)
        case = self._benchmark_case
        started = time.perf_counter()
        try:
            return super()._post(
                payload,
                timeout,
                max_attempts=max_attempts,
                cancellation=cancellation,
            )
        finally:
            finished = time.perf_counter()
            with self._timeline_lock:
                self.timeline.append(
                    {
                        "case": case,
                        "stage": stage,
                        "started": started,
                        "finished": finished,
                        "elapsed_seconds": finished - started,
                    }
                )


def _selected_cases(smoke: bool) -> tuple[Any, ...]:
    if not smoke:
        return tuple(CASES)
    selected = tuple(
        case for case in CASES if case.name in _SMOKE_CASE_NAMES
    )
    if {case.name for case in selected} != _SMOKE_CASE_NAMES:
        raise AssertionError("smoke workload no longer matches canonical cases")
    return selected


def _nearest_rank(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def _latency_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for group in ("all", "action", "conversation"):
        selected = [
            float(case["elapsed_seconds"])
            for case in cases
            if group == "all" or case["expected_mode"] == group
        ]
        result[group] = {
            "count": len(selected),
            "total_seconds": sum(selected),
            "p50_seconds": statistics.median(selected) if selected else None,
            "p95_seconds": _nearest_rank(selected, 0.95),
            "max_seconds": max(selected) if selected else None,
        }
    return result


def _run_arm(profile: str, cases_to_run: tuple[Any, ...]) -> dict[str, Any]:
    runtime = ScheduleRuntime(profile)
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
        "server_pid": server_pid,
        "server_ready_seconds": ready_seconds,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "timeline": runtime.timeline,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "latency": _latency_summary(cases),
    }


def _shared_post_projection(arm: dict[str, Any]) -> dict[str, list[list[Any]]]:
    grouped: dict[str, list[list[Any]]] = {}
    for record in arm["posts"]:
        stage = str(record["stage"])
        if stage == "L":
            continue
        key = f"{record['case']}::{stage}"
        grouped.setdefault(key, []).append(
            [
                record.get("payload_sha256"),
                record.get("content"),
            ]
        )
    return grouped


def _language_call_counts(arm: dict[str, Any]) -> dict[str, int]:
    expected_modes = {
        str(case["case"]): str(case["expected_mode"])
        for case in arm["cases"]
    }
    counts = {"action": 0, "conversation": 0}
    for record in arm["posts"]:
        if record["stage"] != "L":
            continue
        mode = expected_modes.get(str(record["case"]))
        if mode in counts:
            counts[mode] += 1
    return counts


def _case_deltas(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate_by_case = {
        str(case["case"]): case for case in candidate["cases"]
    }
    return [
        {
            "case": case["case"],
            "expected_mode": case["expected_mode"],
            "eager_seconds": case["elapsed_seconds"],
            "gated_seconds": candidate_by_case[str(case["case"])][
                "elapsed_seconds"
            ],
            "gated_minus_eager_seconds": (
                float(candidate_by_case[str(case["case"])]["elapsed_seconds"])
                - float(case["elapsed_seconds"])
            ),
        }
        for case in baseline["cases"]
    ]


def _latency_deltas(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for group in ("all", "action", "conversation"):
        result[group] = {}
        for metric in (
            "total_seconds",
            "p50_seconds",
            "p95_seconds",
            "max_seconds",
        ):
            eager = baseline["latency"][group][metric]
            gated = candidate["latency"][group][metric]
            result[group][f"{metric}_gated_minus_eager"] = (
                float(gated) - float(eager)
                if eager is not None and gated is not None
                else None
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("eager-gated", "gated-eager"),
        default="eager-gated",
    )
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
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("registered runtime assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    cases_to_run = _selected_cases(args.smoke)
    arm_order = args.arm_order.split("-")
    arms = [_run_arm(profile, cases_to_run) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    eager = by_profile["eager"]
    gated = by_profile["gated"]
    eager_projection = [
        _case_projection(case) for case in eager["cases"]
    ]
    gated_projection = [
        _case_projection(case) for case in gated["cases"]
    ]
    divergent_cases = [
        {
            "case": control["case"],
            "eager": control,
            "gated": candidate,
        }
        for control, candidate in zip(
            eager_projection,
            gated_projection,
            strict=True,
        )
        if control != candidate
    ]
    exact_outputs = not divergent_cases
    shared_post_content_exact = (
        _shared_post_projection(eager) == _shared_post_projection(gated)
    )
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    language_calls = {
        profile: _language_call_counts(arm)
        for profile, arm in by_profile.items()
    }
    expected_action_cases = sum(
        case.expected_mode == "action" for case in cases_to_run
    )
    expected_conversation_cases = sum(
        case.expected_mode == "conversation" for case in cases_to_run
    )
    scheduling_contracts = (
        language_calls["eager"]["action"] == expected_action_cases
        and language_calls["gated"]["action"] == 0
        and language_calls["eager"]["conversation"]
        == expected_conversation_cases
        and language_calls["gated"]["conversation"]
        == expected_conversation_cases
    )
    quality_gate = (
        exact_outputs
        and shared_post_content_exact
        and mode_contracts
        and scheduling_contracts
    )
    result = {
        "schema": "baxy.guard-gated-language-ab.v1",
        "arm_order": arm_order,
        "smoke": args.smoke,
        "safety": {
            "core_started": False,
            "external_effects_executed": False,
        },
        "control": {
            "only_variable": "_guard_gated_language",
            "same_model_server_prompts_schemas": True,
            "maximum_executor_workers": 3,
            "fresh_server_per_arm": True,
        },
        "quality": {
            "exact_outputs": exact_outputs,
            "shared_non_language_post_content_exact": (
                shared_post_content_exact
            ),
            "mode_contracts": mode_contracts,
            "scheduling_contracts": scheduling_contracts,
            "passed": quality_gate,
            "divergent_cases": divergent_cases,
        },
        "language_calls_by_expected_mode": language_calls,
        "case_deltas": _case_deltas(eager, gated),
        "latency_delta": _latency_deltas(eager, gated),
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require the full quality gate in both physical arm orders, zero "
            "L calls on gated action cases, repeatable action/all E2E gains, "
            "and no material conversation or tail regression."
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
                "smoke": args.smoke,
                "quality": result["quality"],
                "language_calls_by_expected_mode": language_calls,
                "latency_delta": result["latency_delta"],
                "case_deltas": result["case_deltas"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if quality_gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
