"""Train a prompt-masked LoRA adapter for exact BAXY leaf selection."""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

from selector_common import (
    NO_ACTION_OPERATION,
    assistant_selection,
    read_jsonl,
    sha256,
)

EXPECTED_BASE_SHA256 = (
    "af4f8a7c4c5eb82291759fd828720c7bcfcb92a5274556d13dde3caccf5f427b"
)
DEFAULT_MODEL = Path(r"D:\BAXYRuntime\assets\models\functiongemma-270m-it-hf")
DEFAULT_CASES = Path(
    r"D:\BAXY\source\artifacts\research\functiongemma_audio_seed.v1.jsonl"
)
DEFAULT_OUTPUT = Path(r"D:\BAXYRuntime\experiments\functiongemma-selector-audio-v1")


@dataclass(frozen=True)
class EncodedRow:
    input_ids: list[int]
    labels: list[int]
    operation: str
    balance_key: str
    language: str
    source: str


class SelectionDataset(Dataset[EncodedRow]):
    def __init__(self, rows: list[EncodedRow]) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> EncodedRow:
        return self.rows[index]


def _encode_row(tokenizer: Any, row: dict[str, Any], max_length: int) -> EncodedRow:
    user = {"role": "user", "content": str(row["text"])}
    tools = row["tools"]
    prompt = tokenizer.apply_chat_template(
        [user], tools=tools, add_generation_prompt=True, tokenize=False
    )
    complete = tokenizer.apply_chat_template(
        [user, assistant_selection(str(row["operation"]))],
        tools=tools,
        add_generation_prompt=False,
        tokenize=False,
    )
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    input_ids = tokenizer(complete, add_special_tokens=False)["input_ids"]
    if input_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(f"chat template prompt is not a prefix for {row['case_id']}")
    if len(input_ids) > max_length:
        raise ValueError(
            f"encoded row exceeds max_length ({len(input_ids)} > {max_length}): "
            f"{row['case_id']}"
        )
    labels = [-100] * len(prompt_ids) + input_ids[len(prompt_ids) :]
    if all(label == -100 for label in labels):
        raise ValueError(f"row has no supervised completion: {row['case_id']}")
    return EncodedRow(
        input_ids,
        labels,
        str(row["operation"]),
        str(row.get("balance_key") or row["operation"]),
        str(row.get("language") or "unknown"),
        str(row.get("source") or "unknown"),
    )


def _source_priority(source: str) -> int:
    if source == "core-contract-authored-contrastive-v3":
        return 0
    if source == "core-contract-authored-targeted-v2":
        return 1
    if source in {
        "core-contract-authored-targeted-v1",
        "authored:audio-seed-v1",
    }:
        return 2
    if source == "qwen-generator+gemma-reviewer":
        return 3
    return 4


def _balanced_rows(
    rows: list[EncodedRow],
    per_operation: int,
    seed: int,
    no_action_ratio: float | None = None,
    preferred_source: str | None = None,
    preferred_per_operation: int = 0,
) -> list[EncodedRow]:
    grouped: dict[str, list[EncodedRow]] = collections.defaultdict(list)
    for row in rows:
        grouped[row.balance_key].append(row)
    rng = random.Random(seed)
    balanced: list[EncodedRow] = []
    no_action_pool = grouped.pop(NO_ACTION_OPERATION, [])
    if not 0 <= preferred_per_operation <= per_operation:
        raise ValueError("preferred_per_operation must be between 0 and per_operation")
    if preferred_per_operation and not preferred_source:
        raise ValueError("preferred_source is required when preferred_per_operation is set")
    for operation in sorted(grouped):
        pool = grouped[operation]
        rng.shuffle(pool)
        pool.sort(key=lambda row: _source_priority(row.source))
        preferred = (
            [row for row in pool if row.source == preferred_source]
            if preferred_source
            else []
        )
        fallback = [row for row in pool if row.source != preferred_source]
        preferred_selected = preferred[:preferred_per_operation]
        remaining = per_operation - len(preferred_selected)
        if len(fallback) >= remaining:
            selected = [*preferred_selected, *fallback[:remaining]]
        else:
            refill = fallback or preferred or pool
            selected = [*preferred_selected, *fallback]
            selected.extend(
                refill[index % len(refill)]
                for index in range(per_operation - len(selected))
            )
            rng.shuffle(selected)
        balanced.extend(selected)
    if no_action_ratio is None:
        target_no_action = per_operation
    else:
        if not math.isfinite(no_action_ratio) or not 0.0 <= no_action_ratio <= 2.0:
            raise ValueError("no_action_ratio must be finite and between 0 and 2")
        target_no_action = round(len(balanced) * no_action_ratio)
    if target_no_action and not no_action_pool:
        raise ValueError("no-action sampling requested but the corpus has no no-action rows")
    if no_action_pool:
        rng.shuffle(no_action_pool)
        selected_no_action = [
            no_action_pool[index % len(no_action_pool)]
            for index in range(target_no_action)
        ]
        balanced.extend(selected_no_action)
    rng.shuffle(balanced)
    return balanced


