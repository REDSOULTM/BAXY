"""Effect-free per-case diagnostic for BAXY's frozen GPU turn workload.

This reuses the exact runtime resolver, catalog handshake, sidecar environment,
30 ``turn.decide`` inputs and transport limits from ``measure_mind_budget``.
It records only stable decision metadata and latency; model prose is excluded.
No Core operation is dispatched and no registered asset is changed.
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
import time
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    build_workload,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    validate_reply,
    write_json_atomic,
)


DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "gpu_turn_tail_diagnostic_20260729.json"
)
PV_GRAMMAR_ARTIFACT = (
    REPO
    / "artifacts"
    / "fixes"
    / "pv_response_format_direct_gbnf_ab_20260729.json"
)


def _run_budget_sidecar(policy_budget: int, count_budget: int) -> int:
    """Enter the normal sidecar with isolated b10182 request-local budgets."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_command = LlmRuntime._server_command
    original_post = LlmRuntime._post

    def budget_server_command(self: LlmRuntime) -> list[str]:
        command = original_command(self)
        for option in ("--reasoning", "--reasoning-budget"):
            if option in command:
                index = command.index(option)
                del command[index : index + 2]
        command.extend(
            [
                "--reasoning-budget-message",
                "Finish the requested response now.",
            ]
        )
        return command

    def budget_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        wire = dict(payload)
        response_format = wire.get("response_format")
        envelope = (
            response_format.get("json_schema")
            if isinstance(response_format, dict)
            else None
        )
        name = envelope.get("name") if isinstance(envelope, dict) else None
        if name == "baxy_turn_decision":
            wire["thinking_budget_tokens"] = policy_budget
        elif name == "baxy_effect_count_verification":
            wire["thinking_budget_tokens"] = count_budget
        return original_post(
            self,
            wire,
            timeout,
            max_attempts=max_attempts,
            cancellation=cancellation,
        )

    LlmRuntime._server_command = budget_server_command
    LlmRuntime._post = budget_post
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._server_command = original_command
        LlmRuntime._post = original_post


def _run_retry_scheduler_sidecar() -> int:
    """Enter the sidecar with speculative V disabled only on logical retries."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_begin_attempt = LlmRuntime.begin_request_attempt

    def begin_request_attempt(
        self: LlmRuntime,
        timeout: float,
        *,
        attempt: int,
    ) -> None:
        original_begin_attempt(self, timeout, attempt=attempt)
        self._speculative_count_after_guard = bool(
            self._parallel_turn_verification and attempt == 0
        )

    LlmRuntime.begin_request_attempt = begin_request_attempt
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.begin_request_attempt = original_begin_attempt


def _run_retry_reuse_sidecar() -> int:
    """Reuse validated G/L only inside the same logical turn retry."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_begin_attempt = LlmRuntime.begin_request_attempt
    original_detect_language = LlmRuntime.detect_response_language

    def begin_request_attempt(
        self: LlmRuntime,
        timeout: float,
        *,
        attempt: int,
    ) -> None:
        saved_guard = dict(getattr(self, "_semantic_effect_cache", {}))
        saved_language = dict(getattr(self, "_response_language_cache", {}))
        original_begin_attempt(self, timeout, attempt=attempt)
        if attempt > 0:
            self._semantic_effect_cache.update(saved_guard)
            self._response_language_cache.update(saved_language)
        self._speculative_count_after_guard = bool(
            self._parallel_turn_verification and attempt == 0
        )

    def detect_response_language(
        self: LlmRuntime,
        text: str,
        *,
        cancellation: Any = None,
        cache_result: bool = True,
    ) -> str:
        result = original_detect_language(
            self,
            text,
            cancellation=cancellation,
            cache_result=cache_result,
        )
        cache = getattr(self, "_response_language_cache", None)
        if cache is not None:
            cache[text] = result
        return result

    LlmRuntime.begin_request_attempt = begin_request_attempt
    LlmRuntime.detect_response_language = detect_response_language
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.begin_request_attempt = original_begin_attempt
        LlmRuntime.detect_response_language = original_detect_language


def _primary_whitespace_free_grammar(source_grammar: str) -> str:
    """Retain the generated grammar byte-for-byte except for ``space``."""

    source_rule = 'space ::= | " " | "\\n"{1,2} [ \\t]{0,20}'
    target_rule = 'space ::= | " " | "\\n" ("  " | "    ")?'
    if source_grammar.count(source_rule) != 1:
        raise ValueError("generated grammar has an unexpected space rule")
    candidate = source_grammar.replace(source_rule, target_rule, 1)
    if len(source_grammar) - len(candidate) != len(source_rule) - len(target_rule):
        raise AssertionError("whitespace-free grammar changed outside the space rule")
    return candidate


def _primary_direct_compact_grammar(source_grammar: str) -> str:
    """Retain P's schema while emitting only its bare, compact JSON object."""

    compact = _primary_whitespace_free_grammar(source_grammar)
    source_rule = (
        'root ::= start (thought | )? "```json" space '
        'response-format-schema space "```"'
    )
    target_rule = "root ::= response-format-schema"
    if compact.count(source_rule) != 1:
        raise ValueError("generated grammar has an unexpected root rule")
    return compact.replace(source_rule, target_rule, 1)


