"""Evaluate preregistered xLAM-2-3B native JSON-array tool selection.

V58 showed that llama-server's OpenAI tool_calls parser cannot read this GGUF:
the embedded chat template (Qwen2 `<|im_start|>`, Salesforce JSON array) emits
calls in assistant content, and passing `tools` trips llama.cpp's peg-native
format with HTTP 500. This probe therefore injects the GGUF's own format
instruction plus the candidate list as prompt text and parses the JSON array.
The synthetic phase must pass before the clean inherited-real phase may run.
No provider is reachable from this harness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.llm import (  # noqa: E402
    LlmRuntime,
    _native_selection_description,
    _prepare_turn_candidates,
)
from experiments.mind_router_spike.probe_goal03_qwen_binary_scope_holdout import (  # noqa: E402
    MAXIMUM_SYNTHETIC_OOS_ACTIONS,
    MINIMUM_REAL_EXACT,
    MINIMUM_SYNTHETIC_EXACT,
    REAL_VALIDATION,
    TRAIN,
    VALIDATION,
    clean_real_rows,
    percentile,
    read_jsonl,
    sha256,
    summarize,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
)


SCHEMA = "baxy.goal03-xlam2-3b-native-holdout.v1"
MODEL = Path(
    r"D:\BAXYRuntime\candidates\xlam-2-3b-fc-r"
    r"\xLAM-2-3B-fc-r-Q4_K_M.gguf"
)
SERVER = Path(
    r"C:\Users\usuario\Desktop\ETC\Programacion\BAXY"
    r"\legacy\models\artifacts\llama-b9980\llama-server.exe"
)
SMOKE_OUTPUT = REPO / "artifacts/development/goal03_xlam2_3b_native_smoke_v58b.json"
SYNTHETIC_OUTPUT = REPO / "artifacts/development/goal03_xlam2_3b_native_synthetic_v59.json"
REAL_OUTPUT = REPO / "artifacts/development/goal03_xlam2_3b_native_real_v60.json"
EXPECTED_SHA256 = {
    VALIDATION: "a81a50fc80af209d9c6827ac81e300d2ebcc9f493c473b2708e58aa5b52ddab2",
    TRAIN: "69e8bcde6760258a6e8d750caa3c648fc85695c0cccd7f6ad6926a92935b8bad",
    REAL_VALIDATION: "c42d27e6ccdc03d0ee6dcce20ca26a52b5c1e49e869b8bdfa91db2b88e622300",
    MODEL: "bd1a0480eadf5eddced7159e4b7aa68cc3cb47715d7410c99d3b4c485e47ae43",
    SERVER: "38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e",
}
SMOKE_CONTROLS = (
    {
        "case_id": "smoke-app-open",
        "text": "open calculator",
        "expected_operation": "app.open",
        "candidate_operations": ["app.open", "system.time", "web.search"],
    },
    {
        "case_id": "smoke-no-call",
        "text": "what is the capital of France",
        "expected_operation": "__no_action__",
        "candidate_operations": ["app.open", "system.time", "web.search"],
    },
)
XLAM_FORMAT_INSTRUCTION = (
    "You are a helpful assistant that can use tools. You are developed by "
    "Salesforce xLAM team.\n"
    "You have access to a set of tools. When using tools, make calls in a "
    "single JSON array:\n\n"
    '[{"name": "tool_call_name", "arguments": {"arg1": "value1", "arg2": '
    '"value2"}}, ... (additional parallel tool calls as needed)]\n\n'
    "If no tool is suitable, state that explicitly. If the user's input lacks "
    "required parameters, ask for clarification. Do not interpret or respond "
    "until tool results are returned. Once they are available, process them or "
    "make additional calls if needed. For tasks that don't require tools, such "
    "as casual conversation or general advice, respond directly in plain text.\n"
    "The available tools are:\n"
)
_NAME_RE = re.compile(r'"name"\s*:\s*"([^"]+)"')


def population(phase: str) -> tuple[list[dict[str, Any]], Path, dict[str, Any]]:
    if phase == "smoke":
        return list(SMOKE_CONTROLS), SMOKE_OUTPUT, {"positive": 1, "no_action": 1}
    if phase == "synthetic":
        rows = read_jsonl(VALIDATION)
        positives = sum(row["operation"] != "__no_action__" for row in rows)
        if len(rows) != 784 or positives != 477:
            raise RuntimeError("unexpected synthetic validation population")
        return rows, SYNTHETIC_OUTPUT, {"positive": 477, "no_action": 307}
    if not SYNTHETIC_OUTPUT.is_file():
        raise RuntimeError("real phase requires the sealed synthetic report")
    prior = json.loads(SYNTHETIC_OUTPUT.read_text(encoding="utf-8"))
    if prior.get("decision") != "accepted_for_real_holdout":
        raise RuntimeError("synthetic gate did not authorize real evaluation")
    rows, excluded = clean_real_rows()
    return rows, REAL_OUTPUT, {"positive": 60, "excluded_overlap": excluded}


def candidate_contracts() -> dict[str, dict[str, Any]]:
    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    return {
        str(item["name"]): {
            "name": str(item["name"]),
            "description": str(item["description"]),
            "arguments_schema": item["argumentsSchema"],
        }
        for item in capabilities
    }


def configure_runtime() -> tuple[LlmRuntime, int]:
    registered = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    environment = sidecar_environment(
        registered,
        gpu_layers=99,
        llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
    )
    environment["BAXY_MIND_LLAMA_SERVER"] = str(SERVER)
    environment["BAXY_MIND_LLM_GGUF"] = str(MODEL)
    environment["BAXY_MIND_NGL"] = "99"
    os.environ.update(environment)
    return LlmRuntime(), 99


def parse_xlam_content(
    content: object,
    mapping: dict[str, str],
) -> tuple[tuple[str, ...], bool, dict[str, str] | None]:
    text = content.strip() if isinstance(content, str) else ""
    if not text or not text.lstrip().startswith("["):
        return (), True, None
    blob = text[text.index("[") :]
    end = blob.rfind("]")
    if end >= 0:
        blob = blob[: end + 1]
    native_error: dict[str, str] | None = None
    parsed: Any
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError as error:
        names = _NAME_RE.findall(blob)
        if not names:
            return (), True, {"type": "JSONDecodeError", "message": str(error)}
        parsed = [{"name": name} for name in names]
        native_error = {"type": "JSONDecodeError", "message": str(error)}
    if not isinstance(parsed, list) or len(parsed) > 8:
        return (), True, {"type": "ValueError", "message": "xlam content is not a json array"}
    if not parsed:
        return (), True, native_error
    selected: list[str] = []
    for item in parsed:
        if not isinstance(item, dict):
            return (), True, {"type": "ValueError", "message": "xlam tool item invalid"}
        wire = item.get("name")
        if wire not in mapping:
            return (), True, {
                "type": "ValueError",
                "message": "selector response escaped the declared tools",
            }
        selected.append(mapping[str(wire)])
    return tuple(selected), False, native_error


def select_xlam(
    runtime: LlmRuntime,
    text: str,
    candidates: list[dict[str, Any]],
) -> tuple[tuple[str, ...], bool, dict[str, str] | None]:
    operation_names, _, contracts = _prepare_turn_candidates(candidates)
    mapping = {
        "baxy_" + operation.replace(".", "__"): operation
        for operation in operation_names
    }
    tools = [
        {
            "name": wire,
            "description": _native_selection_description(
                operation,
                contracts[operation]["description"],
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        }
        for wire, operation in mapping.items()
    ]
    system = XLAM_FORMAT_INSTRUCTION + "\n".join(
        json.dumps(tool, ensure_ascii=False, indent=2) for tool in tools
    )
    response = runtime._post(  # noqa: SLF001 - isolated research harness
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": 0.0,
            "seed": 0,
            "max_tokens": 256,
        }
    )
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("selector response has no unique choice")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("selector response has no message")
    return parse_xlam_content(message.get("content"), mapping)


def safe_native_select(
    runtime: LlmRuntime,
    text: str,
    candidates: list[dict[str, Any]],
) -> tuple[tuple[str, ...], bool, dict[str, str] | None]:
    try:
        return select_xlam(runtime, text, candidates)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        return (), True, {"type": type(error).__name__, "message": str(error)}


def _decision_for(phase: str, summary: dict[str, Any]) -> str:
    if phase == "smoke":
        hit = int(summary.get("positive", {}).get("selected_expected") or 0) == 1
        abstained = int(summary.get("no_action", {}).get("selected_action_calls") or 0) == 0
        return "accepted_for_synthetic" if hit and abstained else "rejected_before_synthetic"
    return str(summary["decision"])


def run(phase: str) -> Path:
    required = EXPECTED_SHA256 if phase != "smoke" else {
        MODEL: EXPECTED_SHA256[MODEL],
        SERVER: EXPECTED_SHA256[SERVER],
    }
    for path, expected in required.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"source identity mismatch: {path}")
    rows, output, expected_population = population(phase)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {output}")
    by_name = candidate_contracts()
    for row in rows:
        candidates = list(row.get("candidate_operations") or [])
        if not candidates or any(name not in by_name for name in candidates):
            raise RuntimeError(f"invalid candidates in {row.get('case_id', '?')}")

    runtime, gpu_layers = configure_runtime()
    results: list[dict[str, Any]] = []
    try:
        if phase != "smoke":
            warm_names = ["app.open", "system.time", "web.search"]
            safe_native_select(
                runtime,
                "open calculator",
                [by_name[name] for name in warm_names],
            )
        for index, row in enumerate(rows, 1):
            names = list(row["candidate_operations"])
            started = time.perf_counter()
            selected, no_match, native_error = safe_native_select(
                runtime,
                str(row["text"]),
                [by_name[name] for name in names],
            )
            seconds = time.perf_counter() - started
            expected = str(row["operation"] if "operation" in row else row["expected_operation"])
            results.append(
                {
                    "case_id": str(row["case_id"]),
                    "text": str(row["text"]),
                    "language": str(row.get("language") or "unknown"),
                    "expected_operation": expected,
                    "candidate_operations": names,
                    "selected_no_match": bool(no_match),
                    "selected_operations": list(selected),
                    "selected_expected": expected in selected,
                    "schema_consistent": native_error is None,
                    "native_error": native_error,
                    "seconds": seconds,
                }
            )
            if index % 25 == 0 or index == len(rows):
                print(f"{phase}: {index}/{len(rows)}", flush=True)
    finally:
        runtime.close()

    summary = summarize(results, "synthetic" if phase == "smoke" else phase)
    if phase == "smoke":
        summary["decision"] = _decision_for(phase, summary)
        summary["accepted"] = summary["decision"] == "accepted_for_synthetic"
    durations = [float(row["seconds"]) for row in results]
    report = {
        "schema": SCHEMA,
        "phase": phase,
        "decision": summary.pop("decision"),
        "gates": {
            "synthetic_selected_expected_minimum": MINIMUM_SYNTHETIC_EXACT,
            "synthetic_oos_action_calls_maximum": MAXIMUM_SYNTHETIC_OOS_ACTIONS,
            "real_selected_expected_minimum": MINIMUM_REAL_EXACT,
        },
        "population": expected_population,
        "sources": {
            str(path): {"sha256": digest} for path, digest in required.items()
        },
        "policy": {
            "native_openai_tools": False,
            "xlam_json_array_in_content": True,
            "format_instruction": "gguf_chat_template",
            "no_match_mode": "prose_or_empty_array",
            "parallel_tool_calls": False,
            "temperature": 0.0,
            "seed": 0,
            "max_tokens": 256,
            "gpu_layers": gpu_layers,
            "model": MODEL.name,
        },
        "metrics": summary,
        "latency_seconds": {
            "p50": statistics.median(durations),
            "p90": percentile(durations, 0.9),
            "maximum": max(durations),
        },
        "authority": {
            "providers_enabled": False,
            "effects_executed": 0,
            "runtime_manifest_changed": False,
            "fresh_corpus_rows_used": 0,
        },
        "rows": results,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "synthetic", "real"), required=True)
    args = parser.parse_args()
    output = run(args.phase)
    report = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({"decision": report["decision"], **report["metrics"]}, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