def _collate(tokenizer: Any, rows: list[EncodedRow]) -> dict[str, torch.Tensor]:
    width = max(len(row.input_ids) for row in rows)
    input_ids: list[list[int]] = []
    labels: list[list[int]] = []
    attention: list[list[int]] = []
    for row in rows:
        padding = width - len(row.input_ids)
        input_ids.append(row.input_ids + [tokenizer.pad_token_id] * padding)
        labels.append(row.labels + [-100] * padding)
        attention.append([1] * len(row.input_ids) + [0] * padding)
    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "labels": torch.tensor(labels, dtype=torch.long),
        "attention_mask": torch.tensor(attention, dtype=torch.long),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment")
    model_file = args.model / "model.safetensors"
    if sha256(model_file) != EXPECTED_BASE_SHA256:
        raise ValueError("FunctionGemma base checkpoint hash does not match")
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {args.output}")

    os.environ["HF_HUB_OFFLINE"] = "1"
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    source_rows = read_jsonl(args.cases)
    encoded = [_encode_row(tokenizer, row, args.max_length) for row in source_rows]
    balanced = _balanced_rows(
        encoded,
        args.per_operation,
        args.seed,
        no_action_ratio=args.no_action_ratio,
        preferred_source=args.preferred_source,
        preferred_per_operation=args.preferred_per_operation,
    )
    loader_generator = torch.Generator().manual_seed(args.seed)
    loader = DataLoader(
        SelectionDataset(balanced),
        batch_size=args.batch_size,
        shuffle=True,
        generator=loader_generator,
        collate_fn=lambda rows: _collate(tokenizer, rows),
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
        attn_implementation=args.attention_implementation,
    )
    model.config.use_cache = False
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    config = LoraConfig(
        task_type="CAUSAL_LM",
        r=args.rank,
        lora_alpha=args.alpha,
        lora_dropout=args.dropout,
        bias="none",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, config).to("cuda")
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total = sum(parameter.numel() for parameter in model.parameters())
    if args.preflight_longest_only:
        longest = max(balanced, key=lambda row: len(row.input_ids))
        batch = _collate(tokenizer, [longest])
        batch = {key: value.to("cuda") for key, value in batch.items()}
        model.train()
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            loss = model(**batch).loss
        loss.backward()
        torch.cuda.synchronize()
        print(
            json.dumps(
                {
                    "schema": "baxy.functiongemma-lora-memory-preflight.v1",
                    "attention_implementation": args.attention_implementation,
                    "tokens": len(longest.input_ids),
                    "operation": longest.operation,
                    "loss": round(float(loss.detach().cpu()), 6),
                    "peak_allocated_mib": round(
                        torch.cuda.max_memory_allocated() / 2**20, 1
                    ),
                    "peak_reserved_mib": round(
                        torch.cuda.max_memory_reserved() / 2**20, 1
                    ),
                    "effects_executed": 0,
                },
                sort_keys=True,
            )
        )
        return {}
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    updates_per_epoch = math.ceil(len(loader) / args.gradient_accumulation)
    total_updates = updates_per_epoch * args.epochs
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, round(total_updates * args.warmup_ratio)),
        num_training_steps=total_updates,
    )

    started = time.perf_counter()
    losses: list[float] = []
    updates = 0
    optimizer.zero_grad(set_to_none=True)
    model.train()
    for epoch in range(args.epochs):
        accumulation = 0
        for batch_index, batch in enumerate(loader):
            batch = {key: value.to("cuda", non_blocking=True) for key, value in batch.items()}
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss = model(**batch).loss / args.gradient_accumulation
            loss.backward()
            accumulation += 1
            losses.append(float(loss.detach().cpu()) * args.gradient_accumulation)
            final_batch = batch_index + 1 == len(loader)
            if accumulation == args.gradient_accumulation or final_batch:
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                accumulation = 0
                updates += 1
        print(
            json.dumps(
                {
                    "epoch": epoch + 1,
                    "epochs": args.epochs,
                    "updates": updates,
                    "last_loss": round(losses[-1], 6),
                    "peak_allocated_mib": round(
                        torch.cuda.max_memory_allocated() / 2**20, 1
                    ),
                }
            ),
            flush=True,
        )

    elapsed = time.perf_counter() - started
    args.output.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(args.output, safe_serialization=True)
    report = {
        "schema": "baxy.functiongemma-lora-training.v1",
        "base_model": str(args.model.resolve()),
        "base_model_sha256": EXPECTED_BASE_SHA256,
        "cases": str(args.cases.resolve()),
        "cases_sha256": sha256(args.cases),
        "source_rows": len(source_rows),
        "balanced_rows_per_epoch": len(balanced),
        "counts_per_epoch": dict(collections.Counter(row.operation for row in balanced)),
        "balance_counts_per_epoch": dict(
            collections.Counter(row.balance_key for row in balanced)
        ),
        "source_counts_per_epoch": dict(
            collections.Counter(row.source for row in balanced)
        ),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "gradient_accumulation": args.gradient_accumulation,
        "updates": updates,
        "learning_rate": args.learning_rate,
        "attention_implementation": args.attention_implementation,
        "no_action_ratio": args.no_action_ratio,
        "preferred_source": args.preferred_source,
        "preferred_per_operation": args.preferred_per_operation,
        "rank": args.rank,
        "alpha": args.alpha,
        "trainable_parameters": trainable,
        "total_parameters_with_adapter": total,
        "trainable_fraction": round(trainable / total, 8),
        "loss_first": round(losses[0], 6),
        "loss_last": round(losses[-1], 6),
        "loss_mean": round(sum(losses) / len(losses), 6),
        "training_seconds": round(elapsed, 3),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1),
        "effects_executed": 0,
        "runtime_manifest_changed": False,
    }
    report_path = args.output / "training_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.report_copy is not None:
        args.report_copy.parent.mkdir(parents=True, exist_ok=True)
        args.report_copy.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--per-operation", type=int, default=48)
    parser.add_argument(
        "--no-action-ratio",
        type=float,
        default=None,
        help="sample this many no-action rows per balanced positive row",
    )
    parser.add_argument("--preferred-source")
    parser.add_argument("--preferred-per-operation", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--attention-implementation", default=None)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--dropout", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=5601)
    parser.add_argument("--report-copy", type=Path)
    parser.add_argument("--preflight-longest-only", action="store_true")
    parser.add_argument(
        "--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=True
    )
    args = parser.parse_args()
    args.model = args.model.resolve(strict=True)
    args.cases = args.cases.resolve(strict=True)
    args.output = args.output.resolve()
    if args.report_copy is not None:
        args.report_copy = args.report_copy.resolve()
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