def _run_primary_whitespace_free_sidecar() -> int:
    """Force compact JSON only for P while preserving its generated grammar."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime
    from experiments.mind_router_spike import (
        benchmark_invalid_empty_length_retry as retry_benchmark,
    )
    from experiments.mind_router_spike.benchmark_llama_slot_pinning import (
        _stage,
    )

    artifact = json.loads(PV_GRAMMAR_ARTIFACT.read_text(encoding="utf-8"))
    catalog = artifact.get("grammar_catalog")
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    if not isinstance(entries, dict):
        raise ValueError("missing captured response-format grammar catalog")

    primary_grammars: dict[str, str] = {}
    for entry in entries.values():
        if not isinstance(entry, dict) or entry.get("stage") != "P":
            continue
        response_format_sha256 = entry.get("response_format_sha256")
        source_grammar = entry.get("source_grammar")
        if not isinstance(response_format_sha256, str) or not isinstance(
            source_grammar, str
        ):
            raise ValueError("invalid captured P grammar entry")
        primary_grammars[response_format_sha256] = (
            _primary_whitespace_free_grammar(source_grammar)
        )
    if not primary_grammars:
        raise ValueError("captured grammar catalog contains no P entries")

    original_post = LlmRuntime._post

    def compact_primary_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        wire = dict(payload)
        is_primary = _stage(wire) == "P"
        if is_primary:
            response_format = wire.get("response_format")
            if not isinstance(response_format, dict):
                raise RuntimeError("P reached the wire without response_format")
            response_format_sha256 = retry_benchmark._canonical_hash(
                response_format
            )
            grammar = primary_grammars.get(response_format_sha256)
            if grammar is None:
                raise RuntimeError(
                    "P response format missing from captured grammar catalog"
                )
            # Retain response_format so llama.cpp keeps its JSON extraction
            # and schema metadata. The explicit grammar only narrows whitespace.
            wire["grammar"] = grammar
        return original_post(
            self,
            wire,
            timeout,
            max_attempts=max_attempts,
            cancellation=cancellation,
        )

    LlmRuntime._post = compact_primary_post
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post


def _run_primary_direct_compact_sidecar() -> int:
    """Use P's captured schema as compact direct GBNF."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime
    from experiments.mind_router_spike import (
        benchmark_invalid_empty_length_retry as retry_benchmark,
    )
    from experiments.mind_router_spike.benchmark_llama_slot_pinning import (
        _stage,
    )

    artifact = json.loads(PV_GRAMMAR_ARTIFACT.read_text(encoding="utf-8"))
    catalog = artifact.get("grammar_catalog")
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    if not isinstance(entries, dict):
        raise ValueError("missing captured response-format grammar catalog")
    grammars: dict[str, str] = {}
    for entry in entries.values():
        if not isinstance(entry, dict) or entry.get("stage") != "P":
            continue
        response_format_sha256 = entry.get("response_format_sha256")
        source_grammar = entry.get("source_grammar")
        if isinstance(response_format_sha256, str) and isinstance(
            source_grammar, str
        ):
            grammars[response_format_sha256] = _primary_direct_compact_grammar(
                source_grammar
            )
    if not grammars:
        raise ValueError("captured grammar catalog contains no P entries")

    original_post = LlmRuntime._post
    original_post_schema = LlmRuntime._post_schema_object
    probe_log = os.environ.get("BAXY_PRIMARY_PROBE_LOG", "").strip() or str(
        REPO
        / "artifacts"
        / "fixes"
        / "primary_direct_compact_raw_probe_20260730.jsonl"
    )

    def direct_compact_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        wire = dict(payload)
        is_primary = _stage(wire) == "P"
        if is_primary:
            response_format = wire.get("response_format")
            if not isinstance(response_format, dict):
                raise RuntimeError("P reached the wire without response_format")
            key = retry_benchmark._canonical_hash(response_format)
            grammar = grammars.get(key)
            if grammar is None:
                raise RuntimeError("P response format missing from grammar catalog")
            wire.pop("response_format")
            wire["grammar"] = grammar
        try:
            response = original_post(
                self,
                wire,
                timeout,
                max_attempts=max_attempts,
                cancellation=cancellation,
            )
        except BaseException as error:
            if probe_log and is_primary:
                destination = Path(probe_log).resolve()
                with destination.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "request_attempt": getattr(
                                    self, "_request_attempt", None
                                ),
                                "exception": type(error).__name__,
                                "message": str(error)[:1000],
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
            raise
        if probe_log and is_primary:
            destination = Path(probe_log).resolve()
            fixes = (REPO / "artifacts" / "fixes").resolve()
            if destination.parent != fixes or destination.suffix != ".jsonl":
                raise RuntimeError("BAXY_PRIMARY_PROBE_LOG is outside artifacts/fixes")
            choices = response.get("choices")
            choice = choices[0] if isinstance(choices, list) and choices else {}
            message = choice.get("message") if isinstance(choice, dict) else {}
            with destination.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    json.dumps(
                        {
                            "request_attempt": getattr(self, "_request_attempt", None),
                            "finish_reason": (
                                choice.get("finish_reason")
                                if isinstance(choice, dict)
                                else None
                            ),
                            "content": (
                                message.get("content")
                                if isinstance(message, dict)
                                else None
                            ),
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        return response

    def capture_primary_object(
        self: LlmRuntime,
        payload: dict[str, Any],
        label: str,
    ) -> dict[str, Any]:
        result = original_post_schema(self, payload, label)
        if probe_log and label in {
            "la política de turno",
            "el reanálisis de turno con forma de efecto",
        }:
            destination = Path(probe_log).resolve()
            fixes = (REPO / "artifacts" / "fixes").resolve()
            if destination.parent != fixes or destination.suffix != ".jsonl":
                raise RuntimeError("BAXY_PRIMARY_PROBE_LOG is outside artifacts/fixes")
            with destination.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    json.dumps(
                        {
                            "label": label,
                            "request_attempt": getattr(self, "_request_attempt", None),
                            "result": result,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        return result

    LlmRuntime._post = direct_compact_post
    LlmRuntime._post_schema_object = capture_primary_object
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post
        LlmRuntime._post_schema_object = original_post_schema


def _run_primary_operation_names_only_sidecar() -> int:
    """Remove duplicated candidate prose while retaining every P contract."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind import llm as llm_module

    original_prepare = llm_module._prepare_turn_candidates

    def names_only_candidates(
        candidates: object,
    ) -> tuple[list[str], str, dict[str, dict[str, Any]]]:
        operation_names, _candidate_text, contracts = original_prepare(candidates)
        candidate_text = "\n".join(operation_names) or "(sin operaciones candidatas)"
        return operation_names, candidate_text, contracts

    llm_module._prepare_turn_candidates = names_only_candidates
    try:
        return sidecar_module.main()
    finally:
        llm_module._prepare_turn_candidates = original_prepare


def _run_primary_exclusive_first_sidecar() -> int:
    """Give P the GPU first, then release unchanged G/L verification."""

    import threading

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime
    from experiments.mind_router_spike.benchmark_llama_slot_pinning import (
        _stage,
    )

    original_begin_attempt = LlmRuntime.begin_request_attempt
    original_post = LlmRuntime._post
    original_post_schema = LlmRuntime._post_schema_object
    primary_complete = threading.Event()

    def begin_request_attempt(
        self: LlmRuntime,
        timeout: float,
        *,
        attempt: int,
    ) -> None:
        primary_complete.clear()
        original_begin_attempt(self, timeout, attempt=attempt)

    def priority_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        if _stage(payload) in {"G", "L"}:
            primary_complete.wait(self._effective_request_timeout(timeout))
        return original_post(
            self,
            payload,
            timeout,
            max_attempts=max_attempts,
            cancellation=cancellation,
        )

    def priority_post_schema(
        self: LlmRuntime,
        payload: dict[str, Any],
        label: str,
    ) -> dict[str, Any]:
        if label != "la política de turno":
            return original_post_schema(self, payload, label)
        try:
            return original_post_schema(self, payload, label)
        finally:
            primary_complete.set()

    LlmRuntime.begin_request_attempt = begin_request_attempt
    LlmRuntime._post = priority_post
    LlmRuntime._post_schema_object = priority_post_schema
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.begin_request_attempt = original_begin_attempt
        LlmRuntime._post = original_post
        LlmRuntime._post_schema_object = original_post_schema


def _run_primary_stagger_sidecar(delay_ms: float) -> int:
    """Let P enter llama-server first, then release unchanged G/L shortly after."""

    import threading

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime
    from experiments.mind_router_spike.benchmark_llama_slot_pinning import (
        _stage,
    )

    original_begin_attempt = LlmRuntime.begin_request_attempt
    original_post = LlmRuntime._post

    def begin_request_attempt(
        self: LlmRuntime,
        timeout: float,
        *,
        attempt: int,
    ) -> None:
        original_begin_attempt(self, timeout, attempt=attempt)
        self._benchmark_primary_release_at = (
            time.monotonic() + delay_ms / 1000.0
        )

    def staggered_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        if _stage(payload) in {"G", "L"}:
            release_at = getattr(
                self,
                "_benchmark_primary_release_at",
                time.monotonic(),
            )
            remaining = release_at - time.monotonic()
            if remaining > 0.0:
                threading.Event().wait(remaining)
        return original_post(
            self,
            payload,
            timeout,
            max_attempts=max_attempts,
            cancellation=cancellation,
        )

    LlmRuntime.begin_request_attempt = begin_request_attempt
    LlmRuntime._post = staggered_post
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.begin_request_attempt = original_begin_attempt
        LlmRuntime._post = original_post


def _run_primary_max_tokens_sidecar(max_tokens: int) -> int:
    """Change only P's output ceiling; preserve prompt, schema and sampler."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind import llm as llm_module

    original_build = llm_module._build_turn_policy_payload

    def expanded_policy_payload(
        text: str,
        operation_names: list[str],
        candidate_text: str,
        prior_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        payload = original_build(
            text,
            operation_names,
            candidate_text,
            prior_messages,
        )
        if payload.get("max_tokens") != 160:
            raise AssertionError("production P token ceiling changed")
        payload["max_tokens"] = max_tokens
        return payload

    llm_module._build_turn_policy_payload = expanded_policy_payload
    try:
        return sidecar_module.main()
    finally:
        llm_module._build_turn_policy_payload = original_build


def _run_primary_reasoning_early_abort_sidecar() -> int:
    """Enable the P-only reasoning-prefix abort seam in this child process."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__
    original_prepare = sidecar_module._prepare_turn_result
    abort_starts: dict[str, int] = {}

    def candidate_init(self: LlmRuntime) -> None:
        original_init(self)
        self._early_abort_policy_reasoning = True

    def candidate_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        request_key = str(message.get("id") or id(message))
        before = abort_starts.setdefault(
            request_key,
            int(getattr(llm, "_policy_reasoning_early_aborts", 0)),
        )
        result = original_prepare(message, **kwargs)
        after = int(
            getattr(llm, "_policy_reasoning_early_aborts", before)
        )
        abort_starts.pop(request_key, None)
        result["_diagnostic_policy_reasoning_early_aborts"] = after - before
        return result

    LlmRuntime.__init__ = candidate_init
    sidecar_module._prepare_turn_result = candidate_prepare
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.__init__ = original_init
        sidecar_module._prepare_turn_result = original_prepare


def _run_primary_speculative_retry_sidecar() -> int:
    """Overlap only P's unchanged second seed after reasoning starts."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__
    original_prepare = sidecar_module._prepare_turn_result
    original_recover = sidecar_module._recover_failed_turn
    counter_starts: dict[str, tuple[int, int]] = {}

    def candidate_init(self: LlmRuntime) -> None:
        original_init(self)
        self._speculative_primary_retry = True

    def candidate_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        request_key = str(message.get("id") or id(message))
        before_started, before_used = counter_starts.setdefault(
            request_key,
            (
                int(
                    getattr(
                        llm,
                        "_policy_speculative_retries_started",
                        0,
                    )
                ),
                int(
                    getattr(
                        llm,
                        "_policy_speculative_retries_used",
                        0,
                    )
                ),
            ),
        )
        result = original_prepare(message, **kwargs)
        after_started = int(
            getattr(
                llm,
                "_policy_speculative_retries_started",
                before_started,
            )
        )
        after_used = int(
            getattr(
                llm,
                "_policy_speculative_retries_used",
                before_used,
            )
        )
        counter_starts.pop(request_key, None)
        result["_diagnostic_policy_speculative_retries_started"] = (
            after_started - before_started
        )
        result["_diagnostic_policy_speculative_retries_used"] = (
            after_used - before_used
        )
        return result

    def candidate_recover(
        message: dict[str, Any],
        llm: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        request_key = str(message.get("id") or id(message))
        before_started, before_used = counter_starts.setdefault(
            request_key,
            (
                int(
                    getattr(
                        llm,
                        "_policy_speculative_retries_started",
                        0,
                    )
                ),
                int(
                    getattr(
                        llm,
                        "_policy_speculative_retries_used",
                        0,
                    )
                ),
            ),
        )
        result = original_recover(message, llm, **kwargs)
        result["_diagnostic_policy_speculative_retries_started"] = (
            int(
                getattr(
                    llm,
                    "_policy_speculative_retries_started",
                    before_started,
                )
            )
            - before_started
        )
        result["_diagnostic_policy_speculative_retries_used"] = (
            int(
                getattr(
                    llm,
                    "_policy_speculative_retries_used",
                    before_used,
                )
            )
            - before_used
        )
        counter_starts.pop(request_key, None)
        return result

    LlmRuntime.__init__ = candidate_init
    sidecar_module._prepare_turn_result = candidate_prepare
    sidecar_module._recover_failed_turn = candidate_recover
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.__init__ = original_init
        sidecar_module._prepare_turn_result = original_prepare
        sidecar_module._recover_failed_turn = original_recover


def _run_primary_reasoning_control_sidecar() -> int:
    """End an armed P reasoning block while preserving its live decode."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__
    original_prepare = sidecar_module._prepare_turn_result
    original_recover = sidecar_module._recover_failed_turn
    counter_starts: dict[str, tuple[int, int]] = {}

    def counters(llm: Any) -> tuple[int, int]:
        return (
            int(
                getattr(
                    llm,
                    "_policy_reasoning_controls_requested",
                    0,
                )
            ),
            int(
                getattr(
                    llm,
                    "_policy_reasoning_controls_succeeded",
                    0,
                )
            ),
        )

    def annotate(
        result: dict[str, Any],
        *,
        before: tuple[int, int],
        llm: Any,
    ) -> dict[str, Any]:
        after_requested, after_succeeded = counters(llm)
        result["_diagnostic_policy_reasoning_controls_requested"] = (
            after_requested - before[0]
        )
        result["_diagnostic_policy_reasoning_controls_succeeded"] = (
            after_succeeded - before[1]
        )
        return result

    def candidate_init(self: LlmRuntime) -> None:
        original_init(self)
        self._primary_reasoning_control = True

    def candidate_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        request_key = str(message.get("id") or id(message))
        before = counter_starts.setdefault(request_key, counters(llm))
        result = original_prepare(message, **kwargs)
        counter_starts.pop(request_key, None)
        return annotate(result, before=before, llm=llm)

    def candidate_recover(
        message: dict[str, Any],
        llm: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        request_key = str(message.get("id") or id(message))
        before = counter_starts.setdefault(request_key, counters(llm))
        result = original_recover(message, llm, **kwargs)
        counter_starts.pop(request_key, None)
        return annotate(result, before=before, llm=llm)

    LlmRuntime.__init__ = candidate_init
    sidecar_module._prepare_turn_result = candidate_prepare
    sidecar_module._recover_failed_turn = candidate_recover
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.__init__ = original_init
        sidecar_module._prepare_turn_result = original_prepare
        sidecar_module._recover_failed_turn = original_recover


def _run_primary_stream_sidecar() -> int:
    """Stream only primary P and preserve every reasoning/content token."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__

    def candidate_init(self: LlmRuntime) -> None:
        original_init(self)
        self._stream_primary_policy = True

    LlmRuntime.__init__ = candidate_init
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.__init__ = original_init


def _run_server_reasoning_auto_sidecar() -> int:
    """Let b9980 detect Gemma's reasoning tags while keeping budget zero."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_command = LlmRuntime._server_command

    def candidate_command(self: LlmRuntime) -> list[str]:
        command = original_command(self)
        reasoning_index = command.index("--reasoning")
        if command[reasoning_index + 1] != "off":
            raise AssertionError("production reasoning profile changed")
        command[reasoning_index + 1] = "auto"
        return command

    LlmRuntime._server_command = candidate_command
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._server_command = original_command


def _run_primary_reasoning_format_none_sidecar() -> int:
    """Apply P's JSON Schema to the raw decode instead of a thought channel."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__

    def candidate_init(self: LlmRuntime) -> None:
        original_init(self)
        self._primary_reasoning_format_none = True

    LlmRuntime.__init__ = candidate_init
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.__init__ = original_init


def _run_primary_retry_reasoning_format_none_sidecar() -> int:
    """Use raw-schema decoding only after P already ended empty+length."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__
    original_prepare = sidecar_module._prepare_turn_result
    retry_starts: dict[str, int] = {}

    def candidate_init(self: LlmRuntime) -> None:
        original_init(self)
        self._retry_primary_reasoning_format_none = True

    def candidate_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        request_key = str(message.get("id") or id(message))
        before = retry_starts.setdefault(
            request_key,
            int(
                getattr(
                    llm,
                    "_policy_reasoning_format_none_retries",
                    0,
                )
            ),
        )
        result = original_prepare(message, **kwargs)
        after = int(
            getattr(
                llm,
                "_policy_reasoning_format_none_retries",
                before,
            )
        )
        retry_starts.pop(request_key, None)
        result["_diagnostic_policy_reasoning_format_none_retries"] = (
            after - before
        )
        return result

    LlmRuntime.__init__ = candidate_init
    sidecar_module._prepare_turn_result = candidate_prepare
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.__init__ = original_init
        sidecar_module._prepare_turn_result = original_prepare


def _run_primary_reasoning_cutoff_sidecar(cutoff: int) -> int:
    """Abort P only after its remaining budget cannot fit any valid suffix."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_init = LlmRuntime.__init__
    original_prepare = sidecar_module._prepare_turn_result
    abort_starts: dict[str, int] = {}

    def candidate_init(self: LlmRuntime) -> None:
        original_init(self)
        self._policy_reasoning_abort_after_predicted_n = cutoff

    def candidate_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        request_key = str(message.get("id") or id(message))
        before = abort_starts.setdefault(
            request_key,
            int(getattr(llm, "_policy_reasoning_early_aborts", 0)),
        )
        result = original_prepare(message, **kwargs)
        after = int(
            getattr(llm, "_policy_reasoning_early_aborts", before)
        )
        abort_starts.pop(request_key, None)
        result["_diagnostic_policy_reasoning_early_aborts"] = after - before
        return result

    LlmRuntime.__init__ = candidate_init
    sidecar_module._prepare_turn_result = candidate_prepare
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime.__init__ = original_init
        sidecar_module._prepare_turn_result = original_prepare


def _run_primary_without_redundant_fields_sidecar() -> int:
    """Derive P count/language fields that downstream already recomputes."""

    import copy

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind import llm as llm_module
    from baxy_mind.llm import LlmRuntime

    original_build = llm_module._build_turn_policy_payload
    original_post_schema = LlmRuntime._post_schema_object

    def compact_policy_payload(
        text: str,
        operation_names: list[str],
        candidate_text: str,
        prior_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        payload = original_build(
            text,
            operation_names,
            candidate_text,
            prior_messages,
        )
        compact = copy.deepcopy(payload)
        schema = compact["response_format"]["json_schema"]["schema"]
        properties = schema["properties"]
        required = schema["required"]
        properties.pop("effect_count")
        properties.pop("response_language")
        required.remove("effect_count")
        required.remove("response_language")
        return compact

    def restore_redundant_fields(
        self: LlmRuntime,
        payload: dict[str, Any],
        label: str,
    ) -> dict[str, Any]:
        result = original_post_schema(self, payload, label)
        if label not in {
            "la política de turno",
            "el reanálisis de turno con forma de efecto",
        }:
            return result
        effect_operations = result.get("effect_operations")
        if not isinstance(effect_operations, list):
            raise ValueError("P compacta no devolvió effect_operations")
        result["effect_count"] = (
            "zero"
            if not effect_operations
            else "one"
            if len(effect_operations) == 1
            else "multiple"
        )
        # For modeled turns the outer boundary always consumes L instead of
        # this field. A valid sentinel retains the existing internal contract.
        result["response_language"] = "es"
        return result

    llm_module._build_turn_policy_payload = compact_policy_payload
    LlmRuntime._post_schema_object = restore_redundant_fields
    try:
        return sidecar_module.main()
    finally:
        llm_module._build_turn_policy_payload = original_build
        LlmRuntime._post_schema_object = original_post_schema


def _run_primary_compact_prefill_sidecar() -> int:
    """Prefill P's fixed JSON prefix while retaining its full response schema."""

    import copy

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind import llm as llm_module

    original_build = llm_module._build_turn_policy_payload

    def prefilled_policy_payload(
        text: str,
        operation_names: list[str],
        candidate_text: str,
        prior_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        payload = original_build(
            text,
            operation_names,
            candidate_text,
            prior_messages,
        )
        prefilled = copy.deepcopy(payload)
        prefilled["messages"].append(
            {
                "role": "assistant",
                "content": "```json\n{",
            }
        )
        return prefilled

    llm_module._build_turn_policy_payload = prefilled_policy_payload
    try:
        return sidecar_module.main()
    finally:
        llm_module._build_turn_policy_payload = original_build


def _visible_reply_sha256(reply: dict[str, Any]) -> str | None:
    kind = reply.get("kind")
    field = "question" if kind == "clarify" else "reply"
    value = reply.get(field)
    if not isinstance(value, str):
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _semantic_reply_sha256(reply: dict[str, Any]) -> str:
    ignored = {
        "id",
        "turn_attempts",
        "turn_recovery",
        "recovery_attempts",
        "_diagnostic_policy_reasoning_early_aborts",
        "_diagnostic_policy_reasoning_format_none_retries",
        "_diagnostic_policy_speculative_retries_started",
        "_diagnostic_policy_speculative_retries_used",
        "_diagnostic_policy_reasoning_controls_requested",
        "_diagnostic_policy_reasoning_controls_succeeded",
    }
    return _canonical_sha256(
        {key: value for key, value in reply.items() if key not in ignored}
    )


def _effect_projection(reply: dict[str, Any]) -> dict[str, Any]:
    operations: list[str] = []
    operation = reply.get("operation")
    if isinstance(operation, str) and operation:
        operations.append(operation)
    effect_operations = reply.get("effectOperations")
    if isinstance(effect_operations, list):
        operations.extend(
            item
            for item in effect_operations
            if isinstance(item, str) and item
        )
    plan = reply.get("plan")
    if isinstance(plan, dict) and isinstance(plan.get("steps"), list):
        operations.extend(
            str(step["operation"])
            for step in plan["steps"]
            if isinstance(step, dict)
            and isinstance(step.get("operation"), str)
            and step["operation"]
        )
    return {
        "kind": reply.get("kind"),
        "operations": sorted(set(operations)),
    }


def _decision_projection(reply: dict[str, Any]) -> dict[str, Any]:
    plan = reply.get("plan")
    plan_operations: list[str] = []
    if isinstance(plan, dict):
        steps = plan.get("steps")
        if isinstance(steps, list):
            plan_operations = [
                str(step.get("operation"))
                for step in steps
                if isinstance(step, dict)
                and isinstance(step.get("operation"), str)
            ]
    return {
        "kind": reply.get("kind"),
        "operation": reply.get("operation"),
        "plan_operations": plan_operations,
        "turn_attempts": reply.get("turn_attempts"),
        "recovery": reply.get("recovery"),
        "effect_verification": reply.get("effect_verification"),
        "conversation_kind": reply.get("conversation_kind"),
        "response_language": reply.get("response_language"),
        "policy_reasoning_early_aborts": reply.get(
            "_diagnostic_policy_reasoning_early_aborts"
        ),
        "policy_reasoning_format_none_retries": reply.get(
            "_diagnostic_policy_reasoning_format_none_retries"
        ),
        "policy_speculative_retries_started": reply.get(
            "_diagnostic_policy_speculative_retries_started"
        ),
        "policy_speculative_retries_used": reply.get(
            "_diagnostic_policy_speculative_retries_used"
        ),
        "policy_reasoning_controls_requested": reply.get(
            "_diagnostic_policy_reasoning_controls_requested"
        ),
        "policy_reasoning_controls_succeeded": reply.get(
            "_diagnostic_policy_reasoning_controls_succeeded"
        ),
    }


def run(
    output: Path,
    case_ids: frozenset[str] | None = None,
    server: Path | None = None,
    thinking_budgets: tuple[int, int] | None = None,
    retry_without_speculative_v: bool = False,
    retry_reuse_verified_guard_language: bool = False,
    primary_whitespace_free_grammar: bool = False,
    primary_operation_names_only: bool = False,
    primary_exclusive_first: bool = False,
    primary_stagger_ms: float | None = None,
    primary_max_tokens: int | None = None,
    primary_stream: bool = False,
    server_reasoning_auto: bool = False,
    primary_reasoning_format_none: bool = False,
    primary_retry_reasoning_format_none: bool = False,
    primary_reasoning_cutoff: int | None = None,
    primary_reasoning_early_abort: bool = False,
    primary_speculative_retry: bool = False,
    primary_reasoning_control: bool = False,
    primary_without_redundant_fields: bool = False,
    primary_compact_prefill: bool = False,
    primary_direct_compact: bool = False,
) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    # Prefer the self-contained publish: the framework-dependent development
    # binary may exist while its target runtime is unavailable on the host.
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    if server is not None:
        environment["BAXY_MIND_LLAMA_SERVER"] = str(server)
    command = [str(runtime.python), "-u", "-X", "utf8"]
    if thinking_budgets is not None:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-thinking-budget-p",
                str(thinking_budgets[0]),
                "--sidecar-thinking-budget-v",
                str(thinking_budgets[1]),
            ]
        )
    elif retry_without_speculative_v:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-retry-without-speculative-v",
            ]
        )
    elif retry_reuse_verified_guard_language:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-retry-reuse-verified-guard-language",
            ]
        )
    elif primary_whitespace_free_grammar:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-whitespace-free-grammar",
            ]
        )
    elif primary_operation_names_only:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-operation-names-only",
            ]
        )
    elif primary_exclusive_first:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-exclusive-first",
            ]
        )
    elif primary_stagger_ms is not None:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-stagger-ms",
                str(primary_stagger_ms),
            ]
        )
    elif primary_max_tokens is not None:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-max-tokens",
                str(primary_max_tokens),
            ]
        )
    elif primary_stream:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-stream",
            ]
        )
    elif server_reasoning_auto:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-server-reasoning-auto",
            ]
        )
    elif primary_reasoning_format_none:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-reasoning-format-none",
            ]
        )
    elif primary_retry_reasoning_format_none:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-retry-reasoning-format-none",
            ]
        )
    elif primary_reasoning_cutoff is not None:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-reasoning-cutoff",
                str(primary_reasoning_cutoff),
            ]
        )
    elif primary_reasoning_early_abort:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-reasoning-early-abort",
            ]
        )
    elif primary_speculative_retry:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-speculative-retry",
            ]
        )
    elif primary_reasoning_control:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-reasoning-control",
            ]
        )
    elif primary_without_redundant_fields:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-without-redundant-fields",
            ]
        )
    elif primary_compact_prefill:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-compact-prefill",
            ]
        )
    elif primary_direct_compact:
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-primary-direct-compact",
            ]
        )
    else:
        command.extend(["-m", "baxy_mind"])
    client = JsonLineProcess(
        command,
        environment=environment,
        cwd=REPO,
    )
    observations: list[dict[str, Any]] = []
    workload_identity: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar hello rejected")
        catalog = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-gpu-tail",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if catalog.get("type") != "catalog.ready":
            raise RuntimeError(
                "catalog handshake rejected: "
                f"{json.dumps(catalog, ensure_ascii=False, sort_keys=True)}"
            )

        for item in build_workload():
            if (
                item.request_type != "turn.decide"
                or (case_ids is not None and item.case_id not in case_ids)
            ):
                continue
            workload_identity.append(
                {"case_id": item.case_id, "message": item.message}
            )
            begin = time.perf_counter()
            reply = client.request(item.message, limits["turn.decide"])
            elapsed = time.perf_counter() - begin
            observations.append(
                {
                    "case_id": item.case_id,
                    "elapsed_seconds": round(elapsed, 4),
                    "validation_error": validate_reply(item, reply) or None,
                    "decision": _decision_projection(reply),
                    "semantic_reply_sha256": _semantic_reply_sha256(reply),
                    "effect_projection_sha256": _canonical_sha256(
                        _effect_projection(reply)
                    ),
                    "visible_reply_sha256": _visible_reply_sha256(reply),
                }
            )
            print(
                f"{item.case_id}: {elapsed:.4f}s "
                f"{reply.get('kind')} attempts={reply.get('turn_attempts')}",
                flush=True,
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-gpu-tail"},
            timeout=limits["shutdown"],
        )

    latencies = [float(row["elapsed_seconds"]) for row in observations]
    ordered = sorted(latencies)
    report = {
        "schema": "baxy-gpu-turn-tail-diagnostic-v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": public_runtime_identity(runtime),
        "llama_server_override": str(server) if server is not None else None,
        "thinking_budgets": (
            {
                "policy": thinking_budgets[0],
                "effect_count": thinking_budgets[1],
            }
            if thinking_budgets is not None
            else None
        ),
        "retry_without_speculative_v": retry_without_speculative_v,
        "retry_reuse_verified_guard_language": (
            retry_reuse_verified_guard_language
        ),
        "primary_whitespace_free_grammar": primary_whitespace_free_grammar,
        "primary_operation_names_only": primary_operation_names_only,
        "primary_exclusive_first": primary_exclusive_first,
        "primary_stagger_ms": primary_stagger_ms,
        "primary_max_tokens": primary_max_tokens,
        "primary_stream": primary_stream,
        "server_reasoning_auto": server_reasoning_auto,
        "primary_reasoning_format_none": primary_reasoning_format_none,
        "primary_retry_reasoning_format_none": (
            primary_retry_reasoning_format_none
        ),
        "primary_reasoning_cutoff": primary_reasoning_cutoff,
        "primary_reasoning_early_abort": primary_reasoning_early_abort,
        "primary_speculative_retry": primary_speculative_retry,
        "primary_reasoning_control": primary_reasoning_control,
        "primary_without_redundant_fields": primary_without_redundant_fields,
        "primary_compact_prefill": primary_compact_prefill,
        "primary_direct_compact": primary_direct_compact,
        "catalog_operations": len(capabilities),
        "effects_executed": 0,
        "requests_completed": len(observations),
        "workload_sha256": _canonical_sha256(workload_identity),
        "validation_errors": sum(
            row["validation_error"] is not None for row in observations
        ),
        "policy_reasoning_early_aborts": sum(
            int(row["decision"].get("policy_reasoning_early_aborts") or 0)
            for row in observations
        ),
        "policy_reasoning_format_none_retries": sum(
            int(
                row["decision"].get(
                    "policy_reasoning_format_none_retries"
                )
                or 0
            )
            for row in observations
        ),
        "policy_speculative_retries_started": sum(
            int(
                row["decision"].get(
                    "policy_speculative_retries_started"
                )
                or 0
            )
            for row in observations
        ),
        "policy_speculative_retries_used": sum(
            int(
                row["decision"].get("policy_speculative_retries_used")
                or 0
            )
            for row in observations
        ),
        "policy_reasoning_controls_requested": sum(
            int(
                row["decision"].get(
                    "policy_reasoning_controls_requested"
                )
                or 0
            )
            for row in observations
        ),
        "policy_reasoning_controls_succeeded": sum(
            int(
                row["decision"].get(
                    "policy_reasoning_controls_succeeded"
                )
                or 0
            )
            for row in observations
        ),
        "elapsed_total_seconds": round(time.perf_counter() - started, 3),
        "turn_elapsed_total_seconds": round(sum(latencies), 4),
        "latency_seconds": {
            "p50": round(statistics.median(latencies), 4),
            "p95_nearest_rank": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
            "max": max(latencies),
        },
        "retry_cases": [
            row["case_id"]
            for row in observations
            if row["decision"]["turn_attempts"] not in {None, 1}
        ],
        "slowest": sorted(
            observations,
            key=lambda row: float(row["elapsed_seconds"]),
            reverse=True,
        )[:10],
        "observations": observations,
    }
    write_json_atomic(output.resolve(), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="repeatable turn case id; default runs all 30 frozen turns",
    )
    parser.add_argument(
        "--server",
        type=Path,
        help="optional isolated llama-server executable; the manifest is unchanged",
    )
    parser.add_argument(
        "--thinking-budget-p",
        type=int,
        help="research-only per-request thinking budget for P",
    )
    parser.add_argument(
        "--thinking-budget-v",
        type=int,
        help="research-only per-request thinking budget for V",
    )
    parser.add_argument(
        "--sidecar-thinking-budget-p",
        type=int,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--sidecar-thinking-budget-v",
        type=int,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--retry-without-speculative-v",
        action="store_true",
        help="research-only: defer V on the second logical turn attempt",
    )
    parser.add_argument(
        "--sidecar-retry-without-speculative-v",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--retry-reuse-verified-guard-language",
        action="store_true",
        help="research-only: reuse valid G/L and defer V on a logical retry",
    )
    parser.add_argument(
        "--sidecar-retry-reuse-verified-guard-language",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-whitespace-free-grammar",
        action="store_true",
        help="research-only: remove JSON whitespace from P by grammar alone",
    )
    parser.add_argument(
        "--sidecar-primary-whitespace-free-grammar",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-operation-names-only",
        action="store_true",
        help="research-only: omit candidate descriptions from P",
    )
    parser.add_argument(
        "--sidecar-primary-operation-names-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-exclusive-first",
        action="store_true",
        help="research-only: give P exclusive inference before unchanged G/L",
    )
    parser.add_argument(
        "--sidecar-primary-exclusive-first",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-stagger-ms",
        type=float,
        help="research-only: delay unchanged G/L briefly after starting P",
    )
    parser.add_argument(
        "--sidecar-primary-stagger-ms",
        type=float,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-max-tokens",
        type=int,
        help="research-only: change only P's 160-token output ceiling",
    )
    parser.add_argument(
        "--sidecar-primary-max-tokens",
        type=int,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-stream",
        action="store_true",
        help="research-only: reconstruct primary P through SSE without aborting",
    )
    parser.add_argument(
        "--sidecar-primary-stream",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--server-reasoning-auto",
        action="store_true",
        help=(
            "research-only: replace server --reasoning off with auto "
            "while preserving budget 0"
        ),
    )
    parser.add_argument(
        "--sidecar-server-reasoning-auto",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-reasoning-format-none",
        action="store_true",
        help=(
            "research-only: constrain raw primary P output without a "
            "separate reasoning channel"
        ),
    )
    parser.add_argument(
        "--sidecar-primary-reasoning-format-none",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-retry-reasoning-format-none",
        action="store_true",
        help=(
            "research-only: use raw-schema P only after empty+length"
        ),
    )
    parser.add_argument(
        "--sidecar-primary-retry-reasoning-format-none",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-reasoning-cutoff",
        type=int,
        help=(
            "research-only: abort reasoning-first P at the certified "
            "predicted-token threshold"
        ),
    )
    parser.add_argument(
        "--sidecar-primary-reasoning-cutoff",
        type=int,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-reasoning-early-abort",
        action="store_true",
        help=(
            "research-only: stop a 160-token P attempt when reasoning precedes "
            "all response content"
        ),
    )
    parser.add_argument(
        "--sidecar-primary-reasoning-early-abort",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-speculative-retry",
        action="store_true",
        help=(
            "research-only: overlap P's unchanged second seed after "
            "reasoning starts"
        ),
    )
    parser.add_argument(
        "--sidecar-primary-speculative-retry",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-reasoning-control",
        action="store_true",
        help=(
            "research-only: force an observed live P reasoning block "
            "to end and continue its JSON decode"
        ),
    )
    parser.add_argument(
        "--sidecar-primary-reasoning-control",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-without-redundant-fields",
        action="store_true",
        help="research-only: derive P effect_count/response_language",
    )
    parser.add_argument(
        "--sidecar-primary-without-redundant-fields",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-compact-prefill",
        action="store_true",
        help="research-only: prefill P's fixed compact JSON prefix",
    )
    parser.add_argument(
        "--sidecar-primary-compact-prefill",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--primary-direct-compact",
        action="store_true",
        help="research-only: emit P's unchanged schema as bare compact JSON",
    )
    parser.add_argument(
        "--sidecar-primary-direct-compact",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if (
        args.sidecar_thinking_budget_p is not None
        or args.sidecar_thinking_budget_v is not None
    ):
        if (
            args.sidecar_thinking_budget_p is None
            or args.sidecar_thinking_budget_v is None
        ):
            parser.error("both internal thinking budgets are required")
        return _run_budget_sidecar(
            args.sidecar_thinking_budget_p,
            args.sidecar_thinking_budget_v,
        )
    if args.sidecar_retry_without_speculative_v:
        return _run_retry_scheduler_sidecar()
    if args.sidecar_retry_reuse_verified_guard_language:
        return _run_retry_reuse_sidecar()
    if args.sidecar_primary_whitespace_free_grammar:
        return _run_primary_whitespace_free_sidecar()
    if args.sidecar_primary_operation_names_only:
        return _run_primary_operation_names_only_sidecar()
    if args.sidecar_primary_exclusive_first:
        return _run_primary_exclusive_first_sidecar()
    if args.sidecar_primary_stagger_ms is not None:
        if args.sidecar_primary_stagger_ms < 0.0:
            parser.error("--sidecar-primary-stagger-ms must be non-negative")
        return _run_primary_stagger_sidecar(args.sidecar_primary_stagger_ms)
    if args.sidecar_primary_max_tokens is not None:
        if (
            not 64 <= args.sidecar_primary_max_tokens <= 512
            or args.sidecar_primary_max_tokens == 160
        ):
            parser.error(
                "--sidecar-primary-max-tokens must be 64..512 except 160"
            )
        return _run_primary_max_tokens_sidecar(
            args.sidecar_primary_max_tokens
        )
    if args.sidecar_primary_stream:
        return _run_primary_stream_sidecar()
    if args.sidecar_server_reasoning_auto:
        return _run_server_reasoning_auto_sidecar()
    if args.sidecar_primary_reasoning_format_none:
        return _run_primary_reasoning_format_none_sidecar()
    if args.sidecar_primary_retry_reasoning_format_none:
        return _run_primary_retry_reasoning_format_none_sidecar()
    if args.sidecar_primary_reasoning_cutoff is not None:
        if args.sidecar_primary_reasoning_cutoff != 130:
            parser.error(
                "--sidecar-primary-reasoning-cutoff must equal 130"
            )
        return _run_primary_reasoning_cutoff_sidecar(
            args.sidecar_primary_reasoning_cutoff
        )
    if args.sidecar_primary_reasoning_early_abort:
        return _run_primary_reasoning_early_abort_sidecar()
    if args.sidecar_primary_speculative_retry:
        return _run_primary_speculative_retry_sidecar()
    if args.sidecar_primary_reasoning_control:
        return _run_primary_reasoning_control_sidecar()
    if args.sidecar_primary_without_redundant_fields:
        return _run_primary_without_redundant_fields_sidecar()
    if args.sidecar_primary_compact_prefill:
        return _run_primary_compact_prefill_sidecar()
    if args.sidecar_primary_direct_compact:
        return _run_primary_direct_compact_sidecar()
    output = args.output.resolve()
    fixes = (REPO / "artifacts" / "fixes").resolve()
    if output.parent != fixes or output.suffix.casefold() != ".json":
        parser.error("--output must be a JSON directly below artifacts/fixes")
    case_ids = frozenset(args.case_ids) if args.case_ids else None
    valid_ids = {
        item.case_id
        for item in build_workload()
        if item.request_type == "turn.decide"
    }
    if case_ids is not None and (not case_ids or not case_ids <= valid_ids):
        parser.error("--case must name only frozen turn ids")
    server = args.server.resolve() if args.server is not None else None
    if server is not None and not server.is_file():
        parser.error("--server must identify an existing executable")
    if (args.thinking_budget_p is None) != (args.thinking_budget_v is None):
        parser.error("both --thinking-budget-p and --thinking-budget-v are required")
    thinking_budgets = (
        (args.thinking_budget_p, args.thinking_budget_v)
        if args.thinking_budget_p is not None
        and args.thinking_budget_v is not None
        else None
    )
    if thinking_budgets is not None and (
        thinking_budgets[0] < 0 or thinking_budgets[1] < 0
    ):
        parser.error("thinking budgets must be non-negative")
    selected_profiles = sum(
        (
            thinking_budgets is not None,
            args.retry_without_speculative_v,
            args.retry_reuse_verified_guard_language,
            args.primary_whitespace_free_grammar,
            args.primary_operation_names_only,
            args.primary_exclusive_first,
            args.primary_stagger_ms is not None,
            args.primary_max_tokens is not None,
            args.primary_stream,
            args.server_reasoning_auto,
            args.primary_reasoning_format_none,
            args.primary_retry_reasoning_format_none,
            args.primary_reasoning_cutoff is not None,
            args.primary_reasoning_early_abort,
            args.primary_speculative_retry,
            args.primary_reasoning_control,
            args.primary_without_redundant_fields,
            args.primary_compact_prefill,
            args.primary_direct_compact,
        )
    )
    if selected_profiles > 1:
        parser.error("research profiles must be measured separately")
    if args.primary_stagger_ms is not None and args.primary_stagger_ms < 0.0:
        parser.error("--primary-stagger-ms must be non-negative")
    if (
        args.primary_max_tokens is not None
        and (
            not 64 <= args.primary_max_tokens <= 512
            or args.primary_max_tokens == 160
        )
    ):
        parser.error("--primary-max-tokens must be 64..512 except 160")
    if (
        args.primary_reasoning_cutoff is not None
        and args.primary_reasoning_cutoff != 130
    ):
        parser.error("--primary-reasoning-cutoff must equal 130")
    report = run(
        output,
        case_ids,
        server,
        thinking_budgets,
        args.retry_without_speculative_v,
        args.retry_reuse_verified_guard_language,
        args.primary_whitespace_free_grammar,
        args.primary_operation_names_only,
        args.primary_exclusive_first,
        args.primary_stagger_ms,
        args.primary_max_tokens,
        args.primary_stream,
        args.server_reasoning_auto,
        args.primary_reasoning_format_none,
        args.primary_retry_reasoning_format_none,
        args.primary_reasoning_cutoff,
        args.primary_reasoning_early_abort,
        args.primary_speculative_retry,
        args.primary_reasoning_control,
        args.primary_without_redundant_fields,
        args.primary_compact_prefill,
        args.primary_direct_compact,
    )
    print(
        json.dumps(
            {
                "output": str(output.relative_to(REPO)),
                "requests_completed": report["requests_completed"],
                "validation_errors": report["validation_errors"],
                "latency_seconds": report["latency_seconds"],
                "retry_cases": report["retry_cases"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["validation_errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
