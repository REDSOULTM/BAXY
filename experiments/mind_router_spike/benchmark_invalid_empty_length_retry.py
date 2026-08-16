"""Physical A/B for the empty+length structured retry in BAXY.

The production runtime is not edited.  Each arm starts the registered Python,
llama.cpp and Gemma assets through the normal JSONL sidecar, configures the
real 168-operation Core catalog and executes the frozen 30-turn GPU workload.

The candidate changes only the recovery sampling profile: when the immediately
preceding attempt of the *same* structured object returned empty content with
``finish_reason=length``, the second internal attempt uses temperature 0.1 and
the deterministic seed that the first later logical retry would have used
(``base + 1009``).  Prompts, grammars/schemas, validators, request budgets and
the later full-turn recovery remain unchanged.

Both orders use fresh sidecars and fresh llama-server children:

    baseline -> candidate -> candidate -> baseline

The same response-only ``verbose``/``return_tokens`` diagnostics are enabled
for structured posts in both arms.  No Core operation is dispatched.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

TARGET_STAGES = frozenset({"P", "G", "L", "V", "C", "E"})
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "fixes"
    / "invalid_empty_length_retry_temperature_ab_20260729.json"
)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _payload_signature(payload: dict[str, Any]) -> str:
    canonical = dict(payload)
    for field in (
        "temperature",
        "seed",
        "verbose",
        "return_tokens",
    ):
        canonical.pop(field, None)
    return _canonical_hash(canonical)


def _response_parts(
    response: dict[str, Any],
) -> tuple[str, str | None, str | None, list[int] | None]:
    content = ""
    finish_reason: str | None = None
    try:
        choices = response.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            choice = choices[0]
            value = choice.get("finish_reason")
            finish_reason = value if isinstance(value, str) else None
            message = choice.get("message")
            if isinstance(message, dict):
                raw_content = message.get("content")
                if isinstance(raw_content, str):
                    content = raw_content
    except (IndexError, TypeError):
        pass
    verbose = response.get("__verbose")
    raw_verbose: str | None = None
    tokens: list[int] | None = None
    if isinstance(verbose, dict):
        raw = verbose.get("content")
        if isinstance(raw, str):
            raw_verbose = raw
        token_values = verbose.get("tokens")
        if isinstance(token_values, list) and all(
            isinstance(token, int) and not isinstance(token, bool)
            for token in token_values
        ):
            tokens = list(token_values)
    return content, finish_reason, raw_verbose, tokens


def _text_metadata(value: object) -> dict[str, Any]:
    if value is None:
        return {"state": "null"}
    if not isinstance(value, str):
        return {"state": "non_text", "type": type(value).__name__}
    encoded = value.encode("utf-8")
    return {
        "state": "text",
        "chars": len(value),
        "stripped_chars": len(value.strip()),
        "utf8_bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _response_metadata(response: dict[str, Any]) -> dict[str, Any]:
    choice: dict[str, Any] = {}
    message: dict[str, Any] = {}
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]
        value = choice.get("message")
        if isinstance(value, dict):
            message = value
    usage = response.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    verbose = response.get("__verbose")
    if not isinstance(verbose, dict):
        verbose = {}
    return {
        "response_keys": sorted(str(key) for key in response),
        "choice_keys": sorted(str(key) for key in choice),
        "message_keys": sorted(str(key) for key in message),
        "usage_keys": sorted(str(key) for key in usage),
        "usage": {
            key: usage.get(key)
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            )
            if isinstance(usage.get(key), (int, float))
            and not isinstance(usage.get(key), bool)
        },
        "usage_completion_tokens_details_keys": sorted(
            str(key)
            for key in (
                usage.get("completion_tokens_details")
                if isinstance(usage.get("completion_tokens_details"), dict)
                else {}
            )
        ),
        "content": _text_metadata(message.get("content")),
        "reasoning_content": _text_metadata(message.get("reasoning_content")),
        "reasoning": _text_metadata(message.get("reasoning")),
        "choice_reasoning_content": _text_metadata(
            choice.get("reasoning_content")
        ),
        "verbose_keys": sorted(str(key) for key in verbose),
        "verbose_content": _text_metadata(verbose.get("content")),
    }


def _run_sidecar(profile: str, log_path: Path) -> int:
    """Patch only the experimental process, then enter the normal sidecar."""

    if profile not in {"baseline", "candidate"}:
        raise ValueError(f"unknown sidecar profile: {profile}")

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime
    from experiments.mind_router_spike.benchmark_llama_slot_pinning import (
        _stage,
    )

    original_post = LlmRuntime._post
    original_prepare = sidecar_module._prepare_turn_result
    log_lock = threading.Lock()
    ordinal_lock = threading.Lock()
    ordinals: dict[tuple[str, str], int] = {}
    next_ordinal = 0
    retry_state = threading.local()

    def write_record(record: dict[str, Any]) -> None:
        with log_lock:
            with log_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

    def benchmark_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        nonlocal next_ordinal

        original = dict(payload)
        stage = _stage(original)
        signature = _payload_signature(original)
        source_temperature = original.get("temperature")
        source_seed = original.get("seed")
        pending = getattr(retry_state, "pending", None)
        candidate_applied = (
            profile == "candidate"
            and stage in TARGET_STAGES
            and isinstance(source_temperature, (int, float))
            and not isinstance(source_temperature, bool)
            and float(source_temperature) == 0.0
            and isinstance(source_seed, int)
            and not isinstance(source_seed, bool)
            and isinstance(pending, tuple)
            and len(pending) == 3
            and pending[0] == stage
            and pending[1] == signature
            and source_seed == pending[2] + 1
        )
        retry_state.pending = None

        wire = dict(original)
        if stage in TARGET_STAGES:
            # Response-only diagnostics; identical in baseline and candidate.
            wire["verbose"] = True
            wire["return_tokens"] = True
        if candidate_applied:
            wire["temperature"] = 0.1
            # Reuse exactly the first logical-retry seed. This lets the internal
            # recovery ask for the decode BAXY would otherwise obtain only
            # after discarding already-completed P/G/L/V work and rerunning the
            # whole turn.
            wire["seed"] = pending[2] + 1_009

        case_id = str(getattr(self, "_invalid_retry_benchmark_case", ""))
        with ordinal_lock:
            stage_key = (case_id, stage)
            stage_ordinal = ordinals.get(stage_key, 0)
            ordinals[stage_key] = stage_ordinal + 1
            global_ordinal = next_ordinal
            next_ordinal += 1

        started = time.perf_counter()
        try:
            response = original_post(
                self,
                wire,
                timeout,
                max_attempts=max_attempts,
                cancellation=cancellation,
            )
        except BaseException as error:
            write_record(
                {
                    "profile": profile,
                    "case_id": case_id,
                    "stage": stage,
                    "stage_ordinal": stage_ordinal,
                    "global_ordinal": global_ordinal,
                    "payload_signature": signature,
                    "source_temperature": source_temperature,
                    "wire_temperature": wire.get("temperature"),
                    "source_seed": source_seed,
                    "wire_seed": wire.get("seed"),
                    "candidate_applied": candidate_applied,
                    "elapsed_seconds": time.perf_counter() - started,
                    "exception": type(error).__name__,
                }
            )
            raise

        elapsed = time.perf_counter() - started
        content, finish_reason, raw_verbose, tokens = _response_parts(response)
        empty_length = finish_reason == "length" and not content.strip()
        if (
            stage in TARGET_STAGES
            and empty_length
            and isinstance(source_temperature, (int, float))
            and not isinstance(source_temperature, bool)
            and float(source_temperature) == 0.0
            and isinstance(source_seed, int)
            and not isinstance(source_seed, bool)
        ):
            retry_state.pending = (stage, signature, source_seed)

        timings = response.get("timings")
        if not isinstance(timings, dict):
            timings = {}
        try:
            parsed = json.loads(content)
            valid_json_object = isinstance(parsed, dict)
        except (json.JSONDecodeError, TypeError):
            valid_json_object = False
        write_record(
            {
                "profile": profile,
                "case_id": case_id,
                "stage": stage,
                "stage_ordinal": stage_ordinal,
                "global_ordinal": global_ordinal,
                "payload_signature": signature,
                "source_temperature": source_temperature,
                "wire_temperature": wire.get("temperature"),
                "source_seed": source_seed,
                "wire_seed": wire.get("seed"),
                "candidate_applied": candidate_applied,
                "elapsed_seconds": elapsed,
                "finish_reason": finish_reason,
                "empty_length": empty_length,
                "valid_json_object": valid_json_object,
                "content": content,
                "content_sha256": hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
                "raw_verbose_content": raw_verbose,
                "tokens": tokens,
                "response_metadata": _response_metadata(response),
                "cache_n": timings.get("cache_n"),
                "prompt_n": timings.get("prompt_n"),
                "predicted_n": timings.get("predicted_n"),
                "predicted_ms": timings.get("predicted_ms"),
            }
        )
        return response

    def benchmark_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        if llm is not None:
            llm._invalid_retry_benchmark_case = str(message.get("id") or "")
        return original_prepare(message, **kwargs)

    LlmRuntime._post = benchmark_post
    sidecar_module._prepare_turn_result = benchmark_prepare
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post
        sidecar_module._prepare_turn_result = original_prepare


def _quantile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("cannot quantify an empty sequence")
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1),
    )
    return ordered[index]


def _semantic_reply(reply: dict[str, Any]) -> dict[str, Any]:
    ignored = {
        "id",
        "turn_attempts",
        "turn_recovery",
        "recovery_attempts",
    }
    return {
        key: copy.deepcopy(value)
        for key, value in reply.items()
        if key not in ignored
    }


def _visible_reply(reply: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": reply.get("kind"),
        "reply": reply.get("reply"),
        "question": reply.get("question"),
    }


def _effect_projection(reply: dict[str, Any]) -> dict[str, Any]:
    operations: list[str] = []
    operation = reply.get("operation")
    if isinstance(operation, str) and operation:
        operations.append(operation)
    effect_operations = reply.get("effectOperations")
    if isinstance(effect_operations, list):
        operations.extend(
            str(item)
            for item in effect_operations
            if isinstance(item, str) and item
        )
    plan = reply.get("plan")
    if isinstance(plan, dict):
        steps = plan.get("steps")
        if isinstance(steps, list):
            operations.extend(
                str(step.get("operation"))
                for step in steps
                if isinstance(step, dict)
                and isinstance(step.get("operation"), str)
                and step.get("operation")
            )
    return {
        "kind": reply.get("kind"),
        "operations": sorted(set(operations)),
    }


def _candidate_unsafe_delta(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    base = _effect_projection(baseline)
    cand = _effect_projection(candidate)
    base_effect = base["kind"] in {"action", "plan"} or bool(base["operations"])
    cand_effect = cand["kind"] in {"action", "plan"} or bool(cand["operations"])
    return bool(
        (cand_effect and not base_effect)
        or (
            cand_effect
            and base_effect
            and cand["operations"] != base["operations"]
        )
    )


def _read_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    return records


def _run_arm(
    *,
    profile: str,
    run_id: str,
    log_path: Path,
    runtime: Any,
    capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    from scripts.measure_mind_budget import (
        JsonLineProcess,
        PROFILE_LIMITS,
        build_workload,
        sidecar_environment,
        validate_reply,
    )

    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment.pop("BAXY_CAPTURE_INVALID_SCHEMA_DIR", None)
    command = [
        str(runtime.python),
        "-u",
        "-X",
        "utf8",
        str(Path(__file__).resolve()),
        "--sidecar-profile",
        profile,
        "--sidecar-log",
        str(log_path.resolve()),
    ]
    client = JsonLineProcess(command, environment=environment, cwd=ROOT)
    observations: list[dict[str, Any]] = []
    arm_started = time.perf_counter()
    ready_seconds: float | None = None
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar hello rejected")
        catalog = client.request(
            {
                "type": "catalog.configure",
                "id": f"catalog-{run_id}",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if catalog.get("type") != "catalog.ready":
            raise RuntimeError("catalog handshake rejected")
        ready_seconds = time.perf_counter() - arm_started

        for item in build_workload():
            if item.request_type != "turn.decide":
                continue
            started = time.perf_counter()
            reply = client.request(item.message, limits["turn.decide"])
            elapsed = time.perf_counter() - started
            validation_error = validate_reply(item, reply)
            observations.append(
                {
                    "case_id": item.case_id,
                    "text": item.message["text"],
                    "elapsed_seconds": elapsed,
                    "validation_error": validation_error or None,
                    "reply": reply,
                    "semantic_reply": _semantic_reply(reply),
                    "visible_reply": _visible_reply(reply),
                    "effect_projection": _effect_projection(reply),
                }
            )
            print(
                f"{run_id} {item.case_id}: {elapsed:.3f}s "
                f"{reply.get('kind')} attempts={reply.get('turn_attempts')}",
                flush=True,
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": f"shutdown-{run_id}"},
            timeout=limits["shutdown"],
        )

    posts = _read_records(log_path)
    latencies = [float(row["elapsed_seconds"]) for row in observations]
    structured = [
        post for post in posts if str(post.get("stage")) in TARGET_STAGES
    ]
    return {
        "run_id": run_id,
        "profile": profile,
        "ready_seconds": ready_seconds,
        "elapsed_total_seconds": time.perf_counter() - arm_started,
        "turn_elapsed_total_seconds": sum(latencies),
        "turn_latency_seconds": {
            "p50": statistics.median(latencies),
            "p95_nearest_rank": _quantile(latencies, 0.95),
            "max": max(latencies),
        },
        "validation_errors": sum(
            row["validation_error"] is not None for row in observations
        ),
        "turn_retry_cases": [
            row["case_id"]
            for row in observations
            if row["reply"].get("turn_attempts") not in {None, 1}
        ],
        "empty_length_posts": sum(
            post.get("empty_length") is True for post in structured
        ),
        "candidate_applied_posts": sum(
            post.get("candidate_applied") is True for post in structured
        ),
        "structured_post_elapsed_total_seconds": sum(
            float(post.get("elapsed_seconds") or 0.0) for post in structured
        ),
        "observations": observations,
        "posts": posts,
    }


def _compare_pair(
    pair_id: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    base = {row["case_id"]: row for row in baseline["observations"]}
    cand = {row["case_id"]: row for row in candidate["observations"]}
    case_ids = sorted(set(base) | set(cand))
    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        left = base.get(case_id)
        right = cand.get(case_id)
        present = left is not None and right is not None
        cases.append(
            {
                "case_id": case_id,
                "present_in_both": present,
                "semantic_reply_equal": (
                    present
                    and left["semantic_reply"] == right["semantic_reply"]
                ),
                "visible_reply_equal": (
                    present and left["visible_reply"] == right["visible_reply"]
                ),
                "effect_projection_equal": (
                    present
                    and left["effect_projection"] == right["effect_projection"]
                ),
                "candidate_unsafe_delta": (
                    _candidate_unsafe_delta(left["reply"], right["reply"])
                    if present
                    else True
                ),
                "baseline_turn_attempts": (
                    left["reply"].get("turn_attempts") if left else None
                ),
                "candidate_turn_attempts": (
                    right["reply"].get("turn_attempts") if right else None
                ),
                "baseline_seconds": (
                    left["elapsed_seconds"] if left is not None else None
                ),
                "candidate_seconds": (
                    right["elapsed_seconds"] if right is not None else None
                ),
                "candidate_minus_baseline_seconds": (
                    float(right["elapsed_seconds"])
                    - float(left["elapsed_seconds"])
                    if present
                    else None
                ),
            }
        )

    eligible_tail = [
        row
        for row in cases
        if row["baseline_turn_attempts"] not in {None, 1}
        or row["candidate_turn_attempts"] not in {None, 1}
    ]
    tail_deltas = [
        float(row["candidate_minus_baseline_seconds"])
        for row in eligible_tail
        if isinstance(row.get("candidate_minus_baseline_seconds"), (int, float))
    ]
    return {
        "pair_id": pair_id,
        "all_cases_present": all(row["present_in_both"] for row in cases),
        "semantic_replies_equal": all(
            row["semantic_reply_equal"] for row in cases
        ),
        "visible_replies_equal": all(
            row["visible_reply_equal"] for row in cases
        ),
        "effect_projections_equal": all(
            row["effect_projection_equal"] for row in cases
        ),
        "candidate_unsafe_deltas": sum(
            row["candidate_unsafe_delta"] for row in cases
        ),
        "baseline_retry_cases": baseline["turn_retry_cases"],
        "candidate_retry_cases": candidate["turn_retry_cases"],
        "candidate_retry_reduction": (
            len(baseline["turn_retry_cases"])
            - len(candidate["turn_retry_cases"])
        ),
        "candidate_applied_posts": candidate["candidate_applied_posts"],
        "candidate_minus_baseline_turn_total_seconds": (
            candidate["turn_elapsed_total_seconds"]
            - baseline["turn_elapsed_total_seconds"]
        ),
        "candidate_minus_baseline_p50_seconds": (
            candidate["turn_latency_seconds"]["p50"]
            - baseline["turn_latency_seconds"]["p50"]
        ),
        "candidate_minus_baseline_p95_seconds": (
            candidate["turn_latency_seconds"]["p95_nearest_rank"]
            - baseline["turn_latency_seconds"]["p95_nearest_rank"]
        ),
        "candidate_minus_baseline_max_seconds": (
            candidate["turn_latency_seconds"]["max"]
            - baseline["turn_latency_seconds"]["max"]
        ),
        "tail_cases": len(eligible_tail),
        "candidate_minus_baseline_tail_total_seconds": sum(tail_deltas),
        "candidate_minus_baseline_tail_p50_seconds": (
            statistics.median(tail_deltas) if tail_deltas else None
        ),
        "cases": cases,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_experiment(output: Path) -> int:
    from scripts.baxy_runtime_config import (
        DEFAULT_RUNTIME_MANIFEST,
        public_runtime_identity,
        resolve_runtime,
    )
    from scripts.measure_mind_budget import (
        current_core_capabilities,
        discover_core,
    )

    # The source Core is framework-dependent on this notebook.  Its registered
    # SDK lives in the normal per-user dotnet root, which a non-interactive
    # experiment shell may not have inherited.
    user_dotnet = Path.home() / ".dotnet"
    if (user_dotnet / "dotnet.exe").is_file():
        os.environ["DOTNET_ROOT"] = str(user_dotnet)
        os.environ["DOTNET_ROOT_X64"] = str(user_dotnet)

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(discover_core(None))
    arm_plan = (
        ("order1-baseline", "baseline"),
        ("order1-candidate", "candidate"),
        ("order2-candidate", "candidate"),
        ("order2-baseline", "baseline"),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="invalid-retry-ab-",
        dir=str(output.parent),
    ) as temporary:
        temp_root = Path(temporary).resolve()
        arms = [
            _run_arm(
                profile=profile,
                run_id=run_id,
                log_path=temp_root / f"{run_id}.jsonl",
                runtime=runtime,
                capabilities=capabilities,
            )
            for run_id, profile in arm_plan
        ]

    arms_by_id = {arm["run_id"]: arm for arm in arms}
    comparisons = [
        _compare_pair(
            "baseline-then-candidate",
            arms_by_id["order1-baseline"],
            arms_by_id["order1-candidate"],
        ),
        _compare_pair(
            "candidate-then-baseline",
            arms_by_id["order2-baseline"],
            arms_by_id["order2-candidate"],
        ),
    ]
    validation_clean = all(arm["validation_errors"] == 0 for arm in arms)
    candidate_triggered_both_orders = all(
        comparison["candidate_applied_posts"] > 0
        for comparison in comparisons
    )
    exact_semantic_equivalence = all(
        comparison["all_cases_present"]
        and comparison["semantic_replies_equal"]
        and comparison["visible_replies_equal"]
        and comparison["effect_projections_equal"]
        and comparison["candidate_unsafe_deltas"] == 0
        for comparison in comparisons
    )
    retries_lower_both_orders = all(
        comparison["candidate_retry_reduction"] > 0
        for comparison in comparisons
    )
    tail_faster_both_orders = all(
        isinstance(
            comparison["candidate_minus_baseline_tail_total_seconds"],
            (int, float),
        )
        and comparison["candidate_minus_baseline_tail_total_seconds"] < 0.0
        for comparison in comparisons
    )
    total_faster_both_orders = all(
        comparison["candidate_minus_baseline_turn_total_seconds"] < 0.0
        for comparison in comparisons
    )
    promotion_gate_passed = (
        validation_clean
        and candidate_triggered_both_orders
        and exact_semantic_equivalence
        and retries_lower_both_orders
        and tail_faster_both_orders
        and total_faster_both_orders
    )
    result = {
        "schema": "baxy.invalid-empty-length-retry-temperature-ab.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_status": (
            "eligible_for_minimal_production_patch"
            if promotion_gate_passed
            else "rejected"
        ),
        "effects_executed": 0,
        "candidate": {
            "scope": (
                "second internal retry only, same structured object, only "
                "after empty content plus finish_reason=length"
            ),
            "wire_delta": {
                "temperature": {"baseline": 0.0, "candidate": 0.1},
                "seed": {
                    "baseline": "base+1 (repeated greedy internal attempt)",
                    "candidate": "base+1009 (first logical-retry decode)",
                },
            },
            "unchanged": [
                "prompt",
                "grammar or JSON Schema",
                "downstream validators",
                "request budgets",
                "full-turn recovery",
            ],
            "seed_reuse": (
                "base+1009, exactly the first full logical-retry seed that "
                "would otherwise be reached after rerunning the turn"
            ),
        },
        "workload": {
            "turns_per_arm": 30,
            "arms": [run_id for run_id, _ in arm_plan],
            "fresh_sidecar_and_llama_server_per_arm": True,
            "both_orders": True,
            "catalog_operations": len(capabilities),
        },
        "runtime": public_runtime_identity(runtime),
        "runtime_hashes": {
            "llama_server_sha256": _sha256_file(runtime.llama_server),
            "model_sha256": _sha256_file(runtime.gguf),
        },
        "gates": {
            "validation_clean": validation_clean,
            "candidate_triggered_both_orders": candidate_triggered_both_orders,
            "exact_semantic_equivalence": exact_semantic_equivalence,
            "retries_lower_both_orders": retries_lower_both_orders,
            "tail_faster_both_orders": tail_faster_both_orders,
            "total_faster_both_orders": total_faster_both_orders,
            "promotion_gate_passed": promotion_gate_passed,
        },
        "promotion_rule": (
            "Require 30/30 valid replies per arm, candidate activation and "
            "fewer full-turn retries in both orders, exact semantic/visible/"
            "effect equality with zero unsafe deltas, and lower tail plus "
            "total turn time in both opposite-order pairs."
        ),
        "comparisons": comparisons,
        "arms": arms,
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "candidate_status": result["candidate_status"],
                "gates": result["gates"],
                "comparisons": [
                    {
                        key: comparison[key]
                        for key in (
                            "pair_id",
                            "semantic_replies_equal",
                            "visible_replies_equal",
                            "effect_projections_equal",
                            "candidate_unsafe_deltas",
                            "baseline_retry_cases",
                            "candidate_retry_cases",
                            "candidate_applied_posts",
                            "candidate_minus_baseline_turn_total_seconds",
                            "candidate_minus_baseline_p50_seconds",
                            "candidate_minus_baseline_p95_seconds",
                            "candidate_minus_baseline_max_seconds",
                            "candidate_minus_baseline_tail_total_seconds",
                        )
                    }
                    for comparison in comparisons
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if promotion_gate_passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sidecar-profile",
        choices=("baseline", "candidate"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--sidecar-log", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.sidecar_profile is not None:
        if args.sidecar_log is None:
            parser.error("--sidecar-log is required in sidecar mode")
        return _run_sidecar(args.sidecar_profile, args.sidecar_log.resolve())
    if args.sidecar_log is not None:
        parser.error("--sidecar-log is internal")
    output = args.output.resolve()
    fixes = (ROOT / "artifacts" / "fixes").resolve()
    if output.parent != fixes or output.suffix.casefold() != ".json":
        parser.error("--output must be a JSON directly below artifacts/fixes")
    return _run_experiment(output)


if __name__ == "__main__":
    raise SystemExit(main())
