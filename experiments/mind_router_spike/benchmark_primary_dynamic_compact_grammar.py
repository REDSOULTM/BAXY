"""Effect-free physical A/B for exact transforms of P's captured grammar.

The baseline arm uses production ``response_format`` and captures llama.cpp's
exact generated grammar for every primary-policy schema reached by the
selected frozen turns. The candidate arm removes ``response_format`` only
from a catalog-matched P request and supplies the captured grammar after one
selected mechanical transformation. P7-J0 removes JSON-interior whitespace
references; P7-NT removes only the optional hidden ``thought`` root branch.

* rules whose left-hand side starts with ``response-format-schema`` lose only
  references to the generated ``space`` nonterminal;
* root/start/thought/fences, the global ``space`` rule, all seven P fields,
  enums, key order, prompts, sampling, budgets and downstream validators stay
  unchanged;
* the research transport deterministically extracts the JSON object from the
  retained fence, mirroring the extraction hidden inside ``response_format``.

The catalog normalizes only the two operation-enum rules and specializes them
to each fresh sidecar's current shortlist; every other schema byte must still
match. This isolates compact JSON interior whitespace from Gemma's learned
chat wrapper. A missing schema, grammar template, hash match, wire echo or
exact fence extraction falls closed and invalidates the measurement. No Core
operation is ever dispatched.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import tempfile
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for import_root in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from experiments.mind_router_spike import (  # noqa: E402
    benchmark_invalid_empty_length_retry as retry_benchmark,
)
from experiments.mind_router_spike import (  # noqa: E402
    benchmark_pv_response_format_direct_gbnf as response_format_benchmark,
)


PROFILE_BASELINE = "response-format"
PROFILE_P7_J0 = "p7-j0"
PROFILE_P7_NT = "p7-no-thought"
TARGET_STAGE = "P"
STRUCTURED_STAGES = retry_benchmark.TARGET_STAGES
CATALOG_SCHEMA = "baxy.primary-dynamic-p7-j0-grammar-catalog.v2"
REPORT_SCHEMA = "baxy.primary-dynamic-p7-j0-ab.v2"
DEFAULT_CASE_IDS = ("turn-00", "turn-06", "turn-15", "turn-23")
DEFAULT_OUTPUT = (
    ROOT / "artifacts" / "fixes" / "primary_dynamic_compact_grammar_smoke_20260730.json"
)
_SPACE_REFERENCE = re.compile(r"(?<![A-Za-z0-9-])space(?![A-Za-z0-9-])")
_OPERATION_RULE = "response-format-schema-operation"
_EFFECT_OPERATION_RULE = "response-format-schema-effect-operations-item"
_OPERATION_SENTINEL = "__BAXY_DYNAMIC_OPERATION__"
_ROOT_SPACE = re.compile(r"(?:| |\n{1,2}[ \t]{0,20})\Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _constraint_key(response_format_sha256: str) -> str:
    return response_format_benchmark._constraint_key(
        TARGET_STAGE,
        response_format_sha256,
    )


def _template_key(response_format_template_sha256: str) -> str:
    return f"{TARGET_STAGE}-template:{response_format_template_sha256}"


def _gbnf_enum_rule(rule_name: str, values: tuple[str, ...]) -> str:
    if not values:
        raise ValueError(f"{rule_name} cannot have an empty enum")
    alternatives = " | ".join(
        json.dumps(
            json.dumps(value, ensure_ascii=False),
            ensure_ascii=False,
        )
        for value in values
    )
    return f"{rule_name} ::= ({alternatives})"


def _replace_exact_enum_rule(
    grammar: str,
    *,
    rule_name: str,
    expected_values: tuple[str, ...],
    replacement_values: tuple[str, ...],
) -> str:
    lines = grammar.splitlines(keepends=True)
    indexes = [
        index for index, line in enumerate(lines) if _line_rule_name(line) == rule_name
    ]
    if len(indexes) != 1:
        raise ValueError(f"generated grammar must contain one {rule_name} rule")
    index = indexes[0]
    source_line = lines[index]
    source_body = source_line.rstrip("\r\n")
    ending = source_line[len(source_body) :]
    if source_body != _gbnf_enum_rule(rule_name, expected_values):
        raise ValueError(f"generated grammar {rule_name} enum is not exact")
    lines[index] = _gbnf_enum_rule(rule_name, replacement_values) + ending
    return "".join(lines)


def _operation_values(response_format: dict[str, Any]) -> tuple[str, ...]:
    if response_format.get("type") != "json_schema":
        raise ValueError("P response_format is not json_schema")
    envelope = response_format.get("json_schema")
    if not isinstance(envelope, dict):
        raise ValueError("P response_format has no json_schema envelope")
    schema = envelope.get("schema")
    if not isinstance(schema, dict):
        raise ValueError("P response_format has no schema")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("P response_format has no properties")
    operation = properties.get("operation")
    effect_operations = properties.get("effect_operations")
    if not isinstance(operation, dict) or not isinstance(effect_operations, dict):
        raise ValueError("P response_format has no operation enums")
    items = effect_operations.get("items")
    if not isinstance(items, dict):
        raise ValueError("P effect_operations has no item schema")
    operation_enum = operation.get("enum")
    effect_enum = items.get("enum")
    if not isinstance(operation_enum, list) or not isinstance(effect_enum, list):
        raise ValueError("P operation enums are not lists")
    if (
        not effect_enum
        or any(
            not isinstance(value, str) or not value or value == _OPERATION_SENTINEL
            for value in effect_enum
        )
        or len(set(effect_enum)) != len(effect_enum)
        or operation_enum != ["", *effect_enum]
    ):
        raise ValueError("P operation enums are inconsistent")
    return tuple(effect_enum)


def _response_format_template(
    response_format: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    operations = _operation_values(response_format)
    template = copy.deepcopy(response_format)
    properties = template["json_schema"]["schema"]["properties"]
    properties["operation"]["enum"] = ["", _OPERATION_SENTINEL]
    properties["effect_operations"]["items"]["enum"] = [_OPERATION_SENTINEL]
    return template, operations


def _normalize_source_grammar(
    source_grammar: str,
    operations: tuple[str, ...],
) -> str:
    normalized = _replace_exact_enum_rule(
        source_grammar,
        rule_name=_OPERATION_RULE,
        expected_values=("", *operations),
        replacement_values=("", _OPERATION_SENTINEL),
    )
    return _replace_exact_enum_rule(
        normalized,
        rule_name=_EFFECT_OPERATION_RULE,
        expected_values=operations,
        replacement_values=(_OPERATION_SENTINEL,),
    )


def _specialize_source_grammar(
    source_grammar_template: str,
    operations: tuple[str, ...],
) -> str:
    specialized = _replace_exact_enum_rule(
        source_grammar_template,
        rule_name=_OPERATION_RULE,
        expected_values=("", _OPERATION_SENTINEL),
        replacement_values=("", *operations),
    )
    return _replace_exact_enum_rule(
        specialized,
        rule_name=_EFFECT_OPERATION_RULE,
        expected_values=(_OPERATION_SENTINEL,),
        replacement_values=operations,
    )


def _line_rule_name(line: str) -> str | None:
    body = line.removesuffix("\n").removesuffix("\r")
    if "::=" not in body:
        return None
    name = body.split("::=", 1)[0].strip()
    return name or None


def _derive_p7_j0_grammar(
    source_grammar: str,
) -> tuple[str, dict[str, Any]]:
    """Remove JSON-interior ``space`` references and nothing outside P rules."""

    if not isinstance(source_grammar, str) or not source_grammar:
        raise ValueError("source grammar is empty")
    lines = source_grammar.splitlines(keepends=True)
    if "".join(lines) != source_grammar:
        raise AssertionError("grammar line splitting was not byte-exact")

    root_lines = [line for line in lines if _line_rule_name(line) == "root"]
    global_space_lines = [line for line in lines if _line_rule_name(line) == "space"]
    schema_indexes = [
        index
        for index, line in enumerate(lines)
        if (_line_rule_name(line) or "").startswith("response-format-schema")
    ]
    if len(root_lines) != 1:
        raise ValueError("generated grammar must contain exactly one root rule")
    if len(global_space_lines) != 1:
        raise ValueError("generated grammar must contain exactly one global space rule")
    if not schema_indexes:
        raise ValueError("generated grammar contains no response schema rules")

    candidate_lines = list(lines)
    mutated_rules: list[str] = []
    removed_references = 0
    for index in schema_indexes:
        source_line = lines[index]
        reference_count = len(_SPACE_REFERENCE.findall(source_line))
        if reference_count == 0:
            continue
        candidate_line = _SPACE_REFERENCE.sub("", source_line)
        if candidate_line == source_line:
            raise AssertionError("schema-space rewrite made no progress")
        candidate_lines[index] = candidate_line
        removed_references += reference_count
        rule_name = _line_rule_name(source_line)
        assert rule_name is not None
        mutated_rules.append(rule_name)

    if removed_references == 0 or not mutated_rules:
        raise ValueError("response schema grammar had no interior space references")
    for index in schema_indexes:
        if _SPACE_REFERENCE.search(candidate_lines[index]):
            raise AssertionError("candidate retains JSON-interior space")
    for index, (source_line, candidate_line) in enumerate(
        zip(lines, candidate_lines, strict=True)
    ):
        if index not in schema_indexes and source_line != candidate_line:
            raise AssertionError("candidate changed a non-schema grammar rule")

    candidate_grammar = "".join(candidate_lines)
    candidate_root_lines = [
        line for line in candidate_lines if _line_rule_name(line) == "root"
    ]
    candidate_space_lines = [
        line for line in candidate_lines if _line_rule_name(line) == "space"
    ]
    if candidate_root_lines != root_lines:
        raise AssertionError("P7-J0 changed Gemma's root/wrapper rule")
    if candidate_space_lines != global_space_lines:
        raise AssertionError("P7-J0 changed Gemma's global space rule")

    return candidate_grammar, {
        "source_grammar_sha256": _sha256_text(source_grammar),
        "candidate_grammar_sha256": _sha256_text(candidate_grammar),
        "root_rule": root_lines[0].removesuffix("\n").removesuffix("\r"),
        "global_space_rule": (
            global_space_lines[0].removesuffix("\n").removesuffix("\r")
        ),
        "schema_rule_count": len(schema_indexes),
        "mutated_rule_count": len(mutated_rules),
        "mutated_rules": mutated_rules,
        "removed_space_references": removed_references,
        "non_schema_rules_byte_exact": True,
        "root_rule_byte_exact": True,
        "global_space_rule_byte_exact": True,
    }


def _derive_p7_no_thought_grammar(
    source_grammar: str,
) -> tuple[str, dict[str, Any]]:
    """Remove only P's optional hidden-thought branch from the root rule."""

    source_rule = (
        'root ::= start (thought | )? "```json" space '
        'response-format-schema space "```"'
    )
    target_rule = (
        'root ::= start "```json" space response-format-schema space "```"'
    )
    lines = source_grammar.splitlines(keepends=True)
    indexes = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == source_rule
    ]
    if len(indexes) != 1:
        raise ValueError("generated grammar has an unexpected P root rule")
    index = indexes[0]
    ending = lines[index][len(lines[index].rstrip("\r\n")) :]
    candidate_lines = list(lines)
    candidate_lines[index] = target_rule + ending
    candidate = "".join(candidate_lines)
    if candidate == source_grammar:
        raise AssertionError("no-thought grammar made no progress")
    for other_index, (source_line, candidate_line) in enumerate(
        zip(lines, candidate_lines, strict=True)
    ):
        if other_index != index and source_line != candidate_line:
            raise AssertionError("no-thought grammar changed a non-root rule")
    return candidate, {
        "source_grammar_sha256": _sha256_text(source_grammar),
        "candidate_grammar_sha256": _sha256_text(candidate),
        "source_root_rule": source_rule,
        "candidate_root_rule": target_rule,
        "changed_rule_count": 1,
        "non_root_rules_byte_exact": True,
    }


