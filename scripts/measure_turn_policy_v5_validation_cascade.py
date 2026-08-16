"""Measure a fail-closed v5 turn cascade on public validation data only.

This is a development diagnostic, not a release gate. It trains two linear
students from the public train split, calibrates a high-coverage conformal
action trigger on one deterministic half of public validation, and evaluates
the complete read-only cascade on the other half:

    mode set -> family top-5 -> constrained selector -> pair verifier

The selector and verifier never dispatch an operation. Output records contain
source identities, hashes, labels, operation names, and decisions, but no
utterance text or model response text. The sealed test/reserve is never
decoded or selected by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_turn_policy_gate as gate  # noqa: E402
from baxy_mind.planner import PlannerCatalog, PlannerTool  # noqa: E402
from baxy_mind.router import IntentRouter  # noqa: E402
from baxy_mind.turn_evidence import TurnEvidenceIndex  # noqa: E402
from run_turn_evidence_encoder_gate import (  # noqa: E402
    file_sha256,
    macro_f1,
    wilson_interval,
)
from run_turn_linear_probe_gate import (  # noqa: E402
    configured_cache,
    embed_rows,
    load_holdout_subset,
)


RUNTIME = REPO / "tests" / "data" / "turn_evidence_runtime.v1.jsonl"
HOLDOUT = REPO / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl"
OUTPUT = (
    REPO
    / "artifacts"
    / "validation"
    / "turn_policy_v5_cascade_development.json"
)
CACHE = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "BAXYRuntime"
    / "turn-evidence"
)
SEED = "baxy-turn-policy-v5-public-validation-cascade-v1"
ALPHA = 0.05
SELECTOR_PROMPT = (
    "Select exactly one candidate operation only when its described effect is "
    "the unique operation that semantically matches the user's single digital "
    "or external effect request. Return __none__ for conversation, stable "
    "general knowledge, an unsupported effect, multiple independent effects, "
    "or ambiguity between operations. Reading current, local, or digital "
    "state counts as an effect. A missing human-supplied argument does not by "
    "itself force __none__ when the intended operation is otherwise exact. "
    "Never invent context, arguments, or operations."
)
VERIFIER_PROMPT = (
    "Independently verify only the current request and the one proposed "
    "operation. Do not select, compare, or suggest another operation. "
    "semantic_match is true only when the exact described operation is the "
    "kind of effect the user explicitly requests; missing arguments do not "
    "change semantic_match. required_information_complete is true only when "
    "all human-supplied targets and values required to perform that operation "
    "are present or unambiguously available in the request. effect_count is "
    "zero for conversation or stable general knowledge, one for one atomic "
    "digital/external effect, and multiple for two or more independent "
    "effects. An operation used merely to gather material for a stable "
    "knowledge answer is not a semantic match. Never invent context."
)
V51_FAMILY_SELECTOR_PROMPT = (
    "Choose exactly one candidate family only when that family contains the "
    "kind of operation that semantically matches the user's single digital or "
    "external effect request. Return __none__ for conversation, stable general "
    "knowledge, an unsupported effect, multiple independent effects, or "
    "ambiguity between families. Reading current, local, or digital state "
    "counts as an effect. Missing human-supplied arguments do not change the "
    "requested operation family; argument grounding happens later. Never "
    "invent context, effects, or capabilities."
)
V51_OPERATION_SELECTOR_PROMPT = (
    "Within the already selected family, choose exactly one candidate "
    "operation only when its described effect is the unique semantic match "
    "for the user's requested effect. Return __none__ for conversation, stable "
    "general knowledge, an unsupported or adjacent effect, multiple "
    "independent effects, or ambiguity between operations. Ignore whether "
    "arguments are complete because an independent schema grounder handles "
    "that later. Never invent context, effects, arguments, or operations."
)
V51_NLI_VERIFIER_PROMPT = (
    "Independently judge only the current request and the one proposed "
    "operation. Do not select, compare, or suggest another operation. "
    "entailed_by_request is true only when the user explicitly requests the "
    "kind of effect described by this operation. covers_entire_effect is true "
    "only when this operation covers the whole requested atomic effect rather "
    "than an adjacent, preparatory, or partial effect. Judge semantic effect "
    "coverage, not whether arguments or targets are complete; schema grounding "
    "is a later independent stage. effect_count is zero for conversation or "
    "stable general knowledge, one for one atomic digital/external effect, and "
    "multiple for two or more independent effects. Never invent context."
)


def _rank(seed: str, source_id: str) -> bytes:
    return hashlib.sha256((seed + "\0" + source_id).encode("utf-8")).digest()


def _split_validation(
    rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        families = row.get("families") or []
        family = str(families[0]) if families else "-"
        grouped[(str(row["mode"]), family)].append(row)
    calibration: list[dict[str, Any]] = []
    evaluation: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        ranked = sorted(
            values,
            key=lambda row: (
                _rank(SEED + "\0calibration", str(row["source_id"])),
                str(row["source_id"]),
            ),
        )
        cut = max(1, len(ranked) // 2)
        calibration.extend(ranked[:cut])
        evaluation.extend(ranked[cut:])
    return calibration, evaluation


def _stratified_sample(
    rows: Sequence[dict[str, Any]],
    per_mode: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for mode in ("action", "conversation"):
        eligible = [row for row in rows if row["mode"] == mode]
        if mode == "conversation":
            selected.extend(
                sorted(
                    eligible,
                    key=lambda row: (
                        _rank(SEED + "\0sample", str(row["source_id"])),
                        str(row["source_id"]),
                    ),
                )[:per_mode]
            )
            continue
        by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in eligible:
            by_family[str(row["families"][0])].append(row)
        families = sorted(by_family)
        base = per_mode // len(families)
        remainder = per_mode % len(families)
        for index, family in enumerate(families):
            quota = base + int(index < remainder)
            ranked = sorted(
                by_family[family],
                key=lambda row: (
                    _rank(
                        SEED + "\0sample\0" + family,
                        str(row["source_id"]),
                    ),
                    str(row["source_id"]),
                ),
            )
            selected.extend(ranked[:quota])
        if sum(row["mode"] == "action" for row in selected) < per_mode:
            chosen = {str(row["source_id"]) for row in selected}
            remaining = sorted(
                (
                    row
                    for row in eligible
                    if str(row["source_id"]) not in chosen
                ),
                key=lambda row: (
                    _rank(SEED + "\0sample-fill", str(row["source_id"])),
                    str(row["source_id"]),
                ),
            )
            needed = per_mode - sum(
                row["mode"] == "action" for row in selected
            )
            selected.extend(remaining[:needed])
    return sorted(
        selected,
        key=lambda row: (
            _rank(SEED + "\0sample-order", str(row["source_id"])),
            str(row["source_id"]),
        ),
    )


def _conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    if not scores:
        raise ValueError("calibration scores are empty")
    ordered = sorted(float(value) for value in scores)
    rank = math.ceil((len(ordered) + 1) * (1.0 - alpha))
    return ordered[min(rank, len(ordered)) - 1]


def _one_sided_interval(
    successes: int,
    trials: int,
    alpha: float = ALPHA,
) -> dict[str, float | int]:
    if trials <= 0:
        return {
            "successes": successes,
            "trials": trials,
            "lower": 0.0,
            "upper": 1.0,
        }
    try:
        from scipy.stats import beta

        lower = (
            0.0
            if successes == 0
            else float(beta.ppf(alpha, successes, trials - successes + 1))
        )
        upper = (
            1.0
            if successes == trials
            else float(
                beta.ppf(
                    1.0 - alpha,
                    successes + 1,
                    trials - successes,
                )
            )
        )
    except ImportError:
        lower, upper = wilson_interval(successes, trials)
    return {
        "successes": successes,
        "trials": trials,
        "lower": round(lower, 6),
        "upper": round(upper, 6),
    }


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    return float(np.quantile(np.asarray(values, dtype=np.float64), quantile))


def _tool_catalog(capabilities: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": str(item["name"]).replace(".", "_"),
                "canonical_name": str(item["name"]),
                "description": str(item["description"]),
                "parameters": item["argumentsSchema"],
                "risk": str(item["risk"]),
            },
        }
        for item in capabilities
    ]


def _configure_llm(manifest: dict[str, Any]) -> None:
    os.environ["BAXY_MIND_LLM_GGUF"] = str(manifest["gguf"])
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(manifest["llama_server"])
    os.environ["BAXY_MIND_NGL"] = str(manifest.get("ngl") or 99)
    os.environ["BAXY_MIND_CTX"] = "4096"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "55"
    # Certificación con el default productivo del retraso E5; el estrés
    # delay=0 se solicita explícitamente cuando el escenario lo requiere.
    os.environ.pop("BAXY_MIND_ROUTER_START_DELAY", None)
    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)


def _selector(
    runtime: Any,
    text: str,
    catalog: PlannerCatalog,
    shortlist: Sequence[PlannerTool],
) -> dict[str, Any]:
    names = [tool.name for tool in shortlist]
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": SELECTOR_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        "Candidate operations:\n"
                        + catalog.compact_prompt(shortlist)
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v5_operation_selector",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["__none__", *names],
                            }
                        },
                        "required": ["operation"],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 48,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5 constrained selector",
    )


def _verifier(runtime: Any, text: str, tool: PlannerTool) -> dict[str, Any]:
    required = ", ".join(tool.required) or "none"
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": VERIFIER_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        f"Proposed operation:\n{tool.name}\n\n"
                        f"Description:\n{tool.description}\n\n"
                        f"Required human-supplied fields:\n{required}\n\n"
                        "Operation schema:\n"
                        + json.dumps(
                            tool.schema,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v5_independent_pair_verifier",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "semantic_match": {"type": "boolean"},
                            "required_information_complete": {
                                "type": "boolean"
                            },
                            "effect_count": {
                                "type": "string",
                                "enum": ["zero", "one", "multiple"],
                            },
                        },
                        "required": [
                            "semantic_match",
                            "required_information_complete",
                            "effect_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 72,
            "seed": 17,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5 independent pair verifier",
    )


def _v51_family_selector(
    runtime: Any,
    text: str,
    families: Sequence[str],
    shortlist: Sequence[PlannerTool],
) -> dict[str, Any]:
    grouped: dict[str, list[PlannerTool]] = {
        family: [] for family in families
    }
    for tool in shortlist:
        if tool.family in grouped:
            grouped[tool.family].append(tool)
    available = [family for family in families if grouped[family]]
    if not available:
        raise ValueError("v5.1 family selector has no catalog candidates")
    family_lines: list[str] = []
    for family in available:
        operation_text = "; ".join(
            f"{tool.name}: {tool.description}"
            for tool in grouped[family]
        )
        family_lines.append(f"{family} | {operation_text}")
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": V51_FAMILY_SELECTOR_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        "Candidate families:\n"
                        + "\n".join(family_lines)
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v51_family_selector",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "family": {
                                "type": "string",
                                "enum": ["__none__", *available],
                            }
                        },
                        "required": ["family"],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 40,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.1 constrained family selector",
    )


def _v51_operation_selector(
    runtime: Any,
    text: str,
    catalog: PlannerCatalog,
    family: str,
    shortlist: Sequence[PlannerTool],
) -> dict[str, Any]:
    coherent = tuple(tool for tool in shortlist if tool.family == family)
    if not coherent:
        raise ValueError("v5.1 operation selector has no coherent candidates")
    names = [tool.name for tool in coherent]
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": V51_OPERATION_SELECTOR_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        f"Selected family:\n{family}\n\n"
                        "Candidate operations:\n"
                        + catalog.compact_prompt(coherent)
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v51_coherent_operation_selector",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["__none__", *names],
                            }
                        },
                        "required": ["operation"],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 48,
            "seed": 11,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.1 coherent operation selector",
    )


def _v51_nli_verifier(
    runtime: Any,
    text: str,
    tool: PlannerTool,
) -> dict[str, Any]:
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": V51_NLI_VERIFIER_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        f"Proposed operation:\n{tool.name}\n\n"
                        f"Operation effect description:\n{tool.description}"
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v51_independent_nli_verifier",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "entailed_by_request": {"type": "boolean"},
                            "covers_entire_effect": {"type": "boolean"},
                            "effect_count": {
                                "type": "string",
                                "enum": ["zero", "one", "multiple"],
                            },
                        },
                        "required": [
                            "entailed_by_request",
                            "covers_entire_effect",
                            "effect_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 72,
            "seed": 29,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.1 independent NLI verifier",
    )


def _fit_students(
    router: IntentRouter,
    runtime_path: Path,
) -> tuple[Any, Any, tuple[str, ...], np.ndarray, np.ndarray]:
    from sklearn.linear_model import LogisticRegression

    with configured_cache(CACHE.resolve(strict=True)):
        index = TurnEvidenceIndex.from_corpus(runtime_path, router.encode)
    vectors = np.asarray(index._vectors, dtype=np.float32)  # type: ignore[attr-defined]
    records = index._records  # type: ignore[attr-defined]
    train_indices = [
        index_value
        for index_value, record in enumerate(records)
        if record.split == "train"
    ]
    if not train_indices:
        raise ValueError("public train vectors are missing")
    train_vectors = vectors[train_indices]
    train_modes = [records[index].mode for index in train_indices]
    mode_model = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=1_000,
        random_state=0,
    )
    mode_model.fit(train_vectors, train_modes)
    action_indices = [
        index
        for index in train_indices
        if records[index].mode == "action" and len(records[index].families) == 1
    ]
    family_vectors = vectors[action_indices]
    family_labels = [records[index].families[0] for index in action_indices]
    family_model = LogisticRegression(
        C=4.0,
        class_weight=None,
        solver="lbfgs",
        max_iter=1_000,
        random_state=0,
    )
    family_model.fit(family_vectors, family_labels)
    return (
        mode_model,
        family_model,
        tuple(str(value) for value in family_model.classes_),
        train_vectors,
        family_vectors,
    )


def _top_families(
    family_model: Any,
    classes: Sequence[str],
    vector: np.ndarray,
    limit: int = 5,
) -> tuple[str, ...]:
    probabilities = family_model.predict_proba(vector.reshape(1, -1))[0]
    order = sorted(
        range(len(classes)),
        key=lambda index: (float(probabilities[index]), classes[index]),
        reverse=True,
    )
    return tuple(classes[index] for index in order[:limit])


def _metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    expected = [str(record["expected_mode"]) for record in records]
    predicted = [str(record["final_mode"]) for record in records]
    action_total = sum(label == "action" for label in expected)
    conversation_total = sum(label == "conversation" for label in expected)
    true_actions = sum(
        wanted == "action" and actual == "action"
        for wanted, actual in zip(expected, predicted, strict=True)
    )
    predicted_actions = sum(label == "action" for label in predicted)
    false_actions = sum(
        wanted == "conversation" and actual == "action"
        for wanted, actual in zip(expected, predicted, strict=True)
    )
    conversation_correct = sum(
        wanted == "conversation" and actual == "conversation"
        for wanted, actual in zip(expected, predicted, strict=True)
    )
    family_trials = sum(
        record["expected_mode"] == "action"
        and record["final_mode"] == "action"
        for record in records
    )
    family_successes = sum(
        record["expected_mode"] == "action"
        and record["final_mode"] == "action"
        and record["final_family_correct"] is True
        for record in records
    )
    latencies = [float(record["latency_seconds"]) for record in records]
    return {
        "rows": len(records),
        "accuracy": round(
            sum(wanted == actual for wanted, actual in zip(expected, predicted))
            / len(records),
            6,
        ),
        "macro_f1": round(macro_f1(expected, predicted), 6),
        "action_recall": round(
            true_actions / action_total if action_total else 0.0,
            6,
        ),
        "action_recall_one_sided_95": _one_sided_interval(
            true_actions,
            action_total,
        ),
        "action_precision": round(
            true_actions / predicted_actions if predicted_actions else 0.0,
            6,
        ),
        "action_precision_one_sided_95": _one_sided_interval(
            true_actions,
            predicted_actions,
        ),
        "conversation_recall": round(
            conversation_correct / conversation_total
            if conversation_total
            else 0.0,
            6,
        ),
        "conversation_recall_one_sided_95": _one_sided_interval(
            conversation_correct,
            conversation_total,
        ),
        "false_action_on_conversation": round(
            false_actions / conversation_total if conversation_total else 0.0,
            6,
        ),
        "false_action_one_sided_95": _one_sided_interval(
            false_actions,
            conversation_total,
        ),
        "final_family_accuracy": round(
            family_successes / family_trials if family_trials else 0.0,
            6,
        ),
        "final_family_accuracy_one_sided_95": _one_sided_interval(
            family_successes,
            family_trials,
        ),
        "final_mode_counts": dict(sorted(Counter(predicted).items())),
        "exceptions": sum(record["exception"] is not None for record in records),
        "latency_seconds": {
            "mean": round(statistics.fmean(latencies), 4),
            "p50": round(_percentile(latencies, 0.50), 4),
            "p95": round(_percentile(latencies, 0.95), 4),
            "p99": round(_percentile(latencies, 0.99), 4),
            "max": round(max(latencies), 4),
        },
    }


def _v51_metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    expected = [str(record["expected_mode"]) for record in records]
    predicted = [
        "action"
        if record["recognized_effect_intent"] is True
        else "conversation"
        for record in records
    ]
    action_total = sum(label == "action" for label in expected)
    conversation_total = sum(label == "conversation" for label in expected)
    recognized_actions = sum(
        wanted == "action" and actual == "action"
        for wanted, actual in zip(expected, predicted, strict=True)
    )
    recognized_total = sum(label == "action" for label in predicted)
    false_recognitions = sum(
        wanted == "conversation" and actual == "action"
        for wanted, actual in zip(expected, predicted, strict=True)
    )
    conversation_correct = conversation_total - false_recognitions
    family_trials = sum(
        record["expected_mode"] == "action"
        and record["recognized_effect_intent"] is True
        for record in records
    )
    family_successes = sum(
        record["expected_mode"] == "action"
        and record["recognized_effect_intent"] is True
        and record["final_family_correct"] is True
        for record in records
    )
    latencies = [float(record["latency_seconds"]) for record in records]
    return {
        "rows": len(records),
        "recognized_mode_accuracy": round(
            sum(
                wanted == actual
                for wanted, actual in zip(expected, predicted, strict=True)
            )
            / len(records),
            6,
        ),
        "recognized_mode_macro_f1": round(
            macro_f1(expected, predicted),
            6,
        ),
        "action_or_clarify_intent_recall": round(
            recognized_actions / action_total if action_total else 0.0,
            6,
        ),
        "action_or_clarify_intent_recall_one_sided_95": (
            _one_sided_interval(recognized_actions, action_total)
        ),
        "recognized_intent_precision": round(
            recognized_actions / recognized_total if recognized_total else 0.0,
            6,
        ),
        "recognized_intent_precision_one_sided_95": (
            _one_sided_interval(recognized_actions, recognized_total)
        ),
        "conversation_safe_abstention": round(
            conversation_correct / conversation_total
            if conversation_total
            else 0.0,
            6,
        ),
        "conversation_safe_abstention_one_sided_95": (
            _one_sided_interval(conversation_correct, conversation_total)
        ),
        "false_recognized_effect_on_conversation": round(
            false_recognitions / conversation_total
            if conversation_total
            else 0.0,
            6,
        ),
        "false_recognized_effect_one_sided_95": (
            _one_sided_interval(false_recognitions, conversation_total)
        ),
        "recognized_family_accuracy": round(
            family_successes / family_trials if family_trials else 0.0,
            6,
        ),
        "recognized_family_accuracy_one_sided_95": (
            _one_sided_interval(family_successes, family_trials)
        ),
        "recognized_outcome_counts": dict(
            sorted(Counter(predicted).items())
        ),
        "grounding_status": (
            "deferred_to_independent_schema_grounder_not_measured"
        ),
        "direct_action_authority_emitted": 0,
        "exceptions": sum(
            record["exception"] is not None for record in records
        ),
        "latency_seconds": {
            "mean": round(statistics.fmean(latencies), 4),
            "p50": round(_percentile(latencies, 0.50), 4),
            "p95": round(_percentile(latencies, 0.95), 4),
            "p99": round(_percentile(latencies, 0.99), 4),
            "max": round(max(latencies), 4),
        },
    }


def measure(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    runtime_path = args.runtime.resolve(strict=True)
    holdout_path = args.holdout.resolve(strict=True)
    validation_rows = load_holdout_subset(
        holdout_path,
        split="validation",
    )
    if any(row["mode"] not in {"action", "conversation"} for row in validation_rows):
        raise ValueError("public validation contains unexpected modes")
    calibration_rows, evaluation_rows = _split_validation(validation_rows)

    router = IntentRouter(device="cpu")
    (
        mode_model,
        family_model,
        family_classes,
        train_vectors,
        family_vectors,
    ) = _fit_students(router, runtime_path)
    validation_vectors, validation_encode_seconds = embed_rows(
        router,
        validation_rows,
    )
    vector_by_id = {
        str(row["source_id"]): validation_vectors[index]
        for index, row in enumerate(validation_rows)
    }
    action_index = list(mode_model.classes_).index("action")
    calibration_probabilities = mode_model.predict_proba(
        np.asarray(
            [vector_by_id[str(row["source_id"])] for row in calibration_rows],
            dtype=np.float32,
        )
    )
    mode_quantiles: dict[str, float] = {}
    for label in ("action", "conversation"):
        label_index = list(mode_model.classes_).index(label)
        scores = [
            1.0 - float(calibration_probabilities[index, label_index])
            for index, row in enumerate(calibration_rows)
            if row["mode"] == label
        ]
        mode_quantiles[label] = _conformal_quantile(scores, ALPHA)

    evaluation_matrix = np.asarray(
        [vector_by_id[str(row["source_id"])] for row in evaluation_rows],
        dtype=np.float32,
    )
    evaluation_probabilities = mode_model.predict_proba(evaluation_matrix)
    trigger_diagnostics: list[dict[str, Any]] = []
    family_hits = 0
    family_trials = 0
    for index, row in enumerate(evaluation_rows):
        probability = evaluation_probabilities[index]
        mode_set = tuple(
            label
            for label in ("action", "conversation")
            if 1.0
            - float(probability[list(mode_model.classes_).index(label)])
            <= mode_quantiles[label]
        )
        top5 = _top_families(
            family_model,
            family_classes,
            evaluation_matrix[index],
        )
        expected_family = (
            str(row["families"][0]) if row["mode"] == "action" else None
        )
        if expected_family is not None:
            family_trials += 1
            family_hits += expected_family in top5
        trigger_diagnostics.append(
            {
                "source_id": str(row["source_id"]),
                "mode": str(row["mode"]),
                "action_probability": float(probability[action_index]),
                "mode_set": mode_set,
                "top5": top5,
            }
        )

    by_id = {
        str(row["source_id"]): row
        for row in trigger_diagnostics
    }
    sampled_rows = _stratified_sample(evaluation_rows, args.per_mode)
    manifest = gate.read_runtime_manifest(args.runtime_manifest)
    _configure_llm(manifest)
    capabilities = gate.core_capabilities(args.core)
    catalog = PlannerCatalog(_tool_catalog(capabilities), encoder=router.encode)
    from baxy_mind.llm import LlmRuntime

    llm = LlmRuntime()
    llm.begin_request(args.startup_budget)
    try:
        llm._ensure_started()
    finally:
        llm.end_request()
    original_post = llm._post
    raw_calls: list[dict[str, Any]] = []

    def traced_post(
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        call_started = time.perf_counter()
        try:
            response = original_post(payload, timeout)
        except Exception as error:
            raw_calls.append(
                {
                    "latency_seconds": time.perf_counter() - call_started,
                    "error_type": type(error).__name__,
                }
            )
            raise
        raw_calls.append(
            {
                "latency_seconds": time.perf_counter() - call_started,
                "error_type": None,
            }
        )
        return response

    llm._post = traced_post
    records: list[dict[str, Any]] = []
    logical_calls = 0
    try:
        for row in sampled_rows:
            case_started = time.perf_counter()
            source_id = str(row["source_id"])
            text = str(row["text"])
            diagnostic = by_id[source_id]
            mode_set = tuple(diagnostic["mode_set"])
            top5 = tuple(diagnostic["top5"])
            selector_result: dict[str, Any] | None = None
            family_selector_result: dict[str, Any] | None = None
            operation_selector_result: dict[str, Any] | None = None
            verifier_result: dict[str, Any] | None = None
            selected_family: str | None = None
            selected_operation: str | None = None
            shortlist: tuple[PlannerTool, ...] = ()
            coherent_shortlist: tuple[PlannerTool, ...] = ()
            final_mode = "conversation"
            recognized_effect_intent = False
            exception: str | None = None
            llm.begin_request(args.request_budget)
            try:
                if "action" in mode_set:
                    shortlist = tuple(
                        catalog.shortlist(
                            text,
                            preferred_families=top5,
                            restrict_to_preferred=True,
                        )[: args.max_operations]
                    )
                    if shortlist:
                        if args.protocol == "v5.1":
                            logical_calls += 1
                            family_selector_result = _v51_family_selector(
                                llm,
                                text,
                                top5,
                                shortlist,
                            )
                            family_selection = family_selector_result.get(
                                "family"
                            )
                            allowed_families = {
                                tool.family for tool in shortlist
                            }
                            if family_selection in allowed_families:
                                selected_family = str(family_selection)
                                coherent_shortlist = tuple(
                                    tool
                                    for tool in shortlist
                                    if tool.family == selected_family
                                )
                                logical_calls += 1
                                operation_selector_result = (
                                    _v51_operation_selector(
                                        llm,
                                        text,
                                        catalog,
                                        selected_family,
                                        coherent_shortlist,
                                    )
                                )
                                selector_result = operation_selector_result
                                raw_selection = (
                                    operation_selector_result.get("operation")
                                )
                                allowed_operations = {
                                    tool.name for tool in coherent_shortlist
                                }
                                if raw_selection in allowed_operations:
                                    selected_operation = str(raw_selection)
                                    selected_tool = catalog.get(
                                        selected_operation
                                    )
                                    if (
                                        selected_tool is None
                                        or selected_tool.family
                                        != selected_family
                                    ):
                                        raise ValueError(
                                            "v5.1 selector broke family "
                                            "coherence"
                                        )
                                    logical_calls += 1
                                    verifier_result = _v51_nli_verifier(
                                        llm,
                                        text,
                                        selected_tool,
                                    )
                                    recognized_effect_intent = (
                                        verifier_result.get(
                                            "entailed_by_request"
                                        )
                                        is True
                                        and verifier_result.get(
                                            "covers_entire_effect"
                                        )
                                        is True
                                        and verifier_result.get(
                                            "effect_count"
                                        )
                                        == "one"
                                    )
                                    if recognized_effect_intent:
                                        final_mode = "action_or_clarify"
                        else:
                            logical_calls += 1
                            selector_result = _selector(
                                llm,
                                text,
                                catalog,
                                shortlist,
                            )
                            raw_selection = selector_result.get("operation")
                            allowed = {tool.name for tool in shortlist}
                            if raw_selection in allowed:
                                selected_operation = str(raw_selection)
                                selected_tool = catalog.get(selected_operation)
                                if selected_tool is None:
                                    raise ValueError("selector left the catalog")
                                selected_family = selected_tool.family
                                coherent_shortlist = (selected_tool,)
                                logical_calls += 1
                                verifier_result = _verifier(
                                    llm,
                                    text,
                                    selected_tool,
                                )
                                semantic_match = (
                                    verifier_result.get("semantic_match") is True
                                )
                                complete = (
                                    verifier_result.get(
                                        "required_information_complete"
                                    )
                                    is True
                                )
                                effect_count = verifier_result.get(
                                    "effect_count"
                                )
                                if semantic_match and effect_count == "one":
                                    recognized_effect_intent = True
                                    final_mode = (
                                        "action" if complete else "clarify"
                                    )
            except Exception as error:  # noqa: BLE001 - fail-closed diagnostic
                exception = type(error).__name__
                final_mode = "conversation"
                recognized_effect_intent = False
            finally:
                llm.end_request()
            expected_families = tuple(str(value) for value in row["families"])
            if selected_operation and selected_family is None:
                selected_family = selected_operation.split(".", 1)[0]
            records.append(
                {
                    "source_id": source_id,
                    "text_sha256": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                    "expected_mode": str(row["mode"]),
                    "expected_families": expected_families,
                    "action_probability": round(
                        float(diagnostic["action_probability"]),
                        8,
                    ),
                    "mode_set": mode_set,
                    "triggered": "action" in mode_set,
                    "top5_families": top5,
                    "candidate_operations": tuple(
                        tool.name for tool in shortlist
                    ),
                    "candidate_family_hit": (
                        bool(
                            set(expected_families)
                            & {tool.family for tool in shortlist}
                        )
                        if expected_families
                        else None
                    ),
                    "selector_operation": selected_operation,
                    "selector_none": (
                        (
                            family_selector_result is not None
                            and family_selector_result.get("family")
                            == "__none__"
                        )
                        or (
                            selector_result is not None
                            and selector_result.get("operation") == "__none__"
                        )
                    ),
                    "family_selector": family_selector_result,
                    "operation_selector": operation_selector_result,
                    "coherent_candidate_operations": tuple(
                        tool.name for tool in coherent_shortlist
                    ),
                    "verifier": verifier_result,
                    "final_mode": final_mode,
                    "recognized_effect_intent": recognized_effect_intent,
                    "final_family": selected_family,
                    "final_family_correct": (
                        selected_family in expected_families
                        if expected_families and selected_family is not None
                        else None
                    ),
                    "exception": exception,
                    "latency_seconds": round(
                        time.perf_counter() - case_started,
                        4,
                    ),
                }
            )
    finally:
        llm.close()

    evaluation_action_total = sum(
        row["mode"] == "action" for row in trigger_diagnostics
    )
    evaluation_conversation_total = sum(
        row["mode"] == "conversation" for row in trigger_diagnostics
    )
    action_triggered = sum(
        row["mode"] == "action" and "action" in row["mode_set"]
        for row in trigger_diagnostics
    )
    conversation_triggered = sum(
        row["mode"] == "conversation" and "action" in row["mode_set"]
        for row in trigger_diagnostics
    )
    sample_metrics = (
        _v51_metrics(records)
        if args.protocol == "v5.1"
        else _metrics(records)
    )
    stagewise: dict[str, dict[str, int]] = {}
    for expected_mode in ("action", "conversation"):
        selected = [
            record
            for record in records
            if record["expected_mode"] == expected_mode
        ]
        stagewise[expected_mode] = {
            "rows": len(selected),
            "triggered": sum(
                record["triggered"] is True for record in selected
            ),
            "candidate_family_hit": sum(
                record["candidate_family_hit"] is True
                for record in selected
            ),
            "family_selected": sum(
                isinstance(record["family_selector"], dict)
                and record["family_selector"].get("family") != "__none__"
                for record in selected
            ),
            "expected_family_selected": sum(
                bool(record["expected_families"])
                and isinstance(record["family_selector"], dict)
                and record["family_selector"].get("family")
                in set(record["expected_families"])
                for record in selected
            ),
            "operation_selected": sum(
                record["selector_operation"] is not None
                for record in selected
            ),
            "verifier_called": sum(
                record["verifier"] is not None for record in selected
            ),
            "intent_recognized": sum(
                record["recognized_effect_intent"] is True
                for record in selected
            ),
            "recognized_expected_family": sum(
                record["recognized_effect_intent"] is True
                and record["final_family_correct"] is True
                for record in selected
            ),
        }
    return {
        "schema": (
            "baxy.turn-policy-v51-public-validation-cascade.v1"
            if args.protocol == "v5.1"
            else "baxy.turn-policy-v5-public-validation-cascade.v1"
        ),
        "status": "development_only_not_a_release_gate",
        "contains_text": False,
        "authority": (
            "intent_recognition_only_grounding_deferred_no_operation_dispatch"
            if args.protocol == "v5.1"
            else "read_only_no_operation_dispatch"
        ),
        "data_boundary": {
            "used_splits": ["public_train", "public_validation"],
            "validation_calibration_rows": len(calibration_rows),
            "validation_evaluation_rows": len(evaluation_rows),
            "sealed_test_or_reserve_opened": False,
            "v4_case_text_labels_or_outputs_opened": False,
        },
        "inputs": {
            "runtime_sha256": file_sha256(runtime_path),
            "holdout_sha256": file_sha256(holdout_path),
            "seed": SEED,
            "alpha": ALPHA,
            "protocol": args.protocol,
            "mode_model": "balanced_logreg_C1_lbfgs_train_only",
            "family_model": "logreg_C4_lbfgs_train_action_only",
            "family_limit": 5,
            "operation_limit": args.max_operations,
            "train_vectors_shape": list(train_vectors.shape),
            "family_vectors_shape": list(family_vectors.shape),
            "family_classes": list(family_classes),
        },
        "calibration": {
            "mode_nonconformity": "1-p_true",
            "finite_sample_rule": "ceil((n+1)*(1-alpha)), higher",
            "class_quantiles": {
                key: round(value, 8)
                for key, value in sorted(mode_quantiles.items())
            },
        },
        "evaluation_pool": {
            "rows": len(evaluation_rows),
            "action_trigger_recall": round(
                action_triggered / evaluation_action_total,
                6,
            ),
            "action_trigger_recall_one_sided_95": _one_sided_interval(
                action_triggered,
                evaluation_action_total,
            ),
            "conversation_trigger_rate": round(
                conversation_triggered / evaluation_conversation_total,
                6,
            ),
            "conversation_trigger_rate_one_sided_95": _one_sided_interval(
                conversation_triggered,
                evaluation_conversation_total,
            ),
            "family_top5_recall": round(
                family_hits / family_trials,
                6,
            ),
            "family_top5_recall_one_sided_95": _one_sided_interval(
                family_hits,
                family_trials,
            ),
        },
        "sample": {
            "per_mode": args.per_mode,
            "metrics": sample_metrics,
            "triggered_rows": sum(record["triggered"] for record in records),
            "selector_calls": sum(
                bool(record["candidate_operations"]) for record in records
            ),
            "selector_none": sum(
                record["selector_none"] is True for record in records
            ),
            "verifier_calls": sum(
                record["verifier"] is not None for record in records
            ),
            "verifier_vetoes": sum(
                record["verifier"] is not None
                and record["final_mode"] == "conversation"
                for record in records
            ),
            "candidate_family_hits": sum(
                record["candidate_family_hit"] is True for record in records
            ),
            "candidate_family_trials": sum(
                record["candidate_family_hit"] is not None for record in records
            ),
            "stagewise": stagewise,
            "family_selector_calls": sum(
                record["family_selector"] is not None for record in records
            ),
            "family_selector_none": sum(
                isinstance(record["family_selector"], dict)
                and record["family_selector"].get("family") == "__none__"
                for record in records
            ),
            "operation_selector_calls": sum(
                record["operation_selector"] is not None
                for record in records
            ),
            "operation_selector_none": sum(
                isinstance(record["operation_selector"], dict)
                and record["operation_selector"].get("operation") == "__none__"
                for record in records
            ),
        },
        "llm": {
            "logical_calls": logical_calls,
            "raw_schema_calls": len(raw_calls),
            "schema_recovery_calls": max(0, len(raw_calls) - logical_calls),
            "raw_call_errors": sum(
                call["error_type"] is not None for call in raw_calls
            ),
            "raw_latency_seconds": {
                "p50": round(
                    _percentile(
                        [call["latency_seconds"] for call in raw_calls],
                        0.50,
                    ),
                    4,
                ),
                "p95": round(
                    _percentile(
                        [call["latency_seconds"] for call in raw_calls],
                        0.95,
                    ),
                    4,
                ),
                "max": round(
                    max(
                        (
                            call["latency_seconds"]
                            for call in raw_calls
                        ),
                        default=0.0,
                    ),
                    4,
                ),
            },
        },
        "timing": {
            "validation_encode_seconds": round(
                validation_encode_seconds,
                4,
            ),
            "total_seconds": round(time.perf_counter() - started, 4),
        },
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=RUNTIME)
    parser.add_argument("--holdout", type=Path, default=HOLDOUT)
    parser.add_argument("--runtime-manifest", type=Path, default=gate.DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--core", type=Path, default=gate.DEFAULT_CORE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--protocol", choices=("v5", "v5.1"), default="v5")
    parser.add_argument("--per-mode", type=int, default=12)
    parser.add_argument("--max-operations", type=int, default=15)
    parser.add_argument("--request-budget", type=float, default=20.0)
    parser.add_argument("--startup-budget", type=float, default=240.0)
    args = parser.parse_args()
    if not 1 <= args.per_mode <= 128:
        parser.error("--per-mode must be in [1, 128]")
    if not 1 <= args.max_operations <= 24:
        parser.error("--max-operations must be in [1, 24]")
    if not 2.0 <= args.request_budget <= 55.0:
        parser.error("--request-budget must be in [2, 55]")
    return args


def main() -> int:
    args = parse_args()
    report = measure(args)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    gate.write_json_atomic(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "evaluation_pool": report["evaluation_pool"],
                "sample": report["sample"],
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
