"""Research-only A/B for a P/V empty+length direct-GBNF retry.

The first internal attempt of every P/V structured object keeps the production
``response_format`` unchanged.  Only when that exact attempt returns empty
content with ``finish_reason=length`` may the immediately following internal
attempt of the same object replace ``response_format`` with the grammar that
llama.cpp exposed for the first response, changing exactly one rule:

    root ::= response-format-schema

Prompts, schemas, sampling, seeds, budgets, validators and full-turn recovery
stay unchanged.  The baseline repeats ``response_format`` on the same retry.

The frozen 30-turn workload runs in both physical orders, with a fresh sidecar
and fresh llama-server child for each of the four arms:

    baseline -> candidate -> candidate -> baseline

No Core operation is dispatched.  The gate requires exact decision, semantic
reply, visible reply and effect projections; zero unsafe deltas; and fewer
full-turn retries, lower retry-tail time and lower total turn time in both
orders.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
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

from experiments.mind_router_spike import (  # noqa: E402
    benchmark_invalid_empty_length_retry as retry_benchmark,
)
from experiments.mind_router_spike import (  # noqa: E402
    benchmark_pv_response_format_direct_gbnf as direct_benchmark,
)


PROFILE_BASELINE = "response-format-retry"
PROFILE_CANDIDATE = "direct-gbnf-on-empty-length-retry"
PROFILE_EXPANDED_BUDGET = "expanded-budget-on-empty-length-retry"
TARGET_STAGES = frozenset({"P", "V"})
STRUCTURED_STAGES = retry_benchmark.TARGET_STAGES
EXPECTED_TURNS_PER_ARM = 30
DEFAULT_OUTPUT = (
    ROOT / "artifacts" / "fixes" / "pv_empty_length_retry_direct_gbnf_ab_20260730.json"
)


def _run_sidecar(profile: str, log_path: Path) -> int:
    """Patch only this experimental child, then enter the normal sidecar."""

    if profile not in {
        PROFILE_BASELINE,
        PROFILE_CANDIDATE,
        PROFILE_EXPANDED_BUDGET,
    }:
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
        signature = retry_benchmark._payload_signature(original)
        response_format = original.get("response_format")
        response_format_sha256 = (
            retry_benchmark._canonical_hash(response_format)
            if stage in TARGET_STAGES and isinstance(response_format, dict)
            else None
        )
        catalog_key = (
            direct_benchmark._constraint_key(stage, response_format_sha256)
            if isinstance(response_format_sha256, str)
            else None
        )
        source_seed = original.get("seed")
        case_id = str(getattr(self, "_pv_empty_length_gbnf_benchmark_case", ""))

        pending = getattr(retry_state, "pending", None)
        eligible_retry = bool(
            stage in TARGET_STAGES
            and isinstance(response_format, dict)
            and isinstance(response_format_sha256, str)
            and isinstance(source_seed, int)
            and not isinstance(source_seed, bool)
            and isinstance(pending, dict)
            and pending.get("case_id") == case_id
            and pending.get("stage") == stage
            and pending.get("payload_signature") == signature
            and pending.get("response_format_sha256") == response_format_sha256
            and isinstance(pending.get("source_seed"), int)
            and source_seed == int(pending["source_seed"]) + 1
        )
        # Eligibility is deliberately immediate. Any intervening post clears
        # the evidence and therefore cannot inherit authority to use GBNF.
        retry_state.pending = None

        direct_grammar = (
            pending.get("direct_grammar")
            if eligible_retry and isinstance(pending, dict)
            else None
        )
        candidate_applied = bool(
            (
                profile == PROFILE_CANDIDATE
                and eligible_retry
                and isinstance(direct_grammar, str)
                and direct_grammar
            )
            or (profile == PROFILE_EXPANDED_BUDGET and eligible_retry)
        )
        capture_miss = bool(
            profile == PROFILE_CANDIDATE and eligible_retry and not candidate_applied
        )

        wire = dict(original)
        if stage in STRUCTURED_STAGES:
            # Response-only diagnostics are identical in all four arms.
            wire["verbose"] = True
            wire["return_tokens"] = True
        if candidate_applied and profile == PROFILE_CANDIDATE:
            wire.pop("response_format", None)
            wire["grammar"] = direct_grammar
        elif candidate_applied and profile == PROFILE_EXPANDED_BUDGET:
            wire["max_tokens"] = 256 if stage == "P" else 64

        wire_constraint = (
            "direct_gbnf"
            if candidate_applied and profile == PROFILE_CANDIDATE
            else (
                "response_format"
                if isinstance(wire.get("response_format"), dict)
                else "unchanged"
            )
        )
        with ordinal_lock:
            stage_key = (case_id, stage)
            stage_ordinal = ordinals.get(stage_key, 0)
            ordinals[stage_key] = stage_ordinal + 1
            global_ordinal = next_ordinal
            next_ordinal += 1

        record_prefix = {
            "profile": profile,
            "case_id": case_id,
            "stage": stage,
            "stage_ordinal": stage_ordinal,
            "global_ordinal": global_ordinal,
            "payload_signature": signature,
            "response_format_sha256": response_format_sha256,
            "catalog_key": catalog_key,
            "source_seed": source_seed,
            "wire_seed": wire.get("seed"),
            "source_temperature": original.get("temperature"),
            "wire_temperature": wire.get("temperature"),
            "source_max_tokens": original.get("max_tokens"),
            "wire_max_tokens": wire.get("max_tokens"),
            "eligible_empty_length_retry": eligible_retry,
            "candidate_applied": candidate_applied,
            "capture_miss": capture_miss,
            "wire_constraint": wire_constraint,
            "prior_empty_length_global_ordinal": (
                pending.get("global_ordinal")
                if eligible_retry and isinstance(pending, dict)
                else None
            ),
            "prior_source_grammar_sha256": (
                pending.get("source_grammar_sha256")
                if eligible_retry and isinstance(pending, dict)
                else None
            ),
            "expected_direct_grammar_sha256": (
                pending.get("direct_grammar_sha256")
                if eligible_retry and isinstance(pending, dict)
                else None
            ),
        }
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
                    **record_prefix,
                    "elapsed_seconds": time.perf_counter() - started,
                    "exception": type(error).__name__,
                }
            )
            raise

        elapsed = time.perf_counter() - started
        content, finish_reason, raw_verbose, tokens = retry_benchmark._response_parts(
            response
        )
        empty_length = finish_reason == "length" and not content.strip()
        generated_grammar = direct_benchmark._generated_grammar(response)
        generated_grammar_sha256 = (
            hashlib.sha256(generated_grammar.encode("utf-8")).hexdigest()
            if generated_grammar is not None
            else None
        )
        derived_direct_grammar: str | None = None
        source_root_rule: str | None = None
        derivation_error: str | None = None
        if stage in TARGET_STAGES and wire_constraint == "response_format":
            if generated_grammar is None:
                derivation_error = "missing_generated_grammar"
            else:
                try:
                    (
                        derived_direct_grammar,
                        source_root_rule,
                    ) = direct_benchmark._replace_root_with_response_format_schema(
                        generated_grammar
                    )
                except (AssertionError, ValueError) as error:
                    derivation_error = f"{type(error).__name__}:{error}"

        pending_created = bool(
            stage in TARGET_STAGES
            and wire_constraint == "response_format"
            and not eligible_retry
            and empty_length
            and isinstance(response_format, dict)
            and isinstance(response_format_sha256, str)
            and isinstance(source_seed, int)
            and not isinstance(source_seed, bool)
        )
        if pending_created:
            retry_state.pending = {
                "case_id": case_id,
                "stage": stage,
                "payload_signature": signature,
                "response_format_sha256": response_format_sha256,
                "source_seed": source_seed,
                "global_ordinal": global_ordinal,
                "source_grammar_sha256": generated_grammar_sha256,
                "direct_grammar": derived_direct_grammar,
                "direct_grammar_sha256": (
                    hashlib.sha256(derived_direct_grammar.encode("utf-8")).hexdigest()
                    if derived_direct_grammar is not None
                    else None
                ),
            }

        try:
            parsed = json.loads(content)
            valid_json_object = isinstance(parsed, dict)
        except (json.JSONDecodeError, TypeError):
            valid_json_object = False
        metadata = retry_benchmark._response_metadata(response)
        usage = metadata.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        timings = response.get("timings")
        if not isinstance(timings, dict):
            timings = {}
        write_record(
            {
                **record_prefix,
                "elapsed_seconds": elapsed,
                "finish_reason": finish_reason,
                "empty_length": empty_length,
                "pending_created": pending_created,
                "valid_json_object": valid_json_object,
                "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "raw_verbose_content": raw_verbose,
                "tokens": tokens,
                "returned_token_count": (
                    len(tokens) if isinstance(tokens, list) else None
                ),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "response_metadata": metadata,
                "cache_n": timings.get("cache_n"),
                "prompt_n": timings.get("prompt_n"),
                "predicted_n": timings.get("predicted_n"),
                "predicted_ms": timings.get("predicted_ms"),
                "source_response_format": (
                    response_format
                    if stage in TARGET_STAGES and isinstance(response_format, dict)
                    else None
                ),
                "generated_grammar": (
                    generated_grammar if stage in TARGET_STAGES else None
                ),
                "generated_grammar_sha256": generated_grammar_sha256,
                "derived_direct_grammar": derived_direct_grammar,
                "derived_direct_grammar_sha256": (
                    hashlib.sha256(derived_direct_grammar.encode("utf-8")).hexdigest()
                    if derived_direct_grammar is not None
                    else None
                ),
                "source_root_rule": source_root_rule,
                "derivation_error": derivation_error,
                "wire_grammar_echo_equal": (
                    generated_grammar == direct_grammar if candidate_applied else None
                ),
            }
        )
        return response

    def benchmark_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        if llm is not None:
            llm._pv_empty_length_gbnf_benchmark_case = str(message.get("id") or "")
        return original_prepare(message, **kwargs)

    LlmRuntime._post = benchmark_post
    sidecar_module._prepare_turn_result = benchmark_prepare
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post
        sidecar_module._prepare_turn_result = original_prepare


def _workload_sha256(workload: list[Any]) -> str:
    return retry_benchmark._canonical_hash(
        [
            {
                "case_id": item.case_id,
                "request_type": item.request_type,
                "message": item.message,
            }
            for item in workload
        ]
    )


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
    workload = [item for item in build_workload() if item.request_type == "turn.decide"]
    if len(workload) != EXPECTED_TURNS_PER_ARM:
        raise RuntimeError(
            "frozen GPU workload no longer contains exactly 30 turn.decide cases"
        )
    workload_sha256 = _workload_sha256(workload)
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

        for item in workload:
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
                    "decision_projection": (
                        direct_benchmark._decision_projection(reply)
                    ),
                    "semantic_reply": retry_benchmark._semantic_reply(reply),
                    "visible_reply": retry_benchmark._visible_reply(reply),
                    "effect_projection": (retry_benchmark._effect_projection(reply)),
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

    raw_posts = retry_benchmark._read_records(log_path)
    grammar_captures: list[dict[str, Any]] = []
    posts: list[dict[str, Any]] = []
    for raw_post in raw_posts:
        post = dict(raw_post)
        source_response_format = post.pop("source_response_format", None)
        generated_grammar = post.pop("generated_grammar", None)
        post.pop("derived_direct_grammar", None)
        if (
            post.get("stage") in TARGET_STAGES
            and post.get("wire_constraint") == "response_format"
            and isinstance(source_response_format, dict)
            and isinstance(generated_grammar, str)
        ):
            grammar_captures.append(
                {
                    "stage": post["stage"],
                    "case_id": post.get("case_id"),
                    "response_format": source_response_format,
                    "response_format_sha256": post.get("response_format_sha256"),
                    "source_grammar": generated_grammar,
                    "source_grammar_sha256": post.get("generated_grammar_sha256"),
                }
            )
        posts.append(post)

    latencies = [float(row["elapsed_seconds"]) for row in observations]
    structured_posts = [
        post for post in posts if post.get("stage") in STRUCTURED_STAGES
    ]
    target_posts = [post for post in posts if post.get("stage") in TARGET_STAGES]
    target_by_stage = {
        stage: direct_benchmark._post_metrics(
            [post for post in target_posts if post.get("stage") == stage]
        )
        for stage in sorted(TARGET_STAGES)
    }
    eligible_posts = [
        post for post in target_posts if post.get("eligible_empty_length_retry") is True
    ]
    return {
        "run_id": run_id,
        "profile": profile,
        "ready_seconds": ready_seconds,
        "elapsed_total_seconds": time.perf_counter() - arm_started,
        "turn_elapsed_total_seconds": sum(latencies),
        "turn_latency_seconds": {
            "p50": statistics.median(latencies),
            "p95_nearest_rank": retry_benchmark._quantile(latencies, 0.95),
            "max": max(latencies),
        },
        "workload_sha256": workload_sha256,
        "workload_case_ids": [item.case_id for item in workload],
        "validation_errors": sum(
            row["validation_error"] is not None for row in observations
        ),
        "turn_retry_cases": [
            row["case_id"]
            for row in observations
            if row["reply"].get("turn_attempts") not in {None, 1}
        ],
        "empty_length_posts": sum(
            post.get("empty_length") is True for post in structured_posts
        ),
        "target_empty_length_posts": sum(
            post.get("empty_length") is True for post in target_posts
        ),
        "eligible_retry_posts": len(eligible_posts),
        "candidate_applied_posts": sum(
            post.get("candidate_applied") is True for post in target_posts
        ),
        "candidate_capture_misses": sum(
            post.get("capture_miss") is True for post in target_posts
        ),
        "first_attempt_response_format_violations": sum(
            post.get("eligible_empty_length_retry") is not True
            and post.get("wire_constraint") != "response_format"
            for post in target_posts
        ),
        "direct_scope_violations": sum(
            post.get("wire_constraint") == "direct_gbnf"
            and post.get("eligible_empty_length_retry") is not True
            for post in target_posts
        ),
        "non_target_direct_posts": sum(
            post.get("wire_constraint") == "direct_gbnf"
            for post in posts
            if post.get("stage") not in TARGET_STAGES
        ),
        "response_format_grammar_capture_misses": sum(
            post.get("wire_constraint") == "response_format"
            and post.get("derivation_error") is not None
            for post in target_posts
        ),
        "direct_grammar_echo_mismatches": sum(
            post.get("candidate_applied") is True
            and post.get("wire_grammar_echo_equal") is not True
            for post in target_posts
        ),
        "seed_or_temperature_mutations": sum(
            post.get("source_seed") != post.get("wire_seed")
            or post.get("source_temperature") != post.get("wire_temperature")
            for post in posts
        ),
        "structured_post_elapsed_total_seconds": sum(
            float(post.get("elapsed_seconds") or 0.0) for post in structured_posts
        ),
        "target_post_metrics": {
            "all": direct_benchmark._post_metrics(target_posts),
            "by_stage": target_by_stage,
        },
        "grammar_captures": grammar_captures,
        "observations": observations,
        "posts": posts,
    }


def _compare_pair(
    pair_id: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    comparison = retry_benchmark._compare_pair(
        pair_id,
        baseline,
        candidate,
    )
    baseline_cases = {row["case_id"]: row for row in baseline["observations"]}
    candidate_cases = {row["case_id"]: row for row in candidate["observations"]}
    same_case_ids = set(baseline_cases) == set(candidate_cases)
    decisions_equal = same_case_ids and all(
        baseline_cases[case_id]["decision_projection"]
        == candidate_cases[case_id]["decision_projection"]
        for case_id in baseline_cases
    )
    comparison.update(
        {
            "arm_roles": {
                "baseline": PROFILE_BASELINE,
                "candidate": PROFILE_CANDIDATE,
            },
            "decision_projections_equal": decisions_equal,
            "baseline_eligible_retry_posts": baseline["eligible_retry_posts"],
            "candidate_eligible_retry_posts": candidate["eligible_retry_posts"],
            "baseline_target_empty_length_posts": baseline["target_empty_length_posts"],
            "candidate_target_empty_length_posts": candidate[
                "target_empty_length_posts"
            ],
        }
    )
    return comparison


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

    user_dotnet = Path.home() / ".dotnet"
    if (user_dotnet / "dotnet.exe").is_file():
        os.environ["DOTNET_ROOT"] = str(user_dotnet)
        os.environ["DOTNET_ROOT_X64"] = str(user_dotnet)

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(discover_core(None))
    arm_plan = (
        ("order1-baseline", PROFILE_BASELINE),
        ("order1-candidate", PROFILE_CANDIDATE),
        ("order2-candidate", PROFILE_CANDIDATE),
        ("order2-baseline", PROFILE_BASELINE),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pv-empty-length-gbnf-retry-ab-",
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
    grammar_catalogs = {
        arm["run_id"]: direct_benchmark._build_grammar_catalog(arm) for arm in arms
    }
    catalog_contracts = {
        run_id: direct_benchmark._catalog_contract(catalog)
        for run_id, catalog in grammar_catalogs.items()
    }
    first_catalog_contract = catalog_contracts["order1-baseline"]

    workload_complete = all(
        len(arm["observations"]) == EXPECTED_TURNS_PER_ARM for arm in arms
    )
    workload_identical = (
        len({arm["workload_sha256"] for arm in arms}) == 1
        and len({tuple(arm["workload_case_ids"]) for arm in arms}) == 1
    )
    validation_clean = all(arm["validation_errors"] == 0 for arm in arms)
    source_grammar_stable = all(
        contract == first_catalog_contract for contract in catalog_contracts.values()
    )
    first_attempts_preserved = all(
        arm["first_attempt_response_format_violations"] == 0 for arm in arms
    )
    root_only_capture_complete = all(
        arm["response_format_grammar_capture_misses"] == 0 for arm in arms
    )
    sampling_unchanged = all(arm["seed_or_temperature_mutations"] == 0 for arm in arms)
    candidate_arms = [arm for arm in arms if arm["profile"] == PROFILE_CANDIDATE]
    baseline_arms = [arm for arm in arms if arm["profile"] == PROFILE_BASELINE]
    candidate_triggered_both_orders = all(
        arm["eligible_retry_posts"] > 0 and arm["candidate_applied_posts"] > 0
        for arm in candidate_arms
    )
    candidate_retry_coverage_exact = all(
        arm["candidate_applied_posts"] == arm["eligible_retry_posts"]
        and arm["candidate_capture_misses"] == 0
        and arm["direct_scope_violations"] == 0
        and arm["non_target_direct_posts"] == 0
        for arm in candidate_arms
    )
    baseline_kept_response_format = all(
        arm["candidate_applied_posts"] == 0
        and arm["direct_scope_violations"] == 0
        and arm["non_target_direct_posts"] == 0
        for arm in baseline_arms
    )
    direct_grammar_echo_exact = all(
        arm["direct_grammar_echo_mismatches"] == 0 for arm in candidate_arms
    )
    exact_decisions_replies_effects = all(
        comparison["all_cases_present"]
        and comparison["decision_projections_equal"]
        and comparison["semantic_replies_equal"]
        and comparison["visible_replies_equal"]
        and comparison["effect_projections_equal"]
        for comparison in comparisons
    )
    zero_unsafe_deltas = all(
        comparison["candidate_unsafe_deltas"] == 0 for comparison in comparisons
    )
    retries_lower_both_orders = all(
        comparison["candidate_retry_reduction"] > 0 for comparison in comparisons
    )
    retry_tail_faster_both_orders = all(
        comparison["tail_cases"] > 0
        and comparison["candidate_minus_baseline_tail_total_seconds"] < 0.0
        for comparison in comparisons
    )
    total_faster_both_orders = all(
        comparison["candidate_minus_baseline_turn_total_seconds"] < 0.0
        for comparison in comparisons
    )
    measurement_valid = (
        workload_complete
        and workload_identical
        and validation_clean
        and source_grammar_stable
        and first_attempts_preserved
        and root_only_capture_complete
        and sampling_unchanged
        and candidate_triggered_both_orders
        and candidate_retry_coverage_exact
        and baseline_kept_response_format
        and direct_grammar_echo_exact
        and exact_decisions_replies_effects
        and zero_unsafe_deltas
    )
    hypothesis_supported = (
        measurement_valid
        and retries_lower_both_orders
        and retry_tail_faster_both_orders
        and total_faster_both_orders
    )

    result = {
        "schema": "baxy.pv-empty-length-retry-direct-gbnf-ab.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_status": "research_only",
        "measurement_outcome": (
            "hypothesis_supported"
            if hypothesis_supported
            else (
                "valid_but_hypothesis_not_supported"
                if measurement_valid
                else "invalid_measurement"
            )
        ),
        "effects_executed": 0,
        "candidate": {
            "target_stages": sorted(TARGET_STAGES),
            "scope": (
                "immediately following internal retry of the same P/V "
                "structured object, only after empty content plus "
                "finish_reason=length"
            ),
            "source": (
                "the immediately preceding response_format response's "
                "__verbose.generation_settings.grammar"
            ),
            "wire_delta": {
                "first_internal_attempt": "response_format unchanged",
                "eligible_second_internal_attempt": (
                    "remove response_format; use captured grammar with only "
                    "root replaced by `root ::= response-format-schema`"
                ),
            },
            "unchanged": [
                "messages and prompts",
                "JSON schemas",
                "temperature and seeds",
                "max_tokens and request budgets",
                "every non-root GBNF byte",
                "downstream JSON parsing and validators",
                "logical full-turn recovery",
                "all non-P/V stages",
            ],
        },
        "workload": {
            "turns_per_arm": EXPECTED_TURNS_PER_ARM,
            "workload_sha256": arms[0]["workload_sha256"],
            "case_ids": arms[0]["workload_case_ids"],
            "arms": [run_id for run_id, _ in arm_plan],
            "fresh_sidecar_and_llama_server_per_arm": True,
            "both_orders": True,
            "core_effect_requests_sent": 0,
            "catalog_operations": len(capabilities),
        },
        "runtime": public_runtime_identity(runtime),
        "runtime_hashes": {
            "llama_server_sha256": retry_benchmark._sha256_file(runtime.llama_server),
            "model_sha256": retry_benchmark._sha256_file(runtime.gguf),
        },
        "gates": {
            "workload_complete": workload_complete,
            "workload_identical_across_arms": workload_identical,
            "validation_clean": validation_clean,
            "source_grammar_stable_across_arms": source_grammar_stable,
            "first_attempt_response_format_preserved": (first_attempts_preserved),
            "root_only_capture_complete": root_only_capture_complete,
            "temperature_and_seeds_unchanged": sampling_unchanged,
            "candidate_triggered_both_orders": (candidate_triggered_both_orders),
            "candidate_retry_coverage_exact": (candidate_retry_coverage_exact),
            "baseline_kept_response_format": baseline_kept_response_format,
            "direct_grammar_echo_exact": direct_grammar_echo_exact,
            "exact_decisions_replies_effects": (exact_decisions_replies_effects),
            "zero_unsafe_deltas": zero_unsafe_deltas,
            "retries_lower_both_orders": retries_lower_both_orders,
            "retry_tail_faster_both_orders": (retry_tail_faster_both_orders),
            "total_faster_both_orders": total_faster_both_orders,
            "measurement_valid": measurement_valid,
            "hypothesis_supported": hypothesis_supported,
        },
        "evaluation_rule": (
            "Require the exact frozen 30-turn workload in four fresh physical "
            "arms; response_format on every first P/V internal attempt; direct "
            "GBNF only on the immediately matched empty+length retry; exact "
            "root-only derivation and wire echo; unchanged sampling; 30/30 "
            "valid replies; exact decision, semantic/visible reply and effect "
            "projections; zero unsafe deltas; and fewer full-turn retries, "
            "lower retry-tail total time and lower total turn time in both "
            "opposite-order pairs."
        ),
        "grammar_catalog": grammar_catalogs["order1-baseline"],
        "grammar_catalog_contract_sha256_by_arm": {
            run_id: retry_benchmark._canonical_hash(contract)
            for run_id, contract in catalog_contracts.items()
        },
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
                "measurement_outcome": result["measurement_outcome"],
                "gates": result["gates"],
                "comparisons": [
                    {
                        key: comparison[key]
                        for key in (
                            "pair_id",
                            "decision_projections_equal",
                            "semantic_replies_equal",
                            "visible_replies_equal",
                            "effect_projections_equal",
                            "candidate_unsafe_deltas",
                            "baseline_retry_cases",
                            "candidate_retry_cases",
                            "candidate_retry_reduction",
                            "candidate_applied_posts",
                            "candidate_minus_baseline_tail_total_seconds",
                            "candidate_minus_baseline_turn_total_seconds",
                        )
                    }
                    for comparison in comparisons
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if hypothesis_supported else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sidecar-profile",
        choices=(
            PROFILE_BASELINE,
            PROFILE_CANDIDATE,
            PROFILE_EXPANDED_BUDGET,
        ),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--sidecar-log", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.sidecar_profile is not None:
        if args.sidecar_log is None:
            parser.error("--sidecar-log is required in sidecar mode")
        return _run_sidecar(
            args.sidecar_profile,
            args.sidecar_log.resolve(),
        )
    if args.sidecar_log is not None:
        parser.error("--sidecar-log is internal")

    output = args.output.resolve()
    fixes = (ROOT / "artifacts" / "fixes").resolve()
    if output.parent != fixes or output.suffix.casefold() != ".json":
        parser.error("--output must be a JSON directly below artifacts/fixes")
    return _run_experiment(output)


if __name__ == "__main__":
    raise SystemExit(main())