def _derive_profile_grammar(
    source_grammar: str,
    profile: str,
) -> tuple[str, dict[str, Any]]:
    if profile == PROFILE_P7_J0:
        return _derive_p7_j0_grammar(source_grammar)
    if profile == PROFILE_P7_NT:
        return _derive_p7_no_thought_grammar(source_grammar)
    raise ValueError(f"unknown candidate grammar profile: {profile}")


def _extract_fenced_json_object(content: str) -> str:
    """Mirror response_format's deterministic chat-wrapper extraction."""

    retained_start = "<|turn>model\n"
    if content.startswith(retained_start):
        content = content[len(retained_start) :]
    prefix = "```json"
    suffix = "```"
    if not content.startswith(prefix) or not content.endswith(suffix):
        raise ValueError("wire content does not have the exact JSON fence")
    middle = content[len(prefix) : -len(suffix)]
    first_brace = middle.find("{")
    last_brace = middle.rfind("}")
    if first_brace < 0 or last_brace < first_brace:
        raise ValueError("wire fence contains no JSON object")
    leading = middle[:first_brace]
    body = middle[first_brace : last_brace + 1]
    trailing = middle[last_brace + 1 :]
    if (
        _ROOT_SPACE.fullmatch(leading) is None
        or _ROOT_SPACE.fullmatch(trailing) is None
    ):
        raise ValueError("wire fence whitespace violates the captured root rule")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("wire fence payload is not a JSON object")
    return body


