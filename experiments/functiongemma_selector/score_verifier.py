"""Score both legal verifier completions instead of generating open-ended text."""

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

from selector_common import (
    NO_ACTION_OPERATION,
    REPO,
    assistant_selection,
    read_jsonl,
    sha256,
)

DEFAULT_MODEL = Path(r"D:\BAXYRuntime\assets\models\functiongemma-270m-it-hf")
DEFAULT_ADAPTER = Path(r"D:\BAXYRuntime\experiments\functiongemma-verifier-v1")
DEFAULT_CASES = REPO / "artifacts" / "research" / "functiongemma_verifier_validation.v1.jsonl"
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_verifier_scored_validation_r1.json"


def _completion(tokenizer: Any, row: dict[str, Any], operation: str) -> tuple[list[int], list[int]]:
    user = {"role": "user", "content": str(row["text"])}
    prompt = tokenizer.apply_chat_template(
        [user], tools=row["tools"], add_generation_prompt=True, tokenize=False
    )
    complete = tokenizer.apply_chat_template(
        [user, assistant_selection(operation)],
        tools=row["tools"],
        add_generation_prompt=False,
        tokenize=False,
    )
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    input_ids = tokenizer(complete, add_special_tokens=False)["input_ids"]
    if input_ids[: len(prompt_ids)] != prompt_ids:
        raise RuntimeError("completion does not extend its prompt")
    return input_ids, [-100] * len(prompt_ids) + input_ids[len(prompt_ids) :]


def _batch(tokenizer: Any, pairs: list[tuple[list[int], list[int]]]) -> dict[str, torch.Tensor]:
    width = max(len(value[0]) for value in pairs)
    return {
        "input_ids": torch.tensor(
            [ids + [tokenizer.pad_token_id] * (width - len(ids)) for ids, _ in pairs],
            dtype=torch.long,
        ),
        "labels": torch.tensor(
            [labels + [-100] * (width - len(labels)) for ids, labels in pairs],
            dtype=torch.long,
        ),
        "attention_mask": torch.tensor(
            [[1] * len(ids) + [0] * (width - len(ids)) for ids, _ in pairs],
            dtype=torch.long,
        ),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    rows = read_jsonl(args.cases)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    model = AutoModelForCausalLM.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.bfloat16
    )
    model = PeftModel.from_pretrained(model, args.adapter, local_files_only=True).to("cuda").eval()

    encoded: list[tuple[list[int], list[int]]] = []
    for row in rows:
        encoded.append(_completion(tokenizer, row, str(row["candidate_operation"])))
        encoded.append(_completion(tokenizer, row, NO_ACTION_OPERATION))
    scores: list[float] = []
    batch_seconds: list[float] = []
    for start in range(0, len(encoded), args.batch_size):
        values = _batch(tokenizer, encoded[start : start + args.batch_size])
        values = {key: value.to("cuda") for key, value in values.items()}
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            logits = model(
                input_ids=values["input_ids"],
                attention_mask=values["attention_mask"],
            ).logits[:, :-1].float().log_softmax(dim=-1)
        torch.cuda.synchronize()
        batch_seconds.append(time.perf_counter() - started)
        labels = values["labels"][:, 1:]
        mask = labels != -100
        gathered = logits.gather(-1, labels.clamp_min(0).unsqueeze(-1)).squeeze(-1)
        mean_scores = (gathered * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
        scores.extend(float(value) for value in mean_scores.detach().cpu())

    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        candidate_score = scores[index * 2]
        rejection_score = scores[index * 2 + 1]
        observed = str(row["candidate_operation"]) if candidate_score > rejection_score else NO_ACTION_OPERATION
        expected = str(row["operation"])
        results.append(
            {
                "case_id": row["case_id"],
                "verdict": row["verdict"],
                "negative_kind": row.get("negative_kind"),
                "candidate_operation": row["candidate_operation"],
                "base_operation": row["base_operation"],
                "expected_operation": expected,
                "observed_operation": observed,
                "exact": observed == expected,
                "candidate_mean_log_probability": round(candidate_score, 8),
                "rejection_mean_log_probability": round(rejection_score, 8),
                "accept_margin": round(candidate_score - rejection_score, 8),
            }
        )
    exact = sum(bool(row["exact"]) for row in results)
    report = {
        "schema": "baxy.functiongemma-verifier-scored-evaluation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "forced mean-log-probability comparison of the only two legal completions",
        "cases": str(args.cases),
        "cases_sha256": sha256(args.cases),
        "samples": len(results),
        "exact": exact,
        "accuracy": round(exact / len(results), 6),
        "by_verdict": {
            verdict: {
                "samples": len(group),
                "exact": sum(bool(row["exact"]) for row in group),
                "accuracy": round(sum(bool(row["exact"]) for row in group) / len(group), 6),
            }
            for verdict, group in (
                (value, [row for row in results if row["verdict"] == value])
                for value in sorted({str(row["verdict"]) for row in results})
            )
        },
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
                f"{row['expected_operation']}->{row['observed_operation']}"
                for row in results
                if not row["exact"]
            )
        ),
        "batch_size": args.batch_size,
        "forward_rows_per_second": round(len(encoded) / sum(batch_seconds), 3),
        "forward_batch_seconds": {
            "mean": round(statistics.fmean(batch_seconds), 6),
            "maximum": round(max(batch_seconds), 6),
        },
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
    parser.add_argument("--batch-size", type=int, default=64)
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
