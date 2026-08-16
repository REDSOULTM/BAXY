"""Research-only physical A/B for P/V response_format versus direct GBNF.

This experiment reuses the frozen 30-turn workload, reply projections and
physical-process discipline from ``benchmark_invalid_empty_length_retry.py``.
It does not edit the production runtime and never dispatches a Core operation.

The first response-format arm captures, for every P/V response format, the
exact grammar returned by llama.cpp in
``__verbose.generation_settings.grammar``.  The direct-GBNF arms use that
captured grammar byte-for-byte except for this single rule replacement:

    root ::= response-format-schema

No other grammar rule is regenerated, normalized or reordered.  A missing
catalog entry fails closed to response_format and makes the measurement gate
fail.  The final response-format arm independently verifies that llama.cpp
generated the same source grammars in the opposite order.

Every arm starts a fresh sidecar and therefore a fresh llama-server child:

    response_format -> direct_gbnf -> direct_gbnf -> response_format

The artifact records decision/effect equivalence, empty+length events,
prompt/completion/returned-token counts, and p50/p95/max latency for all 30
turns and for the targeted P/V posts.
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


PROFILE_RESPONSE_FORMAT = "response-format"
PROFILE_DIRECT_GBNF = "direct-gbnf"
TARGET_STAGES = frozenset({"P", "V"})
STRUCTURED_STAGES = retry_benchmark.TARGET_STAGES
EXPECTED_TURNS_PER_ARM = 30
GRAMMAR_CATALOG_SCHEMA = "baxy.pv-response-format-grammar-catalog.v1"
DEFAULT_OUTPUT = (
    ROOT / "artifacts" / "fixes" / "pv_response_format_direct_gbnf_ab_20260729.json"
)


def _constraint_key(stage: str, response_format_sha256: str) -> str:
    return f"{stage}:{response_format_sha256}"


def _constraint_neutral_payload_sha256(payload: dict[str, Any]) -> str:
    canonical = dict(payload)
    for field in (
        "response_format",
        "grammar",
        "verbose",
        "return_tokens",
    ):
        canonical.pop(field, None)
    return retry_benchmark._canonical_hash(canonical)


def _generated_grammar(response: dict[str, Any]) -> str | None:
    verbose = response.get("__verbose")
    if not isinstance(verbose, dict):
        return None
    settings = verbose.get("generation_settings")
    if not isinstance(settings, dict):
        return None
    grammar = settings.get("grammar")
    return grammar if isinstance(grammar, str) and grammar else None


def _replace_root_with_response_format_schema(
    source_grammar: str,
) -> tuple[str, str]:
    """Change only the root rule and retain every other source byte."""

    if not isinstance(source_grammar, str) or not source_grammar:
        raise ValueError("source grammar is empty")
    lines = source_grammar.splitlines(keepends=True)
    root_indexes = [
        index
        for index, line in enumerate(lines)
        if line.removesuffix("\n").removesuffix("\r").startswith("root ::=")
    ]
    response_schema_rules = [
        line
        for line in lines
        if line.removesuffix("\n")
        .removesuffix("\r")
        .startswith("response-format-schema ::=")
    ]
    if len(root_indexes) != 1:
        raise ValueError(
            "expected exactly one top-level root rule in generated grammar"
        )
    if len(response_schema_rules) != 1:
        raise ValueError("expected exactly one response-format-schema subrule")

    root_index = root_indexes[0]
    source_line = lines[root_index]
    source_rule = source_line.removesuffix("\n").removesuffix("\r")
    ending = source_line[len(source_rule) :]
    direct_rule = "root ::= response-format-schema"
    if source_rule == direct_rule:
        raise ValueError("generated grammar already uses the direct root")
    lines[root_index] = direct_rule + ending
    direct_grammar = "".join(lines)

    source_prefix = "".join(lines[:root_index])
    source_suffix = "".join(lines[root_index + 1 :])
    expected_direct = source_prefix + direct_rule + ending + source_suffix
    if direct_grammar != expected_direct:
        raise AssertionError("direct grammar changed outside the root rule")
    return direct_grammar, source_rule


def _load_direct_catalog(path: Path) -> dict[str, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema") != GRAMMAR_CATALOG_SCHEMA
        or not isinstance(value.get("entries"), dict)
    ):
        raise ValueError("invalid P/V grammar catalog")

    validated: dict[str, dict[str, Any]] = {}
    for key, raw_entry in value["entries"].items():
        if not isinstance(key, str) or not isinstance(raw_entry, dict):
            raise ValueError("invalid P/V grammar catalog entry")
        stage = raw_entry.get("stage")
        response_format = raw_entry.get("response_format")
        response_format_sha256 = raw_entry.get("response_format_sha256")
        source_grammar = raw_entry.get("source_grammar")
        direct_grammar = raw_entry.get("direct_grammar")
        if (
            stage not in TARGET_STAGES
            or not isinstance(response_format, dict)
            or not isinstance(response_format_sha256, str)
            or not isinstance(source_grammar, str)
            or not isinstance(direct_grammar, str)
            or key != _constraint_key(stage, response_format_sha256)
            or retry_benchmark._canonical_hash(response_format)
            != response_format_sha256
        ):
            raise ValueError("invalid P/V grammar catalog contract")
        derived, _ = _replace_root_with_response_format_schema(source_grammar)
        if (
            derived != direct_grammar
            or hashlib.sha256(source_grammar.encode("utf-8")).hexdigest()
            != raw_entry.get("source_grammar_sha256")
            or hashlib.sha256(direct_grammar.encode("utf-8")).hexdigest()
            != raw_entry.get("direct_grammar_sha256")
        ):
            raise ValueError("P/V grammar catalog is not root-only")
        validated[key] = raw_entry
    return validated


def _run_sidecar(
    profile: str,
    log_path: Path,
    grammar_catalog_path: Path | None,
) -> int:
    """Patch only this experimental child, then enter the normal sidecar."""

    if profile not in {PROFILE_RESPONSE_FORMAT, PROFILE_DIRECT_GBNF}:
        raise ValueError(f"unknown sidecar profile: {profile}")
    if profile == PROFILE_DIRECT_GBNF:
        if grammar_catalog_path is None:
            raise ValueError("direct GBNF requires a grammar catalog")
        direct_catalog = _load_direct_catalog(grammar_catalog_path)
    else:
        if grammar_catalog_path is not None:
            raise ValueError("response_format arm cannot consume a catalog")
        direct_catalog = {}

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
        response_format = original.get("response_format")
        response_format_sha256 = (
            retry_benchmark._canonical_hash(response_format)
            if stage in TARGET_STAGES and isinstance(response_format, dict)
            else None
        )
        catalog_key = (
            _constraint_key(stage, response_format_sha256)
            if isinstance(response_format_sha256, str)
            else None
        )
        candidate_applied = False
        catalog_miss = False
        expected_direct_grammar: str | None = None

        wire = dict(original)
        if stage in STRUCTURED_STAGES:
            # Response-only diagnostics; identical in both measured profiles.
            wire["verbose"] = True
            wire["return_tokens"] = True
        if stage in TARGET_STAGES:
            if not isinstance(response_format, dict):
                raise RuntimeError(
                    f"{stage} did not reach the wire with response_format"
                )
            if profile == PROFILE_DIRECT_GBNF:
                entry = direct_catalog.get(str(catalog_key))
                if entry is None:
                    # Keep the production response_format rather than inventing
                    # a grammar. The arm records the miss and cannot pass.
                    catalog_miss = True
                else:
                    expected_direct_grammar = str(entry["direct_grammar"])
                    wire.pop("response_format", None)
                    wire["grammar"] = expected_direct_grammar
                    candidate_applied = True

        case_id = str(getattr(self, "_pv_response_format_benchmark_case", ""))
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
            "constraint_neutral_payload_sha256": (
                _constraint_neutral_payload_sha256(original)
            ),
            "response_format_sha256": response_format_sha256,
            "catalog_key": catalog_key,
            "candidate_applied": candidate_applied,
            "catalog_miss": catalog_miss,
            "wire_constraint": (
                "direct_gbnf"
                if candidate_applied
                else (
                    "response_format"
                    if isinstance(response_format, dict)
                    else "unchanged"
                )
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
        generated_grammar = _generated_grammar(response)
        empty_length = finish_reason == "length" and not content.strip()
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
        generated_grammar_sha256 = (
            hashlib.sha256(generated_grammar.encode("utf-8")).hexdigest()
            if generated_grammar is not None
            else None
        )
        write_record(
            {
                **record_prefix,
                "elapsed_seconds": elapsed,
                "finish_reason": finish_reason,
                "empty_length": empty_length,
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
                "wire_grammar_echo_equal": (
                    generated_grammar == expected_direct_grammar
                    if candidate_applied
                    else None
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
            llm._pv_response_format_benchmark_case = str(message.get("id") or "")
        return original_prepare(message, **kwargs)

    LlmRuntime._post = benchmark_post
    sidecar_module._prepare_turn_result = benchmark_prepare
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post
        sidecar_module._prepare_turn_result = original_prepare


def _distribution(values: list[int | float]) -> dict[str, Any]:
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not numeric:
        return {
            "count": 0,
            "sum": 0.0,
            "p50": None,
            "p95_nearest_rank": None,
            "max": None,
        }
    return {
        "count": len(numeric),
        "sum": sum(numeric),
        "p50": statistics.median(numeric),
        "p95_nearest_rank": retry_benchmark._quantile(numeric, 0.95),
        "max": max(numeric),
    }


def _post_metrics(posts: list[dict[str, Any]]) -> dict[str, Any]:
    def numeric_field(name: str) -> list[int | float]:
        return [
            value
            for post in posts
            if isinstance((value := post.get(name)), (int, float))
            and not isinstance(value, bool)
        ]

    return {
        "posts": len(posts),
        "empty_length_posts": sum(post.get("empty_length") is True for post in posts),
        "valid_json_object_posts": sum(
            post.get("valid_json_object") is True for post in posts
        ),
        "direct_gbnf_posts": sum(
            post.get("candidate_applied") is True for post in posts
        ),
        "catalog_misses": sum(post.get("catalog_miss") is True for post in posts),
        "latency_seconds": _distribution(numeric_field("elapsed_seconds")),
        "returned_token_count": _distribution(numeric_field("returned_token_count")),
        "prompt_tokens": _distribution(numeric_field("prompt_tokens")),
        "completion_tokens": _distribution(numeric_field("completion_tokens")),
        "total_tokens": _distribution(numeric_field("total_tokens")),
    }


def _decision_projection(reply: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": reply.get("kind"),
        "operation": reply.get("operation"),
        "effectOperations": reply.get("effectOperations"),
        "question": reply.get("question"),
        "plan": reply.get("plan"),
    }


def _run_arm(
    *,
    profile: str,
    run_id: str,
    log_path: Path,
    grammar_catalog_path: Path | None,
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
    if grammar_catalog_path is not None:
        command.extend(["--grammar-catalog", str(grammar_catalog_path.resolve())])

    client = JsonLineProcess(command, environment=environment, cwd=ROOT)
    observations: list[dict[str, Any]] = []
    arm_started = time.perf_counter()
    ready_seconds: float | None = None
    workload = [item for item in build_workload() if item.request_type == "turn.decide"]
    if len(workload) != EXPECTED_TURNS_PER_ARM:
        raise RuntimeError(
            "frozen GPU workload no longer contains exactly 30 turn.decide cases"
        )
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
                    "decision_projection": _decision_projection(reply),
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
        if (
            post.get("stage") in TARGET_STAGES
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
        stage: _post_metrics(
            [post for post in target_posts if post.get("stage") == stage]
        )
        for stage in sorted(TARGET_STAGES)
    }
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
        "candidate_applied_posts": sum(
            post.get("candidate_applied") is True for post in target_posts
        ),
        "target_constraint_posts": len(target_posts),
        "grammar_catalog_misses": sum(
            post.get("catalog_miss") is True for post in target_posts
        ),
        "wire_grammar_echo_mismatches": sum(
            post.get("candidate_applied") is True
            and post.get("wire_grammar_echo_equal") is not True
            for post in target_posts
        ),
        "structured_post_elapsed_total_seconds": sum(
            float(post.get("elapsed_seconds") or 0.0) for post in structured_posts
        ),
        "target_post_metrics": {
            "all": _post_metrics(target_posts),
            "by_stage": target_by_stage,
        },
        "grammar_captures": grammar_captures,
        "observations": observations,
        "posts": posts,
    }


def _build_grammar_catalog(source_arm: dict[str, Any]) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    observed_keys = {
        str(post["catalog_key"])
        for post in source_arm["posts"]
        if post.get("stage") in TARGET_STAGES
        and isinstance(post.get("catalog_key"), str)
    }
    for capture in source_arm["grammar_captures"]:
        stage = capture.get("stage")
        response_format = capture.get("response_format")
        response_format_sha256 = capture.get("response_format_sha256")
        source_grammar = capture.get("source_grammar")
        if (
            stage not in TARGET_STAGES
            or not isinstance(response_format, dict)
            or not isinstance(response_format_sha256, str)
            or not isinstance(source_grammar, str)
            or retry_benchmark._canonical_hash(response_format)
            != response_format_sha256
        ):
            raise ValueError("invalid response-format grammar capture")

        key = _constraint_key(stage, response_format_sha256)
        direct_grammar, source_root_rule = _replace_root_with_response_format_schema(
            source_grammar
        )
        entry = {
            "stage": stage,
            "response_format": response_format,
            "response_format_sha256": response_format_sha256,
            "source": "__verbose.generation_settings.grammar",
            "source_grammar": source_grammar,
            "source_grammar_sha256": hashlib.sha256(
                source_grammar.encode("utf-8")
            ).hexdigest(),
            "source_root_rule": source_root_rule,
            "direct_grammar": direct_grammar,
            "direct_grammar_sha256": hashlib.sha256(
                direct_grammar.encode("utf-8")
            ).hexdigest(),
            "direct_root_rule": "root ::= response-format-schema",
            "root_only_mutation": True,
            "capture_count": 1,
        }
        existing = entries.get(key)
        if existing is None:
            entries[key] = entry
            continue
        if any(
            existing[field] != entry[field]
            for field in (
                "stage",
                "response_format",
                "response_format_sha256",
                "source_grammar",
                "source_grammar_sha256",
                "source_root_rule",
                "direct_grammar",
                "direct_grammar_sha256",
                "direct_root_rule",
            )
        ):
            raise ValueError(
                "llama.cpp generated inconsistent grammar for one response_format"
            )
        existing["capture_count"] = int(existing["capture_count"]) + 1

    missing = sorted(observed_keys - set(entries))
    if missing:
        raise ValueError(
            "response_format arm did not expose generated grammar for: "
            + ", ".join(missing)
        )
    if not entries or not any(entry["stage"] == "P" for entry in entries.values()):
        raise ValueError("response_format arm did not capture P grammar")
    if not any(entry["stage"] == "V" for entry in entries.values()):
        raise ValueError("response_format arm did not capture V grammar")
    return {
        "schema": GRAMMAR_CATALOG_SCHEMA,
        "source_run_id": source_arm["run_id"],
        "derivation": (
            "Exact __verbose.generation_settings.grammar with only the "
            "top-level root rule replaced by "
            "`root ::= response-format-schema`."
        ),
        "entries": entries,
    }


def _catalog_contract(catalog: dict[str, Any]) -> dict[str, Any]:
    entries = catalog.get("entries")
    if not isinstance(entries, dict):
        return {}
    return {
        key: {
            field: entry.get(field)
            for field in (
                "stage",
                "response_format",
                "response_format_sha256",
                "source_grammar",
                "source_grammar_sha256",
                "source_root_rule",
                "direct_grammar",
                "direct_grammar_sha256",
                "direct_root_rule",
                "root_only_mutation",
            )
        }
        for key, entry in entries.items()
        if isinstance(key, str) and isinstance(entry, dict)
    }


def _distribution_delta(
    direct: dict[str, Any],
    response_format: dict[str, Any],
) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for field in ("sum", "p50", "p95_nearest_rank", "max"):
        left = direct.get(field)
        right = response_format.get(field)
        delta[field] = (
            float(left) - float(right)
            if isinstance(left, (int, float))
            and not isinstance(left, bool)
            and isinstance(right, (int, float))
            and not isinstance(right, bool)
            else None
        )
    return delta


def _metric_comparison(
    response_format: dict[str, Any],
    direct_gbnf: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "posts_delta": int(direct_gbnf["posts"]) - int(response_format["posts"]),
        "empty_length_posts_delta": int(direct_gbnf["empty_length_posts"])
        - int(response_format["empty_length_posts"]),
    }
    for metric in (
        "latency_seconds",
        "returned_token_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ):
        result[f"{metric}_direct_minus_response_format"] = _distribution_delta(
            direct_gbnf[metric],
            response_format[metric],
        )
    return result


def _compare_pair(
    pair_id: str,
    response_format: dict[str, Any],
    direct_gbnf: dict[str, Any],
) -> dict[str, Any]:
    comparison = retry_benchmark._compare_pair(
        pair_id,
        response_format,
        direct_gbnf,
    )
    response_cases = {row["case_id"]: row for row in response_format["observations"]}
    direct_cases = {row["case_id"]: row for row in direct_gbnf["observations"]}
    decision_projection_equal = all(
        case_id in direct_cases
        and response_row["decision_projection"]
        == direct_cases[case_id]["decision_projection"]
        for case_id, response_row in response_cases.items()
    ) and set(response_cases) == set(direct_cases)

    response_target = response_format["target_post_metrics"]
    direct_target = direct_gbnf["target_post_metrics"]
    comparison.update(
        {
            "arm_roles": {
                "baseline": PROFILE_RESPONSE_FORMAT,
                "candidate": PROFILE_DIRECT_GBNF,
            },
            "decision_projections_equal": decision_projection_equal,
            "response_format_target_empty_length_posts": response_format[
                "target_empty_length_posts"
            ],
            "direct_gbnf_target_empty_length_posts": direct_gbnf[
                "target_empty_length_posts"
            ],
            "direct_minus_response_format_target_metrics": (
                _metric_comparison(
                    response_target["all"],
                    direct_target["all"],
                )
            ),
            "direct_minus_response_format_stage_metrics": {
                stage: _metric_comparison(
                    response_target["by_stage"][stage],
                    direct_target["by_stage"][stage],
                )
                for stage in sorted(TARGET_STAGES)
            },
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
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pv-response-format-gbnf-ab-",
        dir=str(output.parent),
    ) as temporary:
        temp_root = Path(temporary).resolve()
        arms: list[dict[str, Any]] = []

        first_response = _run_arm(
            profile=PROFILE_RESPONSE_FORMAT,
            run_id="order1-response-format",
            log_path=temp_root / "order1-response-format.jsonl",
            grammar_catalog_path=None,
            runtime=runtime,
            capabilities=capabilities,
        )
        arms.append(first_response)
        grammar_catalog = _build_grammar_catalog(first_response)
        grammar_catalog_path = temp_root / "grammar-catalog.json"
        grammar_catalog_path.write_text(
            json.dumps(
                grammar_catalog,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        for run_id in ("order1-direct-gbnf", "order2-direct-gbnf"):
            arms.append(
                _run_arm(
                    profile=PROFILE_DIRECT_GBNF,
                    run_id=run_id,
                    log_path=temp_root / f"{run_id}.jsonl",
                    grammar_catalog_path=grammar_catalog_path,
                    runtime=runtime,
                    capabilities=capabilities,
                )
            )

        second_response = _run_arm(
            profile=PROFILE_RESPONSE_FORMAT,
            run_id="order2-response-format",
            log_path=temp_root / "order2-response-format.jsonl",
            grammar_catalog_path=None,
            runtime=runtime,
            capabilities=capabilities,
        )
        arms.append(second_response)
        verification_catalog = _build_grammar_catalog(second_response)

    arms_by_id = {arm["run_id"]: arm for arm in arms}
    comparisons = [
        _compare_pair(
            "response-format-then-direct-gbnf",
            arms_by_id["order1-response-format"],
            arms_by_id["order1-direct-gbnf"],
        ),
        _compare_pair(
            "direct-gbnf-then-response-format",
            arms_by_id["order2-response-format"],
            arms_by_id["order2-direct-gbnf"],
        ),
    ]

    workload_complete = all(
        len(arm["observations"]) == EXPECTED_TURNS_PER_ARM for arm in arms
    )
    validation_clean = all(arm["validation_errors"] == 0 for arm in arms)
    source_grammar_stable = _catalog_contract(grammar_catalog) == _catalog_contract(
        verification_catalog
    )
    direct_arms = [arm for arm in arms if arm["profile"] == PROFILE_DIRECT_GBNF]
    direct_coverage_complete = all(
        arm["target_constraint_posts"] > 0
        and arm["candidate_applied_posts"] == arm["target_constraint_posts"]
        and arm["grammar_catalog_misses"] == 0
        for arm in direct_arms
    )
    direct_grammar_echo_exact = all(
        arm["wire_grammar_echo_mismatches"] == 0 for arm in direct_arms
    )
    decisions_and_effects_equal = all(
        comparison["all_cases_present"]
        and comparison["decision_projections_equal"]
        and comparison["effect_projections_equal"]
        and comparison["candidate_unsafe_deltas"] == 0
        for comparison in comparisons
    )
    semantic_replies_equal = all(
        comparison["semantic_replies_equal"] and comparison["visible_replies_equal"]
        for comparison in comparisons
    )
    empty_length_lower_both_orders = all(
        comparison["direct_gbnf_target_empty_length_posts"]
        < comparison["response_format_target_empty_length_posts"]
        for comparison in comparisons
    )
    completion_tokens_lower_both_orders = all(
        (
            comparison["direct_minus_response_format_target_metrics"][
                "completion_tokens_direct_minus_response_format"
            ]["sum"]
            is not None
        )
        and (
            comparison["direct_minus_response_format_target_metrics"][
                "completion_tokens_direct_minus_response_format"
            ]["sum"]
            < 0.0
        )
        for comparison in comparisons
    )
    turn_p95_lower_both_orders = all(
        comparison["candidate_minus_baseline_p95_seconds"] < 0.0
        for comparison in comparisons
    )
    measurement_valid = (
        workload_complete
        and validation_clean
        and source_grammar_stable
        and direct_coverage_complete
        and direct_grammar_echo_exact
        and decisions_and_effects_equal
    )
    hypothesis_supported = (
        measurement_valid
        and semantic_replies_equal
        and empty_length_lower_both_orders
        and completion_tokens_lower_both_orders
        and turn_p95_lower_both_orders
    )

    result = {
        "schema": "baxy.pv-response-format-direct-gbnf-ab.v1",
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
            "source": "__verbose.generation_settings.grammar",
            "wire_delta": {
                "response_format": "removed only for matched P/V posts",
                "grammar": (
                    "captured source grammar with only root replaced by "
                    "`root ::= response-format-schema`"
                ),
            },
            "unchanged": [
                "messages and prompts",
                "temperature and seeds",
                "max_tokens and request budgets",
                "every non-root GBNF byte",
                "downstream JSON parsing and validators",
                "logical turn recovery",
                "all non-P/V stages",
            ],
            "catalog_source_arm": "order1-response-format",
            "catalog_verification_arm": "order2-response-format",
        },
        "workload": {
            "turns_per_arm": EXPECTED_TURNS_PER_ARM,
            "arms": [
                "order1-response-format",
                "order1-direct-gbnf",
                "order2-direct-gbnf",
                "order2-response-format",
            ],
            "fresh_sidecar_and_llama_server_per_arm": True,
            "both_orders": True,
            "catalog_operations": len(capabilities),
        },
        "runtime": public_runtime_identity(runtime),
        "runtime_hashes": {
            "llama_server_sha256": retry_benchmark._sha256_file(runtime.llama_server),
            "model_sha256": retry_benchmark._sha256_file(runtime.gguf),
        },
        "gates": {
            "workload_complete": workload_complete,
            "validation_clean": validation_clean,
            "root_only_derivation": True,
            "source_grammar_stable_across_orders": source_grammar_stable,
            "direct_coverage_complete": direct_coverage_complete,
            "direct_grammar_echo_exact": direct_grammar_echo_exact,
            "decisions_and_effects_equal": decisions_and_effects_equal,
            "semantic_and_visible_replies_equal": semantic_replies_equal,
            "empty_length_lower_both_orders": (empty_length_lower_both_orders),
            "completion_tokens_lower_both_orders": (
                completion_tokens_lower_both_orders
            ),
            "turn_p95_lower_both_orders": turn_p95_lower_both_orders,
            "measurement_valid": measurement_valid,
            "hypothesis_supported": hypothesis_supported,
        },
        "evaluation_rule": (
            "A valid measurement requires 30/30 contract-valid replies in "
            "every fresh-server arm, exact root-only grammar derivation and "
            "echo, stable source grammars, complete P/V coverage, equal "
            "decision/effect projections and zero unsafe effect deltas. The "
            "hypothesis additionally requires exact semantic/visible replies, "
            "fewer P/V empty+length posts, fewer P/V completion tokens and "
            "lower turn p95 in both opposite-order pairs."
        ),
        "grammar_catalog": grammar_catalog,
        "verification_grammar_catalog": verification_catalog,
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
                        "pair_id": comparison["pair_id"],
                        "decision_projections_equal": comparison[
                            "decision_projections_equal"
                        ],
                        "effect_projections_equal": comparison[
                            "effect_projections_equal"
                        ],
                        "candidate_unsafe_deltas": comparison[
                            "candidate_unsafe_deltas"
                        ],
                        "response_format_target_empty_length_posts": (
                            comparison["response_format_target_empty_length_posts"]
                        ),
                        "direct_gbnf_target_empty_length_posts": comparison[
                            "direct_gbnf_target_empty_length_posts"
                        ],
                        "candidate_minus_baseline_p50_seconds": comparison[
                            "candidate_minus_baseline_p50_seconds"
                        ],
                        "candidate_minus_baseline_p95_seconds": comparison[
                            "candidate_minus_baseline_p95_seconds"
                        ],
                        "candidate_minus_baseline_max_seconds": comparison[
                            "candidate_minus_baseline_max_seconds"
                        ],
                        "target_metric_deltas": comparison[
                            "direct_minus_response_format_target_metrics"
                        ],
                    }
                    for comparison in comparisons
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if measurement_valid else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sidecar-profile",
        choices=(PROFILE_RESPONSE_FORMAT, PROFILE_DIRECT_GBNF),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--sidecar-log", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--grammar-catalog",
        type=Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.sidecar_profile is not None:
        if args.sidecar_log is None:
            parser.error("--sidecar-log is required in sidecar mode")
        return _run_sidecar(
            args.sidecar_profile,
            args.sidecar_log.resolve(),
            (
                args.grammar_catalog.resolve()
                if args.grammar_catalog is not None
                else None
            ),
        )
    if args.sidecar_log is not None or args.grammar_catalog is not None:
        parser.error("sidecar arguments are internal")

    output = args.output.resolve()
    fixes = (ROOT / "artifacts" / "fixes").resolve()
    if output.parent != fixes or output.suffix.casefold() != ".json":
        parser.error("--output must be a JSON directly below artifacts/fixes")
    return _run_experiment(output)


if __name__ == "__main__":
    raise SystemExit(main())