def _replace_first_choice_content(
    response: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    adapted = copy.deepcopy(response)
    choices = adapted.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("response has no first choice")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("response has no first-choice text content")
    message["content"] = content
    return adapted


def _load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema") != CATALOG_SCHEMA
        or not isinstance(value.get("entries"), dict)
        or not isinstance(value.get("templates"), dict)
    ):
        raise ValueError("invalid P7-J0 grammar catalog")

    exact_entries: dict[str, dict[str, Any]] = {}
    for key, raw_entry in value["entries"].items():
        if not isinstance(key, str) or not isinstance(raw_entry, dict):
            raise ValueError("invalid P7-J0 grammar catalog entry")
        response_format = raw_entry.get("response_format")
        response_format_sha256 = raw_entry.get("response_format_sha256")
        source_grammar = raw_entry.get("source_grammar")
        candidate_grammar = raw_entry.get("candidate_grammar")
        if (
            raw_entry.get("stage") != TARGET_STAGE
            or not isinstance(response_format, dict)
            or not isinstance(response_format_sha256, str)
            or not isinstance(source_grammar, str)
            or not isinstance(candidate_grammar, str)
            or key != _constraint_key(response_format_sha256)
            or retry_benchmark._canonical_hash(response_format)
            != response_format_sha256
        ):
            raise ValueError("P7-J0 catalog contract mismatch")
        derived, derivation = _derive_p7_j0_grammar(source_grammar)
        if (
            derived != candidate_grammar
            or derivation["source_grammar_sha256"]
            != raw_entry.get("source_grammar_sha256")
            or derivation["candidate_grammar_sha256"]
            != raw_entry.get("candidate_grammar_sha256")
            or derivation["mutated_rules"] != raw_entry.get("mutated_rules")
            or derivation["removed_space_references"]
            != raw_entry.get("removed_space_references")
        ):
            raise ValueError("P7-J0 catalog derivation/hash mismatch")
        exact_entries[key] = raw_entry
    if not exact_entries:
        raise ValueError("P7-J0 grammar catalog is empty")

    templates: dict[str, dict[str, Any]] = {}
    for key, raw_template in value["templates"].items():
        if not isinstance(key, str) or not isinstance(raw_template, dict):
            raise ValueError("invalid P7-J0 grammar template")
        response_template = raw_template.get("response_format_template")
        response_template_sha256 = raw_template.get("response_format_template_sha256")
        source_template = raw_template.get("source_grammar_template")
        if (
            raw_template.get("stage") != TARGET_STAGE
            or not isinstance(response_template, dict)
            or not isinstance(response_template_sha256, str)
            or not isinstance(source_template, str)
            or key != _template_key(response_template_sha256)
            or retry_benchmark._canonical_hash(response_template)
            != response_template_sha256
            or _sha256_text(source_template)
            != raw_template.get("source_grammar_template_sha256")
        ):
            raise ValueError("P7-J0 grammar template contract mismatch")
        try:
            template_copy = copy.deepcopy(response_template)
            properties = template_copy["json_schema"]["schema"]["properties"]
            operation_enum = properties["operation"].get("enum")
            effect_enum = properties["effect_operations"]["items"].get("enum")
        except (KeyError, TypeError) as error:
            raise ValueError("P7-J0 response template shape is invalid") from error
        if operation_enum != ["", _OPERATION_SENTINEL] or effect_enum != [
            _OPERATION_SENTINEL
        ]:
            raise ValueError("P7-J0 response template sentinels are invalid")
        sentinel_source = _specialize_source_grammar(
            source_template,
            (_OPERATION_SENTINEL,),
        )
        if sentinel_source != source_template:
            raise ValueError("P7-J0 source template sentinels are invalid")
        candidate_template, template_derivation = _derive_p7_j0_grammar(source_template)
        if (
            candidate_template != raw_template.get("candidate_grammar_template")
            or template_derivation["candidate_grammar_sha256"]
            != raw_template.get("candidate_grammar_template_sha256")
            or raw_template.get("dynamic_rules")
            != [_OPERATION_RULE, _EFFECT_OPERATION_RULE]
        ):
            raise ValueError("P7-J0 grammar template derivation mismatch")
        templates[key] = raw_template
    if not templates:
        raise ValueError("P7-J0 grammar template catalog is empty")
    return templates


