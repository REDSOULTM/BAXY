"""Measure the inherited FunctionGemma R2 selector on Goal 03 candidates.

This probe reuses the previous BAXY's tool-call contract and LoRA adapter.  It
only selects authenticated operation names; Core, providers and dispatch stay
disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)

CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
RESULT_DIR = REPO / "artifacts/development"
NO_ACTION = "__no_action__"
TOOL_PREFIX = "baxy_"
CALL_PATTERN = re.compile(
    r"<start_function_call>\s*call:([A-Za-z0-9_]+)\{.*?\}"
    r"<end_function_call>",
    flags=re.DOTALL,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _tool_name(operation: str) -> str:
    if operation == NO_ACTION:
        return f"{TOOL_PREFIX}no_action"
    return TOOL_PREFIX + operation.replace(".", "__")


def _operation_name(tool: str) -> str | None:
    if tool == f"{TOOL_PREFIX}no_action":
        return NO_ACTION
    if not tool.startswith(TOOL_PREFIX):
        return None
    return tool[len(TOOL_PREFIX) :].replace("__", ".")


def _selection_tools(
    catalog: dict[str, dict[str, Any]], operations: Iterable[str]
) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for operation in operations:
        description = (
            "Select this only when the message requests no concrete action or "
            "external read covered by the other declared BAXY operations."
            if operation == NO_ACTION
            else str(catalog[operation].get("description") or operation)
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": _tool_name(operation),
                    "description": description,
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        )
    return tools


def _parse_operations(generated: str) -> list[str]:
    return [
        operation
        for name in CALL_PATTERN.findall(generated)
        if (operation := _operation_name(name)) is not None
    ]


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def _write_lf(path: Path, value: dict[str, Any]) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(rendered)


def run(
    *,
    model_path: Path,
    adapter_path: Path,
    union_artifact: Path,
    label: str,
    union_budget: int,
) -> Path:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment")
    if union_budget not in {16, 28}:
        raise ValueError("union budget must be 16 or 28")
    os.environ["HF_HUB_OFFLINE"] = "1"

    corpus = {str(row["case_id"]): row for row in _jsonl(CORPUS)}
    union_value = json.loads(union_artifact.read_text(encoding="utf-8"))
    union_rows = {str(row["case_id"]): row for row in union_value["rows"]}
    if set(corpus) != set(union_rows):
        raise ValueError("the union artifact does not contain the exact corpus")

    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    catalog = {str(row["name"]): row for row in capabilities}
    candidates: dict[str, list[str]] = {}
    tools: dict[str, list[dict[str, Any]]] = {}
    per_ranker = union_budget // 2
    for case_id, row in union_rows.items():
        names = list(
            dict.fromkeys(
                row["top_28"][:per_ranker] + row["e5_top_28"][:per_ranker]
            )
        )
        names = [name for name in names if name in catalog]
        candidates[case_id] = names
        tools[case_id] = _selection_tools(catalog, [*names, NO_ACTION])

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    load_started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    model = PeftModel.from_pretrained(model, adapter_path, local_files_only=True)
    model = model.to("cuda").eval()
    load_seconds = time.perf_counter() - load_started

    first_id = next(iter(corpus))
    warm_prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": "open calculator"}],
        tools=tools[first_id],
        add_generation_prompt=True,
        tokenize=False,
    )
    warm_inputs = tokenizer(warm_prompt, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        model.generate(**warm_inputs, max_new_tokens=8, do_sample=False)

    rows: list[dict[str, Any]] = []
    try:
        for case_id, row in corpus.items():
            prompt = tokenizer.apply_chat_template(
                [{"role": "user", "content": str(row["text"])}],
                tools=tools[case_id],
                add_generation_prompt=True,
                tokenize=False,
            )
            inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
            torch.cuda.synchronize()
            started = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=32,
                    do_sample=False,
                    use_cache=True,
                )
            torch.cuda.synchronize()
            seconds = time.perf_counter() - started
            generated = tokenizer.decode(
                output[0, inputs.input_ids.shape[1] :], skip_special_tokens=False
            )
            observed_wire = _parse_operations(generated)
            selected = [name for name in observed_wire if name != NO_ACTION]
            expected = set(row.get("expected_operations") or [])
            rows.append(
                {
                    "case_id": case_id,
                    "language": row["language"],
                    "in_catalog": bool(row["in_catalog"]),
                    "text": row["text"],
                    "expected_operations": sorted(expected),
                    "candidate_operations": candidates[case_id],
                    "retrieved": bool(expected & set(candidates[case_id])),
                    "observed_wire_operations": observed_wire,
                    "selected_operations": selected,
                    "selected_expected": bool(expected & set(selected)),
                    "generated": generated,
                    "seconds": seconds,
                }
            )
    finally:
        del model
        torch.cuda.empty_cache()

    inside = [row for row in rows if row["in_catalog"]]
    outside = [row for row in rows if not row["in_catalog"]]
    durations = [float(row["seconds"]) for row in rows]
    result = {
        "schema": "baxy.goal03-functiongemma-selector.v1",
        "corpus": {"path": str(CORPUS.relative_to(REPO)), "sha256": _sha256(CORPUS)},
        "candidate_union": {
            "path": str(union_artifact.relative_to(REPO)),
            "sha256": _sha256(union_artifact),
            "budget": union_budget,
        },
        "base_model": {
            "path": str(model_path),
            "sha256": _sha256(model_path / "model.safetensors"),
        },
        "adapter": {
            "path": str(adapter_path),
            "sha256": _sha256(adapter_path / "adapter_model.safetensors"),
            "training_report_sha256": _sha256(adapter_path / "training_report.json"),
        },
        "attention_implementation": "sdpa",
        "in_catalog": {
            "rows": len(inside),
            "retrieved": sum(bool(row["retrieved"]) for row in inside),
            "selected_expected": sum(bool(row["selected_expected"]) for row in inside),
        },
        "out_of_catalog": {
            "rows": len(outside),
            "honest_abstentions": sum(not row["selected_operations"] for row in outside),
        },
        "latency_seconds": {
            "rows": len(durations),
            "p50": statistics.median(durations),
            "p90": _percentile(durations, 0.9),
            "max": max(durations),
            "load": load_seconds,
        },
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1),
        "three_zeros": {
            "effects_executed": 0,
            "providers_enabled": False,
            "unsolicited_effects": 0,
            "unverified_successes": 0,
            "fixed_visible_replies": 0,
        },
        "rows": rows,
    }
    output = RESULT_DIR / f"goal03_{label}.json"
    _write_lf(output, result)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--union-artifact", required=True, type=Path)
    parser.add_argument("--union-budget", type=int, choices=(16, 28), default=28)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    output = run(
        model_path=args.model.resolve(strict=True),
        adapter_path=args.adapter.resolve(strict=True),
        union_artifact=args.union_artifact.resolve(strict=True),
        union_budget=args.union_budget,
        label=args.label,
    )
    value = json.loads(output.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                key: value[key]
                for key in (
                    "in_catalog",
                    "out_of_catalog",
                    "latency_seconds",
                    "peak_allocated_mib",
                    "peak_reserved_mib",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
