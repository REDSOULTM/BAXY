"""Physical A/B for compact exact GBNF on BAXY action validators V and C."""

from __future__ import annotations

import argparse
import json
import os
import statistics
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

_ORIGINAL_COMPACTOR = llm_module._compact_structured_grammar


def _candidate_compactor(payload: dict[str, Any]) -> str | None:
    existing = _ORIGINAL_COMPACTOR(payload)
    if existing is not None:
        return existing
    response_format = payload.get("response_format")
    if (
        not isinstance(response_format, dict)
        or response_format.get("type") != "json_schema"
    ):
        return None
    envelope = response_format.get("json_schema")
    if not isinstance(envelope, dict) or envelope.get("strict") is not True:
        return None
    schema = envelope.get("schema")
    if not isinstance(schema, dict):
        return None
    name = envelope.get("name")
    if name == "baxy_effect_count_verification" and schema == {
        "type": "object",
        "properties": {
            "effect_count": {
                "type": "string",
                "enum": ["zero", "one", "multiple"],
            }
        },
        "required": ["effect_count"],
        "additionalProperties": False,
    }:
        return "\n".join(
            [
                'root ::= "{\\"effect_count\\":" effect-count "}"',
                'effect-count ::= "\\"zero\\"" | "\\"one\\"" | "\\"multiple\\""',
            ]
        )
    if name == "baxy_operation_compatibility" and schema == {
        "type": "object",
        "properties": {"compatible": {"type": "boolean"}},
        "required": ["compatible"],
        "additionalProperties": False,
    }:
        return "\n".join(
            [
                'root ::= "{\\"compatible\\":" compatible "}"',
                'compatible ::= "true" | "false"',
            ]
        )
    return None


def _run_arm(profile: str) -> dict[str, Any]:
    llm_module._compact_structured_grammar = (
        _candidate_compactor if profile == "compact" else _ORIGINAL_COMPACTOR
    )
    runtime = InstrumentedRuntime(profile)
    cases: list[dict[str, Any]] = []
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        for case in CASES:
            cases.append(_run_case(runtime, case))
    finally:
        runtime.close()
        llm_module._compact_structured_grammar = _ORIGINAL_COMPACTOR
    elapsed = [float(case["elapsed_seconds"]) for case in cases]
    return {
        "profile": profile,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "elapsed_p50_seconds": statistics.median(elapsed),
        "elapsed_total_seconds": sum(elapsed),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
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
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("official runtime assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    arms = [_run_arm(profile) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    schema_projection = [
        _case_projection(case) for case in by_profile["schema"]["cases"]
    ]
    compact_projection = [
        _case_projection(case) for case in by_profile["compact"]["cases"]
    ]
    exact_outputs = schema_projection == compact_projection
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    result = {
        "schema": "baxy.compact-action-validators-ab.v1",
        "arm_order": arm_order,
        "runtime": {
            "server": str(args.server.resolve()),
            "model": str(args.model.resolve()),
            "parallel": 3,
            "context_per_slot": 4096,
        },
        "candidate": [
            "baxy_effect_count_verification",
            "baxy_operation_compatibility",
        ],
        "exact_outputs": exact_outputs,
        "mode_contracts": mode_contracts,
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Promote only after opposite-order replicas preserve every output, "
            "all expected modes, and improve V/C plus action end-to-end without "
            "a material tail regression."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if exact_outputs and mode_contracts else 2


if __name__ == "__main__":
    raise SystemExit(main())