def _run_sidecar(
    profile: str,
    log_path: Path,
    catalog_path: Path | None,
) -> int:
    """Patch only this research child and enter the normal mind sidecar."""

    candidate_profiles = {PROFILE_P7_J0, PROFILE_P7_NT}
    if profile not in {PROFILE_BASELINE, *candidate_profiles}:
        raise ValueError(f"unknown profile: {profile}")
    if profile in candidate_profiles:
        if catalog_path is None:
            raise ValueError("candidate requires a captured grammar catalog")
        catalog = _load_catalog(catalog_path)
    else:
        if catalog_path is not None:
            raise ValueError("baseline cannot consume a grammar catalog")
        catalog = {}

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
            if stage == TARGET_STAGE and isinstance(response_format, dict)
            else None
        )
        catalog_key = (
            _constraint_key(response_format_sha256)
            if isinstance(response_format_sha256, str)
            else None
        )
        response_format_template_sha256: str | None = None
        catalog_template_key: str | None = None
        candidate_applied = False
        catalog_miss = False
        catalog_miss_reason: str | None = None
        expected_grammar: str | None = None
        specialized_source_grammar_sha256: str | None = None
        wire = dict(original)
        if stage in STRUCTURED_STAGES:
            wire["verbose"] = True
            wire["return_tokens"] = True
        if stage == TARGET_STAGE:
            if not isinstance(response_format, dict):
                raise RuntimeError("P reached the wire without response_format")
            if profile in candidate_profiles:
                try:
                    response_template, operations = _response_format_template(
                        response_format
                    )
                    response_format_template_sha256 = retry_benchmark._canonical_hash(
                        response_template
                    )
                    catalog_template_key = _template_key(
                        response_format_template_sha256
                    )
                    entry = catalog.get(catalog_template_key)
                    if entry is None:
                        raise ValueError("unseen response-format template")
                    source_template = str(entry["source_grammar_template"])
                    specialized_source = _specialize_source_grammar(
                        source_template,
                        operations,
                    )
                    if (
                        _normalize_source_grammar(
                            specialized_source,
                            operations,
                        )
                        != source_template
                    ):
                        raise ValueError("specialized grammar did not round-trip")
                    expected_grammar, _ = _derive_profile_grammar(
                        specialized_source,
                        profile,
                    )
                    specialized_source_grammar_sha256 = _sha256_text(specialized_source)
                except (KeyError, TypeError, ValueError) as error:
                    # Never invent a grammar for an unseen schema shape.
                    # Production response_format remains in force and the
                    # coverage gate must fail.
                    catalog_miss = True
                    catalog_miss_reason = str(error)
                else:
                    wire.pop("response_format", None)
                    wire["grammar"] = expected_grammar
                    candidate_applied = True

        case_id = str(getattr(self, "_primary_dynamic_compact_case", ""))
        with ordinal_lock:
            stage_key = (case_id, stage)
            stage_ordinal = ordinals.get(stage_key, 0)
            ordinals[stage_key] = stage_ordinal + 1
            global_ordinal = next_ordinal
            next_ordinal += 1

        prefix = {
            "profile": profile,
            "case_id": case_id,
            "stage": stage,
            "stage_ordinal": stage_ordinal,
            "global_ordinal": global_ordinal,
            "constraint_neutral_payload_sha256": (
                response_format_benchmark._constraint_neutral_payload_sha256(original)
            ),
            "response_format_sha256": response_format_sha256,
            "catalog_key": catalog_key,
            "response_format_template_sha256": (response_format_template_sha256),
            "catalog_template_key": catalog_template_key,
            "candidate_applied": candidate_applied,
            "catalog_miss": catalog_miss,
            "catalog_miss_reason": catalog_miss_reason,
            "specialized_source_grammar_sha256": (specialized_source_grammar_sha256),
            "expected_candidate_grammar_sha256": (
                _sha256_text(expected_grammar)
                if isinstance(expected_grammar, str)
                else None
            ),
            "wire_constraint": (
                profile
                if candidate_applied
                else (
                    PROFILE_BASELINE
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
                    **prefix,
                    "elapsed_seconds": time.perf_counter() - started,
                    "exception": type(error).__name__,
                }
            )
            raise

        elapsed = time.perf_counter() - started
        wire_response = response
        wire_content, finish_reason, raw_verbose, tokens = (
            retry_benchmark._response_parts(wire_response)
        )
        generated_grammar = response_format_benchmark._generated_grammar(response)
        wire_grammar_echo_equal = (
            generated_grammar == expected_grammar if candidate_applied else None
        )
        response_extraction_attempted = False
        response_extraction_applied = False
        response_extraction_error: str | None = None
        if candidate_applied and wire_grammar_echo_equal:
            response_extraction_attempted = True
            try:
                extracted_content = _extract_fenced_json_object(wire_content)
                response = _replace_first_choice_content(
                    wire_response,
                    extracted_content,
                )
                response_extraction_applied = True
            except (json.JSONDecodeError, ValueError) as error:
                response_extraction_error = str(error)
        content, _, _, _ = retry_benchmark._response_parts(response)
        try:
            parsed = json.loads(content)
            valid_json_object = isinstance(parsed, dict)
        except (json.JSONDecodeError, TypeError):
            valid_json_object = False
        metadata = retry_benchmark._response_metadata(wire_response)
        usage = metadata.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        timings = wire_response.get("timings")
        if not isinstance(timings, dict):
            timings = {}
        generated_grammar_sha256 = (
            _sha256_text(generated_grammar) if generated_grammar is not None else None
        )
        write_record(
            {
                **prefix,
                "elapsed_seconds": elapsed,
                "finish_reason": finish_reason,
                "empty_length": (finish_reason == "length" and not content.strip()),
                "valid_json_object": valid_json_object,
                "wire_content": wire_content,
                "wire_content_sha256": _sha256_text(wire_content),
                "content": content,
                "content_sha256": _sha256_text(content),
                "response_extraction_attempted": (response_extraction_attempted),
                "response_extraction_applied": response_extraction_applied,
                "response_extraction_error": response_extraction_error,
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
                    if stage == TARGET_STAGE and isinstance(response_format, dict)
                    else None
                ),
                "generated_grammar": (
                    generated_grammar if stage == TARGET_STAGE else None
                ),
                "generated_grammar_sha256": generated_grammar_sha256,
                "wire_grammar_echo_equal": (wire_grammar_echo_equal),
            }
        )
        return response

    def benchmark_prepare(
        message: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        llm = kwargs.get("llm")
        if llm is not None:
            llm._primary_dynamic_compact_case = str(message.get("id") or "")
        return original_prepare(message, **kwargs)

    LlmRuntime._post = benchmark_post
    sidecar_module._prepare_turn_result = benchmark_prepare
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post
        sidecar_module._prepare_turn_result = original_prepare


def _visible_reply_sha256(reply: dict[str, Any]) -> str:
    visible = retry_benchmark._visible_reply(reply)
    return retry_benchmark._canonical_hash(visible)


def _run_arm(
    *,
    profile: str,
    run_id: str,
    log_path: Path,
    catalog_path: Path | None,
    runtime: Any,
    capabilities: list[dict[str, Any]],
    case_ids: tuple[str, ...],
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
    if catalog_path is not None:
        command.extend(["--grammar-catalog", str(catalog_path.resolve())])

    selected = set(case_ids)
    workload = [
        item
        for item in build_workload()
        if item.request_type == "turn.decide" and item.case_id in selected
    ]
    if {item.case_id for item in workload} != selected:
        raise ValueError("selected case IDs are not in the frozen turn workload")

    client = JsonLineProcess(command, environment=environment, cwd=ROOT)
    observations: list[dict[str, Any]] = []
    arm_started = time.perf_counter()
    ready_seconds: float | None = None
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar hello rejected")
        catalog_ready = client.request(
            {
                "type": "catalog.configure",
                "id": f"catalog-{run_id}",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if catalog_ready.get("type") != "catalog.ready":
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
                    "text_sha256": _sha256_text(str(item.message["text"])),
                    "elapsed_seconds": elapsed,
                    "validation_error": validation_error or None,
                    "reply": reply,
                    "visible_reply_sha256": _visible_reply_sha256(reply),
                    "decision_projection": (
                        response_format_benchmark._decision_projection(reply)
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
    captures: list[dict[str, Any]] = []
    posts: list[dict[str, Any]] = []
    for raw_post in raw_posts:
        post = dict(raw_post)
        source_response_format = post.pop("source_response_format", None)
        generated_grammar = post.pop("generated_grammar", None)
        if (
            post.get("stage") == TARGET_STAGE
            and isinstance(source_response_format, dict)
            and isinstance(generated_grammar, str)
        ):
            captures.append(
                {
                    "case_id": post.get("case_id"),
                    "response_format": source_response_format,
                    "response_format_sha256": post.get("response_format_sha256"),
                    "source_grammar": generated_grammar,
                    "source_grammar_sha256": post.get("generated_grammar_sha256"),
                }
            )
        posts.append(post)

    latencies = [float(row["elapsed_seconds"]) for row in observations]
    primary_posts = [post for post in posts if post.get("stage") == TARGET_STAGE]
    structured_posts = [
        post for post in posts if post.get("stage") in STRUCTURED_STAGES
    ]
    return {
        "run_id": run_id,
        "profile": profile,
        "ready_seconds": ready_seconds,
        "elapsed_total_seconds": time.perf_counter() - arm_started,
        "turn_elapsed_total_seconds": sum(latencies),
        "turn_latency_seconds": {
            "p50": statistics.median(latencies),
            "p95_nearest_rank": retry_benchmark._quantile(
                latencies,
                0.95,
            ),
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
        "candidate_applied_posts": sum(
            post.get("candidate_applied") is True for post in primary_posts
        ),
        "primary_constraint_posts": len(primary_posts),
        "grammar_catalog_misses": sum(
            post.get("catalog_miss") is True for post in primary_posts
        ),
        "primary_post_exceptions": sum(
            isinstance(post.get("exception"), str) for post in primary_posts
        ),
        "wire_grammar_echo_mismatches": sum(
            post.get("candidate_applied") is True
            and not isinstance(post.get("exception"), str)
            and post.get("wire_grammar_echo_equal") is not True
            for post in primary_posts
        ),
        "wire_grammar_echo_observed_posts": sum(
            post.get("candidate_applied") is True
            and not isinstance(post.get("exception"), str)
            for post in primary_posts
        ),
        "response_extraction_applied_posts": sum(
            post.get("response_extraction_applied") is True for post in primary_posts
        ),
        "response_extraction_failures": sum(
            post.get("candidate_applied") is True
            and not isinstance(post.get("exception"), str)
            and post.get("response_extraction_applied") is not True
            for post in primary_posts
        ),
        "structured_post_elapsed_total_seconds": sum(
            float(post.get("elapsed_seconds") or 0.0) for post in structured_posts
        ),
        "primary_post_metrics": (
            response_format_benchmark._post_metrics(primary_posts)
        ),
        "grammar_captures": captures,
        "observations": observations,
        "posts": posts,
    }


def _build_catalog(baseline: dict[str, Any]) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    templates: dict[str, dict[str, Any]] = {}
    observed_keys = {
        str(post["catalog_key"])
        for post in baseline["posts"]
        if post.get("stage") == TARGET_STAGE
        and isinstance(post.get("catalog_key"), str)
    }
    for capture in baseline["grammar_captures"]:
        response_format = capture.get("response_format")
        response_format_sha256 = capture.get("response_format_sha256")
        source_grammar = capture.get("source_grammar")
        if (
            not isinstance(response_format, dict)
            or not isinstance(response_format_sha256, str)
            or not isinstance(source_grammar, str)
            or retry_benchmark._canonical_hash(response_format)
            != response_format_sha256
            or _sha256_text(source_grammar) != capture.get("source_grammar_sha256")
        ):
            raise ValueError("invalid dynamic P grammar capture")
        candidate_grammar, derivation = _derive_p7_j0_grammar(source_grammar)
        key = _constraint_key(response_format_sha256)
        entry = {
            "stage": TARGET_STAGE,
            "response_format": response_format,
            "response_format_sha256": response_format_sha256,
            "source": "__verbose.generation_settings.grammar",
            "source_grammar": source_grammar,
            "source_grammar_sha256": derivation["source_grammar_sha256"],
            "candidate_grammar": candidate_grammar,
            "candidate_grammar_sha256": derivation["candidate_grammar_sha256"],
            "root_rule": derivation["root_rule"],
            "global_space_rule": derivation["global_space_rule"],
            "schema_rule_count": derivation["schema_rule_count"],
            "mutated_rule_count": derivation["mutated_rule_count"],
            "mutated_rules": derivation["mutated_rules"],
            "removed_space_references": derivation["removed_space_references"],
            "non_schema_rules_byte_exact": True,
            "root_rule_byte_exact": True,
            "global_space_rule_byte_exact": True,
            "capture_count": 1,
        }
        existing = entries.get(key)
        if existing is None:
            entries[key] = entry
        else:
            stable_fields = (
                "response_format",
                "response_format_sha256",
                "source_grammar",
                "source_grammar_sha256",
                "candidate_grammar",
                "candidate_grammar_sha256",
                "root_rule",
                "global_space_rule",
                "mutated_rules",
                "removed_space_references",
            )
            if any(existing[field] != entry[field] for field in stable_fields):
                raise ValueError(
                    "llama.cpp generated inconsistent grammar for one P schema"
                )
            existing["capture_count"] = int(existing["capture_count"]) + 1

        response_template, operations = _response_format_template(response_format)
        response_template_sha256 = retry_benchmark._canonical_hash(response_template)
        source_template = _normalize_source_grammar(
            source_grammar,
            operations,
        )
        if _specialize_source_grammar(source_template, operations) != source_grammar:
            raise ValueError("dynamic operation grammar did not round-trip")
        candidate_template, template_derivation = _derive_p7_j0_grammar(source_template)
        template_key = _template_key(response_template_sha256)
        template_entry = {
            "stage": TARGET_STAGE,
            "response_format_template": response_template,
            "response_format_template_sha256": response_template_sha256,
            "source": "__verbose.generation_settings.grammar",
            "source_grammar_template": source_template,
            "source_grammar_template_sha256": _sha256_text(source_template),
            "candidate_grammar_template": candidate_template,
            "candidate_grammar_template_sha256": template_derivation[
                "candidate_grammar_sha256"
            ],
            "dynamic_rules": [_OPERATION_RULE, _EFFECT_OPERATION_RULE],
            "specialization_round_trip_exact": True,
            "capture_count": 1,
            "captured_response_format_sha256": [response_format_sha256],
        }
        existing_template = templates.get(template_key)
        if existing_template is None:
            templates[template_key] = template_entry
        else:
            template_stable_fields = (
                "response_format_template",
                "response_format_template_sha256",
                "source_grammar_template",
                "source_grammar_template_sha256",
                "candidate_grammar_template",
                "candidate_grammar_template_sha256",
                "dynamic_rules",
            )
            if any(
                existing_template[field] != template_entry[field]
                for field in template_stable_fields
            ):
                raise ValueError("llama.cpp generated inconsistent P grammar templates")
            existing_template["capture_count"] = (
                int(existing_template["capture_count"]) + 1
            )
            hashes = existing_template["captured_response_format_sha256"]
            if response_format_sha256 not in hashes:
                hashes.append(response_format_sha256)

    missing = sorted(observed_keys - set(entries))
    if missing:
        raise ValueError(
            "baseline did not expose generated P grammar for: " + ", ".join(missing)
        )
    if not entries:
        raise ValueError("baseline captured no P grammar")
    return {
        "schema": CATALOG_SCHEMA,
        "source_run_id": baseline["run_id"],
        "derivation": (
            "Remove the `space` nonterminal only from rules whose LHS "
            "starts with `response-format-schema`; retain every non-schema "
            "rule, including root/thought/fences/global space, byte-exact. "
            "Normalize and specialize only the two operation-enum rules so "
            "fresh-sidecar shortlist changes cannot become false misses."
        ),
        "entries": entries,
        "templates": templates,
    }


def _paired_primary_post_hashes(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    def indexed(arm: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(post.get("case_id")): post
            for post in arm["posts"]
            if post.get("stage") == TARGET_STAGE
            and int(post.get("stage_ordinal") or 0) == 0
        }

    left = indexed(baseline)
    right = indexed(candidate)
    shared = sorted(set(left) & set(right))
    mismatches = [
        {"case_id": case_id, "stage_ordinal": 0}
        for case_id in shared
        if left[case_id].get("constraint_neutral_payload_sha256")
        != right[case_id].get("constraint_neutral_payload_sha256")
    ]
    all_initial_cases_paired = set(left) == set(right)
    hashes_equal = all_initial_cases_paired and not mismatches
    return {
        "baseline_initial_posts": len(left),
        "candidate_initial_posts": len(right),
        "shared_initial_posts": len(shared),
        "all_initial_cases_paired": all_initial_cases_paired,
        "initial_constraint_neutral_hash_mismatches": mismatches,
        "confounded_case_ids": [row["case_id"] for row in mismatches],
        "initial_constraint_neutral_hashes_equal": hashes_equal,
    }


def _compare_pair(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    pair_id: str,
) -> dict[str, Any]:
    comparison = retry_benchmark._compare_pair(
        pair_id,
        baseline,
        candidate,
    )
    baseline_by_id = {row["case_id"]: row for row in baseline["observations"]}
    candidate_by_id = {row["case_id"]: row for row in candidate["observations"]}
    comparison["decision_projections_equal"] = all(
        case_id in candidate_by_id
        and baseline_by_id[case_id]["decision_projection"]
        == candidate_by_id[case_id]["decision_projection"]
        for case_id in baseline_by_id
    ) and set(baseline_by_id) == set(candidate_by_id)
    comparison["visible_reply_hashes_equal"] = all(
        case_id in candidate_by_id
        and baseline_by_id[case_id]["visible_reply_sha256"]
        == candidate_by_id[case_id]["visible_reply_sha256"]
        for case_id in baseline_by_id
    ) and set(baseline_by_id) == set(candidate_by_id)
    comparison["primary_post_pairing"] = _paired_primary_post_hashes(
        baseline,
        candidate,
    )
    comparison["primary_post_metrics"] = {
        "baseline": baseline["primary_post_metrics"],
        "candidate": candidate["primary_post_metrics"],
        "candidate_minus_baseline": (
            response_format_benchmark._metric_comparison(
                candidate["primary_post_metrics"],
                baseline["primary_post_metrics"],
            )
        ),
    }
    return comparison


def _run_experiment(
    output: Path,
    case_ids: tuple[str, ...],
    *,
    arm_order: str,
    catalog_source: Path | None,
    candidate_profile: str,
) -> int:
    from scripts.baxy_runtime_config import (
        DEFAULT_RUNTIME_MANIFEST,
        public_runtime_identity,
        resolve_runtime,
    )
    from scripts.measure_mind_budget import (
        build_workload,
        current_core_capabilities,
        discover_core,
        write_json_atomic,
    )

    user_dotnet = Path.home() / ".dotnet"
    if (user_dotnet / "dotnet.exe").is_file():
        os.environ["DOTNET_ROOT"] = str(user_dotnet)
        os.environ["DOTNET_ROOT_X64"] = str(user_dotnet)

    valid_ids = {
        item.case_id for item in build_workload() if item.request_type == "turn.decide"
    }
    if not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("--case values must be non-empty and unique")
    if not set(case_ids) <= valid_ids:
        unknown = sorted(set(case_ids) - valid_ids)
        raise ValueError("unknown frozen turn cases: " + ", ".join(unknown))

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(discover_core(None))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="primary-dynamic-grammar-",
        dir=str(output.parent),
    ) as temporary:
        temp_root = Path(temporary).resolve()
        catalog_path = temp_root / "grammar-catalog.json"
        if arm_order == "baseline-candidate":
            baseline = _run_arm(
                profile=PROFILE_BASELINE,
                run_id="baseline-response-format",
                log_path=temp_root / "baseline.jsonl",
                catalog_path=None,
                runtime=runtime,
                capabilities=capabilities,
                case_ids=case_ids,
            )
            grammar_catalog = _build_catalog(baseline)
        elif arm_order == "candidate-baseline":
            if catalog_source is None:
                raise ValueError(
                    "--catalog-source is required for candidate-baseline"
                )
            try:
                catalog_document = json.loads(
                    catalog_source.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid --catalog-source: {exc}") from exc
            if isinstance(catalog_document.get("grammar_catalog"), dict):
                catalog_document = catalog_document.get("grammar_catalog")
            if (
                not isinstance(catalog_document, dict)
                or catalog_document.get("schema") != CATALOG_SCHEMA
            ):
                raise ValueError("--catalog-source has no valid grammar catalog")
            grammar_catalog = catalog_document
        else:
            raise ValueError(f"unknown arm order: {arm_order}")
        catalog_path.write_text(
            json.dumps(
                grammar_catalog,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        if arm_order == "baseline-candidate":
            candidate = _run_arm(
                profile=candidate_profile,
                run_id=f"candidate-{candidate_profile}",
                log_path=temp_root / "candidate.jsonl",
                catalog_path=catalog_path,
                runtime=runtime,
                capabilities=capabilities,
                case_ids=case_ids,
            )
        else:
            candidate = _run_arm(
                profile=candidate_profile,
                run_id=f"candidate-{candidate_profile}",
                log_path=temp_root / "candidate.jsonl",
                catalog_path=catalog_path,
                runtime=runtime,
                capabilities=capabilities,
                case_ids=case_ids,
            )
            baseline = _run_arm(
                profile=PROFILE_BASELINE,
                run_id="baseline-response-format",
                log_path=temp_root / "baseline.jsonl",
                catalog_path=None,
                runtime=runtime,
                capabilities=capabilities,
                case_ids=case_ids,
            )

    comparison = _compare_pair(
        baseline,
        candidate,
        pair_id=(
            f"baseline-then-{candidate_profile}"
            if arm_order == "baseline-candidate"
            else f"{candidate_profile}-then-baseline"
        ),
    )
    workload_complete = all(
        len(arm["observations"]) == len(case_ids) for arm in (baseline, candidate)
    )
    validation_clean = all(
        arm["validation_errors"] == 0 for arm in (baseline, candidate)
    )
    candidate_coverage_complete = (
        candidate["primary_constraint_posts"] > 0
        and candidate["candidate_applied_posts"]
        == candidate["primary_constraint_posts"]
        and candidate["grammar_catalog_misses"] == 0
    )
    primary_posts_exception_free = all(
        arm["primary_post_exceptions"] == 0 for arm in (baseline, candidate)
    )
    wire_grammar_echo_exact = (
        candidate["wire_grammar_echo_mismatches"] == 0
        and candidate["wire_grammar_echo_observed_posts"]
        == candidate["candidate_applied_posts"]
    )
    response_extraction_exact = (
        candidate["response_extraction_failures"] == 0
        and candidate["response_extraction_applied_posts"]
        == candidate["candidate_applied_posts"]
    )
    neutral_hashes_equal = comparison["primary_post_pairing"][
        "initial_constraint_neutral_hashes_equal"
    ]
    decisions_equal = (
        comparison["all_cases_present"]
        and comparison["decision_projections_equal"]
        and comparison["effect_projections_equal"]
        and comparison["candidate_unsafe_deltas"] == 0
    )
    replies_equal = (
        comparison["semantic_replies_equal"]
        and comparison["visible_replies_equal"]
        and comparison["visible_reply_hashes_equal"]
    )
    measurement_valid = (
        workload_complete
        and validation_clean
        and candidate_coverage_complete
        and primary_posts_exception_free
        and wire_grammar_echo_exact
        and response_extraction_exact
        and neutral_hashes_equal
        and decisions_equal
        and replies_equal
    )
    baseline_tokens = baseline["primary_post_metrics"]["completion_tokens"]["sum"]
    candidate_tokens = candidate["primary_post_metrics"]["completion_tokens"]["sum"]
    tokens_lower = (
        isinstance(baseline_tokens, (int, float))
        and isinstance(candidate_tokens, (int, float))
        and candidate_tokens < baseline_tokens
    )
    p50_lower = (
        candidate["turn_latency_seconds"]["p50"]
        < baseline["turn_latency_seconds"]["p50"]
    )
    hypothesis_supported = measurement_valid and tokens_lower and p50_lower

    result = {
        "schema": (
            REPORT_SCHEMA
            if candidate_profile == PROFILE_P7_J0
            else "baxy.primary-dynamic-p7-no-thought-ab.v1"
        ),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_status": "research_only",
        "measurement_outcome": (
            "hypothesis_supported"
            if hypothesis_supported
            else (
                "valid_but_not_faster" if measurement_valid else "invalid_measurement"
            )
        ),
        "effects_executed": 0,
        "candidate": {
            "name": (
                "P7-J0"
                if candidate_profile == PROFILE_P7_J0
                else "P7-NT"
            ),
            "profile": candidate_profile,
            "target_stage": TARGET_STAGE,
            "source": "__verbose.generation_settings.grammar",
            "wire_delta": {
                "response_format": "removed only for catalog-matched P posts",
                "grammar": (
                    (
                        "captured schema-template grammar specialized to the "
                        "current operation shortlist, with `space` removed only "
                        "inside response-format-schema* rules"
                    )
                    if candidate_profile == PROFILE_P7_J0
                    else (
                        "captured schema-template grammar with only the "
                        "optional hidden `thought` branch removed from root"
                    )
                ),
                "response_adapter": (
                    "exactly unwrap the captured root's ```json ... ``` "
                    "envelope before the unchanged product JSON parser"
                ),
            },
            "unchanged": [
                "TURN_POLICY_PROMPT and all messages",
                "seven P fields, enums and key order",
                (
                    "root, start, thought, fences and global space rule"
                    if candidate_profile == PROFILE_P7_J0
                    else (
                        "all non-root rules, start, fences, schema fields, "
                        "enums and global space rule"
                    )
                ),
                "temperature, seeds, max_tokens and request budgets",
                "product parsing after deterministic envelope extraction, "
                "canonicalization and authority validators",
                "G, L, V, C and every non-P stage",
            ],
        },
        "workload": {
            "case_ids": list(case_ids),
            "turns_per_arm": len(case_ids),
            "arm_order": (
                [PROFILE_BASELINE, candidate_profile]
                if arm_order == "baseline-candidate"
                else [candidate_profile, PROFILE_BASELINE]
            ),
            "catalog_source": (
                str(catalog_source.resolve())
                if catalog_source is not None
                else "captured_from_first_baseline_arm"
            ),
            "fresh_sidecar_and_llama_server_per_arm": True,
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
            "dynamic_catalog_hashes_validated": True,
            "candidate_coverage_complete": candidate_coverage_complete,
            "primary_posts_exception_free": primary_posts_exception_free,
            "wire_grammar_echo_exact": wire_grammar_echo_exact,
            "response_extraction_exact": response_extraction_exact,
            "initial_constraint_neutral_payload_hashes_equal": (neutral_hashes_equal),
            "decisions_and_effects_equal": decisions_equal,
            "semantic_and_visible_replies_equal": replies_equal,
            "primary_completion_tokens_lower": tokens_lower,
            "turn_p50_lower": p50_lower,
            "measurement_valid": measurement_valid,
            "hypothesis_supported": hypothesis_supported,
        },
        "evaluation_rule": (
            "The measurement is valid only with every selected turn present "
            "and contract-valid, dynamic catalog/hash coverage for every P "
            "post, no P exception, exact wire grammar echo and deterministic "
            "JSON-envelope extraction, equal initial constraint-neutral "
            "payload hashes, exact decisions/effects/replies and zero unsafe "
            "effect deltas. Speed is supported only if P completion-token "
            "sum and turn p50 are both lower."
        ),
        "grammar_catalog": grammar_catalog,
        "comparison": comparison,
        "arms": [baseline, candidate],
    }
    write_json_atomic(output, result)
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "measurement_outcome": result["measurement_outcome"],
                "gates": result["gates"],
                "turn_latency_seconds": {
                    arm["profile"]: arm["turn_latency_seconds"]
                    for arm in result["arms"]
                },
                "primary_completion_tokens": {
                    arm["profile"]: arm["primary_post_metrics"]["completion_tokens"]
                    for arm in result["arms"]
                },
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
        "--case",
        dest="case_ids",
        action="append",
        help=(
            "Frozen turn case to measure; repeat for multiple cases. "
            "Defaults to turn-00, turn-06, turn-15 and turn-23."
        ),
    )
    parser.add_argument(
        "--arm-order",
        choices=("baseline-candidate", "candidate-baseline"),
        default="baseline-candidate",
    )
    parser.add_argument(
        "--candidate-profile",
        choices=(PROFILE_P7_J0, PROFILE_P7_NT),
        default=PROFILE_P7_J0,
    )
    parser.add_argument(
        "--catalog-source",
        type=Path,
        help=(
            "Prior valid report or direct catalog required when the candidate "
            "must run before the fresh baseline."
        ),
    )
    parser.add_argument(
        "--sidecar-profile",
        choices=(PROFILE_BASELINE, PROFILE_P7_J0, PROFILE_P7_NT),
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
    case_ids = tuple(args.case_ids or DEFAULT_CASE_IDS)
    catalog_source = (
        args.catalog_source.resolve()
        if args.catalog_source is not None
        else None
    )
    if args.arm_order == "candidate-baseline" and catalog_source is None:
        parser.error("--catalog-source is required for candidate-baseline")
    if (
        args.arm_order == "baseline-candidate"
        and catalog_source is not None
    ):
        parser.error("--catalog-source is only valid for candidate-baseline")
    try:
        return _run_experiment(
            output,
            case_ids,
            arm_order=args.arm_order,
            catalog_source=catalog_source,
            candidate_profile=args.candidate_profile,
        )
    except ValueError as error:
        parser.error(str(error))
    raise AssertionError("argparse.error must terminate")


if __name__ == "__main__":
    raise SystemExit(main())
