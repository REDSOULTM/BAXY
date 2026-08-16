"""Corpus-backed physical A/B for BAXY's compact V/C grammars.

This experiment compares the production compact GBNF for the independent
effect-count verifier (V) and operation-compatibility verifier (C) against
llama.cpp's generic JSON Schema conversion.  Both arms:

* use the same deterministic selection from the canonical historical corpus;
* use the same prompts, schemas, seed, model, server profile and case order;
* start a fresh, internally owned llama-server process;
* call only the two read-only LLM validators and never execute a capability.

The schema baseline bypasses compact compilation for exactly
``baxy_effect_count_verification`` and
``baxy_operation_compatibility``.  Every other production compaction rule is
left untouched.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import statistics
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from baxy_mind import llm as llm_module  # noqa: E402
from baxy_mind.llm import LlmRuntime  # noqa: E402
from run_turn_policy_gate import core_capabilities  # noqa: E402

_PRODUCTION_COMPACTOR = llm_module._compact_structured_grammar
_TARGET_SCHEMAS = frozenset(
    {
        "baxy_effect_count_verification",
        "baxy_operation_compatibility",
    }
)
_SELECTION_SEED = "baxy-compact-validator-corpus-v1"
_DEFAULT_CORPUS = ROOT / "tests" / "data" / "historical_messages.jsonl"
_NATURAL_CORPUS_ORIGINS = frozenset(
    {
        "historical_test",
        "acceptance_example",
        "document_example",
    }
)
_SINGLE_EFFECT_OPERATIONS = frozenset(
    {
        "app.open",
        "audio.volume",
        "browser.navigate",
        "capture.screenshot",
        "filesystem.search",
        "filesystem.trash",
        "game.launch",
        "media.control",
        "media.play",
        "memory.forget",
        "memory.recall",
        "memory.save",
        "note.create",
        "system.status",
        "task.manage",
        "web.search",
        "window.manage",
    }
)
_EXPLICIT_COMPOUND = re.compile(
    r"(?:[,;]|\b(?:y|e|and|then|luego|después|además)\b)",
    re.IGNORECASE,
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
    r"renombra\b|renombr[aá]\b|rename\b|"
    r"recuerda\b|remember\b|olvida\b|forget\b|"
    r"sube\b|baja\b|dim\b|mute\b|turn\b|connect\b|"
    r"quiero abrir\b|toma\b|saca\b|take\b"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidatorCase:
    case_id: str
    stage: str
    message_id: str
    text: str
    expected: str | bool
    operation: str | None = None
    contract: dict[str, Any] | None = None
    source_operation: str | None = None


def _response_schema_name(payload: dict[str, Any]) -> str | None:
    response_format = payload.get("response_format")
    if not isinstance(response_format, dict):
        return None
    envelope = response_format.get("json_schema")
    if not isinstance(envelope, dict):
        return None
    name = envelope.get("name")
    return name if isinstance(name, str) else None


def _schema_baseline_compactor(payload: dict[str, Any]) -> str | None:
    """Disable only the two candidate compact grammars."""

    if _response_schema_name(payload) in _TARGET_SCHEMAS:
        return None
    return _PRODUCTION_COMPACTOR(payload)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_rank(bucket: str, value: str) -> str:
    return hashlib.sha256(
        f"{_SELECTION_SEED}\0{bucket}\0{value}".encode("utf-8")
    ).hexdigest()


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"invalid corpus JSON on line {line_number}"
                ) from error
            if isinstance(row, dict):
                rows.append(row)
    if not rows:
        raise ValueError("canonical historical corpus is empty")
    return rows


def _eligible_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            or row.get("origin") not in _NATURAL_CORPUS_ORIGINS
        ):
            continue
        text_key = str(row.get("text_sha256") or text.casefold().strip())
        unique.setdefault(text_key, row)
    return list(unique.values())


def _effect_bucket(row: dict[str, Any]) -> str:
    count = len(row["operations"])
    if count == 0:
        return "zero"
    if count == 1:
        return "one"
    return "multiple"


def _select_diverse(
    rows: list[dict[str, Any]],
    *,
    bucket: str,
    count: int,
    diversity_key: Callable[[dict[str, Any]], str],
) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: _stable_rank(bucket, str(row["message_id"])),
    )
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for row in ranked:
        diversity = diversity_key(row)
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
    raise ValueError(f"not enough eligible rows for {bucket}: {len(selected)}/{count}")


def _contract_by_name(
    capabilities: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        name = capability.get("name")
        description = capability.get("description")
        arguments_schema = capability.get("argumentsSchema")
        if (
            isinstance(name, str)
            and name
            and isinstance(description, str)
            and isinstance(arguments_schema, dict)
        ):
            contracts[name] = {
                "description": description,
                "arguments_schema": copy.deepcopy(arguments_schema),
            }
    if not contracts:
        raise ValueError("Core catalog has no usable contracts")
    return contracts


def _mismatch_operation(
    source_operation: str,
    contracts: dict[str, dict[str, Any]],
    message_id: str,
) -> str:
    source_family = source_operation.split(".", 1)[0]
    candidates = [
        name
        for name in contracts
        if (
            name in _SINGLE_EFFECT_OPERATIONS
            and name != source_operation
            and name.split(".", 1)[0] != source_family
        )
    ]
    if not candidates:
        raise ValueError(f"no mismatch candidate for {source_operation}")
    return min(
        candidates,
        key=lambda name: _stable_rank(
            f"mismatch:{message_id}:{source_operation}",
            name,
        ),
    )


def _select_cases(
    rows: list[dict[str, Any]],
    contracts: dict[str, dict[str, Any]],
    *,
    per_effect_bucket: int,
    compatibility_pairs: int,
) -> list[ValidatorCase]:
    eligible = _eligible_rows(rows)
    cases: list[ValidatorCase] = []
    for effect_count in ("zero", "one", "multiple"):
        bucket_rows = [
            row
            for row in eligible
            if _effect_bucket(row) == effect_count
            and (
                effect_count != "zero"
                or (
                    row.get("class") == "conversation_question"
                    and row.get("intent")
                    in {
                        "conversation:knowledge_or_chat",
                        "conversation:smalltalk",
                    }
                    and _STABLE_CONVERSATION_START.search(
                        str(row["text_literal"]).strip()
                    )
                    is not None
                )
            )
            and (
                effect_count == "zero"
                or (
                    row.get("class") == "user_mission"
                    and (
                        (
                            effect_count == "one"
                            and row["operations"][0]
                            in _SINGLE_EFFECT_OPERATIONS
                            and row.get("intent")
                            == f"user_mission:{row['operations'][0]}"
                            and _ACTION_REQUEST_START.search(
                                str(row["text_literal"]).strip()
                            )
                            is not None
                            and _EXPLICIT_COMPOUND.search(
                                str(row["text_literal"])
                            )
                            is None
                        )
                        or (
                            effect_count == "multiple"
                            and row.get("possible_chain") is True
                            and _ACTION_REQUEST_START.search(
                                str(row["text_literal"]).strip()
                            )
                            is not None
                            and _EXPLICIT_COMPOUND.search(
                                str(row["text_literal"])
                            )
                            is not None
                        )
                    )
                )
            )
        ]
        selected = _select_diverse(
            bucket_rows,
            bucket=f"V:{effect_count}",
            count=per_effect_bucket,
            diversity_key=lambda row: str(
                row.get("intent") or row.get("canonical_signature") or ""
            ),
        )
        for index, row in enumerate(selected, 1):
            cases.append(
                ValidatorCase(
                    case_id=f"V-{effect_count}-{index:02d}",
                    stage="V",
                    message_id=str(row["message_id"]),
                    text=str(row["text_literal"]),
                    expected=effect_count,
                )
            )

    compatible_rows = [
        row
        for row in eligible
        if row.get("class") == "user_mission"
        and len(row["operations"]) == 1
        and row["operations"][0] in contracts
        and row["operations"][0] in _SINGLE_EFFECT_OPERATIONS
        and row.get("intent") == f"user_mission:{row['operations'][0]}"
        and _ACTION_REQUEST_START.search(str(row["text_literal"]).strip())
        is not None
        and _EXPLICIT_COMPOUND.search(str(row["text_literal"])) is None
    ]
    selected_compatible = _select_diverse(
        compatible_rows,
        bucket="C:pairs",
        count=compatibility_pairs,
        diversity_key=lambda row: str(row["operations"][0]),
    )
    for index, row in enumerate(selected_compatible, 1):
        source_operation = str(row["operations"][0])
        mismatch = _mismatch_operation(
            source_operation,
            contracts,
            str(row["message_id"]),
        )
        common = {
            "message_id": str(row["message_id"]),
            "text": str(row["text_literal"]),
            "source_operation": source_operation,
        }
        cases.extend(
            [
                ValidatorCase(
                    case_id=f"C-true-{index:02d}",
                    stage="C",
                    expected=True,
                    operation=source_operation,
                    contract=copy.deepcopy(contracts[source_operation]),
                    **common,
                ),
                ValidatorCase(
                    case_id=f"C-false-{index:02d}",
                    stage="C",
                    expected=False,
                    operation=mismatch,
                    contract=copy.deepcopy(contracts[mismatch]),
                    **common,
                ),
            ]
        )
    return cases


def _stage(payload: dict[str, Any], case_id: str = "") -> str:
    case_stage = case_id.split("-", 1)[0]
    if case_stage in {"V", "C"}:
        return case_stage
    name = _response_schema_name(payload)
    if name == "baxy_effect_count_verification":
        return "V"
    if name == "baxy_operation_compatibility":
        return "C"
    return "other"


def _payload_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _content(response: dict[str, Any]) -> str:
    try:
        choices = response["choices"]
        message = choices[0]["message"]
        return str(message.get("content") or "")
    except (KeyError, IndexError, TypeError):
        return ""


class InstrumentedValidatorRuntime(LlmRuntime):
    def __init__(self, profile: str) -> None:
        self.benchmark_profile = profile
        self.benchmark_case = ""
        self.benchmark_posts: list[dict[str, Any]] = []
        self._benchmark_lock = threading.Lock()
        super().__init__()
        self._speculative_knowledge_enabled = False

    def _post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        wire = dict(payload)
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
        record = {
            "case_id": self.benchmark_case,
            "stage": _stage(wire, self.benchmark_case),
            "wire_constraint": (
                "compact_gbnf" if "grammar" in wire else "generic_json_schema"
            ),
            "payload_sha256": _payload_fingerprint(wire),
            "elapsed_seconds": elapsed,
            "cache_n": timings.get("cache_n"),
            "prompt_n": timings.get("prompt_n"),
            "prompt_ms": timings.get("prompt_ms"),
            "predicted_n": timings.get("predicted_n"),
            "predicted_ms": timings.get("predicted_ms"),
            "raw_content": _content(response),
        }
        with self._benchmark_lock:
            self.benchmark_posts.append(record)
        return response


def _run_case(
    runtime: InstrumentedValidatorRuntime,
    case: ValidatorCase,
) -> dict[str, Any]:
    runtime.benchmark_case = case.case_id
    runtime.begin_request(55.0)
    started = time.perf_counter()
    try:
        if case.stage == "V":
            result: str | bool | None = runtime._verify_effect_count(case.text)
        else:
            if (
                case.operation is None
                or case.contract is None
            ):
                raise ValueError(f"incomplete C case: {case.case_id}")
            result = runtime._operation_is_fully_compatible(
                case.text,
                case.operation,
                case.contract,
            )
        elapsed = time.perf_counter() - started
        return {
            "case_id": case.case_id,
            "stage": case.stage,
            "message_id": case.message_id,
            "text": case.text,
            "expected": case.expected,
            "operation": case.operation,
            "source_operation": case.source_operation,
            "result": result,
            "matches_corpus_expectation": result == case.expected,
            "elapsed_seconds": elapsed,
        }
    finally:
        runtime.end_request()


def _numeric(
    records: list[dict[str, Any]],
    key: str,
) -> list[float]:
    return [
        float(record[key])
        for record in records
        if (
            isinstance(record.get(key), (int, float))
            and not isinstance(record.get(key), bool)
            and math.isfinite(float(record[key]))
        )
    ]


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return (
        ordered[lower] * (upper - position)
        + ordered[upper] * (position - lower)
    )


def _stage_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for stage in ("V", "C"):
        selected = [record for record in records if record["stage"] == stage]
        elapsed = _numeric(selected, "elapsed_seconds")
        predicted_n = _numeric(selected, "predicted_n")
        predicted_ms = _numeric(selected, "predicted_ms")
        prompt_n = _numeric(selected, "prompt_n")
        prompt_ms = _numeric(selected, "prompt_ms")
        result[stage] = {
            "calls": len(selected),
            "wire_constraints": sorted(
                {str(record["wire_constraint"]) for record in selected}
            ),
            "elapsed_total_seconds": sum(elapsed),
            "elapsed_p50_seconds": statistics.median(elapsed) if elapsed else None,
            "elapsed_p95_seconds": _percentile(elapsed, 0.95),
            "elapsed_max_seconds": max(elapsed) if elapsed else None,
            "prompt_n_p50": statistics.median(prompt_n) if prompt_n else None,
            "prompt_ms_p50": statistics.median(prompt_ms) if prompt_ms else None,
            "predicted_n_p50": (
                statistics.median(predicted_n) if predicted_n else None
            ),
            "predicted_ms_p50": (
                statistics.median(predicted_ms) if predicted_ms else None
            ),
        }
    return result


def _run_arm(
    profile: str,
    cases: list[ValidatorCase],
) -> dict[str, Any]:
    llm_module._compact_structured_grammar = (
        _schema_baseline_compactor
        if profile == "schema"
        else _PRODUCTION_COMPACTOR
    )
    runtime = InstrumentedValidatorRuntime(profile)
    outputs: list[dict[str, Any]] = []
    process_id: int | None = None
    started = time.perf_counter()
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        process = runtime._process
        process_id = process.pid if process is not None else None
        for case in cases:
            outputs.append(_run_case(runtime, case))
    finally:
        runtime.close()
        llm_module._compact_structured_grammar = _PRODUCTION_COMPACTOR
    return {
        "profile": profile,
        "fresh_server_pid": process_id,
        "elapsed_total_seconds": time.perf_counter() - started,
        "cases": outputs,
        "posts": runtime.benchmark_posts,
        "stage_summary": _stage_summary(runtime.benchmark_posts),
        "corpus_expectation_matches": sum(
            1 for case in outputs if case["matches_corpus_expectation"]
        ),
        "corpus_expectation_total": len(outputs),
    }


def _case_projection(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: case[key]
        for key in (
            "case_id",
            "stage",
            "message_id",
            "expected",
            "operation",
            "source_operation",
            "result",
        )
    }


def _value_coverage(cases: list[dict[str, Any]]) -> dict[str, list[Any]]:
    return {
        "V": sorted(
            {
                case["result"]
                for case in cases
                if case["stage"] == "V" and isinstance(case["result"], str)
            }
        ),
        "C": sorted(
            {
                case["result"]
                for case in cases
                if case["stage"] == "C" and isinstance(case["result"], bool)
            }
        ),
    }


def _latency_delta(
    schema: dict[str, Any],
    compact: dict[str, Any],
) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for stage in ("V", "C"):
        baseline = schema["stage_summary"][stage]
        candidate = compact["stage_summary"][stage]
        baseline_p50 = float(baseline["elapsed_p50_seconds"])
        candidate_p50 = float(candidate["elapsed_p50_seconds"])
        baseline_total = float(baseline["elapsed_total_seconds"])
        candidate_total = float(candidate["elapsed_total_seconds"])
        delta[stage] = {
            "p50_seconds": candidate_p50 - baseline_p50,
            "p50_percent": (
                ((candidate_p50 / baseline_p50) - 1.0) * 100.0
                if baseline_p50
                else None
            ),
            "total_seconds": candidate_total - baseline_total,
            "total_percent": (
                ((candidate_total / baseline_total) - 1.0) * 100.0
                if baseline_total
                else None
            ),
        }
    return delta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument("--per-effect-bucket", type=int, default=8)
    parser.add_argument("--compatibility-pairs", type=int, default=8)
    parser.add_argument(
        "--arm-order",
        choices=("schema-compact", "compact-schema"),
        default="schema-compact",
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
    for label, path in (
        ("corpus", args.corpus),
        ("Core", args.core),
        ("llama-server", args.server),
        ("model", args.model),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} is missing: {path}")
    if args.per_effect_bucket < 1 or args.compatibility_pairs < 1:
        raise ValueError("sample sizes must be positive")

    rows = _load_corpus(args.corpus)
    capabilities = core_capabilities(args.core)
    contracts = _contract_by_name(capabilities)
    cases = _select_cases(
        rows,
        contracts,
        per_effect_bucket=args.per_effect_bucket,
        compatibility_pairs=args.compatibility_pairs,
    )

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    arms = [_run_arm(profile, cases) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    schema_projection = [
        _case_projection(case) for case in by_profile["schema"]["cases"]
    ]
    compact_projection = [
        _case_projection(case) for case in by_profile["compact"]["cases"]
    ]
    divergent_cases = [
        {
            "case_id": baseline["case_id"],
            "schema_result": baseline["result"],
            "compact_result": candidate["result"],
        }
        for baseline, candidate in zip(
            schema_projection,
            compact_projection,
            strict=True,
        )
        if baseline != candidate
    ]
    exact_outputs = not divergent_cases
    schema_coverage = _value_coverage(by_profile["schema"]["cases"])
    compact_coverage = _value_coverage(by_profile["compact"]["cases"])
    full_value_coverage = (
        set(schema_coverage["V"]) == {"zero", "one", "multiple"}
        and set(compact_coverage["V"]) == {"zero", "one", "multiple"}
        and set(schema_coverage["C"]) == {False, True}
        and set(compact_coverage["C"]) == {False, True}
    )
    result = {
        "schema": "baxy.compact-validator-corpus-ab.v1",
        "arm_order": arm_order,
        "safety": {
            "external_effects_executed": False,
            "calls": (
                "Only LlmRuntime._verify_effect_count and "
                "LlmRuntime._operation_is_fully_compatible"
            ),
        },
        "runtime": {
            "server": str(args.server.resolve()),
            "model": str(args.model.resolve()),
            "core": str(args.core.resolve()),
            "parallel": 3,
            "context_per_slot": 4096,
        },
        "corpus": {
            "path": str(args.corpus.resolve()),
            "sha256": _sha256_file(args.corpus),
            "row_count": len(rows),
            "selection_seed": _SELECTION_SEED,
            "per_effect_bucket": args.per_effect_bucket,
            "compatibility_pairs": args.compatibility_pairs,
            "selected_case_count": len(cases),
            "selected_message_ids": [case.message_id for case in cases],
        },
        "control": {
            "schema_baseline": (
                "Returns None only for baxy_effect_count_verification and "
                "baxy_operation_compatibility, delegating every other schema "
                "to the production compactor."
            ),
            "compact_candidate": "Unmodified production compactor.",
            "fresh_server_per_arm": True,
            "same_case_order_per_arm": True,
            "temperature": 0.0,
            "seed": 0,
        },
        "exact_normalized_outputs": exact_outputs,
        "divergent_cases": divergent_cases,
        "value_coverage": {
            "schema": schema_coverage,
            "compact": compact_coverage,
            "complete": full_value_coverage,
        },
        "latency_delta_compact_minus_schema": _latency_delta(
            by_profile["schema"],
            by_profile["compact"],
        ),
        "arms": arms,
        "candidate_status": (
            "quality_equivalent"
            if exact_outputs and full_value_coverage
            else "rejected"
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
                    "exact_normalized_outputs",
                    "divergent_cases",
                    "value_coverage",
                    "latency_delta_compact_minus_schema",
                    "candidate_status",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if exact_outputs and full_value_coverage else 2


if __name__ == "__main__":
    raise SystemExit(main())
