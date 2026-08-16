"""Physical, effect-free A/B for q8_0 versus q4_0 KV cache.

The experiment keeps BAXY's official b9980 server, Gemma 4 model, prompts,
schemas, seeds, scheduling and request payloads fixed.  It changes only the
fresh server's K/V cache types:

* ``q8``: ``-ctk q8_0 -ctv q8_0`` (the production baseline);
* ``q4``: ``-ctk q4_0 -ctv q4_0`` (research candidate).

Both profiles retain ``-fa on``.  Structured calls request llama.cpp's raw
generated token ids in both arms for response-only observability.  The
workload never starts Core or executes an external effect.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    _case_projection,
    _run_case,
    _stage,
)
from benchmark_structured_top_k1 import (  # type: ignore[import-not-found]
    TARGET_STAGES,
    InstrumentedRuntime as TokenInstrumentedRuntime,
    _case_decision_projection,
    _compare_pair,
    _file_sha256,
    _finish_reason,
    _payload_fingerprint,
    _quantile,
    _raw_response_content,
    _raw_response_tokens,
    _response_content,
    _stage_summary,
)


_CACHE_TYPES = {
    "q8": ("q8_0", "q8_0"),
    "q4": ("q4_0", "q4_0"),
}
_MEASUREMENT_FIELDS = ("verbose", "return_tokens")


def _replace_option(command: list[str], option: str, value: str) -> None:
    try:
        index = command.index(option)
    except ValueError as exc:
        raise AssertionError(f"runtime command is missing {option}") from exc
    if index + 1 >= len(command):
        raise AssertionError(f"runtime command has no value after {option}")
    command[index + 1] = value


class KvQuantRuntime(TokenInstrumentedRuntime):
    def __init__(self, profile: str, run_id: str) -> None:
        if profile not in _CACHE_TYPES:
            raise ValueError(f"unknown KV profile: {profile}")
        self._kv_profile = profile
        # The inherited initializer supplies the benchmark locks, ordinals,
        # runtime lifecycle and disables speculative knowledge.  Its sampler
        # profile is irrelevant because _post is overridden below.
        super().__init__("baseline", run_id)

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        cache_k, cache_v = _CACHE_TYPES[self._kv_profile]
        _replace_option(command, "-ctk", cache_k)
        _replace_option(command, "-ctv", cache_v)
        if "-fa" not in command or command[command.index("-fa") + 1] != "on":
            raise AssertionError("KV quantization experiment requires -fa on")
        return command

    def _record_profile(self) -> str:
        return self._kv_profile

    def _extra_response_record(
        self,
        response: dict[str, Any],
        timings: dict[str, Any],
    ) -> dict[str, Any]:
        del response, timings
        return {}

    def _post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        wire = dict(payload)
        stage = _stage(wire)
        if stage in TARGET_STAGES:
            wire["verbose"] = True
            wire["return_tokens"] = True
        with self._benchmark_lock:
            case = self._benchmark_case
            ordinal_key = (case, stage)
            ordinal = self._benchmark_ordinals.get(ordinal_key, 0)
            self._benchmark_ordinals[ordinal_key] = ordinal + 1

        started = time.perf_counter()
        response = super(TokenInstrumentedRuntime, self)._post(
            wire,
            timeout,
            max_attempts=max_attempts,
            cancellation=cancellation,
        )
        elapsed = time.perf_counter() - started
        timings = response.get("timings")
        if not isinstance(timings, dict):
            timings = {}
        content = _response_content(response)
        record = {
            "run_id": self._benchmark_run_id,
            "profile": self._record_profile(),
            "case": case,
            "stage": stage,
            "stage_ordinal": ordinal,
            "temperature": payload.get("temperature"),
            "seed": payload.get("seed"),
            "payload_sha256_without_measurement": _payload_fingerprint(wire),
            # Keep the key expected by the shared exact-pair comparator.
            "payload_sha256_without_instrumentation_or_candidate": (
                _payload_fingerprint(wire)
            ),
            "measurement_fields": [
                field for field in _MEASUREMENT_FIELDS if field in wire
            ],
            "elapsed_seconds": elapsed,
            "cache_n": timings.get("cache_n"),
            "prompt_n": timings.get("prompt_n"),
            "prompt_ms": timings.get("prompt_ms"),
            "predicted_n": timings.get("predicted_n"),
            "predicted_ms": timings.get("predicted_ms"),
            "finish_reason": _finish_reason(response),
            "content": content,
            "raw_content": _raw_response_content(response),
            "tokens": _raw_response_tokens(response),
        }
        record.update(self._extra_response_record(response, timings))
        with self._benchmark_lock:
            self._benchmark_records.append(record)
        return response


def _run_arm(profile: str, run_id: str) -> dict[str, Any]:
    runtime = KvQuantRuntime(profile, run_id)
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
        "cache_type_k": _CACHE_TYPES[profile][0],
        "cache_type_v": _CACHE_TYPES[profile][1],
        "server_ready_seconds": ready_seconds,
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
    if order == "q8-q4":
        return [("order1-q8", "q8"), ("order1-q4", "q4")]
    if order == "q4-q8":
        return [("order2-q4", "q4"), ("order2-q8", "q8")]
    if order == "both":
        return [
            ("order1-q8", "q8"),
            ("order1-q4", "q4"),
            ("order2-q4", "q4"),
            ("order2-q8", "q8"),
        ]
    raise ValueError(f"unknown order: {order}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("both", "q8-q4", "q4-q8"),
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
        validations = {}
        for profile in ("q8", "q4"):
            runtime = KvQuantRuntime(profile, f"validate-{profile}")
            try:
                command = runtime._server_command()
            finally:
                runtime.close()
            validations[profile] = {
                "cache_type_k": command[command.index("-ctk") + 1],
                "cache_type_v": command[command.index("-ctv") + 1],
                "flash_attention": command[command.index("-fa") + 1],
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
    if args.arm_order in {"both", "q8-q4"}:
        comparisons.append(
            _compare_pair(
                pair_id="q8-then-q4",
                baseline=by_id["order1-q8"],
                candidate=by_id["order1-q4"],
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "q8-then-q4",
                "equal": (
                    by_id["order1-q8"]["case_projection"]
                    == by_id["order1-q4"]["case_projection"]
                ),
            }
        )
    if args.arm_order in {"both", "q4-q8"}:
        comparisons.append(
            _compare_pair(
                pair_id="q4-then-q8",
                baseline=by_id["order2-q8"],
                candidate=by_id["order2-q4"],
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "q4-then-q8",
                "equal": (
                    by_id["order2-q8"]["case_projection"]
                    == by_id["order2-q4"]["case_projection"]
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
    opposite_order_improvement = len(comparisons) == 2 and all(
        comparison["candidate_minus_baseline_structured_total_seconds"] < 0.0
        and comparison["candidate_minus_baseline_case_p50_seconds"] < 0.0
        and comparison["candidate_minus_baseline_case_total_seconds"] < 0.0
        for comparison in comparisons
    )
    smoke_gate_passed = (
        stage_coverage
        and mode_contracts
        and exact_equivalence
        and opposite_order_improvement
    )
    result = {
        "schema": "baxy.llama-kv-q4-ab.v1",
        "candidate_status": "research_only",
        "arm_order": args.arm_order,
        "runtime": {
            "server": str(args.server.resolve()),
            "server_sha256": _file_sha256(args.server),
            "model": str(args.model.resolve()),
            "parallel": 3,
            "context_per_slot": 4_096,
            "ngl": 99,
            "flash_attention": "on in both profiles",
        },
        "control": {
            "only_variable": (
                "-ctk/-ctv q8_0/q8_0 versus q4_0/q4_0"
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
            "target_stages": list(TARGET_STAGES),
            "end_to_end_case_latency": True,
        },
        "stage_coverage": stage_coverage,
        "mode_contracts": mode_contracts,
        "exact_case_outputs": exact_case_outputs,
        "exact_equivalence": exact_equivalence,
        "opposite_order_improvement": opposite_order_improvement,
        "comparisons": comparisons,
        "arms": arms,
        "smoke_gate_passed": smoke_gate_passed,
        "promotion_gate_passed": False,
        "promotion_rule": (
            "Reject immediately unless both orders preserve every raw "
            "structured token, content, final decision, extraction, language "
            "and free-form reply while improving structured total, turn p50 "
            "and turn total. Even a passing physical smoke remains research "
            "only until the expanded canonical corpus and tail gates prove no "
            "quality loss."
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
                    "opposite_order_improvement",
                    "smoke_gate_passed",
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
