"""Physical A/B for first-turn P/G/L prefix priming on llama.cpp b9980.

This experiment deliberately does not change BAXY production code.  Each
individual case and arm starts a fresh, internally owned llama-server.  The
baseline sends the first real turn immediately after ``/health`` becomes
ready.  The candidate first pre-evaluates only token prefixes that are common
to every possible first-turn P, G and L request, then sends the exact same real
turn.

The priming prefixes are derived from llama-server itself:

* ``/apply-template`` formats several synthetic suffix variants;
* ``/tokenize`` turns those prompts into model token IDs;
* their token-level longest common prefix, with one final token removed
  conservatively, is submitted to ``/completion`` with one predicted token.

No real case text is present in a priming request.  P/G/L prefixes are primed
concurrently into the three existing slots.  The report keeps startup-to-ready,
priming, real first-turn and startup-to-complete timings separate so a faster
hot first turn cannot hide latency merely moved into warmup.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import statistics
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    InstrumentedRuntime,
    _case_projection,
    _run_case,
    _stage_summary,
)
from baxy_mind import llm as llm_module


_PREFIX_SENTINELS = (
    "Alpha",
    "Zulu",
    "¿Qué?",
    "9",
    "日本語",
)
_PRIME_SLOTS = {"P": 0, "G": 1, "L": 2}


def _http_json(
    endpoint: str,
    path: str,
    payload: dict[str, Any],
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{endpoint}{path}",
        data=json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise TypeError(f"{path} did not return a JSON object")
    return decoded


def _language_messages(text: str) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": llm_module.RESPONSE_LANGUAGE_PROMPT}
    ]
    for example, language in llm_module._RESPONSE_LANGUAGE_EXAMPLES:
        messages.extend(
            [
                {
                    "role": "user",
                    "content": f"Mensaje actual:\n{example}",
                },
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {"language": language},
                        separators=(",", ":"),
                    ),
                },
            ]
        )
    messages.append(
        {"role": "user", "content": f"Mensaje actual:\n{text}"}
    )
    return messages


def _messages_for_stage(stage: str, text: str) -> list[dict[str, str]]:
    if stage == "P":
        return [
            {"role": "system", "content": llm_module.TURN_POLICY_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Mensaje actual:\n{text}\n\n"
                    "Operaciones candidatas:\n"
                    "synthetic.prefix | never executed"
                ),
            },
        ]
    if stage == "G":
        return [
            {
                "role": "system",
                "content": llm_module.SEMANTIC_EFFECT_GUARD_PROMPT,
            },
            {"role": "user", "content": f"Mensaje actual:\n{text}"},
        ]
    if stage == "L":
        return _language_messages(text)
    raise ValueError(f"unsupported priming stage: {stage}")


def _longest_common_prefix(
    sequences: list[list[int]],
) -> list[int]:
    if not sequences:
        return []
    limit = min(len(sequence) for sequence in sequences)
    index = 0
    while index < limit:
        token = sequences[0][index]
        if any(sequence[index] != token for sequence in sequences[1:]):
            break
        index += 1
    return sequences[0][:index]


def _derive_stage_prefix(
    endpoint: str,
    stage: str,
) -> dict[str, Any]:
    sequences: list[list[int]] = []
    formatted_lengths: list[int] = []
    for sentinel in _PREFIX_SENTINELS:
        templated = _http_json(
            endpoint,
            "/apply-template",
            {
                "messages": _messages_for_stage(stage, sentinel),
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        prompt = templated.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError(f"{stage} template did not return a prompt")
        formatted_lengths.append(len(prompt))
        tokenized = _http_json(
            endpoint,
            "/tokenize",
            {
                "content": prompt,
                # ``/v1/chat/completions`` asks the tokenizer to add the
                # model's leading special token.  The raw token-array request
                # must contain the same token or its cache cannot match at
                # position zero.
                "add_special": True,
                "parse_special": True,
            },
        )
        tokens = tokenized.get("tokens")
        if (
            not isinstance(tokens, list)
            or not tokens
            or any(
                not isinstance(token, int) or isinstance(token, bool)
                for token in tokens
            )
        ):
            raise ValueError(f"{stage} template did not tokenize to integer IDs")
        sequences.append(list(tokens))
    common = _longest_common_prefix(sequences)
    # Avoid relying on a tokenizer merge at the synthetic/real suffix boundary.
    safe = common[:-1]
    if not safe:
        raise ValueError(f"{stage} has no safe common token prefix")
    return {
        "stage": stage,
        "tokens": safe,
        "lcp_tokens_before_margin": len(common),
        "safe_prefix_tokens": len(safe),
        "safe_prefix_sha256": hashlib.sha256(
            b"".join(
                int(token).to_bytes(4, byteorder="little", signed=True)
                for token in safe
            )
        ).hexdigest(),
        "synthetic_prompt_token_lengths": [len(item) for item in sequences],
        "synthetic_prompt_character_lengths": formatted_lengths,
        "conservative_margin_tokens": 1,
    }


def _prime_prefixes(endpoint: str) -> dict[str, Any]:
    derive_started = time.perf_counter()
    prefixes = {
        stage: _derive_stage_prefix(endpoint, stage)
        for stage in ("P", "G", "L")
    }
    derive_seconds = time.perf_counter() - derive_started

    records: list[dict[str, Any]] = []
    records_lock = threading.Lock()

    def prime(stage: str) -> None:
        prefix = prefixes[stage]
        started = time.perf_counter()
        response = _http_json(
            endpoint,
            "/completion",
            {
                "prompt": prefix["tokens"],
                "n_predict": 1,
                "cache_prompt": True,
                "temperature": 0.0,
                "seed": 0,
                "id_slot": _PRIME_SLOTS[stage],
            },
        )
        elapsed = time.perf_counter() - started
        timings = response.get("timings")
        if not isinstance(timings, dict):
            timings = {}
        record = {
            "stage": stage,
            "id_slot": _PRIME_SLOTS[stage],
            "elapsed_seconds": elapsed,
            "safe_prefix_tokens": prefix["safe_prefix_tokens"],
            "tokens_cached": response.get("tokens_cached"),
            "tokens_evaluated": response.get("tokens_evaluated"),
            "cache_n": timings.get("cache_n"),
            "prompt_n": timings.get("prompt_n"),
            "prompt_ms": timings.get("prompt_ms"),
            "predicted_n": timings.get("predicted_n"),
            "predicted_ms": timings.get("predicted_ms"),
            "stopped_limit": response.get("stopped_limit"),
        }
        with records_lock:
            records.append(record)

    inference_started = time.perf_counter()
    with ThreadPoolExecutor(
        max_workers=3,
        thread_name_prefix="baxy-prefix-prime",
    ) as executor:
        futures = [
            executor.submit(prime, stage)
            for stage in ("P", "G", "L")
        ]
        for future in futures:
            future.result()
    inference_seconds = time.perf_counter() - inference_started
    records.sort(key=lambda item: str(item["stage"]))
    return {
        "derive_seconds": derive_seconds,
        "inference_seconds": inference_seconds,
        "total_seconds": derive_seconds + inference_seconds,
        "prefixes": {
            stage: {
                key: value
                for key, value in prefix.items()
                if key != "tokens"
            }
            for stage, prefix in prefixes.items()
        },
        "requests": records,
    }


def _actual_request_projection(
    posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "stage": post["stage"],
            "payload_sha256": post["payload_sha256"],
            "prompt_tokens_total": (
                int(post["cache_n"]) + int(post["prompt_n"])
                if isinstance(post.get("cache_n"), (int, float))
                and isinstance(post.get("prompt_n"), (int, float))
                else None
            ),
            "content": post["content"],
        }
        for post in posts
    ]


def _run_fresh_arm(
    arm: str,
    case: Any,
) -> dict[str, Any]:
    runtime = InstrumentedRuntime(arm)
    startup_started = time.perf_counter()
    priming: dict[str, Any] | None = None
    turn: dict[str, Any] | None = None
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        ready_at = time.perf_counter()
        startup_to_ready = ready_at - startup_started
        if arm == "primed":
            endpoint = runtime._endpoint
            if not isinstance(endpoint, str) or not endpoint:
                raise RuntimeError("owned llama-server endpoint is missing")
            priming = _prime_prefixes(endpoint)
        turn_started = time.perf_counter()
        turn = _run_case(runtime, case)
        completed_at = time.perf_counter()
    finally:
        runtime.close()
    assert turn is not None
    priming_seconds = (
        float(priming["total_seconds"])
        if priming is not None
        else 0.0
    )
    return {
        "arm": arm,
        "case": case.name,
        "startup_to_ready_seconds": startup_to_ready,
        "priming": priming,
        "priming_seconds": priming_seconds,
        "first_turn_e2e_seconds": completed_at - turn_started,
        "ready_to_first_turn_complete_seconds": completed_at - ready_at,
        "startup_to_first_turn_complete_seconds": completed_at - startup_started,
        "turn": turn,
        "posts": runtime._benchmark_records,
        "actual_request_projection": _actual_request_projection(
            runtime._benchmark_records
        ),
        "stage_summary": _stage_summary(runtime._benchmark_records),
    }


def _pair_result(
    case: Any,
    arm_order: list[str],
) -> dict[str, Any]:
    arms = [_run_fresh_arm(arm, case) for arm in arm_order]
    by_arm = {arm["arm"]: arm for arm in arms}
    baseline = by_arm["baseline"]
    primed = by_arm["primed"]
    baseline_turn = _case_projection(baseline["turn"])
    primed_turn = _case_projection(primed["turn"])
    baseline_requests = baseline["actual_request_projection"]
    primed_requests = primed["actual_request_projection"]
    request_identity = [
        (item["stage"], item["payload_sha256"])
        for item in baseline_requests
    ] == [
        (item["stage"], item["payload_sha256"])
        for item in primed_requests
    ]
    prompt_token_identity = [
        (item["stage"], item["prompt_tokens_total"])
        for item in baseline_requests
    ] == [
        (item["stage"], item["prompt_tokens_total"])
        for item in primed_requests
    ]
    return {
        "case": case.name,
        "expected_mode": case.expected_mode,
        "arm_order": arm_order,
        "exact_turn_output": baseline_turn == primed_turn,
        "actual_request_identity": request_identity,
        "actual_prompt_token_identity": prompt_token_identity,
        "delta_primed_minus_baseline_seconds": {
            "first_turn_e2e": (
                float(primed["first_turn_e2e_seconds"])
                - float(baseline["first_turn_e2e_seconds"])
            ),
            "ready_to_first_turn_complete_including_priming": (
                float(primed["ready_to_first_turn_complete_seconds"])
                - float(baseline["ready_to_first_turn_complete_seconds"])
            ),
            "startup_to_first_turn_complete": (
                float(primed["startup_to_first_turn_complete_seconds"])
                - float(baseline["startup_to_first_turn_complete_seconds"])
            ),
        },
        "arms": arms,
    }


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("baseline-primed", "primed-baseline"),
        default="baseline-primed",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help="case name; repeat to select several (default: all)",
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

    selected = list(CASES)
    if args.cases:
        requested = set(args.cases)
        selected = [case for case in CASES if case.name in requested]
        missing = requested - {case.name for case in selected}
        if missing:
            raise ValueError(f"unknown cases: {sorted(missing)}")
    if not selected:
        raise ValueError("at least one case is required")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    pairs = [_pair_result(case, arm_order) for case in selected]
    delta_keys = (
        "first_turn_e2e",
        "ready_to_first_turn_complete_including_priming",
        "startup_to_first_turn_complete",
    )
    deltas = {
        key: [
            float(pair["delta_primed_minus_baseline_seconds"][key])
            for pair in pairs
        ]
        for key in delta_keys
    }
    exact_outputs = all(pair["exact_turn_output"] for pair in pairs)
    request_identity = all(pair["actual_request_identity"] for pair in pairs)
    prompt_token_identity = all(
        pair["actual_prompt_token_identity"] for pair in pairs
    )
    result = {
        "schema": "baxy.first-turn-prefix-priming-ab.v1",
        "arm_order": arm_order,
        "server": str(args.server.resolve()),
        "model": str(args.model.resolve()),
        "profile": {
            "parallel": 3,
            "context_per_slot": 4_096,
            "cache_prompt": "llama.cpp b9980 default true",
            "fresh_server_per_case_and_arm": True,
            "one_real_turn_per_server": True,
            "prime_slots": copy.deepcopy(_PRIME_SLOTS),
            "real_requests_use_automatic_slot_selection": True,
        },
        "safety": {
            "production_code_changed": False,
            "core_started": False,
            "external_effects_executed": False,
            "real_case_text_in_priming_requests": False,
        },
        "exact_turn_outputs": exact_outputs,
        "actual_request_identity": request_identity,
        "actual_prompt_token_identity": prompt_token_identity,
        "aggregate_delta_primed_minus_baseline_seconds": {
            key: {
                "median": _median(values),
                "total": sum(values),
                "wins": sum(value < 0.0 for value in values),
                "pairs": len(values),
                "minimum": min(values),
                "maximum": max(values),
            }
            for key, values in deltas.items()
        },
        "pairs": pairs,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require exact projected outputs, identical real request payloads "
            "and prompt-token totals, increased real P/G/L cache_n, and a "
            "repeatable opposite-order first-turn gain. Report priming and "
            "startup-to-complete separately; do not promote as a cold-start "
            "optimization if priming merely moves equal or greater latency "
            "ahead of the real turn."
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
                    "exact_turn_outputs",
                    "actual_request_identity",
                    "actual_prompt_token_identity",
                    "aggregate_delta_primed_minus_baseline_seconds",
                    "candidate_status",
                )
            },
            ensure_ascii=False,
        )
    )
    return (
        0
        if exact_outputs and request_identity and prompt_token_identity
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
