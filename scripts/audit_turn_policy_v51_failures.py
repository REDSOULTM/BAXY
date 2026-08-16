"""Candidate-free audit of v5.1 public-validation errors.

The input is an existing text-free v5.1 development report. Only its false
recognized conversations and unrecognized public-validation actions are
selected. The audit then decodes exactly those public validation rows and asks
one independent, candidate-free question about explicit effect-request
semantics and cardinality. It never opens test/reserve data, never dispatches
an operation, and never serializes utterance or model-response text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import measure_turn_policy_v5_validation_cascade as cascade  # noqa: E402
import run_turn_policy_gate as gate  # noqa: E402
from baxy_mind.llm import LlmRuntime  # noqa: E402
from run_turn_evidence_encoder_gate import file_sha256  # noqa: E402


DEFAULT_INPUT = (
    REPO
    / "artifacts"
    / "validation"
    / "turn_policy_v51_cascade_development_48x2.json"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts"
    / "validation"
    / "turn_policy_v51_failure_candidate_free_audit.json"
)
EXPLICIT_EFFECT_PROMPT = (
    "Classify only the speech act and effect cardinality of the current "
    "utterance, without seeing candidate capabilities. "
    "explicit_effect_request is true only when the speaker explicitly asks "
    "the assistant to read, create, change, or control a current digital or "
    "external state or result. It is false for a mere statement, disclosure, "
    "hypothetical, social conversation, or stable general knowledge. A direct "
    "request for time-varying current external information counts as an "
    "effect request. Ignore whether the effect is supported and whether human "
    "arguments are complete. effect_count is zero when no effect is explicitly "
    "requested, one for one atomic effect, and multiple for two or more "
    "independent effects. Never infer a request from a merely possible future "
    "action and never invent context."
)
CONTRADICTION_PROMPT = (
    "Classify only the primary speech act of the current utterance without "
    "seeing candidate capabilities. speech_act is request_or_question for a "
    "direct request, command, or information question; assertion_only when "
    "the speaker merely states or discloses something without asking the "
    "assistant to do or answer anything; and other only when neither applies. "
    "explicit_effect_request is true only when the speaker explicitly asks to "
    "read, create, change, or control a current digital or external state or "
    "result. Ignore support and missing arguments. effect_count is zero when "
    "no effect is explicitly requested, one for one atomic effect, and "
    "multiple for two or more independent effects. Never infer a request from "
    "a possible future action and never invent context."
)


def _guard(runtime: LlmRuntime, text: str) -> dict[str, Any]:
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": EXPLICIT_EFFECT_PROMPT},
                {
                    "role": "user",
                    "content": f"Current utterance:\n{text}",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v51_candidate_free_effect_guard",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "explicit_effect_request": {"type": "boolean"},
                            "effect_count": {
                                "type": "string",
                                "enum": ["zero", "one", "multiple"],
                            },
                        },
                        "required": [
                            "explicit_effect_request",
                            "effect_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 48,
            "seed": 41,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.1 candidate-free explicit-effect guard",
    )


def _contradiction_guard(
    runtime: LlmRuntime,
    text: str,
) -> dict[str, Any]:
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": CONTRADICTION_PROMPT},
                {
                    "role": "user",
                    "content": f"Current utterance:\n{text}",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v51_candidate_free_contradiction_guard",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "speech_act": {
                                "type": "string",
                                "enum": [
                                    "request_or_question",
                                    "assertion_only",
                                    "other",
                                ],
                            },
                            "explicit_effect_request": {"type": "boolean"},
                            "effect_count": {
                                "type": "string",
                                "enum": ["zero", "one", "multiple"],
                            },
                        },
                        "required": [
                            "speech_act",
                            "explicit_effect_request",
                            "effect_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 64,
            "seed": 53,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.1 candidate-free contradiction guard",
    )


def audit(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    input_path = args.input.resolve(strict=True)
    holdout_path = args.holdout.resolve(strict=True)
    prior = json.loads(input_path.read_text(encoding="utf-8"))
    if (
        not isinstance(prior, dict)
        or prior.get("schema")
        != "baxy.turn-policy-v51-public-validation-cascade.v1"
        or prior.get("contains_text") is not False
        or prior.get("data_boundary", {}).get(
            "sealed_test_or_reserve_opened"
        )
        is not False
    ):
        raise ValueError("input is not a compatible text-free v5.1 report")
    prior_records = prior.get("records")
    if not isinstance(prior_records, list):
        raise ValueError("v5.1 input has no records")
    if args.scope == "errors":
        selected_prior = [
            record
            for record in prior_records
            if isinstance(record, dict)
            and (
                (
                    record.get("expected_mode") == "conversation"
                    and record.get("recognized_effect_intent") is True
                )
                or (
                    record.get("expected_mode") == "action"
                    and record.get("recognized_effect_intent") is False
                )
            )
        ]
    else:
        selected_prior = [
            record
            for record in prior_records
            if isinstance(record, dict)
            and record.get("recognized_effect_intent") is True
            and isinstance(record.get("verifier"), dict)
        ]
    selected_ids = {
        str(record["source_id"]) for record in selected_prior
    }
    if len(selected_ids) != len(selected_prior) or not selected_ids:
        raise ValueError("selected v5.1 failures have invalid identities")
    validation_rows = cascade.load_holdout_subset(
        holdout_path,
        split="validation",
    )
    rows_by_id = {
        str(row["source_id"]): row
        for row in validation_rows
        if str(row["source_id"]) in selected_ids
    }
    if set(rows_by_id) != selected_ids:
        raise ValueError("selected failures are not all public validation")

    manifest = gate.read_runtime_manifest(args.runtime_manifest)
    cascade._configure_llm(manifest)
    runtime = LlmRuntime()
    runtime.begin_request(args.startup_budget)
    try:
        runtime._ensure_started()
    finally:
        runtime.end_request()
    original_post = runtime._post
    raw_calls: list[dict[str, Any]] = []

    def traced_post(
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        call_started = time.perf_counter()
        try:
            result = original_post(payload, timeout)
        except Exception as error:
            raw_calls.append(
                {
                    "seconds": time.perf_counter() - call_started,
                    "error": type(error).__name__,
                }
            )
            raise
        raw_calls.append(
            {
                "seconds": time.perf_counter() - call_started,
                "error": None,
            }
        )
        return result

    runtime._post = traced_post
    records: list[dict[str, Any]] = []
    logical_calls = 0
    try:
        for prior_record in sorted(
            selected_prior,
            key=lambda record: str(record["source_id"]),
        ):
            source_id = str(prior_record["source_id"])
            text = str(rows_by_id[source_id]["text"])
            logical_calls += 1
            runtime.begin_request(args.request_budget)
            try:
                guard = (
                    _contradiction_guard(runtime, text)
                    if args.guard_mode == "contradiction"
                    else _guard(runtime, text)
                )
                exception = None
            except Exception as error:  # noqa: BLE001 - fail closed
                guard = None
                exception = type(error).__name__
            finally:
                runtime.end_request()
            if args.guard_mode == "contradiction":
                contradiction = (
                    isinstance(guard, dict)
                    and guard.get("speech_act") == "assertion_only"
                    and guard.get("explicit_effect_request") is False
                    and guard.get("effect_count") == "zero"
                )
                guard_pass = not contradiction
            else:
                guard_pass = (
                    isinstance(guard, dict)
                    and guard.get("explicit_effect_request") is True
                    and guard.get("effect_count") == "one"
                )
            records.append(
                {
                    "source_id": source_id,
                    "text_sha256": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                    "expected_mode": prior_record["expected_mode"],
                    "expected_families": prior_record[
                        "expected_families"
                    ],
                    "prior_triggered": prior_record["triggered"],
                    "prior_family": (
                        prior_record.get("family_selector") or {}
                    ).get("family"),
                    "prior_operation": prior_record.get(
                        "selector_operation"
                    ),
                    "prior_verifier": prior_record.get("verifier"),
                    "prior_recognized_effect_intent": prior_record[
                        "recognized_effect_intent"
                    ],
                    "candidate_free_guard": guard,
                    "guard_pass": guard_pass,
                    "exception": exception,
                }
            )
    finally:
        runtime.close()

    conversation_prior = [
        record
        for record in records
        if record["expected_mode"] == "conversation"
    ]
    action_prior = [
        record
        for record in records
        if record["expected_mode"] == "action"
    ]
    latencies = [float(call["seconds"]) for call in raw_calls]
    if args.scope == "errors":
        counterfactual = {
            "prior_false_recognized_conversations": len(
                conversation_prior
            ),
            "guard_vetoed_false_recognitions": sum(
                record["guard_pass"] is False
                for record in conversation_prior
            ),
            "false_recognitions_remaining_after_guard": sum(
                record["guard_pass"] is True
                for record in conversation_prior
            ),
            "prior_unrecognized_actions": len(action_prior),
            "unrecognized_actions_with_explicit_single_effect": sum(
                record["guard_pass"] is True for record in action_prior
            ),
            "unrecognized_actions_without_explicit_single_effect": sum(
                record["guard_pass"] is False for record in action_prior
            ),
        }
    else:
        counterfactual = {
            "prior_approved_pairs": len(records),
            "prior_approved_actions": len(action_prior),
            "prior_approved_conversations": len(conversation_prior),
            "approved_actions_retained_by_guard": sum(
                record["guard_pass"] is True for record in action_prior
            ),
            "approved_actions_vetoed_by_guard": sum(
                record["guard_pass"] is False for record in action_prior
            ),
            "approved_conversations_retained_by_guard": sum(
                record["guard_pass"] is True
                for record in conversation_prior
            ),
            "approved_conversations_vetoed_by_guard": sum(
                record["guard_pass"] is False
                for record in conversation_prior
            ),
        }
    counterfactual["guard_output_counts"] = dict(
        sorted(
            Counter(
                (
                    str(
                        (
                            record["candidate_free_guard"]
                            or {}
                        ).get("explicit_effect_request")
                    )
                    + "|"
                    + str(
                        (
                            record["candidate_free_guard"]
                            or {}
                        ).get("effect_count")
                    )
                )
                for record in records
            ).items()
        )
    )
    return {
        "schema": "baxy.turn-policy-v51-candidate-free-error-audit.v1",
        "status": "focused_public_validation_development_audit",
        "contains_text": False,
        "authority": "veto_only_no_operation_dispatch",
        "data_boundary": {
            "used_split": "public_validation",
            "selection_scope": args.scope,
            "guard_mode": args.guard_mode,
            "selected_only_from_prior_report": True,
            "selected_rows": len(records),
            "sealed_test_or_reserve_opened": False,
            "v4_case_text_labels_or_outputs_opened": False,
        },
        "inputs": {
            "prior_report_sha256": file_sha256(input_path),
            "holdout_sha256": file_sha256(holdout_path),
        },
        "counterfactual": counterfactual,
        "llm": {
            "logical_calls": logical_calls,
            "raw_schema_calls": len(raw_calls),
            "schema_recovery_calls": max(
                0,
                len(raw_calls) - logical_calls,
            ),
            "raw_call_errors": sum(
                call["error"] is not None for call in raw_calls
            ),
            "raw_latency_seconds": {
                "mean": round(
                    statistics.fmean(latencies) if latencies else 0.0,
                    4,
                ),
                "p95": round(
                    cascade._percentile(latencies, 0.95),
                    4,
                ),
                "max": round(max(latencies, default=0.0), 4),
            },
        },
        "timing_seconds": round(time.perf_counter() - started, 4),
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--holdout", type=Path, default=cascade.HOLDOUT)
    parser.add_argument(
        "--scope",
        choices=("errors", "approved"),
        default="errors",
    )
    parser.add_argument(
        "--guard-mode",
        choices=("explicit", "contradiction"),
        default="explicit",
    )
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=gate.DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--request-budget", type=float, default=10.0)
    parser.add_argument("--startup-budget", type=float, default=240.0)
    args = parser.parse_args()
    if not 2.0 <= args.request_budget <= 55.0:
        parser.error("--request-budget must be in [2, 55]")
    return args


def main() -> int:
    args = parse_args()
    report = audit(args)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    gate.write_json_atomic(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "counterfactual": report["counterfactual"],
                "llm": report["llm"],
                "output": gate.repo_relative(output),
                "sha256": file_sha256(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
