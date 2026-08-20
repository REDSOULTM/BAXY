"""Evaluate a FunctionGemma adapter on the sealed current-union holdout."""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from selector_common import NO_ACTION_OPERATION, parse_operations, read_jsonl, sha256


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return round(ordered[round((len(ordered) - 1) * fraction)], 6)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment")
    os.environ["HF_HUB_OFFLINE"] = "1"
    cases = read_jsonl(args.cases)
    if not cases:
        raise ValueError("validation corpus is empty")
    if any(not row.get("tools") or not row.get("operation") for row in cases):
        raise ValueError("every validation row must contain tools and operation")

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    load_started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    model = PeftModel.from_pretrained(model, args.adapter, local_files_only=True)
    model = model.to("cuda").eval()
    load_seconds = time.perf_counter() - load_started

    warm_prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": str(cases[0]["text"])}],
        tools=cases[0]["tools"],
        add_generation_prompt=True,
        tokenize=False,
    )
    warm_inputs = tokenizer(warm_prompt, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        model.generate(**warm_inputs, max_new_tokens=8, do_sample=False)

    rows: list[dict[str, Any]] = []
    for case in cases:
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": str(case["text"])}],
            tools=case["tools"],
            add_generation_prompt=True,
            tokenize=False,
        )
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                use_cache=True,
            )
        torch.cuda.synchronize()
        seconds = time.perf_counter() - started
        generated = tokenizer.decode(
            output[0, inputs.input_ids.shape[1] :], skip_special_tokens=False
        )
        observed = parse_operations(generated)
        expected = str(case["operation"])
        rows.append(
            {
                "case_id": case["case_id"],
                "language": case.get("language"),
                "source": case.get("source"),
                "text": case["text"],
                "expected_operation": expected,
                "candidate_operations": case.get("candidate_operations"),
                "observed_operations": observed,
                "exact": observed == [expected],
                "selected_actions": [
                    operation
                    for operation in observed
                    if operation != NO_ACTION_OPERATION
                ],
                "generated": generated,
                "seconds": round(seconds, 6),
            }
        )

    positive = [
        row for row in rows if row["expected_operation"] != NO_ACTION_OPERATION
    ]
    negative = [
        row for row in rows if row["expected_operation"] == NO_ACTION_OPERATION
    ]
    latencies = [float(row["seconds"]) for row in rows]
    peak_allocated = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    peak_reserved = round(torch.cuda.max_memory_reserved() / 2**20, 1)
    del model
    torch.cuda.empty_cache()

    report = {
        "schema": "baxy.functiongemma-current-union-validation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": {
            "path": str(args.cases),
            "sha256": sha256(args.cases),
            "rows": len(cases),
        },
        "base_model": {
            "path": str(args.model),
            "sha256": sha256(args.model / "model.safetensors"),
        },
        "adapter": {
            "path": str(args.adapter),
            "sha256": sha256(args.adapter / "adapter_model.safetensors"),
            "training_report_sha256": sha256(args.adapter / "training_report.json"),
        },
        "attention_implementation": "sdpa",
        "positive": {
            "rows": len(positive),
            "exact": sum(bool(row["exact"]) for row in positive),
        },
        "negative": {
            "rows": len(negative),
            "exact_no_action": sum(bool(row["exact"]) for row in negative),
            "honest_abstentions": sum(not row["selected_actions"] for row in negative),
            "selected_actions": sum(bool(row["selected_actions"]) for row in negative),
        },
        "confusions": dict(
            collections.Counter(
                f"{row['expected_operation']}->{','.join(row['observed_operations']) or 'NONE'}"
                for row in rows
                if not row["exact"]
            )
        ),
        "latency_seconds": {
            "p50": round(statistics.median(latencies), 6),
            "p90": _percentile(latencies, 0.9),
            "maximum": round(max(latencies), 6),
            "load": round(load_seconds, 6),
        },
        "peak_allocated_mib": peak_allocated,
        "peak_reserved_mib": peak_reserved,
        "effects_executed": 0,
        "providers_enabled": False,
        "runtime_manifest_changed": False,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"rows", "confusions"}},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    args = parser.parse_args()
    args.model = args.model.resolve(strict=True)
    args.adapter = args.adapter.resolve(strict=True)
    args.cases = args.cases.resolve(strict=True)
    args.output = args.output.resolve()
    evaluate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
