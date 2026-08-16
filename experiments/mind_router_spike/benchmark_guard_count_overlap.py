"""Physical A/B for reusing G's released slot to start V before P ends.

Both arms use BAXY's unchanged prompts, JSON Schemas, model, llama.cpp build,
three-slot limit and reactive action tail.  The candidate only enables the
request-local scheduler flag that starts the candidate-free effect-count
validator after the semantic guard completes.  No Core capability is started
or executed.
"""

from __future__ import annotations

import argparse
import json
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


class TimelineRuntime(InstrumentedRuntime):
    def __init__(self, profile: str) -> None:
        self._overlap_profile = profile
        self.timeline: list[dict[str, Any]] = []
        self._timeline_lock = threading.Lock()
        super().__init__(profile)
        self._speculative_count_after_guard = profile == "overlap"

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


def _run_arm(profile: str) -> dict[str, Any]:
    runtime = TimelineRuntime(profile)
    cases: list[dict[str, Any]] = []
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        for case in CASES:
            cases.append(_run_case(runtime, case))
    finally:
        runtime.close()
    elapsed = [float(case["elapsed_seconds"]) for case in cases]
    action_elapsed = [
        float(case["elapsed_seconds"])
        for case in cases
        if case["expected_mode"] == "action"
    ]
    return {
        "profile": profile,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "timeline": runtime.timeline,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "elapsed_p50_seconds": statistics.median(elapsed),
        "elapsed_total_seconds": sum(elapsed),
        "action_p50_seconds": statistics.median(action_elapsed),
        "action_total_seconds": sum(action_elapsed),
    }


def _timeline_evidence(arm: dict[str, Any]) -> dict[str, Any]:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for record in arm["timeline"]:
        by_case.setdefault(str(record["case"]), []).append(record)
    evidence: list[dict[str, Any]] = []
    for case in arm["cases"]:
        if case["expected_mode"] != "action":
            continue
        records = by_case.get(str(case["case"]), [])
        policy = next(
            (record for record in records if record["stage"] == "P"),
            None,
        )
        guard = next(
            (record for record in records if record["stage"] == "G"),
            None,
        )
        count = next(
            (record for record in records if record["stage"] == "V"),
            None,
        )
        evidence.append(
            {
                "case": case["case"],
                "guard_finished_before_count_started": (
                    bool(guard and count)
                    and float(guard["finished"])
                    <= float(count["started"])
                ),
                "count_started_before_policy_finished": (
                    bool(policy and count)
                    and float(count["started"])
                    < float(policy["finished"])
                ),
                "count_finished_before_policy_finished": (
                    bool(policy and count)
                    and float(count["finished"])
                    <= float(policy["finished"])
                ),
                "policy_count_overlap_seconds": (
                    max(
                        0.0,
                        min(
                            float(policy["finished"]),
                            float(count["finished"]),
                        )
                        - max(
                            float(policy["started"]),
                            float(count["started"]),
                        ),
                    )
                    if policy and count
                    else 0.0
                ),
            }
        )
    return {
        "action_cases": evidence,
        "count_started_before_policy_finished": sum(
            1
            for item in evidence
            if item["count_started_before_policy_finished"]
        ),
        "count_finished_before_policy_finished": sum(
            1
            for item in evidence
            if item["count_finished_before_policy_finished"]
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("baseline-overlap", "overlap-baseline"),
        default="baseline-overlap",
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
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    arms = [_run_arm(profile) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    baseline_projection = [
        _case_projection(case) for case in by_profile["baseline"]["cases"]
    ]
    overlap_projection = [
        _case_projection(case) for case in by_profile["overlap"]["cases"]
    ]
    divergent_cases = [
        {
            "case": baseline["case"],
            "baseline": baseline,
            "overlap": candidate,
        }
        for baseline, candidate in zip(
            baseline_projection,
            overlap_projection,
            strict=True,
        )
        if baseline != candidate
    ]
    exact_outputs = not divergent_cases
    baseline = by_profile["baseline"]
    overlap = by_profile["overlap"]
    result = {
        "schema": "baxy.guard-count-overlap-ab.v1",
        "arm_order": arm_order,
        "safety": {
            "core_started": False,
            "external_effects_executed": False,
        },
        "control": {
            "only_variable": "_speculative_count_after_guard",
            "same_model_server_prompts_schemas": True,
            "maximum_executor_workers": 3,
            "fresh_server_per_arm": True,
        },
        "exact_outputs": exact_outputs,
        "divergent_cases": divergent_cases,
        "latency_delta_overlap_minus_baseline": {
            "all_p50_seconds": (
                float(overlap["elapsed_p50_seconds"])
                - float(baseline["elapsed_p50_seconds"])
            ),
            "all_total_seconds": (
                float(overlap["elapsed_total_seconds"])
                - float(baseline["elapsed_total_seconds"])
            ),
            "action_p50_seconds": (
                float(overlap["action_p50_seconds"])
                - float(baseline["action_p50_seconds"])
            ),
            "action_total_seconds": (
                float(overlap["action_total_seconds"])
                - float(baseline["action_total_seconds"])
            ),
        },
        "timeline_evidence": {
            profile: _timeline_evidence(arm)
            for profile, arm in by_profile.items()
        },
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require exact outputs, V after G and before P completion on action "
            "cases, and a repeatable action E2E gain in opposite arm orders "
            "without a non-action or tail regression."
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
                    "arm_order",
                    "exact_outputs",
                    "divergent_cases",
                    "latency_delta_overlap_minus_baseline",
                    "timeline_evidence",
                    "candidate_status",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if exact_outputs else 2


if __name__ == "__main__":
    raise SystemExit(main())
