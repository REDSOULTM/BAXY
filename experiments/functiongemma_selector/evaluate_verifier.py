"""Evaluate a FunctionGemma candidate verifier on a frozen pair corpus."""

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

from selector_common import NO_ACTION_OPERATION, REPO, parse_operations, read_jsonl, sha256

DEFAULT_MODEL = Path(r"D:\BAXYRuntime\assets\models\functiongemma-270m-it-hf")
DEFAULT_ADAPTER = Path(r"D:\BAXYRuntime\experiments\functiongemma-verifier-v1")
DEFAULT_CASES = REPO / "artifacts" / "research" / "functiongemma_verifier_validation.v1.jsonl"
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_verifier_validation_r1.json"


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * probability)]


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment")
    os.environ["HF_HUB_OFFLINE"] = "1"
    rows = read_jsonl(args.cases)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    tokenizer.padding_side = "left"
    tokenizer.pad_token = tokenizer.eos_token
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started_load = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.bfloat16
    )
    model = PeftModel.from_pretrained(model, args.adapter, local_files_only=True).to("cuda").eval()
    load_seconds = time.perf_counter() - started_load

    prompts = [
        tokenizer.apply_chat_template(
            [{"role": "user", "content": str(row["text"])}],
            tools=row["tools"],
            add_generation_prompt=True,
            tokenize=False,
        )
        for row in rows
    ]
    warm = tokenizer(prompts[:1], return_tensors="pt", padding=True).to("cuda")
    with torch.inference_mode():
        model.generate(**warm, max_new_tokens=8, do_sample=False)

    results: list[dict[str, Any]] = []
    batch_seconds: list[float] = []
    for start in range(0, len(rows), args.batch_size):
        batch_rows = rows[start : start + args.batch_size]
        batch_prompts = prompts[start : start + args.batch_size]
        inputs = tokenizer(batch_prompts, return_tensors="pt", padding=True).to("cuda")
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
        batch_seconds.append(seconds)
        generated_ids = output[:, inputs.input_ids.shape[1] :]
        generated = tokenizer.batch_decode(generated_ids, skip_special_tokens=False)
        for row, text in zip(batch_rows, generated, strict=True):
            observed = parse_operations(text)
            expected = [str(row["operation"])]
            results.append(
                {
                    "case_id": row["case_id"],
                    "verdict": row["verdict"],
                    "negative_kind": row.get("negative_kind"),
                    "candidate_operation": row["candidate_operation"],
                    "base_operation": row["base_operation"],
                    "expected_operations": expected,
                    "observed_operations": observed,
                    "exact": observed == expected,
                    "generated": text,
                }
            )
    exact = sum(bool(row["exact"]) for row in results)
    by_verdict = {
        verdict: {
            "samples": len(group),
            "exact": sum(bool(row["exact"]) for row in group),
            "accuracy": round(sum(bool(row["exact"]) for row in group) / len(group), 6),
        }
        for verdict, group in (
            (value, [row for row in results if row["verdict"] == value])
            for value in sorted({str(row["verdict"]) for row in results})
        )
    }
    report = {
        "schema": "baxy.functiongemma-verifier-evaluation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "frozen disjoint candidate-pair validation",
        "cases": str(args.cases),
        "cases_sha256": sha256(args.cases),
        "samples": len(results),
        "exact": exact,
        "accuracy": round(exact / len(results), 6),
        "by_verdict": by_verdict,
        "by_negative_kind": {
            kind: {
                "samples": len(group),
                "exact": sum(bool(row["exact"]) for row in group),
                "accuracy": round(sum(bool(row["exact"]) for row in group) / len(group), 6),
            }
            for kind, group in (
                (value, [row for row in results if row["negative_kind"] == value])
                for value in sorted({str(row["negative_kind"]) for row in results if row["negative_kind"] is not None})
            )
        },
        "confusions": dict(
            collections.Counter(
                f"{','.join(row['expected_operations'])}->{','.join(row['observed_operations']) or 'NONE'}"
                for row in results
                if not row["exact"]
            )
        ),
        "batch_size": args.batch_size,
        "latency_seconds_per_batch": {
            "mean": round(statistics.fmean(batch_seconds), 6),
            "p50": round(_percentile(batch_seconds, 0.5), 6),
            "p95": round(_percentile(batch_seconds, 0.95), 6),
            "maximum": round(max(batch_seconds), 6),
        },
        "throughput_rows_per_second": round(len(results) / sum(batch_seconds), 3),
        "load_seconds": round(load_seconds, 6),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1),
        "base_model": str(args.model),
        "adapter": str(args.adapter),
        "effects_executed": 0,
        "runtime_manifest_changed": False,
        "rows": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
