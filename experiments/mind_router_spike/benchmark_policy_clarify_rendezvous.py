"""Physical A/B for the P-first clarification rendezvous.

Both arms execute the current BAXY runtime with the same model, prompts,
schemas, candidates, three-slot server and clarification inputs.  The control
arm reproduces the former scheduler barrier by withholding a completed P from
the scheduler until G has finished.  The rendezvous arm uses the production
scheduler unchanged, so a P-first ``clarify`` may cancel G and L immediately.

The barrier is confined to this experiment's transport wrapper.  No Core
capability is started and no external effect can be executed.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.llm import LlmRuntime  # noqa: E402

from benchmark_llama_slot_pinning import (  # noqa: E402
    _payload_fingerprint,
    _response_content,
    _stage,
    _stage_summary,
)


@dataclass(frozen=True)
class ClarifyCase:
    name: str
    text: str


CASES = (
    ClarifyCase("critical_ambiguous_reference_es", "Abre eso"),
)

APP_OPEN_CANDIDATE: dict[str, Any] = {
    "name": "app.open",
    "description": (
        "Abre por nombre exacto una aplicación del catálogo Inicio del usuario "
        "y verifica su proceso, ventana visible y foco; también acepta "
        "windows.notepad y windows.calculator."
    ),
    "arguments_schema": {
        "type": "object",
        "properties": {
            "appId": {
                "type": "string",
                "x-maxUtf8Bytes": 512,
                "x-nonWhitespace": True,
            }
        },
        "required": ["appId"],
        "additionalProperties": False,
    },
}


def _existing_llama_servers() -> list[dict[str, str]]:
    """Return existing Windows llama-server processes without altering them."""

    completed = subprocess.run(
        [
            "tasklist",
            "/FI",
            "IMAGENAME eq llama-server.exe",
            "/FO",
            "CSV",
            "/NH",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    rows: list[dict[str, str]] = []
    for fields in csv.reader(completed.stdout.splitlines()):
        if len(fields) < 2 or fields[0].lower() != "llama-server.exe":
            continue
        rows.append({"image": fields[0], "pid": fields[1]})
    return rows


class ClarifyTimelineRuntime(LlmRuntime):
    """Record successful and cancelled P/G/L requests for one A/B arm."""

    def __init__(self, profile: str) -> None:
        self._benchmark_profile = profile
        self._benchmark_case = ""
        self._benchmark_records: list[dict[str, Any]] = []
        self._benchmark_lock = threading.Lock()
        self._guard_finished = threading.Event()
        self._language_finished = threading.Event()
        super().__init__()
        self._parallel_turn_verification = True
        self._speculative_count_after_guard = True
        self._speculative_knowledge_enabled = False

    def begin_case(self, name: str) -> None:
        self._benchmark_case = name
        self._guard_finished = threading.Event()
        self._language_finished = threading.Event()

    def settle_case(self, timeout: float = 10.0) -> bool:
        """Wait outside measured latency for cancelled sockets to retire."""

        deadline = time.monotonic() + timeout
        for event in (self._guard_finished, self._language_finished):
            remaining = deadline - time.monotonic()
            if remaining <= 0.0 or not event.wait(remaining):
                return False
        return True

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
        model_finished: float | None = None
        response: dict[str, Any] | None = None
        outcome = "success"
        error_type: str | None = None
        try:
            response = super()._post(
                payload,
                timeout,
                max_attempts=max_attempts,
                cancellation=cancellation,
            )
            model_finished = time.perf_counter()
            if self._benchmark_profile == "barrier" and stage == "P":
                if not self._guard_finished.wait(30.0):
                    raise TimeoutError(
                        "the control barrier did not observe G completion"
                    )
            return response
        except BaseException as exc:
            error_type = type(exc).__name__
            outcome = (
                "cancelled"
                if cancellation is not None
                and bool(getattr(cancellation, "cancelled", False))
                else "error"
            )
            raise
        finally:
            finished = time.perf_counter()
            timings = (
                response.get("timings")
                if isinstance(response, dict)
                and isinstance(response.get("timings"), dict)
                else {}
            )
            record = {
                "case": case,
                "stage": stage,
                "payload_sha256": _payload_fingerprint(payload),
                "outcome": outcome,
                "error_type": error_type,
                "started": started,
                "model_finished": model_finished,
                "finished": finished,
                "model_elapsed_seconds": (
                    model_finished - started
                    if model_finished is not None
                    else None
                ),
                "elapsed_seconds": finished - started,
                "scheduler_elapsed_seconds": finished - started,
                "cache_n": timings.get("cache_n"),
                "prompt_n": timings.get("prompt_n"),
                "prompt_ms": timings.get("prompt_ms"),
                "predicted_n": timings.get("predicted_n"),
                "predicted_ms": timings.get("predicted_ms"),
                "content": (
                    _response_content(response)
                    if isinstance(response, dict)
                    else ""
                ),
            }
            with self._benchmark_lock:
                self._benchmark_records.append(record)
            if stage == "G":
                self._guard_finished.set()
            elif stage == "L":
                self._language_finished.set()


def _run_case(
    runtime: ClarifyTimelineRuntime,
    case: ClarifyCase,
    repetition: int,
) -> dict[str, Any]:
    case_id = f"{case.name}_{repetition:02d}"
    runtime.begin_case(case_id)
    runtime.begin_request(55.0)
    started = time.perf_counter()
    decision: dict[str, Any]
    returned: float
    try:
        decision = runtime.decide_turn(
            case.text,
            [copy.deepcopy(APP_OPEN_CANDIDATE)],
            evidence=[],
        )
        returned = time.perf_counter()
        runtime.retire_deferred_response_language(case.text)
    finally:
        runtime.end_request()
    settled = runtime.settle_case()
    return {
        "case": case_id,
        "source_case": case.name,
        "repetition": repetition,
        "text": case.text,
        "expected_mode": "clarify",
        "elapsed_seconds": returned - started,
        "returned": returned,
        "settled": settled,
        "decision": copy.deepcopy(decision),
    }


def _case_evidence(
    case: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = [
        record for record in records if record["case"] == case["case"]
    ]
    by_stage = {str(record["stage"]): record for record in selected}
    policy = by_stage.get("P")
    guard = by_stage.get("G")
    language = by_stage.get("L")
    policy_model_finished = (
        policy.get("model_finished") if policy is not None else None
    )
    guard_finished = guard.get("finished") if guard is not None else None
    try:
        policy_content = (
            json.loads(str(policy.get("content") or ""))
            if policy is not None
            else None
        )
    except json.JSONDecodeError:
        policy_content = None
    return {
        "case": case["case"],
        "stages": [str(record["stage"]) for record in selected],
        "post_count": len(selected),
        "maximum_three_posts": len(selected) <= 3,
        "no_count_or_compatibility_post": not any(
            record["stage"] in {"V", "C"} for record in selected
        ),
        "policy_model_finished_before_guard": (
            isinstance(policy_model_finished, (int, float))
            and isinstance(guard_finished, (int, float))
            and float(policy_model_finished) < float(guard_finished)
        ),
        "decision_returned_before_guard_retired": (
            isinstance(guard_finished, (int, float))
            and float(case["returned"]) < float(guard_finished)
        ),
        "guard_outcome": guard.get("outcome") if guard else None,
        "language_outcome": language.get("outcome") if language else None,
        "policy_mode": (
            policy_content.get("mode")
            if isinstance(policy_content, dict)
            else None
        ),
    }


def _run_arm(profile: str, repetitions: int) -> dict[str, Any]:
    runtime = ClarifyTimelineRuntime(profile)
    cases: list[dict[str, Any]] = []
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        for repetition in range(1, repetitions + 1):
            for case in CASES:
                cases.append(_run_case(runtime, case, repetition))
    finally:
        runtime.close()
    elapsed = [float(case["elapsed_seconds"]) for case in cases]
    evidence = [
        _case_evidence(case, runtime._benchmark_records) for case in cases
    ]
    return {
        "profile": profile,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "evidence": evidence,
        "elapsed_p50_seconds": statistics.median(elapsed),
        "elapsed_max_seconds": max(elapsed),
        "elapsed_total_seconds": sum(elapsed),
        "all_expected_modes": all(
            case["decision"].get("mode") == case["expected_mode"]
            for case in cases
        ),
        "all_sockets_settled": all(bool(case["settled"]) for case in cases),
        "all_maximum_three_posts": all(
            bool(item["maximum_three_posts"]) for item in evidence
        ),
        "all_without_v_or_c": all(
            bool(item["no_count_or_compatibility_post"])
            for item in evidence
        ),
    }


def _projection(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case": case["case"],
        "text": case["text"],
        "decision": case["decision"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help=(
            "run only the production rendezvous arm and require every initial "
            "P to clarify plus at least one observed P-first cancellation"
        ),
    )
    parser.add_argument(
        "--arm-order",
        choices=("barrier-rendezvous", "rendezvous-barrier"),
        default="barrier-rendezvous",
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
    if args.repetitions < 1:
        raise ValueError("--repetitions must be positive")
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("official runtime assets are missing")
    existing = _existing_llama_servers()
    if existing:
        raise RuntimeError(
            "refusing to overlap an existing llama-server campaign: "
            + json.dumps(existing, ensure_ascii=False)
        )

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    if args.preflight:
        arm = _run_arm("rendezvous", args.repetitions)
        policy_clarifications = sum(
            1
            for item in arm["evidence"]
            if item["policy_mode"] == "clarify"
        )
        policy_first_cancellations = sum(
            1
            for item in arm["evidence"]
            if item["policy_mode"] == "clarify"
            and item["policy_model_finished_before_guard"]
            and item["guard_outcome"] == "cancelled"
        )
        passed = (
            policy_clarifications == len(arm["cases"])
            and policy_first_cancellations > 0
            and bool(arm["all_expected_modes"])
            and bool(arm["all_sockets_settled"])
            and bool(arm["all_maximum_three_posts"])
            and bool(arm["all_without_v_or_c"])
        )
        result = {
            "schema": "baxy.policy-clarify-rendezvous-preflight.v1",
            "profile": "rendezvous",
            "repetitions": args.repetitions,
            "server": str(args.server.resolve()),
            "model": str(args.model.resolve()),
            "safety": {
                "preexisting_llama_server": False,
                "fresh_server": True,
                "core_started": False,
                "external_effects_executed": False,
            },
            "passed": passed,
            "policy_clarifications": policy_clarifications,
            "required_policy_clarifications": len(arm["cases"]),
            "policy_first_cancellations": policy_first_cancellations,
            "arm": arm,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if passed else 2

    arm_order = args.arm_order.split("-")
    arms = [_run_arm(profile, args.repetitions) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    barrier = by_profile["barrier"]
    rendezvous = by_profile["rendezvous"]
    barrier_projection = [_projection(case) for case in barrier["cases"]]
    rendezvous_projection = [
        _projection(case) for case in rendezvous["cases"]
    ]
    exact_outputs = barrier_projection == rendezvous_projection
    rendezvous_cancellations = sum(
        1
        for item in rendezvous["evidence"]
        if item["guard_outcome"] == "cancelled"
    )
    rendezvous_returned_before_guard = sum(
        1
        for item in rendezvous["evidence"]
        if item["decision_returned_before_guard_retired"]
    )
    rendezvous_policy_first_cancellations = sum(
        1
        for item in rendezvous["evidence"]
        if item["guard_outcome"] == "cancelled"
        and item["policy_model_finished_before_guard"]
    )
    quality_and_shape_pass = (
        exact_outputs
        and all(bool(arm["all_expected_modes"]) for arm in arms)
        and all(bool(arm["all_sockets_settled"]) for arm in arms)
        and all(bool(arm["all_maximum_three_posts"]) for arm in arms)
        and all(bool(arm["all_without_v_or_c"]) for arm in arms)
    )
    latency_delta_p50 = (
        float(rendezvous["elapsed_p50_seconds"])
        - float(barrier["elapsed_p50_seconds"])
    )
    observed_short_circuit = rendezvous_policy_first_cancellations > 0
    result = {
        "schema": "baxy.policy-clarify-rendezvous-ab.v1",
        "arm_order": arm_order,
        "repetitions": args.repetitions,
        "server": str(args.server.resolve()),
        "model": str(args.model.resolve()),
        "safety": {
            "preexisting_llama_server": False,
            "fresh_server_per_arm": True,
            "core_started": False,
            "external_effects_executed": False,
        },
        "control": {
            "only_variable": (
                "control withholds a completed P until G finishes; candidate "
                "uses the production FIRST_COMPLETED rendezvous"
            ),
            "same_model_server_prompts_schemas_candidates": True,
            "maximum_executor_workers": 3,
        },
        "exact_outputs": exact_outputs,
        "quality_and_shape_pass": quality_and_shape_pass,
        "observed_short_circuit": observed_short_circuit,
        "rendezvous_guard_cancellations": rendezvous_cancellations,
        "rendezvous_policy_first_cancellations": (
            rendezvous_policy_first_cancellations
        ),
        "rendezvous_returns_before_guard_retired": (
            rendezvous_returned_before_guard
        ),
        "latency_delta_rendezvous_minus_barrier": {
            "p50_seconds": latency_delta_p50,
            "total_seconds": (
                float(rendezvous["elapsed_total_seconds"])
                - float(barrier["elapsed_total_seconds"])
            ),
            "max_seconds": (
                float(rendezvous["elapsed_max_seconds"])
                - float(barrier["elapsed_max_seconds"])
            ),
        },
        "arms": arms,
        "promotion_rule": (
            "Promote only with exact decisions, all expected clarification "
            "modes, no V/C, at most P/G/L, settled cancelled sockets, an "
            "observed P-first cancellation, and a repeated opposite-order "
            "p50 improvement without tail regression."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not quality_and_shape_pass:
        return 2
    if not observed_short_circuit or latency_delta_p50 >= 0.0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
