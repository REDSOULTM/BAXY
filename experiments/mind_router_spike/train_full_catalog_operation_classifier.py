"""Train a conditional full-catalog mDeBERTa operation selector.

The model is deliberately not an open-world effect detector: it ranks one
authenticated operation only after the independent effect boundary has fired.
Training uses the reviewed FunctionGemma development corpus; the current
catalog review remains validation-only.  No blind holdout is opened and no
checkpoint is promoted by this experiment.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.__main__ import configure_tools  # noqa: E402
from baxy_mind.planner import PlannerCatalog  # noqa: E402
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


TRAINING = ROOT / "artifacts/research/functiongemma_training_corpus.v1.jsonl"
VALIDATION = (
    ROOT
    / "artifacts"
    / "development"
    / "current_catalog_review_development.v1.jsonl"
)
SOURCE = Path(r"D:\BAXYRuntime\experiments\mtop-operation-classifier-v8-mdeberta")
OUTPUT = Path(
    r"D:\BAXYRuntime\experiments\full-catalog-operation-classifier-v1-mdeberta"
)
REPORT = ROOT / "artifacts/research/full_catalog_operation_classifier_v1.json"
EXPECTED_TRAINING_SHA256 = (
    "b27e871a49aacd0f1e527235422547a21ceb0fabcb01505a4f687ad3ed51ba18"
)
SEED = 20260801


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(folded.split())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@dataclass(frozen=True)
class EncodedDataset:
    encodings: dict[str, list[list[int]]]
    labels: list[int]

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return {
            key: values[index]
            for key, values in self.encodings.items()
        } | {"labels": self.labels[index]}


def _checkpoint_identity(path: Path) -> list[dict[str, object]]:
    files = []
    for item in sorted(path.iterdir(), key=lambda value: value.name):
        if item.is_file():
            files.append(
                {
                    "name": item.name,
                    "bytes": item.stat().st_size,
                    "sha256": _sha256(item),
                }
            )
    return files


def train(args: argparse.Namespace) -> dict[str, object]:
    import numpy as np
    import torch
    from torch.utils.data import DataLoader
    from transformers import (
        Adafactor,
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        get_linear_schedule_with_warmup,
    )

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA training is unavailable")
    if _sha256(args.training) != args.expected_training_sha256:
        raise RuntimeError("reviewed training corpus identity changed")
    if args.output.exists() and any(args.output.iterdir()):
        raise RuntimeError(f"output checkpoint already exists: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    planner = PlannerCatalog(configure_tools(capabilities))
    available = {tool.name for tool in planner.tools}
    validation_source = _read_jsonl(args.validation)
    validation_keys = {_normal_key(str(row["text"])) for row in validation_source}

    training_rows: list[tuple[str, str]] = []
    excluded_no_action = 0
    excluded_unavailable = 0
    excluded_overlap = 0
    seen: set[tuple[str, str]] = set()
    for row in _read_jsonl(args.training):
        operation = str(row["operation"])
        text = str(row["text"])
        key = _normal_key(text)
        if operation == "__no_action__":
            excluded_no_action += 1
            continue
        if operation not in available:
            excluded_unavailable += 1
            continue
        if key in validation_keys:
            excluded_overlap += 1
            continue
        identity = (key, operation)
        if not key or identity in seen:
            continue
        seen.add(identity)
        training_rows.append((text, operation))

    validation_rows: list[tuple[str, str, str]] = []
    for row in validation_source:
        accepted = {
            str(operations[0])
            for operations in row["compatible_terminal_operation_sets"]
            if len(operations) == 1
        }
        if len(accepted) != 1:
            continue
        operation = next(iter(accepted))
        if operation in available:
            validation_rows.append(
                (str(row["case_id"]), str(row["text"]), operation)
            )
    classes = sorted({operation for _text, operation in training_rows})
    if not {operation for _case, _text, operation in validation_rows} <= set(classes):
        raise RuntimeError("validation contains an operation absent from training")
    label_to_id = {label: index for index, label in enumerate(classes)}
    train_counts = collections.Counter(label for _text, label in training_rows)
    repeated_training = training_rows * args.repeat

    tokenizer = AutoTokenizer.from_pretrained(args.source, local_files_only=True)

    def encode(items: list[tuple[str, str]]) -> EncodedDataset:
        encoded = tokenizer(
            [text for text, _label in items],
            truncation=True,
            max_length=args.max_length,
            padding=False,
        )
        return EncodedDataset(
            encodings={key: list(value) for key, value in encoded.items()},
            labels=[label_to_id[label] for _text, label in items],
        )

    train_dataset = encode(repeated_training)
    validation_dataset = encode(
        [(text, operation) for _case, text, operation in validation_rows]
    )
    collator = DataCollatorWithPadding(
        tokenizer=tokenizer,
        pad_to_multiple_of=8,
        return_tensors="pt",
    )
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
        collate_fn=collator,
        num_workers=0,
        pin_memory=True,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.eval_batch_size,
        shuffle=False,
        collate_fn=collator,
        num_workers=0,
        pin_memory=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        args.source,
        local_files_only=True,
        num_labels=len(classes),
        id2label={index: label for index, label in enumerate(classes)},
        label2id=label_to_id,
        ignore_mismatched_sizes=True,
    ).cuda()
    model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    optimizer = Adafactor(
        model.parameters(),
        lr=args.learning_rate,
        scale_parameter=False,
        relative_step=False,
        warmup_init=False,
        weight_decay=0.01,
    )
    steps_per_epoch = math.ceil(len(train_loader) / args.gradient_accumulation)
    total_steps = steps_per_epoch * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=math.ceil(total_steps * 0.1),
        num_training_steps=total_steps,
    )
    class_weights = torch.tensor(
        [
            (
                len(training_rows) / (len(classes) * train_counts[label])
            )
            ** args.class_weight_power
            for label in classes
        ],
        dtype=torch.float32,
        device="cuda",
    )
    scaler = torch.amp.GradScaler("cuda")
    torch.cuda.reset_peak_memory_stats()
    epochs: list[dict[str, object]] = []
    best_accuracy = -1.0
    best_epoch = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        losses: list[float] = []
        epoch_started = time.perf_counter()
        for batch_index, batch in enumerate(train_loader, start=1):
            labels = batch.pop("labels").cuda(non_blocking=True)
            inputs = {
                key: value.cuda(non_blocking=True)
                for key, value in batch.items()
            }
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(**inputs).logits
                loss = torch.nn.functional.cross_entropy(
                    logits,
                    labels,
                    weight=class_weights,
                    label_smoothing=0.02,
                ) / args.gradient_accumulation
            scaler.scale(loss).backward()
            losses.append(float(loss.detach().cpu()) * args.gradient_accumulation)
            if (
                batch_index % args.gradient_accumulation == 0
                or batch_index == len(train_loader)
            ):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()

        model.eval()
        truth: list[int] = []
        predictions: list[int] = []
        top_three: list[list[int]] = []
        validation_started = time.perf_counter()
        with torch.inference_mode():
            for batch in validation_loader:
                labels = batch.pop("labels").cuda(non_blocking=True)
                inputs = {
                    key: value.cuda(non_blocking=True)
                    for key, value in batch.items()
                }
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    logits = model(**inputs).logits
                order = torch.argsort(logits, dim=1, descending=True)
                truth.extend(int(value) for value in labels.cpu())
                predictions.extend(int(value) for value in order[:, 0].cpu())
                top_three.extend(
                    [[int(value) for value in row] for row in order[:, :3].cpu()]
                )
        exact = [left == right for left, right in zip(truth, predictions, strict=True)]
        top3 = [
            expected in offered
            for expected, offered in zip(truth, top_three, strict=True)
        ]
        metrics = {
            "epoch": epoch,
            "train_loss": round(float(np.mean(losses)), 6),
            "train_seconds": round(time.perf_counter() - epoch_started, 3),
            "validation_seconds": round(
                time.perf_counter() - validation_started,
                3,
            ),
            "validation_top_1_accuracy": round(float(np.mean(exact)), 6),
            "validation_top_3_accuracy": round(float(np.mean(top3)), 6),
        }
        epochs.append(metrics)
        print(json.dumps(metrics, ensure_ascii=False), flush=True)
        if metrics["validation_top_1_accuracy"] > best_accuracy:
            best_accuracy = float(metrics["validation_top_1_accuracy"])
            best_epoch = epoch
            model.save_pretrained(args.output, safe_serialization=True)
            tokenizer.save_pretrained(args.output)

    identity = {
        "schema": "baxy.full-catalog-operation-classifier-checkpoint.v1",
        "source_checkpoint": str(args.source),
        "source_checkpoint_config_sha256": _sha256(args.source / "config.json"),
        "training_sha256": _sha256(args.training),
        "validation_sha256": _sha256(args.validation),
        "catalog_operations": len(available),
        "classes": classes,
        "best_epoch": best_epoch,
        "best_validation_top_1_accuracy": best_accuracy,
        "blind_holdout_opened": False,
    }
    (args.output / "training_identity.json").write_text(
        json.dumps(identity, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report: dict[str, object] = {
        "schema": "baxy.full-catalog-operation-classifier-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_not_blind_not_promoted",
        "configuration": {
            "epochs": args.epochs,
            "repeat": args.repeat,
            "batch_size": args.batch_size,
            "gradient_accumulation": args.gradient_accumulation,
            "learning_rate": args.learning_rate,
            "class_weight_power": args.class_weight_power,
            "max_length": args.max_length,
        },
        "data": {
            "training_unique_rows": len(training_rows),
            "training_repeated_rows": len(repeated_training),
            "validation_rows": len(validation_rows),
            "classes": len(classes),
            "excluded_no_action": excluded_no_action,
            "excluded_unavailable": excluded_unavailable,
            "excluded_validation_overlap": excluded_overlap,
            "class_counts": dict(sorted(train_counts.items())),
        },
        "epochs": epochs,
        "best_epoch": best_epoch,
        "best_validation_top_1_accuracy": best_accuracy,
        "cuda": {
            "device": torch.cuda.get_device_name(0),
            "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 3),
            "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 3),
        },
        "checkpoint": {
            "path": str(args.output),
            "files": _checkpoint_identity(args.output),
        },
        "blind_holdout_opened": False,
    }
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--training", type=Path, default=TRAINING)
    parser.add_argument("--validation", type=Path, default=VALIDATION)
    parser.add_argument(
        "--expected-training-sha256",
        default=EXPECTED_TRAINING_SHA256,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--eval-batch-size", type=int, default=64)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--class-weight-power", type=float, default=0.5)
    parser.add_argument("--max-length", type=int, default=96)
    args = parser.parse_args()
    if args.epochs < 1 or args.repeat < 1:
        raise SystemExit("epochs and repeat must be positive")
    args.source = args.source.resolve(strict=True)
    args.training = args.training.resolve(strict=True)
    args.validation = args.validation.resolve(strict=True)
    args.output = args.output.resolve()
    args.report = args.report.resolve()
    report = train(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
