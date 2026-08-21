"""Evaluate preregistered Qwen3.5-9B native optional tool selection.

This probe reuses BAXY's inherited native selector and changes only the GGUF.
The synthetic phase must pass before the clean inherited-real phase may run.
No provider is reachable from this harness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.llm import LlmRuntime  # noqa: E402
from experiments.mind_router_spike.benchmark_native_no_match_tool import (  # noqa: E402
    _select,
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


SCHEMA = "baxy.goal03-qwen35-9b-native-holdout.v1"
MODEL = Path(
    r"D:\BAXYRuntime\candidates\qwen35-9b-iq2xxs"
    r"\Qwen3.5-9B-UD-IQ2_XXS.gguf"
)
SERVER = Path(
    r"C:\Users\usuario\Desktop\ETC\Programacion\BAXY"
    r"\legacy\models\artifacts\llama-b9980\llama-server.exe"
)
SYNTHETIC_OUTPUT = REPO / "artifacts/development/goal03_qwen35_9b_native_synthetic_v52.json"
REAL_OUTPUT = REPO / "artifacts/development/goal03_qwen35_9b_native_real_v53.json"
EXPECTED_SHA256 = {
    VALIDATION: "a81a50fc80af209d9c6827ac81e300d2ebcc9f493c473b2708e58aa5b52ddab2",
    TRAIN: "69e8bcde6760258a6e8d750caa3c648fc85695c0cccd7f6ad6926a92935b8bad",
    REAL_VALIDATION: "c42d27e6ccdc03d0ee6dcce20ca26a52b5c1e49e869b8bdfa91db2b88e622300",
    MODEL: "570ce2bbc92545cffbcb01df43cba59d86093dadc34c25da9f554d256bc70b91",
    SERVER: "38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e",
}


def population(phase: str) -> tuple[list[dict[str, Any]], Path, dict[str, Any]]:
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
        gpu_layers=registered.gpu_layers,
        llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
    )
    environment["BAXY_MIND_LLAMA_SERVER"] = str(SERVER)
    environment["BAXY_MIND_LLM_GGUF"] = str(MODEL)
    os.environ.update(environment)
    return LlmRuntime(), registered.gpu_layers


def run(phase: str) -> Path:
    for path, expected in EXPECTED_SHA256.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"source identity mismatch: {path}")
    rows, output, expected_population = population(phase)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {output}")
    by_name = candidate_contracts()
    for row in rows:
        candidates = list(row.get("candidate_operations") or [])
        if not candidates or any(name not in by_name for name in candidates):
            raise RuntimeError(f"invalid candidates in {row['case_id']}")

    runtime, gpu_layers = configure_runtime()
    results: list[dict[str, Any]] = []
    try:
        warm_names = ["app.open", "system.time", "web.search"]
        _select(
            runtime,
            "open calculator",
            [by_name[name] for name in warm_names],
            no_match_mode="none",
            tool_choice="auto",
            parallel_tool_calls=False,
        )
        for index, row in enumerate(rows, 1):
            names = list(row["candidate_operations"])
            started = time.perf_counter()
            selected, no_match = _select(
                runtime,
                str(row["text"]),
                [by_name[name] for name in names],
                no_match_mode="none",
                tool_choice="auto",
                parallel_tool_calls=False,
            )
            seconds = time.perf_counter() - started
            expected = str(row["operation"])
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
                    "schema_consistent": True,
                    "seconds": seconds,
                }
            )
            if index % 25 == 0 or index == len(rows):
                print(f"{phase}: {index}/{len(rows)}", flush=True)
    finally:
        runtime.close()

    summary = summarize(results, phase)
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
            str(path): {"sha256": digest} for path, digest in EXPECTED_SHA256.items()
        },
        "policy": {
            "native_openai_tools": True,
            "tool_choice": "auto",
            "no_match_mode": "absence_of_tool_calls",
            "parallel_tool_calls": False,
            "temperature": 0.0,
            "seed": 0,
            "gpu_layers": gpu_layers,
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
    parser.add_argument("--phase", choices=("synthetic", "real"), required=True)
    args = parser.parse_args()
    output = run(args.phase)
    report = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({"decision": report["decision"], **report["metrics"]}, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
