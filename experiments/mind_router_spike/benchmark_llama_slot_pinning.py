"""Physical A/B for llama.cpp slot pinning in BAXY's three-slot pipeline.

The benchmark is deliberately isolated from product code.  Both arms use the
official registered ``llama-server`` profile and the same public ``LlmRuntime``
contracts.  The pinned arm adds only llama.cpp's request-local ``id_slot`` to
the initial P/G/L calls, while the auto arm removes those three fields to
reproduce the pre-promotion scheduler:

* slot 0: primary turn policy (P)
* slot 1: independent semantic guard (G)
* slot 2: independent language detector (L)

All later V/C/chat/argument calls retain automatic scheduling.  Each arm gets
a fresh server so the measured ``cache_n``, ``prompt_n`` and ``prompt_ms``
values cannot inherit state from the other arm.  No manifest, installation,
model, prompt, schema or authority boundary is changed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import statistics
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import llm as llm_module  # noqa: E402
from baxy_mind.llm import DirectArgumentExtraction, LlmRuntime  # noqa: E402


def _schema(
    properties: dict[str, dict[str, Any]],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


TOOLS: dict[str, dict[str, Any]] = {
    "task.create": {
        "description": (
            "Crea una tarea local privada; la fecha opcional es metadato y no "
            "programa recordatorios."
        ),
        "schema": _schema(
            {
                "details": {"type": "string", "x-maxUtf8Bytes": 65_536},
                "due": {"type": ["string", "null"], "maxLength": 64},
                "title": {
                    "type": "string",
                    "x-maxUtf8Bytes": 1_024,
                    "x-nonWhitespace": True,
                },
            },
            ["title"],
        ),
    },
    "note.create": {
        "description": "Crea una nota privada local y verifica su relectura.",
        "schema": _schema(
            {
                "content": {"type": "string", "x-maxUtf8Bytes": 65_536},
                "title": {
                    "type": "string",
                    "x-maxUtf8Bytes": 512,
                    "x-nonWhitespace": True,
                },
            },
            ["content", "title"],
        ),
    },
    "web.search": {
        "description": (
            "Busca mediante un proveedor web configurado y devuelve resultados "
            "estructurados acotados."
        ),
        "schema": _schema(
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "query": {
                    "type": "string",
                    "x-maxUtf8Bytes": 2_000,
                    "x-nonWhitespace": True,
                },
            },
            ["query"],
        ),
    },
}


@dataclass(frozen=True)
class Case:
    name: str
    text: str
    expected_mode: str


CASES = (
    Case(
        "task_create_a",
        "Crea una tarea titulada preparar el informe trimestral",
        "action",
    ),
    Case(
        "knowledge_a",
        "¿Qué es la fotosíntesis?",
        "conversation",
    ),
    Case(
        "note_create_a",
        "Crea una nota titulada Aurora con contenido revisar el presupuesto",
        "action",
    ),
    Case(
        "knowledge_b",
        "¿Por qué el cielo se ve azul?",
        "conversation",
    ),
    Case(
        "task_create_b",
        "Crea una tarea titulada revisar el presupuesto anual",
        "action",
    ),
    Case(
        "knowledge_c",
        "Explícame brevemente qué causa las mareas",
        "conversation",
    ),
)

_PINNED_SLOTS = {"P": 0, "G": 1, "L": 2}


def _candidate(name: str) -> dict[str, Any]:
    contract = TOOLS[name]
    return {
        "name": name,
        "description": contract["description"],
        "arguments_schema": copy.deepcopy(contract["schema"]),
    }


def _tool(name: str) -> dict[str, Any]:
    contract = TOOLS[name]
    return {
        "type": "function",
        "function": {
            "name": name.replace(".", "_"),
            "canonical_name": name,
            "description": contract["description"],
            "parameters": copy.deepcopy(contract["schema"]),
        },
    }


def _stage(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    system = ""
    if (
        isinstance(messages, list)
        and messages
        and isinstance(messages[0], dict)
    ):
        system = str(messages[0].get("content") or "")
    if system == llm_module.TURN_POLICY_PROMPT:
        return "P"
    if system == llm_module.SEMANTIC_EFFECT_GUARD_PROMPT:
        return "G"
    if system == llm_module.RESPONSE_LANGUAGE_PROMPT:
        return "L"
    if system == llm_module.EFFECT_COUNT_VERIFIER_PROMPT:
        return "V"
    if system == llm_module.OPERATION_COMPATIBILITY_PROMPT:
        return "C"
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        envelope = response_format.get("json_schema")
        if (
            isinstance(envelope, dict)
            and envelope.get("name") == "direct_grounded_arguments"
        ):
            return "E"
    if system == llm_module.SYSTEM_PROMPT:
        return "chat"
    return "other"


def _payload_fingerprint(payload: dict[str, Any]) -> str:
    canonical = dict(payload)
    canonical.pop("id_slot", None)
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _response_content(response: dict[str, Any]) -> str:
    try:
        return str(response["choices"][0]["message"].get("content") or "")
    except (KeyError, IndexError, TypeError):
        return ""


class InstrumentedRuntime(LlmRuntime):
    def __init__(self, arm: str) -> None:
        self._benchmark_arm = arm
        self._benchmark_case = ""
        self._benchmark_records: list[dict[str, Any]] = []
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
        stage = _stage(wire)
        if stage in _PINNED_SLOTS:
            if self._benchmark_arm == "pinned":
                wire["id_slot"] = _PINNED_SLOTS[stage]
            elif self._benchmark_arm == "auto":
                wire.pop("id_slot", None)
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
            "case": self._benchmark_case,
            "stage": stage,
            "id_slot": wire.get("id_slot"),
            "payload_sha256": _payload_fingerprint(wire),
            "elapsed_seconds": elapsed,
            "cache_n": timings.get("cache_n"),
            "prompt_n": timings.get("prompt_n"),
            "prompt_ms": timings.get("prompt_ms"),
            "predicted_n": timings.get("predicted_n"),
            "predicted_ms": timings.get("predicted_ms"),
            "content": _response_content(response),
        }
        with self._benchmark_lock:
            self._benchmark_records.append(record)
        return response


def _extraction_json(
    extraction: DirectArgumentExtraction | None,
) -> dict[str, Any] | None:
    if extraction is None:
        return None
    return {
        "arguments": copy.deepcopy(extraction.arguments),
        "evidence": [list(item) for item in extraction.evidence],
        "fallback_question": extraction.fallback_question,
    }


def _run_case(
    runtime: InstrumentedRuntime,
    case: Case,
) -> dict[str, Any]:
    runtime._benchmark_case = case.name
    started = time.perf_counter()
    runtime.begin_request(55.0)
    decision: dict[str, Any]
    extraction: DirectArgumentExtraction | None = None
    response_language: str | None = None
    reply: str | None = None
    try:
        decision = runtime.decide_turn(
            case.text,
            [_candidate(name) for name in TOOLS],
            evidence=[],
        )
        mode = str(decision.get("mode") or "")
        if mode == "action":
            operation = decision.get("operation")
            if isinstance(operation, str) and operation in TOOLS:
                extraction = runtime.extract_direct_arguments(
                    case.text,
                    _tool(operation),
                )
            runtime.retire_deferred_response_language(case.text)
        elif mode == "conversation":
            _, deferred_language = runtime.consume_deferred_response_language(
                case.text
            )
            response_language = (
                deferred_language
                if deferred_language in {"es", "en", "mixed"}
                else runtime.detect_response_language(case.text)
            )
            reply, _ = runtime.chat(
                case.text,
                history=[],
                tools=None,
                temperature=0.0,
                conversation_kind=str(
                    decision.get("conversation_kind") or "knowledge"
                ),
                response_language=response_language,
            )
        else:
            runtime.retire_deferred_response_language(case.text)
        return {
            "case": case.name,
            "expected_mode": case.expected_mode,
            "elapsed_seconds": time.perf_counter() - started,
            "decision": copy.deepcopy(decision),
            "extraction": _extraction_json(extraction),
            "response_language": response_language,
            "reply": reply,
        }
    finally:
        runtime.end_request()


def _numeric(records: list[dict[str, Any]], key: str) -> list[float]:
    return [
        float(record[key])
        for record in records
        if isinstance(record.get(key), (int, float))
    ]


def _stage_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for stage in ("P", "G", "L", "V", "C", "E", "chat", "other"):
        selected = [record for record in records if record["stage"] == stage]
        if not selected:
            continue
        cache_n = _numeric(selected, "cache_n")
        prompt_n = _numeric(selected, "prompt_n")
        prompt_ms = _numeric(selected, "prompt_ms")
        elapsed = _numeric(selected, "elapsed_seconds")
        summary[stage] = {
            "calls": len(selected),
            "cache_n_median": statistics.median(cache_n) if cache_n else None,
            "prompt_n_median": statistics.median(prompt_n) if prompt_n else None,
            "prompt_ms_median": (
                statistics.median(prompt_ms) if prompt_ms else None
            ),
            "elapsed_median_seconds": (
                statistics.median(elapsed) if elapsed else None
            ),
        }
    return summary


def _run_arm(arm: str) -> dict[str, Any]:
    runtime = InstrumentedRuntime(arm)
    cases: list[dict[str, Any]] = []
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        for case in CASES:
            cases.append(_run_case(runtime, case))
    finally:
        runtime.close()
    return {
        "arm": arm,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
    }


def _case_projection(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: case[key]
        for key in (
            "case",
            "expected_mode",
            "decision",
            "extraction",
            "response_language",
            "reply",
        )
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("auto-pinned", "pinned-auto"),
        default="auto-pinned",
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
    arms = [_run_arm(arm) for arm in arm_order]
    arms_by_name = {arm["arm"]: arm for arm in arms}
    auto_cases = [
        _case_projection(case) for case in arms_by_name["auto"]["cases"]
    ]
    pinned_cases = [
        _case_projection(case) for case in arms_by_name["pinned"]["cases"]
    ]
    exact_outputs = auto_cases == pinned_cases
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    payload = {
        "schema": "baxy.llama-slot-pinning-ab.v1",
        "arm_order": arm_order,
        "server": str(args.server.resolve()),
        "model": str(args.model.resolve()),
        "profile": {
            "parallel": 3,
            "context_per_slot": 4_096,
            "cache_prompt": "llama.cpp default true",
            "prototype": "id_slot only on P/G/L",
        },
        "candidate_status": "research_only",
        "exact_outputs": exact_outputs,
        "mode_contracts": mode_contracts,
        "arms": arms,
        "promotion_rule": (
            "Promote only if every projected output is exactly equal, every "
            "expected mode holds, and repeated opposite-order runs show a "
            "stable P/G/L and end-to-end latency improvement with no material "
            "tail regression."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if exact_outputs and mode_contracts else 2


if __name__ == "__main__":
    raise SystemExit(main())
