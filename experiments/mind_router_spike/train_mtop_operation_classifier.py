"""Fine-tune pinned multilingual E5 for exact MTOP operation classification.

This is a development experiment.  It reads only the hash-bound MTOP
``train`` and ``validation`` partitions, excludes the predeclared structural
quarantine, never opens official ``test``, and never dispatches an operation.
The checkpoint is written outside Git; the repo report contains hashes and
metrics but no utterance text.
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
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
for path in (REPO, SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
from baxy_mind.planner import required_predecessors  # noqa: E402
from baxy_mind.router import MODEL_NAME, MODEL_REVISION, QUERY_PREFIX  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_OUTPUT = (
    Path("D:/BAXYRuntime/experiments/mtop-operation-classifier-v1-direct")
)
DEFAULT_REPORT = (
    REPO
    / "artifacts"
    / "research"
    / "mtop_operation_classifier_finetune_v1.json"
)
DEFAULT_SUPPLEMENT = (
    REPO / "artifacts/research/functiongemma_training_corpus.v1.jsonl"
)
EXPECTED_SUPPLEMENT_SHA256 = (
    "b27e871a49aacd0f1e527235422547a21ceb0fabcb01505a4f687ad3ed51ba18"
)
NO_ACTION = "__none__"
LABEL_SEPARATOR = "\u241f"
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


def _terminal_operations(operations: Iterable[str]) -> tuple[str, ...]:
    ordered = tuple(dict.fromkeys(operations))
    technical = {
        predecessor
        for operation in ordered
        for predecessor in required_predecessors(operation)
        if predecessor in ordered
    }
    return tuple(operation for operation in ordered if operation not in technical)


def operation_label(row: dict[str, Any]) -> str | None:
    projection = row["projection"]
    if projection["reason"] in mtop.QUARANTINED_PROJECTION_REASONS:
        return None
    if projection["disposition"] not in {
        "candidate",
        "candidate_missing_information",
    }:
        return NO_ACTION
    terminal = _terminal_operations(projection["candidate_operations"])
    return terminal[0] if len(terminal) == 1 else None


def training_label(row: dict[str, Any], operation: str, mode: str) -> str:
    if mode == "operation":
        return operation
    if mode == "source-operation":
        source_intent = str(row["semantic"]["intent"])
        return f"{source_intent}{LABEL_SEPARATOR}{operation}"
    if mode == "operation-disposition":
        disposition = str(row["projection"]["disposition"])
        turn_kind = (
            "action"
            if disposition == "candidate"
            else "clarify"
            if disposition == "candidate_missing_information"
            else "conversation"
        )
        return f"{operation}{LABEL_SEPARATOR}{turn_kind}"
    if mode == "disposition":
        disposition = str(row["projection"]["disposition"])
        return (
            "action"
            if disposition == "candidate"
            else "clarify"
            if disposition == "candidate_missing_information"
            else "conversation"
        )
    if mode == "compatibility":
        return "compatible" if operation != NO_ACTION else "incompatible"
    raise ValueError(f"unsupported label mode: {mode}")


def operation_from_training_label(label: str, mode: str) -> str:
    if mode == "operation":
        return label
    if mode == "source-operation":
        return label.rsplit(LABEL_SEPARATOR, 1)[1]
    if mode == "operation-disposition":
        return label.split(LABEL_SEPARATOR, 1)[0]
    if mode == "disposition":
        return NO_ACTION
    if mode == "compatibility":
        return NO_ACTION
    raise ValueError(f"unsupported label mode: {mode}")


def disposition_from_training_label(label: str, mode: str) -> str:
    """Project a training label onto its user-visible turn disposition."""

    if mode == "operation-disposition":
        disposition = label.rsplit(LABEL_SEPARATOR, 1)[1]
        if disposition not in {"action", "clarify", "conversation"}:
            raise ValueError("unsupported disposition label")
        return disposition
    if mode == "disposition":
        if label not in {"action", "clarify", "conversation"}:
            raise ValueError("unsupported disposition label")
        return label
    if mode == "compatibility":
        if label not in {"compatible", "incompatible"}:
            raise ValueError("unsupported compatibility label")
        return "conversation"
    return "conversation" if operation_from_training_label(label, mode) == NO_ACTION else "action"


def _conditioned_operation(row: dict[str, Any]) -> str | None:
    override = row.get("_condition_operation")
    return str(override) if isinstance(override, str) else operation_label(row)


def _wrong_operation_pairs(
    rows: list[tuple[dict[str, Any], str]],
    operations: Iterable[str],
    *,
    count: int,
    negative_label: str = "conversation",
) -> list[tuple[dict[str, Any], str]]:
    """Pair supported turns with deterministic wrong sibling operations."""

    if count <= 0:
        return []
    supported = tuple(
        sorted({operation for operation in operations if operation != NO_ACTION})
    )
    by_family = {
        family: tuple(
            operation
            for operation in supported
            if operation.split(".", 1)[0] == family
        )
        for family in {operation.split(".", 1)[0] for operation in supported}
    }
    negatives: list[tuple[dict[str, Any], str]] = []
    for row, _label in rows:
        correct = operation_label(row)
        if correct in {None, NO_ACTION}:
            continue
        family = str(correct).split(".", 1)[0]
        siblings = tuple(
            operation
            for operation in by_family.get(family, ())
            if operation != correct
        )
        pool = siblings or tuple(
            operation for operation in supported if operation != correct
        )
        if not pool:
            continue
        identity = str(
            row.get("source_id") or row.get("mission_id") or row["text"]
        )
        offset = int(
            hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8],
            16,
        )
        for index in range(min(count, len(pool))):
            negative = dict(row)
            negative["_condition_operation"] = pool[(offset + index) % len(pool)]
            negatives.append((negative, negative_label))
    return negatives


@dataclass(frozen=True)
class EncodedDataset:
    encodings: dict[str, list[list[int]]]
    labels: list[int]
    auxiliary_labels: list[int] | None = None

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = {
            key: values[index]
            for key, values in self.encodings.items()
        } | {"labels": self.labels[index]}
        if self.auxiliary_labels is not None:
            item["auxiliary_labels"] = self.auxiliary_labels[index]
        return item


def _evaluate(
    model: Any,
    loader: Any,
    classes: list[str],
    class_operations: list[str],
    class_dispositions: list[str],
    *,
    device: Any,
) -> dict[str, Any]:
    import numpy as np
    import torch

    model.eval()
    losses: list[float] = []
    expected: list[int] = []
    scores: list[np.ndarray] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for batch in loader:
            labels = batch.pop("labels").to(device, non_blocking=True)
            batch.pop("auxiliary_labels", None)
            inputs = {
                key: value.to(device, non_blocking=True)
                for key, value in batch.items()
            }
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                output = model(**inputs, labels=labels)
            losses.append(float(output.loss.detach().cpu()))
            expected.extend(int(value) for value in labels.detach().cpu())
            scores.append(output.logits.detach().float().cpu().numpy())
    logits = np.concatenate(scores, axis=0)
    truth = np.asarray(expected, dtype=np.int64)
    order = np.argsort(-logits, axis=1)
    predictions = order[:, 0]
    label_exact = predictions == truth
    truth_operations = np.asarray(
        [class_operations[index] for index in truth],
        dtype=object,
    )
    predicted_operations = np.asarray(
        [class_operations[index] for index in predictions],
        dtype=object,
    )
    truth_dispositions = np.asarray(
        [class_dispositions[index] for index in truth],
        dtype=object,
    )
    predicted_dispositions = np.asarray(
        [class_dispositions[index] for index in predictions],
        dtype=object,
    )
    exact = predicted_operations == truth_operations
    disposition_exact = predicted_dispositions == truth_dispositions
    no_action = truth_operations == NO_ACTION
    supported = ~no_action
    per_operation: dict[str, Any] = {}
    for operation in sorted(set(class_operations)):
        mask = truth_operations == operation
        if mask.any():
            per_operation[operation] = {
                "cases": int(mask.sum()),
                "accuracy": round(float(exact[mask].mean()), 6),
            }
    per_disposition = {
        disposition: {
            "cases": int(mask.sum()),
            "accuracy": round(float(disposition_exact[mask].mean()), 6),
        }
        for disposition in sorted(set(class_dispositions))
        for mask in [truth_dispositions == disposition]
        if mask.any()
    }

    def operation_in_top_k(row_index: int, k: int) -> bool:
        ranked: list[str] = []
        for class_index in order[row_index]:
            operation = class_operations[int(class_index)]
            if operation not in ranked:
                ranked.append(operation)
            if len(ranked) >= k:
                break
        return str(truth_operations[row_index]) in ranked

    return {
        "loss": round(float(np.mean(losses)), 6),
        "cases": len(truth),
        "label_top_1_accuracy": round(float(label_exact.mean()), 6),
        "top_1_accuracy": round(float(exact.mean()), 6),
        "disposition_accuracy": round(float(disposition_exact.mean()), 6),
        "top_2_accuracy": round(
            float(np.mean([operation_in_top_k(i, 2) for i in range(len(truth))])),
            6,
        ),
        "top_3_accuracy": round(
            float(np.mean([operation_in_top_k(i, 3) for i in range(len(truth))])),
            6,
        ),
        "supported_accuracy": round(float(exact[supported].mean()), 6),
        "no_action_accuracy": round(float(exact[no_action].mean()), 6),
        "false_supported_on_no_action": round(
            float((predicted_operations[no_action] != NO_ACTION).mean()),
            6,
        ),
        "seconds": round(time.perf_counter() - started, 3),
        "per_operation": per_operation,
        "per_disposition": per_disposition,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import torch
    import torch.nn.functional as functional
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
    if args.output.exists() and any(args.output.iterdir()):
        raise RuntimeError(f"output checkpoint already exists: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    operations = [(row, operation_label(row)) for row in rows]
    condition_operations = tuple(
        sorted(
            {
                str(operation)
                for _row, operation in operations
                if operation not in {None, NO_ACTION}
            }
        )
    )
    labelled = [
        (row, training_label(row, str(operation), args.label_mode))
        for row, operation in operations
        if operation is not None
        and not (
            args.label_mode == "compatibility" and operation == NO_ACTION
        )
    ]
    classes = sorted(
        {str(label) for _row, label in labelled}
        | (
            {"compatible", "incompatible"}
            if args.label_mode == "compatibility"
            else set()
        )
    )
    class_operations = [
        operation_from_training_label(label, args.label_mode)
        for label in classes
    ]
    class_dispositions = [
        disposition_from_training_label(label, args.label_mode)
        for label in classes
    ]
    label_to_id = {label: index for index, label in enumerate(classes)}
    train_rows = [(row, str(label)) for row, label in labelled if row["split"] == "train"]
    validation_rows = [
        (row, str(label))
        for row, label in labelled
        if row["split"] == "validation"
    ]
    mtop_train_rows = len(train_rows)
    supplement_unique_rows = 0
    supplement_overlap_excluded = 0
    supplement_unsupported_excluded = 0
    supplement_sha256: str | None = None
    if args.supplement_repeat:
        if args.condition_on_operation:
            raise RuntimeError(
                "operation conditioning requires canonical MTOP projections"
            )
        if args.label_mode != "operation":
            raise RuntimeError("the reviewed supplement supports operation labels only")
        supplement_sha256 = _sha256(args.supplement_corpus)
        if supplement_sha256 != EXPECTED_SUPPLEMENT_SHA256:
            raise RuntimeError("the reviewed supplement corpus identity changed")
        validation_keys = {
            _normal_key(str(row["text"])) for row, _label in validation_rows
        }
        seen_keys: set[str] = set()
        supplement_rows: list[tuple[dict[str, Any], str]] = []
        for line in args.supplement_corpus.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            operation = str(row["operation"])
            operation = NO_ACTION if operation == "__no_action__" else operation
            key = _normal_key(str(row["text"]))
            if not key or key in validation_keys or key in seen_keys:
                supplement_overlap_excluded += 1
                continue
            if operation not in set(class_operations):
                supplement_unsupported_excluded += 1
                continue
            seen_keys.add(key)
            label = training_label(row, operation, args.label_mode)
            if label not in classes:
                supplement_unsupported_excluded += 1
                continue
            supplement_rows.append((row, label))
        supplement_unique_rows = len(supplement_rows)
        train_rows.extend(supplement_rows * args.supplement_repeat)
    if args.wrong_operation_negatives:
        if not args.condition_on_operation or args.label_mode not in {
            "compatibility",
            "disposition",
        }:
            raise RuntimeError(
                "wrong-operation negatives require conditioned disposition labels"
            )
    wrong_train_rows = _wrong_operation_pairs(
        train_rows,
        condition_operations,
        count=args.wrong_operation_negatives,
        negative_label=(
            "incompatible" if args.label_mode == "compatibility" else "conversation"
        ),
    )
    wrong_validation_rows = _wrong_operation_pairs(
        validation_rows,
        condition_operations,
        count=args.wrong_operation_negatives,
        negative_label=(
            "incompatible" if args.label_mode == "compatibility" else "conversation"
        ),
    )
    train_rows.extend(wrong_train_rows)
    train_counts = collections.Counter(label for _row, label in train_rows)
    auxiliary_classes = sorted(
        {
            str(row["semantic"]["intent"])
            for row, _label in train_rows
            if "semantic" in row
        }
    )
    auxiliary_label_to_id = {
        label: index for index, label in enumerate(auxiliary_classes)
    }
    class_weights = torch.tensor(
        [
            (
                (len(train_rows) / (len(classes) * train_counts[label]))
                ** args.class_weight_power
                if train_counts[label]
                else 0.0
            )
            for label in classes
        ],
        dtype=torch.float32,
        device="cuda",
    )
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_source,
        revision=args.model_revision or None,
        local_files_only=True,
    )

    def encode(items: list[tuple[dict[str, Any], str]]) -> EncodedDataset:
        texts = [args.query_prefix + str(row["text"]) for row, _label in items]
        if args.condition_on_operation:
            operations = [_conditioned_operation(row) for row, _label in items]
            if any(operation is None for operation in operations):
                raise RuntimeError("conditioned row has no operation projection")
            encodings = tokenizer(
                texts,
                text_pair=[
                    f"authenticated operation nomination: {operation}"
                    for operation in operations
                ],
                truncation=True,
                max_length=args.max_length,
                padding=False,
            )
        else:
            encodings = tokenizer(
                texts,
                truncation=True,
                max_length=args.max_length,
                padding=False,
            )
        return EncodedDataset(
            encodings={key: list(value) for key, value in encodings.items()},
            labels=[label_to_id[label] for _row, label in items],
            auxiliary_labels=(
                [
                    auxiliary_label_to_id.get(
                        str(row.get("semantic", {}).get("intent", "")),
                        -100,
                    )
                    for row, _label in items
                ]
                if args.auxiliary_intent_weight
                else None
            ),
        )

    train_dataset = encode(train_rows)
    validation_dataset = encode(validation_rows)
    wrong_validation_dataset = (
        encode(wrong_validation_rows) if wrong_validation_rows else None
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
    wrong_validation_loader = (
        DataLoader(
            wrong_validation_dataset,
            batch_size=args.eval_batch_size,
            shuffle=False,
            collate_fn=collator,
            num_workers=0,
            pin_memory=True,
        )
        if wrong_validation_dataset is not None
        else None
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_source,
        revision=args.model_revision or None,
        local_files_only=True,
        num_labels=len(classes),
        id2label={index: label for index, label in enumerate(classes)},
        label2id=label_to_id,
        ignore_mismatched_sizes=True,
    ).cuda()
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
    auxiliary_head = None
    if args.auxiliary_intent_weight:
        auxiliary_head = torch.nn.Linear(
            int(model.config.hidden_size),
            len(auxiliary_classes),
        ).cuda()
        torch.nn.init.normal_(auxiliary_head.weight, mean=0.0, std=0.02)
        torch.nn.init.zeros_(auxiliary_head.bias)
    parameters = list(model.parameters()) + (
        list(auxiliary_head.parameters()) if auxiliary_head is not None else []
    )
    if args.optimizer == "adafactor":
        optimizer = Adafactor(
            parameters,
            lr=args.learning_rate,
            scale_parameter=False,
            relative_step=False,
            warmup_init=False,
            weight_decay=args.weight_decay,
        )
    else:
        optimizer = torch.optim.AdamW(
            parameters,
            lr=args.learning_rate,
            weight_decay=args.weight_decay,
            fused=True,
        )
    steps_per_epoch = math.ceil(len(train_loader) / args.gradient_accumulation)
    total_steps = steps_per_epoch * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=math.ceil(total_steps * args.warmup_ratio),
        num_training_steps=total_steps,
    )
    scaler = torch.amp.GradScaler("cuda")
    torch.cuda.reset_peak_memory_stats()
    epochs: list[dict[str, Any]] = []
    best_accuracy = -1.0
    training_started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        if auxiliary_head is not None:
            auxiliary_head.train()
        losses: list[float] = []
        epoch_started = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        for batch_index, batch in enumerate(train_loader, start=1):
            labels = batch.pop("labels").cuda(non_blocking=True)
            auxiliary_labels = batch.pop("auxiliary_labels", None)
            if auxiliary_labels is not None:
                auxiliary_labels = auxiliary_labels.cuda(non_blocking=True)
            inputs = {
                key: value.cuda(non_blocking=True)
                for key, value in batch.items()
            }
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                output = model(
                    **inputs,
                    output_hidden_states=auxiliary_head is not None,
                )
                if args.focal_gamma:
                    log_probabilities = functional.log_softmax(
                        output.logits,
                        dim=-1,
                    )
                    probabilities = log_probabilities.exp()
                    true_probabilities = probabilities.gather(
                        1,
                        labels.unsqueeze(1),
                    ).squeeze(1)
                    per_example_cross_entropy = functional.nll_loss(
                        log_probabilities,
                        labels,
                        weight=class_weights,
                        reduction="none",
                    )
                    loss = (
                        (1.0 - true_probabilities).pow(args.focal_gamma)
                        * per_example_cross_entropy
                    ).mean()
                else:
                    loss = functional.cross_entropy(
                        output.logits,
                        labels,
                        weight=class_weights,
                        label_smoothing=args.label_smoothing,
                    )
                if auxiliary_head is not None and auxiliary_labels is not None:
                    auxiliary_logits = auxiliary_head(
                        output.hidden_states[-1][:, 0, :]
                    )
                    auxiliary_loss = functional.cross_entropy(
                        auxiliary_logits,
                        auxiliary_labels,
                        ignore_index=-100,
                    )
                    loss = loss + args.auxiliary_intent_weight * auxiliary_loss
            losses.append(float(loss.detach().cpu()))
            accumulated_loss = loss / args.gradient_accumulation
            scaler.scale(accumulated_loss).backward()
            update = (
                batch_index % args.gradient_accumulation == 0
                or batch_index == len(train_loader)
            )
            if update:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(parameters, args.max_grad_norm)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
        evaluation = _evaluate(
            model,
            validation_loader,
            classes,
            class_operations,
            class_dispositions,
            device=torch.device("cuda"),
        )
        wrong_operation_evaluation = (
            _evaluate(
                model,
                wrong_validation_loader,
                classes,
                class_operations,
                class_dispositions,
                device=torch.device("cuda"),
            )
            if wrong_validation_loader is not None
            else None
        )
        epoch_report = {
            "epoch": epoch,
            "train_loss": round(float(np.mean(losses)), 6),
            "learning_rate": float(scheduler.get_last_lr()[0]),
            "train_seconds": round(time.perf_counter() - epoch_started, 3),
            "validation": evaluation,
            "wrong_operation_validation": wrong_operation_evaluation,
        }
        epochs.append(epoch_report)
        print(json.dumps(epoch_report, ensure_ascii=False), flush=True)
        selection_accuracy = (
            evaluation["label_top_1_accuracy"]
            if args.label_mode in {
                "compatibility",
                "operation-disposition",
                "disposition",
            }
            else evaluation["top_1_accuracy"]
        )
        if wrong_operation_evaluation is not None:
            selection_accuracy = min(
                float(selection_accuracy),
                float(wrong_operation_evaluation["label_top_1_accuracy"]),
            )
        if selection_accuracy > best_accuracy:
            best_accuracy = float(selection_accuracy)
            model.save_pretrained(
                args.output,
                safe_serialization=True,
                max_shard_size="1GB",
            )
            tokenizer.save_pretrained(args.output)
            (args.output / "training_identity.json").write_text(
                json.dumps(
                    {
                        "schema": "baxy.mtop-operation-classifier-checkpoint.v1",
                        "source_model": args.model_source,
                        "source_revision": args.model_revision,
                        "mtop_development_sha256": identity.corpus.sha256,
                        "mtop_manifest_sha256": identity.manifest.sha256,
                        "mtop_map_sha256": manifest["source"]["map_sha256"],
                        "mtop_test_content_read": False,
                        "supplement_sha256": supplement_sha256,
                        "auxiliary_intent_weight": args.auxiliary_intent_weight,
                        "focal_gamma": args.focal_gamma,
                        "label_mode": args.label_mode,
                        "condition_on_operation": args.condition_on_operation,
                        "wrong_operation_negatives": args.wrong_operation_negatives,
                        "class_to_operation": dict(
                            zip(classes, class_operations, strict=True)
                        ),
                        "class_to_disposition": dict(
                            zip(classes, class_dispositions, strict=True)
                        ),
                        "best_epoch": epoch,
                        "best_validation_top_1_accuracy": best_accuracy,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

    mtop._assert_input_identity_stable(identity)
    checkpoint_files = sorted(
        path for path in args.output.iterdir() if path.is_file()
    )
    report = {
        "schema": "baxy.mtop-operation-classifier-finetune.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_mtop_test_remains_sealed",
        "source": {
            "model": args.model_source,
            "revision": args.model_revision,
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
        },
        "configuration": {
            "seed": SEED,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "eval_batch_size": args.eval_batch_size,
            "max_length": args.max_length,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "warmup_ratio": args.warmup_ratio,
            "max_grad_norm": args.max_grad_norm,
            "class_weight_power": args.class_weight_power,
            "label_smoothing": args.label_smoothing,
            "label_mode": args.label_mode,
            "supplement_repeat": args.supplement_repeat,
            "auxiliary_intent_weight": args.auxiliary_intent_weight,
            "focal_gamma": args.focal_gamma,
            "mixed_precision": "fp16",
            "optimizer": args.optimizer,
            "gradient_accumulation": args.gradient_accumulation,
            "gradient_checkpointing": args.gradient_checkpointing,
            "query_prefix": args.query_prefix,
            "condition_on_operation": args.condition_on_operation,
            "wrong_operation_negatives": args.wrong_operation_negatives,
        },
        "data": {
            "train_rows": len(train_rows),
            "mtop_train_rows": mtop_train_rows,
            "wrong_operation_train_rows": len(wrong_train_rows),
            "supplement_unique_rows": supplement_unique_rows,
            "supplement_overlap_excluded": supplement_overlap_excluded,
            "supplement_unsupported_excluded": supplement_unsupported_excluded,
            "supplement_sha256": supplement_sha256,
            "validation_rows": len(validation_rows),
            "wrong_operation_validation_rows": len(wrong_validation_rows),
            "classes": len(classes),
            "operations": len(condition_operations),
            "auxiliary_intent_classes": len(auxiliary_classes),
            "class_to_operation": dict(
                zip(classes, class_operations, strict=True)
            ),
            "class_to_disposition": dict(
                zip(classes, class_dispositions, strict=True)
            ),
            "train_class_counts": dict(sorted(train_counts.items())),
            "class_weights": {
                label: round(float(class_weights[index].detach().cpu()), 6)
                for index, label in enumerate(classes)
            },
            "validation_class_counts": dict(
                sorted(
                    collections.Counter(
                        label for _row, label in validation_rows
                    ).items()
                )
            ),
        },
        "epochs": epochs,
        "best_validation_top_1_accuracy": best_accuracy,
        "training_seconds": round(time.perf_counter() - training_started, 3),
        "cuda": {
            "device": torch.cuda.get_device_name(0),
            "peak_allocated_mib": round(
                torch.cuda.max_memory_allocated() / (1024 * 1024),
                3,
            ),
            "peak_reserved_mib": round(
                torch.cuda.max_memory_reserved() / (1024 * 1024),
                3,
            ),
        },
        "checkpoint": {
            "path": str(args.output.resolve()),
            "files": [
                {
                    "name": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in checkpoint_files
            ],
        },
        "status": "candidate" if best_accuracy >= 0.99 else "rejected_below_0_99",
    }
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--eval-batch-size", type=int, default=128)
    parser.add_argument("--max-length", type=int, default=96)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--class-weight-power", type=float, default=0.0)
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument(
        "--label-mode",
        choices=(
            "operation",
            "source-operation",
            "operation-disposition",
            "disposition",
            "compatibility",
        ),
        default="operation",
    )
    parser.add_argument(
        "--supplement-corpus",
        type=Path,
        default=DEFAULT_SUPPLEMENT,
    )
    parser.add_argument("--supplement-repeat", type=int, default=0)
    parser.add_argument("--auxiliary-intent-weight", type=float, default=0.0)
    parser.add_argument("--focal-gamma", type=float, default=0.0)
    parser.add_argument("--model-source", default=MODEL_NAME)
    parser.add_argument("--model-revision", default=MODEL_REVISION)
    parser.add_argument("--query-prefix", default=QUERY_PREFIX)
    parser.add_argument("--optimizer", choices=("adamw", "adafactor"), default="adamw")
    parser.add_argument("--gradient-accumulation", type=int, default=1)
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--condition-on-operation", action="store_true")
    parser.add_argument("--wrong-operation-negatives", type=int, default=0)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.report = args.report.resolve()
    args.supplement_corpus = args.supplement_corpus.resolve()
    report = train(args)
    print(
        json.dumps(
            {
                "status": report["status"],
                "best_validation_top_1_accuracy": report[
                    "best_validation_top_1_accuracy"
                ],
                "training_seconds": report["training_seconds"],
                "cuda": report["cuda"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
