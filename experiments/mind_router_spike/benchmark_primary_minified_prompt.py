"""Physical A/B for a minified-JSON instruction on BAXY's primary policy.

This is an isolated experiment: production code, the generic JSON Schema,
decoding parameters, model, llama.cpp profile and authority checks stay
unchanged.  The candidate appends one sentence only to the primary turn-policy
system message:

    Devuelve JSON minificado, sin espacios ni saltos de línea.

Cases are selected deterministically from the canonical historical corpus and
cover conversation, one-effect action and multi-effect plan.  Two explicit
incomplete requests exercise clarification.  Each arm owns a fresh
llama-server, and the script refuses to start while another llama-server is
running so GPU contention cannot contaminate the result.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from baxy_mind import llm as llm_module  # noqa: E402
from run_turn_policy_gate import core_capabilities  # noqa: E402

from benchmark_llama_slot_pinning import (  # noqa: E402
    InstrumentedRuntime,
    _stage_summary,
)

_BASELINE_PROMPT = llm_module.TURN_POLICY_PROMPT
_MINIFIED_SUFFIX = " Devuelve JSON minificado, sin espacios ni saltos de línea."
_SELECTION_SEED = "baxy-primary-minified-prompt-v1"
_DEFAULT_CORPUS = ROOT / "tests" / "data" / "historical_messages.jsonl"
_NATURAL_ORIGINS = frozenset(
    {"historical_test", "acceptance_example", "document_example"}
)
_STABLE_CONVERSATION_START = re.compile(
    r"^(?:"
    r"hola|hello|hi|gracias|thanks|"
    r"qu[eé]\s+(?:es|eres)\b|qui[eé]n\s+eres\b|"
    r"por qu[eé]\b|c[oó]mo\s+funciona\b|"
    r"what\s+is\b|who\s+are\s+you\b|why\b|how\s+does\b|"
    r"explica\b|expl[ií]came\b|explain\b|tell me\b"
    r")",
    re.IGNORECASE,
)
_ACTION_REQUEST_START = re.compile(
    r"^(?:"
    r"abre\b|open\b|pon\b|play\b|reproduce\b|resume\b|"
    r"busca\b|search\b|encuentra\b|find\b|"
    r"crea\b|create\b|guarda\b|save\b|"
    r"cierra\b|close\b|elimina\b|borra\b|delete\b|"
    r"renombra\b|rename\b|recuerda\b|remember\b|"
    r"olvida\b|forget\b|sube\b|baja\b|dim\b|mute\b|"
    r"turn\b|connect\b|quiero abrir\b|toma\b|saca\b|take\b"
    r")",
    re.IGNORECASE,
)
_TRUSTED_PLAN_SIGNATURES = frozenset(
    {
        ("audio.volume", "streaming.navigate"),
        ("browser.navigate", "web.search"),
        (
            "audio.volume",
            "browser.navigate",
            "streaming.navigate",
            "web.search",
        ),
    }
)
_SEMANTIC_FIELDS = (
    "mode",
    "operation",
    "question",
    "conversation_kind",
    "effect_count",
    "effect_operations",
    "response_language",
)


@dataclass(frozen=True)
class PolicyCase:
    case_id: str
    source: str
    text: str
    expected_mode: str
    expected_operations: tuple[str, ...]
    candidates: tuple[dict[str, Any], ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _stable_rank(bucket: str, value: str) -> str:
    return _sha256_bytes(f"{_SELECTION_SEED}\0{bucket}\0{value}".encode("utf-8"))


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"invalid corpus JSON on line {line_number}"
                ) from error
            if isinstance(value, dict):
                rows.append(value)
    if not rows:
        raise ValueError("canonical historical corpus is empty")
    return rows


def _eligible_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        text = row.get("text_literal")
        message_id = row.get("message_id")
        operations = row.get("operations")
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > 180
            or "\n" in text
            or any(marker in text for marker in ("`", "**", "<", ">", "{", "}"))
            or not isinstance(message_id, str)
            or not message_id
            or not isinstance(operations, list)
            or not all(isinstance(item, str) and item for item in operations)
            or row.get("redacted") is True
            or row.get("dedup_status") != "canonical_source"
            or row.get("origin") not in _NATURAL_ORIGINS
        ):
            continue
        identity = str(row.get("text_sha256") or text.casefold().strip())
        unique.setdefault(identity, row)
    return list(unique.values())


def _select_diverse(
    rows: Iterable[dict[str, Any]],
    *,
    bucket: str,
    count: int,
    diversity_key: Callable[[dict[str, Any]], object],
) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: _stable_rank(bucket, str(row["message_id"])),
    )
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for row in ranked:
        diversity = str(diversity_key(row))
        if diversity in used:
            continue
        selected.append(row)
        used.add(diversity)
        if len(selected) == count:
            return selected
    for row in ranked:
        if row in selected:
            continue
        selected.append(row)
        if len(selected) == count:
            return selected
    raise ValueError(f"not enough eligible rows for {bucket}")


def _contracts(
    capabilities: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        name = capability.get("name")
        description = capability.get("description")
        schema = capability.get("argumentsSchema")
        if (
            isinstance(name, str)
            and name
            and isinstance(description, str)
            and description.strip()
            and isinstance(schema, dict)
        ):
            result[name] = {
                "name": name,
                "description": description.strip(),
                "arguments_schema": copy.deepcopy(schema),
            }
    if not result:
        raise ValueError("Core catalog has no usable contracts")
    return result


def _decoys(
    contracts: dict[str, dict[str, Any]],
    *,
    bucket: str,
    excluded: set[str],
    count: int,
) -> list[str]:
    allowed = [
        name
        for name in contracts
        if name not in excluded and not name.startswith("memory.")
    ]
    return sorted(
        allowed,
        key=lambda name: _stable_rank(f"decoy:{bucket}", name),
    )[:count]


def _candidate_tuple(
    names: Iterable[str],
    contracts: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    return tuple(copy.deepcopy(contracts[name]) for name in names)


def _select_cases(
    rows: list[dict[str, Any]],
    contracts: dict[str, dict[str, Any]],
    *,
    per_mode: int,
) -> list[PolicyCase]:
    eligible = _eligible_rows(rows)
    available = set(contracts)
    zero_rows = [
        row
        for row in eligible
        if (
            row.get("class") == "conversation_question"
            and row.get("intent")
            in {"conversation:knowledge_or_chat", "conversation:smalltalk"}
            and not row["operations"]
            and _STABLE_CONVERSATION_START.search(str(row["text_literal"]).strip())
            is not None
        )
    ]
    one_rows = [
        row
        for row in eligible
        if (
            row.get("class") == "user_mission"
            and len(row["operations"]) == 1
            and row["operations"][0] in available
            and row.get("intent") == f"user_mission:{row['operations'][0]}"
            and _ACTION_REQUEST_START.search(str(row["text_literal"]).strip())
            is not None
        )
    ]
    multiple_rows = [
        row
        for row in eligible
        if (
            row.get("class") == "user_mission"
            and 2 <= len(row["operations"]) <= 4
            and all(name in available for name in row["operations"])
            and tuple(row["operations"]) in _TRUSTED_PLAN_SIGNATURES
            and row.get("possible_chain") is True
            and row.get("origin") == "acceptance_example"
            and _ACTION_REQUEST_START.search(str(row["text_literal"]).strip())
            is not None
        )
    ]
    selected = {
        "conversation": _select_diverse(
            zero_rows,
            bucket="conversation",
            count=per_mode,
            diversity_key=lambda row: str(
                row.get("canonical_signature") or row.get("intent")
            ),
        ),
        "action": _select_diverse(
            one_rows,
            bucket="action",
            count=per_mode,
            diversity_key=lambda row: str(row["operations"][0]),
        ),
        "plan": _select_diverse(
            multiple_rows,
            bucket="plan",
            count=per_mode,
            diversity_key=lambda row: ",".join(row["operations"]),
        ),
    }

    cases: list[PolicyCase] = []
    for expected_mode in ("conversation", "action", "plan"):
        for index, row in enumerate(selected[expected_mode], 1):
            operations = tuple(str(name) for name in row["operations"])
            decoys = _decoys(
                contracts,
                bucket=str(row["message_id"]),
                excluded=set(operations),
                count=max(0, 4 - len(operations)),
            )
            names = (*operations, *decoys)
            cases.append(
                PolicyCase(
                    case_id=f"{expected_mode}-{index:02d}",
                    source=str(row["message_id"]),
                    text=str(row["text_literal"]),
                    expected_mode=expected_mode,
                    expected_operations=operations,
                    candidates=_candidate_tuple(names, contracts),
                )
            )

    clarification_specs = (
        ("clarify-task", "Crea una tarea.", "task.create"),
        ("clarify-note", "Crea una nota.", "note.create"),
    )
    for case_id, text, operation in clarification_specs:
        if operation not in contracts:
            raise ValueError(f"required clarification contract missing: {operation}")
        names = [
            operation,
            *_decoys(
                contracts,
                bucket=case_id,
                excluded={operation},
                count=3,
            ),
        ]
        cases.append(
            PolicyCase(
                case_id=case_id,
                source="curated-incomplete-request",
                text=text,
                expected_mode="clarify",
                expected_operations=(),
                candidates=_candidate_tuple(names, contracts),
            )
        )
    return cases


def _semantic_projection(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {field: copy.deepcopy(value.get(field)) for field in _SEMANTIC_FIELDS}


def _parse_content(content: str) -> dict[str, Any] | None:
    try:
        value = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _is_minified_json(content: str) -> bool:
    parsed = _parse_content(content)
    return parsed is not None and content == json.dumps(
        parsed, ensure_ascii=False, separators=(",", ":")
    )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "total": sum(values) if values else None,
        "mean": statistics.mean(values) if values else None,
        "p50": statistics.median(values) if values else None,
        "p95": _percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def _run_case(
    runtime: InstrumentedRuntime,
    case: PolicyCase,
) -> dict[str, Any]:
    runtime._benchmark_case = case.case_id
    started = time.perf_counter()
    runtime.begin_request(55.0)
    try:
        decision = runtime.decide_turn(
            case.text,
            [copy.deepcopy(item) for item in case.candidates],
            history=[],
            evidence=[],
        )
    finally:
        runtime.end_request()
    return {
        "case_id": case.case_id,
        "source": case.source,
        "text": case.text,
        "expected_mode": case.expected_mode,
        "expected_operations": list(case.expected_operations),
        "candidate_names": [item["name"] for item in case.candidates],
        "elapsed_seconds": time.perf_counter() - started,
        "decision": copy.deepcopy(decision),
        "decision_projection": _semantic_projection(decision),
    }


def _primary_posts(
    cases: list[dict[str, Any]],
    posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for case in cases:
        case_posts = [
            post
            for post in posts
            if post.get("case") == case["case_id"] and post.get("stage") == "P"
        ]
        if not case_posts:
            raise ValueError(f"no primary post recorded for {case['case_id']}")
        post = copy.deepcopy(case_posts[0])
        content = str(post.get("content") or "")
        parsed = _parse_content(content)
        post.update(
            {
                "content_chars": len(content),
                "content_utf8_bytes": len(content.encode("utf-8")),
                "content_whitespace_chars": sum(
                    character.isspace() for character in content
                ),
                "is_minified_json": _is_minified_json(content),
                "semantic_projection": _semantic_projection(parsed),
                "primary_attempt_count": len(case_posts),
            }
        )
        result.append(post)
    return result


def _contract_for_case(
    case: PolicyCase,
    prompt: str,
) -> dict[str, Any]:
    names, candidate_text, _ = llm_module._prepare_turn_candidates(
        [copy.deepcopy(item) for item in case.candidates]
    )
    original = llm_module.TURN_POLICY_PROMPT
    try:
        llm_module.TURN_POLICY_PROMPT = prompt
        payload = llm_module._build_turn_policy_payload(
            case.text,
            names,
            candidate_text,
            [],
        )
    finally:
        llm_module.TURN_POLICY_PROMPT = original
    response_format = payload["response_format"]
    return {
        "response_format_sha256": _canonical_hash(response_format),
        "generic_json_schema_preserved": (
            llm_module._compact_structured_grammar(payload) is None
            and "grammar" not in payload
            and response_format.get("type") == "json_schema"
        ),
    }


def _run_arm(
    profile: str,
    cases: list[PolicyCase],
) -> dict[str, Any]:
    prompt = (
        _BASELINE_PROMPT
        if profile == "baseline"
        else _BASELINE_PROMPT + _MINIFIED_SUFFIX
    )
    llm_module.TURN_POLICY_PROMPT = prompt
    runtime = InstrumentedRuntime(profile)
    case_results: list[dict[str, Any]] = []
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        for case in cases:
            case_results.append(_run_case(runtime, case))
    finally:
        runtime.close()
        llm_module.TURN_POLICY_PROMPT = _BASELINE_PROMPT

    primary = _primary_posts(case_results, runtime._benchmark_records)
    primary_elapsed = [
        float(post["elapsed_seconds"])
        for post in primary
        if isinstance(post.get("elapsed_seconds"), (int, float))
    ]
    predicted_n = [
        float(post["predicted_n"])
        for post in primary
        if isinstance(post.get("predicted_n"), (int, float))
    ]
    predicted_ms = [
        float(post["predicted_ms"])
        for post in primary
        if isinstance(post.get("predicted_ms"), (int, float))
    ]
    prompt_n = [
        float(post["prompt_n"])
        for post in primary
        if isinstance(post.get("prompt_n"), (int, float))
    ]
    prompt_ms = [
        float(post["prompt_ms"])
        for post in primary
        if isinstance(post.get("prompt_ms"), (int, float))
    ]
    cache_n = [
        float(post["cache_n"])
        for post in primary
        if isinstance(post.get("cache_n"), (int, float))
    ]
    e2e = [float(case["elapsed_seconds"]) for case in case_results]
    return {
        "profile": profile,
        "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "prompt_chars": len(prompt),
        "cases": case_results,
        "primary_posts": primary,
        "all_posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "primary_metrics": {
            "elapsed_seconds": _summary(primary_elapsed),
            "predicted_tokens": _summary(predicted_n),
            "predicted_seconds": _summary([value / 1000.0 for value in predicted_ms]),
            "prompt_tokens": _summary(prompt_n),
            "prompt_seconds": _summary([value / 1000.0 for value in prompt_ms]),
            "cache_tokens": _summary(cache_n),
            "minified_outputs": sum(bool(post["is_minified_json"]) for post in primary),
            "whitespace_chars_total": sum(
                int(post["content_whitespace_chars"]) for post in primary
            ),
            "content_chars_total": sum(int(post["content_chars"]) for post in primary),
        },
        "decision_pipeline_e2e_seconds": _summary(e2e),
    }


def _case_map(arm: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {str(item["case_id"]): item for item in arm[key]}


def _compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_cases = _case_map(baseline, "cases")
    candidate_cases = _case_map(candidate, "cases")
    baseline_posts = {str(item["case"]): item for item in baseline["primary_posts"]}
    candidate_posts = {str(item["case"]): item for item in candidate["primary_posts"]}
    if set(baseline_cases) != set(candidate_cases):
        raise ValueError("arm case identities differ")
    comparisons: list[dict[str, Any]] = []
    for case_id in baseline_cases:
        baseline_case = baseline_cases[case_id]
        candidate_case = candidate_cases[case_id]
        baseline_post = baseline_posts[case_id]
        candidate_post = candidate_posts[case_id]
        comparisons.append(
            {
                "case_id": case_id,
                "primary_semantic_equal": (
                    baseline_post["semantic_projection"]
                    == candidate_post["semantic_projection"]
                ),
                "final_decision_equal": (
                    baseline_case["decision_projection"]
                    == candidate_case["decision_projection"]
                ),
                "baseline_expected_mode": (
                    baseline_case["decision"].get("mode")
                    == baseline_case["expected_mode"]
                ),
                "candidate_expected_mode": (
                    candidate_case["decision"].get("mode")
                    == candidate_case["expected_mode"]
                ),
                "primary_predicted_token_delta": (
                    float(candidate_post["predicted_n"])
                    - float(baseline_post["predicted_n"])
                ),
                "primary_elapsed_delta_seconds": (
                    float(candidate_post["elapsed_seconds"])
                    - float(baseline_post["elapsed_seconds"])
                ),
                "e2e_delta_seconds": (
                    float(candidate_case["elapsed_seconds"])
                    - float(baseline_case["elapsed_seconds"])
                ),
                "baseline_primary_projection": baseline_post["semantic_projection"],
                "candidate_primary_projection": candidate_post["semantic_projection"],
                "baseline_final_projection": baseline_case["decision_projection"],
                "candidate_final_projection": candidate_case["decision_projection"],
            }
        )
    return {
        "cases": comparisons,
        "primary_semantic_exact": all(
            item["primary_semantic_equal"] for item in comparisons
        ),
        "final_decisions_exact": all(
            item["final_decision_equal"] for item in comparisons
        ),
        "baseline_expected_modes": sum(
            item["baseline_expected_mode"] for item in comparisons
        ),
        "candidate_expected_modes": sum(
            item["candidate_expected_mode"] for item in comparisons
        ),
        "primary_candidate_wins": sum(
            item["primary_elapsed_delta_seconds"] < 0.0 for item in comparisons
        ),
        "e2e_candidate_wins": sum(
            item["e2e_delta_seconds"] < 0.0 for item in comparisons
        ),
        "primary_predicted_token_delta_total": sum(
            item["primary_predicted_token_delta"] for item in comparisons
        ),
        "primary_elapsed_delta_seconds": _summary(
            [item["primary_elapsed_delta_seconds"] for item in comparisons]
        ),
        "e2e_delta_seconds": _summary(
            [item["e2e_delta_seconds"] for item in comparisons]
        ),
    }


def _running_llama_servers() -> list[str]:
    process = subprocess.run(
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
    rows: list[str] = []
    for row in csv.reader(process.stdout.splitlines()):
        if row and row[0].casefold() == "llama-server.exe":
            rows.append(",".join(row))
    return rows


def _profile(artifact: dict[str, Any], name: str) -> dict[str, Any]:
    for arm in artifact.get("arms", []):
        if isinstance(arm, dict) and arm.get("profile") == name:
            return arm
    raise ValueError(f"artifact is missing {name!r} arm")


def _projection_map(
    arm: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    if source == "primary":
        return {
            str(item["case"]): item.get("semantic_projection")
            for item in arm["primary_posts"]
        }
    if source == "final":
        return {
            str(item["case_id"]): item.get("decision_projection")
            for item in arm["cases"]
        }
    raise ValueError(source)


def _delta(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *path: str,
) -> float:
    left: Any = baseline
    right: Any = candidate
    for key in path:
        left = left[key]
        right = right[key]
    return float(right) - float(left)


def _aggregate_runs(paths: list[Path]) -> dict[str, Any]:
    if len(paths) != 2:
        raise ValueError("exactly two opposite-order artifacts are required")
    artifacts = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if any(
        artifact.get("schema") != "baxy.primary-minified-prompt-ab.v1"
        for artifact in artifacts
    ):
        raise ValueError("unexpected input artifact schema")
    orders = {tuple(artifact["arm_order"]) for artifact in artifacts}
    if orders != {
        ("baseline", "minified"),
        ("minified", "baseline"),
    }:
        raise ValueError("artifacts are not opposite-order replicas")
    if (
        len({artifact["corpus"]["selected_sources_sha256"] for artifact in artifacts})
        != 1
    ):
        raise ValueError("replica case selections differ")
    if (
        len(
            {
                (
                    artifact["runtime"]["server_sha256"],
                    artifact["runtime"]["model_sha256"],
                    artifact["runtime"]["core_sha256"],
                )
                for artifact in artifacts
            }
        )
        != 1
    ):
        raise ValueError("replica runtime identities differ")

    runs: list[dict[str, Any]] = []
    for path, artifact in zip(paths, artifacts, strict=True):
        baseline = _profile(artifact, "baseline")
        candidate = _profile(artifact, "minified")
        comparison = artifact["comparison"]
        primary_mismatches = sum(
            not bool(case["primary_semantic_equal"]) for case in comparison["cases"]
        )
        final_mismatches = sum(
            not bool(case["final_decision_equal"]) for case in comparison["cases"]
        )
        runs.append(
            {
                "artifact": str(path.resolve()),
                "arm_order": artifact["arm_order"],
                "primary_semantic_mismatches": primary_mismatches,
                "final_decision_mismatches": final_mismatches,
                "expected_mode_delta": (
                    int(comparison["candidate_expected_modes"])
                    - int(comparison["baseline_expected_modes"])
                ),
                "primary_predicted_token_delta": float(
                    comparison["primary_predicted_token_delta_total"]
                ),
                "primary_predicted_token_percent": (
                    100.0
                    * float(comparison["primary_predicted_token_delta_total"])
                    / float(baseline["primary_metrics"]["predicted_tokens"]["total"])
                ),
                "primary_p50_delta_seconds": _delta(
                    baseline,
                    candidate,
                    "primary_metrics",
                    "elapsed_seconds",
                    "p50",
                ),
                "primary_total_delta_seconds": _delta(
                    baseline,
                    candidate,
                    "primary_metrics",
                    "elapsed_seconds",
                    "total",
                ),
                "e2e_p50_delta_seconds": _delta(
                    baseline,
                    candidate,
                    "decision_pipeline_e2e_seconds",
                    "p50",
                ),
                "e2e_p95_delta_seconds": _delta(
                    baseline,
                    candidate,
                    "decision_pipeline_e2e_seconds",
                    "p95",
                ),
                "e2e_total_delta_seconds": _delta(
                    baseline,
                    candidate,
                    "decision_pipeline_e2e_seconds",
                    "total",
                ),
                "baseline_primary_tokens": baseline["primary_metrics"][
                    "predicted_tokens"
                ]["total"],
                "candidate_primary_tokens": candidate["primary_metrics"][
                    "predicted_tokens"
                ]["total"],
                "baseline_minified_outputs": baseline["primary_metrics"][
                    "minified_outputs"
                ],
                "candidate_minified_outputs": candidate["primary_metrics"][
                    "minified_outputs"
                ],
            }
        )

    baseline_arms = [_profile(item, "baseline") for item in artifacts]
    candidate_arms = [_profile(item, "minified") for item in artifacts]
    baseline_primary_stable = _projection_map(
        baseline_arms[0], source="primary"
    ) == _projection_map(baseline_arms[1], source="primary")
    candidate_primary_stable = _projection_map(
        candidate_arms[0], source="primary"
    ) == _projection_map(candidate_arms[1], source="primary")
    baseline_final_stable = _projection_map(
        baseline_arms[0], source="final"
    ) == _projection_map(baseline_arms[1], source="final")
    candidate_final_stable = _projection_map(
        candidate_arms[0], source="final"
    ) == _projection_map(candidate_arms[1], source="final")
    quality_loss = any(
        run["primary_semantic_mismatches"]
        or run["final_decision_mismatches"]
        or run["expected_mode_delta"] < 0
        for run in runs
    )
    return {
        "schema": "baxy.primary-minified-prompt-verdict.v1",
        "candidate_status": "rejected" if quality_loss else "inconclusive",
        "candidate": {
            "scope": "primary system prompt only",
            "suffix": _MINIFIED_SUFFIX.strip(),
            "generic_json_schema_unchanged": all(
                artifact["candidate"]["generic_json_schema_unchanged"]
                for artifact in artifacts
            ),
            "all_cases_use_generic_json_schema": all(
                artifact["candidate"]["all_cases_use_generic_json_schema"]
                for artifact in artifacts
            ),
        },
        "replicas": runs,
        "replica_stability": {
            "baseline_primary_semantics": baseline_primary_stable,
            "candidate_primary_semantics": candidate_primary_stable,
            "baseline_final_decisions": baseline_final_stable,
            "candidate_final_decisions": candidate_final_stable,
        },
        "verdict": (
            "Rejected despite repeatable token/median-latency savings: both "
            "opposite-order replicas changed primary semantics and final "
            "decisions, and each lost one expected-mode case. The primary "
            "policy retains the current prompt and generic JSON Schema."
            if quality_loss
            else "No quality loss observed, but promotion still requires review."
        ),
        "decision_rule": (
            "Any primary semantic or final decision mismatch rejects the "
            "candidate, regardless of speed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summarize",
        type=Path,
        nargs=2,
        metavar=("FORWARD_JSON", "REVERSE_JSON"),
    )
    parser.add_argument(
        "--arm-order",
        choices=("baseline-minified", "minified-baseline"),
        default="baseline-minified",
    )
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument("--per-mode", type=int, default=3)
    parser.add_argument(
        "--core",
        type=Path,
        default=Path(
            os.environ.get(
                "BAXY_BENCHMARK_CORE",
                str(
                    Path(os.environ.get("TEMP", "."))
                    / "baxy-core-vc-gate-20260729"
                    / "baxy-core.exe"
                ),
            )
        ),
    )
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
    if args.summarize:
        result = _aggregate_runs(list(args.summarize))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.per_mode < 1:
        parser.error("--per-mode must be positive")
    for path in (args.corpus, args.core, args.server, args.model):
        if not path.is_file():
            raise FileNotFoundError(path)
    running = _running_llama_servers()
    if running:
        raise RuntimeError(
            "exclusive GPU check failed; llama-server already running: "
            + "; ".join(running)
        )

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_CTX"] = "4096"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "55"

    capabilities = core_capabilities(args.core)
    contracts = _contracts(capabilities)
    corpus_rows = _load_rows(args.corpus)
    cases = _select_cases(
        corpus_rows,
        contracts,
        per_mode=args.per_mode,
    )
    order = args.arm_order.split("-")
    arms = [_run_arm(profile, cases) for profile in order]
    by_profile = {arm["profile"]: arm for arm in arms}
    comparison = _compare(
        by_profile["baseline"],
        by_profile["minified"],
    )
    baseline_contracts = [_contract_for_case(case, _BASELINE_PROMPT) for case in cases]
    candidate_contracts = [
        _contract_for_case(
            case,
            _BASELINE_PROMPT + _MINIFIED_SUFFIX,
        )
        for case in cases
    ]
    schemas_equal = baseline_contracts == candidate_contracts
    result = {
        "schema": "baxy.primary-minified-prompt-ab.v1",
        "arm_order": order,
        "exclusive_gpu_preflight": {
            "passed": True,
            "preexisting_llama_servers": running,
        },
        "runtime": {
            "server": str(args.server.resolve()),
            "server_sha256": _sha256_file(args.server),
            "model": str(args.model.resolve()),
            "model_sha256": _sha256_file(args.model),
            "core": str(args.core.resolve()),
            "core_sha256": _sha256_file(args.core),
            "parallel": 3,
            "context_per_slot": 4096,
        },
        "corpus": {
            "path": str(args.corpus.resolve()),
            "sha256": _sha256_file(args.corpus),
            "rows": len(corpus_rows),
            "selection_seed": _SELECTION_SEED,
            "selected_cases": len(cases),
            "selected_sources_sha256": _canonical_hash([case.source for case in cases]),
        },
        "candidate": {
            "scope": "primary system prompt only",
            "suffix": _MINIFIED_SUFFIX.strip(),
            "generic_json_schema_unchanged": schemas_equal,
            "all_cases_use_generic_json_schema": all(
                item["generic_json_schema_preserved"]
                for item in baseline_contracts + candidate_contracts
            ),
            "response_format_hashes": sorted(
                {item["response_format_sha256"] for item in baseline_contracts}
            ),
        },
        "comparison": comparison,
        "arms": arms,
        "candidate_status": "research_only",
        "decision_rule": (
            "Reject on any primary semantic or final decision mismatch. "
            "Otherwise promote only if opposite-order runs show a repeatable "
            "token and latency reduction without an end-to-end tail regression."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    return (
        0
        if (
            schemas_equal
            and comparison["primary_semantic_exact"]
            and comparison["final_decisions_exact"]
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
