"""Physical A/B for request-local top-k=1 on greedy structured stages.

This experiment does not edit the product runtime.  It keeps the registered
model, server profile, prompts, schemas, seeds and request scheduling fixed and
changes exactly two request-local llama.cpp fields in the candidate arm:

    "samplers": ["top_k"]
    "top_k": 1

The fields are added only when the request is one of P/G/L/V/C/E and its
effective temperature is exactly 0.0.  Logical retries at 0.1/0.2, chat,
narration and every other request retain the current sampler chain.

Both arms request ``verbose`` plus ``return_tokens`` on the measured structured
POSTs.  llama.cpp b9980 then exposes the actual generated token ids under
``__verbose.tokens``; these response-only diagnostics are identical in both
arms and are excluded from the payload-equivalence fingerprint.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]  # noqa: E402
    CASES,
    _run_case,
    _stage,
)
from baxy_mind import llm as llm_module  # noqa: E402
from baxy_mind.llm import LlmRuntime  # noqa: E402


TARGET_STAGES = ("P", "G", "L", "V", "C", "E")
_MEASUREMENT_FIELDS = frozenset({"return_tokens", "verbose"})
_CANDIDATE_FIELDS = frozenset({"samplers", "top_k"})


def _is_exact_zero(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) == 0.0
    )


def _eligible(stage: str, payload: dict[str, Any]) -> bool:
    return stage in TARGET_STAGES and _is_exact_zero(payload.get("temperature"))


def _candidate_wire(
    payload: dict[str, Any],
    *,
    profile: str,
) -> tuple[dict[str, Any], str, bool]:
    if profile not in {"baseline", "topk1"}:
        raise ValueError(f"unknown profile: {profile}")
    wire = dict(payload)
    stage = _stage(wire)
    eligible = _eligible(stage, wire)
    if stage in TARGET_STAGES:
        # Response-only observability.  These fields are identical in both arms.
        wire["verbose"] = True
        wire["return_tokens"] = True
    if profile == "topk1" and eligible:
        wire["samplers"] = ["top_k"]
        wire["top_k"] = 1
    return wire, stage, eligible


def _payload_fingerprint(payload: dict[str, Any]) -> str:
    canonical = dict(payload)
    for field in _MEASUREMENT_FIELDS | _CANDIDATE_FIELDS:
        canonical.pop(field, None)
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _response_content(response: dict[str, Any]) -> str:
    try:
        choices = response["choices"]
        if not isinstance(choices, list) or not choices:
            return ""
        choice = choices[0]
        if not isinstance(choice, dict):
            return ""
        message = choice.get("message")
        if not isinstance(message, dict):
            return ""
        return str(message.get("content") or "")
    except (KeyError, TypeError):
        return ""


def _raw_response_content(response: dict[str, Any]) -> str | None:
    verbose = response.get("__verbose")
    if not isinstance(verbose, dict):
        return None
    content = verbose.get("content")
    return content if isinstance(content, str) else None


def _raw_response_tokens(response: dict[str, Any]) -> list[int] | None:
    verbose = response.get("__verbose")
    if not isinstance(verbose, dict):
        return None
    tokens = verbose.get("tokens")
    if not isinstance(tokens, list) or any(
        not isinstance(token, int) or isinstance(token, bool) for token in tokens
    ):
        return None
    return list(tokens)


def _finish_reason(response: dict[str, Any]) -> str | None:
    try:
        value = response["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        return None
    return value if isinstance(value, str) else None


def _numeric(records: list[dict[str, Any]], key: str) -> list[float]:
    return [
        float(record[key])
        for record in records
        if isinstance(record.get(key), (int, float))
        and not isinstance(record.get(key), bool)
    ]


def _quantile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1),
    )
    return ordered[index]


def _stage_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for stage in TARGET_STAGES:
        selected = [record for record in records if record["stage"] == stage]
        elapsed = _numeric(selected, "elapsed_seconds")
        predicted_n = _numeric(selected, "predicted_n")
        predicted_ms = _numeric(selected, "predicted_ms")
        prompt_n = _numeric(selected, "prompt_n")
        prompt_ms = _numeric(selected, "prompt_ms")
        cache_n = _numeric(selected, "cache_n")
        summary[stage] = {
            "calls": len(selected),
            "raw_token_calls": sum(
                isinstance(record.get("tokens"), list) for record in selected
            ),
            "predicted_n_total": sum(predicted_n),
            "predicted_n_p50": (
                statistics.median(predicted_n) if predicted_n else None
            ),
            "predicted_ms_total": sum(predicted_ms),
            "predicted_ms_p50": (
                statistics.median(predicted_ms) if predicted_ms else None
            ),
            "prompt_n_total": sum(prompt_n),
            "prompt_ms_total": sum(prompt_ms),
            "cache_n_total": sum(cache_n),
            "elapsed_total_seconds": sum(elapsed),
            "elapsed_p50_seconds": (statistics.median(elapsed) if elapsed else None),
            "elapsed_p95_seconds": _quantile(elapsed, 0.95),
            "elapsed_max_seconds": max(elapsed) if elapsed else None,
        }
    return summary


class InstrumentedRuntime(LlmRuntime):
    def __init__(self, profile: str, run_id: str) -> None:
        self._benchmark_profile = profile
        self._benchmark_run_id = run_id
        self._benchmark_case = ""
        self._benchmark_records: list[dict[str, Any]] = []
        self._benchmark_lock = threading.Lock()
        self._benchmark_ordinals: dict[tuple[str, str], int] = {}
        super().__init__()
        # Chat is deliberately out of scope; disabling speculative K makes the
        # P/G/L/V/C/E workload and its final decisions directly comparable.
        self._speculative_knowledge_enabled = False

    def _post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        original = dict(payload)
        wire, stage, eligible = _candidate_wire(
            original,
            profile=self._benchmark_profile,
        )
        with self._benchmark_lock:
            case = self._benchmark_case
            ordinal_key = (case, stage)
            ordinal = self._benchmark_ordinals.get(ordinal_key, 0)
            self._benchmark_ordinals[ordinal_key] = ordinal + 1
        sampler_applied = wire.get("samplers") == ["top_k"] and wire.get("top_k") == 1
        started = time.perf_counter()
        response = super()._post(
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
            "profile": self._benchmark_profile,
            "case": case,
            "stage": stage,
            "stage_ordinal": ordinal,
            "temperature": original.get("temperature"),
            "seed": original.get("seed"),
            "eligible": eligible,
            "sampler_applied": sampler_applied,
            "wire_samplers": copy.deepcopy(wire.get("samplers")),
            "wire_top_k": wire.get("top_k"),
            "payload_sha256_without_instrumentation_or_candidate": (
                _payload_fingerprint(wire)
            ),
            "elapsed_seconds": elapsed,
            "cache_n": timings.get("cache_n"),
            "prompt_n": timings.get("prompt_n"),
            "prompt_ms": timings.get("prompt_ms"),
            "predicted_n": timings.get("predicted_n"),
            "predicted_ms": timings.get("predicted_ms"),
            "finish_reason": _finish_reason(response),
            "content": content,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "raw_content": _raw_response_content(response),
            "tokens": _raw_response_tokens(response),
        }
        with self._benchmark_lock:
            self._benchmark_records.append(record)
        return response


def _case_decision_projection(case: dict[str, Any]) -> dict[str, Any]:
    # Free-form chat is explicitly outside the candidate.  The final routing
    # decision, language and structured E result are the relevant contract.
    return {
        "case": case["case"],
        "expected_mode": case["expected_mode"],
        "decision": copy.deepcopy(case["decision"]),
        "extraction": copy.deepcopy(case["extraction"]),
        "response_language": case["response_language"],
    }


def _run_arm(profile: str, run_id: str) -> dict[str, Any]:
    runtime = InstrumentedRuntime(profile, run_id)
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
    targeted = [
        record
        for record in runtime._benchmark_records
        if record["stage"] in TARGET_STAGES
    ]
    return {
        "run_id": run_id,
        "profile": profile,
        "cases": cases,
        "decision_projection": [_case_decision_projection(case) for case in cases],
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


def _post_map(arm: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, Any]]:
    selected = [record for record in arm["posts"] if record["stage"] in TARGET_STAGES]
    mapped = {
        (
            str(record["case"]),
            str(record["stage"]),
            int(record["stage_ordinal"]),
        ): record
        for record in selected
    }
    if len(mapped) != len(selected):
        raise AssertionError("duplicate structured post comparison key")
    return mapped


def _compare_pair(
    *,
    pair_id: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_posts = _post_map(baseline)
    candidate_posts = _post_map(candidate)
    all_keys = sorted(set(baseline_posts) | set(candidate_posts))
    comparisons: list[dict[str, Any]] = []
    for key in all_keys:
        base = baseline_posts.get(key)
        cand = candidate_posts.get(key)
        comparisons.append(
            {
                "case": key[0],
                "stage": key[1],
                "stage_ordinal": key[2],
                "present_in_both": base is not None and cand is not None,
                "payload_equal": (
                    base is not None
                    and cand is not None
                    and base["payload_sha256_without_instrumentation_or_candidate"]
                    == cand["payload_sha256_without_instrumentation_or_candidate"]
                ),
                "content_equal": (
                    base is not None
                    and cand is not None
                    and base["content"] == cand["content"]
                ),
                "raw_content_equal": (
                    base is not None
                    and cand is not None
                    and base["raw_content"] == cand["raw_content"]
                ),
                "tokens_available": (
                    base is not None
                    and cand is not None
                    and isinstance(base.get("tokens"), list)
                    and isinstance(cand.get("tokens"), list)
                ),
                "tokens_equal": (
                    base is not None
                    and cand is not None
                    and isinstance(base.get("tokens"), list)
                    and isinstance(cand.get("tokens"), list)
                    and base["tokens"] == cand["tokens"]
                ),
                "baseline_elapsed_seconds": (
                    base.get("elapsed_seconds") if base is not None else None
                ),
                "candidate_elapsed_seconds": (
                    cand.get("elapsed_seconds") if cand is not None else None
                ),
                "candidate_minus_baseline_seconds": (
                    float(cand["elapsed_seconds"]) - float(base["elapsed_seconds"])
                    if base is not None and cand is not None
                    else None
                ),
                "baseline_predicted_n": (
                    base.get("predicted_n") if base is not None else None
                ),
                "candidate_predicted_n": (
                    cand.get("predicted_n") if cand is not None else None
                ),
            }
        )

    stage_latency: dict[str, Any] = {}
    for stage in TARGET_STAGES:
        selected = [
            comparison
            for comparison in comparisons
            if comparison["stage"] == stage
            and isinstance(
                comparison.get("candidate_minus_baseline_seconds"),
                (int, float),
            )
        ]
        deltas = [
            float(comparison["candidate_minus_baseline_seconds"])
            for comparison in selected
        ]
        stage_latency[stage] = {
            "pairs": len(deltas),
            "candidate_minus_baseline_p50_seconds": (
                statistics.median(deltas) if deltas else None
            ),
            "candidate_minus_baseline_total_seconds": sum(deltas),
            "candidate_wins": sum(delta < 0.0 for delta in deltas),
            "candidate_losses": sum(delta > 0.0 for delta in deltas),
            "ties": sum(delta == 0.0 for delta in deltas),
        }
    decision_equal = baseline["decision_projection"] == candidate["decision_projection"]
    return {
        "pair_id": pair_id,
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
        "structured_post_count_equal": (len(baseline_posts) == len(candidate_posts)),
        "payloads_equal": all(item["payload_equal"] for item in comparisons),
        "contents_equal": all(item["content_equal"] for item in comparisons),
        "raw_contents_equal": all(item["raw_content_equal"] for item in comparisons),
        "raw_tokens_available": all(item["tokens_available"] for item in comparisons),
        "tokens_equal": all(item["tokens_equal"] for item in comparisons),
        "final_decisions_equal": decision_equal,
        "candidate_minus_baseline_structured_total_seconds": (
            float(candidate["structured_elapsed_total_seconds"])
            - float(baseline["structured_elapsed_total_seconds"])
        ),
        "candidate_minus_baseline_case_p50_seconds": (
            float(candidate["case_elapsed_p50_seconds"])
            - float(baseline["case_elapsed_p50_seconds"])
        ),
        "candidate_minus_baseline_case_total_seconds": (
            float(candidate["case_elapsed_total_seconds"])
            - float(baseline["case_elapsed_total_seconds"])
        ),
        "stage_latency": stage_latency,
        "posts": comparisons,
    }


def _selector_contract() -> dict[str, Any]:
    def payload(stage: str, temperature: float) -> dict[str, Any]:
        stage_prompts = {
            "P": llm_module.TURN_POLICY_PROMPT,
            "G": llm_module.SEMANTIC_EFFECT_GUARD_PROMPT,
            "L": llm_module.RESPONSE_LANGUAGE_PROMPT,
            "V": llm_module.EFFECT_COUNT_VERIFIER_PROMPT,
            "C": llm_module.OPERATION_COMPATIBILITY_PROMPT,
            "chat": llm_module.SYSTEM_PROMPT,
            "narrate": llm_module.NARRATOR_PROMPT,
        }
        base: dict[str, Any] = {
            "messages": [
                {
                    "role": "system",
                    "content": stage_prompts.get(stage, "unrelated"),
                }
            ],
            "temperature": temperature,
        }
        if stage == "E":
            base["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "direct_grounded_arguments"},
            }
        return base

    matrix = [(stage, 0.0, True) for stage in TARGET_STAGES] + [
        ("P", 0.1, False),
        ("E", 0.2, False),
        ("chat", 0.0, False),
        ("chat", 0.7, False),
        ("narrate", 0.4, False),
        ("other", 0.0, False),
    ]
    checks: list[dict[str, Any]] = []
    for stage, temperature, expected in matrix:
        source = payload(stage, temperature)
        baseline, detected, baseline_eligible = _candidate_wire(
            source,
            profile="baseline",
        )
        candidate, candidate_detected, candidate_eligible = _candidate_wire(
            source,
            profile="topk1",
        )
        applied = candidate.get("samplers") == ["top_k"] and candidate.get("top_k") == 1
        passed = (
            detected == candidate_detected
            and baseline_eligible == candidate_eligible
            and candidate_eligible == expected
            and applied == expected
            and "samplers" not in baseline
            and "top_k" not in baseline
            and _payload_fingerprint(baseline) == _payload_fingerprint(candidate)
        )
        checks.append(
            {
                "requested_stage": stage,
                "detected_stage": detected,
                "temperature": temperature,
                "expected_candidate": expected,
                "candidate_applied": applied,
                "passed": passed,
            }
        )
    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _arm_plan(order: str) -> list[tuple[str, str]]:
    if order == "baseline-topk1":
        return [("order1-baseline", "baseline"), ("order1-topk1", "topk1")]
    if order == "topk1-baseline":
        return [("order2-topk1", "topk1"), ("order2-baseline", "baseline")]
    if order == "both":
        return [
            ("order1-baseline", "baseline"),
            ("order1-topk1", "topk1"),
            ("order2-topk1", "topk1"),
            ("order2-baseline", "baseline"),
        ]
    raise ValueError(f"unknown order: {order}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "artifacts"
        / "fixes"
        / "llama_structured_top_k1_ab_20260729.json",
    )
    parser.add_argument(
        "--arm-order",
        choices=("both", "baseline-topk1", "topk1-baseline"),
        default="both",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--server",
        type=Path,
        default=Path(r"D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe"),
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

    selector_contract = _selector_contract()
    if not selector_contract["passed"]:
        print(json.dumps(selector_contract, ensure_ascii=False, indent=2))
        return 3
    if args.validate_only:
        print(json.dumps(selector_contract, ensure_ascii=False, indent=2))
        return 0
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("official runtime assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arms = [_run_arm(profile, run_id) for run_id, profile in _arm_plan(args.arm_order)]
    arms_by_id = {arm["run_id"]: arm for arm in arms}
    comparisons: list[dict[str, Any]] = []
    if args.arm_order in {"both", "baseline-topk1"}:
        comparisons.append(
            _compare_pair(
                pair_id="baseline-then-topk1",
                baseline=arms_by_id["order1-baseline"],
                candidate=arms_by_id["order1-topk1"],
            )
        )
    if args.arm_order in {"both", "topk1-baseline"}:
        comparisons.append(
            _compare_pair(
                pair_id="topk1-then-baseline",
                baseline=arms_by_id["order2-baseline"],
                candidate=arms_by_id["order2-topk1"],
            )
        )

    stage_coverage = all(
        arm["stage_summary"][stage]["calls"] > 0
        for arm in arms
        for stage in TARGET_STAGES
    )
    sampler_scope_valid = all(
        (
            record["sampler_applied"]
            == (arm["profile"] == "topk1" and bool(record["eligible"]))
        )
        for arm in arms
        for record in arm["posts"]
    )
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    exact_equivalence = all(
        comparison["payloads_equal"]
        and comparison["contents_equal"]
        and comparison["raw_contents_equal"]
        and comparison["raw_tokens_available"]
        and comparison["tokens_equal"]
        and comparison["final_decisions_equal"]
        for comparison in comparisons
    )
    opposite_order_improvement = len(comparisons) == 2 and all(
        comparison["candidate_minus_baseline_structured_total_seconds"] < 0.0
        and comparison["candidate_minus_baseline_case_p50_seconds"] < 0.0
        for comparison in comparisons
    )
    result = {
        "schema": "baxy.structured-top-k1-ab.v1",
        "candidate_status": "research_only",
        "arm_order": args.arm_order,
        "selector_contract": selector_contract,
        "candidate": {
            "samplers": ["top_k"],
            "top_k": 1,
            "scope": "P/G/L/V/C/E with effective temperature exactly 0.0",
            "explicit_exclusions": [
                "logical retries at temperature 0.1 or 0.2",
                "chat at every temperature",
                "narration at temperature 0.4",
                "all non-structured or unrecognized stages",
            ],
        },
        "runtime": {
            "server": str(args.server.resolve()),
            "server_sha256": _file_sha256(args.server),
            "model": str(args.model.resolve()),
            "model_sha256": _file_sha256(args.model),
            "parallel": 3,
            "context_per_slot": 4096,
            "ngl": 99,
            "request_timeout_seconds": 19,
        },
        "measurement": {
            "raw_tokens": (
                "llama.cpp b9980 __verbose.tokens via identical "
                "verbose=true, return_tokens=true on both structured arms"
            ),
            "target_stages": list(TARGET_STAGES),
            "fresh_server_per_arm": True,
        },
        "stage_coverage": stage_coverage,
        "sampler_scope_valid": sampler_scope_valid,
        "mode_contracts": mode_contracts,
        "exact_equivalence": exact_equivalence,
        "opposite_order_improvement": opposite_order_improvement,
        "comparisons": comparisons,
        "arms": arms,
        "promotion_gate_passed": (
            stage_coverage
            and sampler_scope_valid
            and mode_contracts
            and exact_equivalence
            and opposite_order_improvement
        ),
        "promotion_rule": (
            "Require raw token, content, payload and final-decision equality in "
            "both orders, correct sampler scope, full P/G/L/V/C/E coverage, and "
            "lower structured total plus turn p50 in both opposite-order pairs."
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
                    "sampler_scope_valid",
                    "mode_contracts",
                    "exact_equivalence",
                    "opposite_order_improvement",
                    "promotion_gate_passed",
                    "comparisons",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["promotion_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
