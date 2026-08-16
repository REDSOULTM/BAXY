"""Train a contract-conditioned verifier over frozen MTOP top-k candidates.

The operation retriever is frozen before this run.  Training reads only the
hash-bound MTOP train partition plus static operation contract descriptions;
validation is used for development model selection and official test remains
sealed.  The verifier is advisory and never dispatches an operation.
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
import train_mtop_operation_classifier as trainer  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_RETRIEVER = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-classifier-v8-mdeberta"
)
DEFAULT_OUTPUT = Path(
    "D:/BAXYRuntime/experiments/mtop-contract-verifier-v9"
)
DEFAULT_REPORT = REPO / "artifacts/research/mtop_contract_verifier_v9.json"
SEED = 20260801

CONTRACTS = {
    "__none__": "No authenticated computer operation is requested. The utterance is conversational, informational outside the available tools, or must not cause an effect.",
    "calendar.event.list": "Read and list existing calendar events or agenda entries. Do not create, update, or delete an event.",
    "media.control": "Control the current media session: pause, resume, stop, skip to the next track, or return to the previous track.",
    "media.play.query": "Search for and start playing music, a song, artist, album, genre, playlist, podcast, or other requested media.",
    "media.seek.relative": "Move the current media playback position forward or backward by a relative duration.",
    "media.status": "Read what is currently playing or the current media playback status without changing playback.",
    "message.send": "Send a message containing user-provided content to a named recipient or destination.",
    "notification.cancel.latest": "Delete or cancel a previously scheduled alarm, timer, or notification so it will not fire later. This is not silencing an alarm that is ringing now.",
    "notification.dismiss": "Silence, stop, or dismiss an alarm or notification that is ringing or due now. This does not delete a future scheduled alarm.",
    "notification.schedule": "Create or set a new alarm, timer, or scheduled notification for a future time or after a duration.",
    "reminder.create": "Create a new reminder for a task, event, person, place, date, or time.",
    "reminder.delete": "Delete an existing reminder identified by its title or description.",
    "reminder.list": "List or read multiple existing reminders without changing them.",
    "reminder.resolve.exact": "Find and read one existing reminder matching a specific title or description without deleting it.",
    "web.search": "Search the web for requested information, facts, weather, places, people, products, media information, or general knowledge.",
}

HARD_NEGATIVES = {
    "__none__": (),
    "calendar.event.list": ("web.search", "reminder.list", "__none__"),
    "media.control": ("media.play.query", "media.status", "media.seek.relative", "__none__"),
    "media.play.query": ("media.control", "media.status", "web.search", "__none__"),
    "media.seek.relative": ("media.control", "media.status", "__none__"),
    "media.status": ("media.play.query", "media.control", "web.search", "__none__"),
    "message.send": ("web.search", "reminder.create", "__none__"),
    "notification.cancel.latest": ("notification.dismiss", "notification.schedule", "reminder.delete", "__none__"),
    "notification.dismiss": ("notification.cancel.latest", "notification.schedule", "media.control", "__none__"),
    "notification.schedule": ("notification.cancel.latest", "notification.dismiss", "reminder.create", "__none__"),
    "reminder.create": ("reminder.resolve.exact", "reminder.delete", "notification.schedule", "__none__"),
    "reminder.delete": ("reminder.resolve.exact", "reminder.create", "reminder.list", "__none__"),
    "reminder.list": ("reminder.resolve.exact", "calendar.event.list", "__none__"),
    "reminder.resolve.exact": ("reminder.list", "reminder.create", "reminder.delete", "__none__"),
    "web.search": ("media.status", "media.play.query", "calendar.event.list", "__none__"),
}

DOMAIN_NEGATIVES = {
    "alarm": ("notification.schedule", "notification.cancel.latest", "notification.dismiss"),
    "calendar": ("calendar.event.list", "reminder.create"),
    "messaging": ("message.send",),
    "music": ("media.play.query", "media.control", "media.status", "media.seek.relative"),
    "reminder": ("reminder.create", "reminder.delete", "reminder.list", "reminder.resolve.exact"),
    "weather": ("web.search",),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class PairDataset:
    encodings: dict[str, list[list[int]]]
    labels: list[int] | None = None

    def __len__(self) -> int:
        return len(next(iter(self.encodings.values())))

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = {key: values[index] for key, values in self.encodings.items()}
        if self.labels is not None:
            item["labels"] = self.labels[index]
        return item


def _select_negatives(row: dict[str, Any], expected: str, classes: list[str], count: int) -> list[str]:
    priority = list(HARD_NEGATIVES[expected])
    if expected == trainer.NO_ACTION:
        priority = list(DOMAIN_NEGATIVES.get(str(row["semantic"]["domain"]), ()))
    digest = hashlib.sha256(str(row["source_id"]).encode("utf-8")).digest()
    offset = int.from_bytes(digest[:4], "big") % len(classes)
    rotated = classes[offset:] + classes[:offset]
    selected: list[str] = []
    for candidate in priority + rotated:
        if candidate != expected and candidate not in selected:
            selected.append(candidate)
        if len(selected) == count:
            break
    return selected


def _retrieve_candidates(
    checkpoint: Path,
    texts: list[str],
    batch_size: int,
    count: int,
) -> tuple[list[str], Any]:
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint, local_files_only=True
    ).cuda().eval()
    chunks: list[np.ndarray] = []
    with torch.inference_mode():
        for offset in range(0, len(texts), batch_size):
            inputs = tokenizer(
                texts[offset : offset + batch_size],
                padding=True,
                truncation=True,
                max_length=96,
                return_tensors="pt",
            )
            inputs = {key: value.cuda(non_blocking=True) for key, value in inputs.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                chunks.append(model(**inputs).logits.float().cpu().numpy())
    scores = np.concatenate(chunks, axis=0)
    classes = [str(model.config.id2label[index]) for index in range(model.config.num_labels)]
    order = np.argsort(-scores, axis=1)[:, :count]
    del model
    torch.cuda.empty_cache()
    return classes, order


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

    if args.output.exists() and any(args.output.iterdir()):
        raise RuntimeError(f"output checkpoint already exists: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS, mtop.MANIFEST
    )
    labelled = [(row, trainer.operation_label(row)) for row in rows]
    labelled = [(row, str(label)) for row, label in labelled if label is not None]
    train_rows = [(row, label) for row, label in labelled if row["split"] == "train"]
    validation_rows = [(row, label) for row, label in labelled if row["split"] == "validation"]
    classes = sorted({label for _row, label in labelled})
    if set(classes) != set(CONTRACTS):
        raise RuntimeError("contract descriptions do not match MTOP operation classes")

    validation_texts = [str(row["text"]) for row, _label in validation_rows]
    retriever_classes, validation_candidate_ids = _retrieve_candidates(
        args.retriever, validation_texts, args.eval_batch_size, args.candidates
    )
    validation_expected = [label for _row, label in validation_rows]
    retrieval_hits = np.asarray(
        [
            expected in [retriever_classes[int(index)] for index in candidate_ids]
            for expected, candidate_ids in zip(validation_expected, validation_candidate_ids, strict=True)
        ]
    )

    tokenizer = AutoTokenizer.from_pretrained(args.retriever, local_files_only=True)
    train_first: list[str] = []
    train_second: list[str] = []
    train_labels: list[int] = []
    for row, expected in train_rows:
        candidates = [expected] + _select_negatives(
            row, expected, classes, args.negatives_per_positive
        )
        for candidate in candidates:
            train_first.append(str(row["text"]))
            train_second.append(f"{candidate}: {CONTRACTS[candidate]}")
            train_labels.append(int(candidate == expected))
    train_encodings = tokenizer(
        train_first,
        text_pair=train_second,
        truncation=True,
        max_length=args.max_length,
        padding=False,
    )
    train_dataset = PairDataset(
        {key: list(value) for key, value in train_encodings.items()}, train_labels
    )

    validation_first: list[str] = []
    validation_second: list[str] = []
    validation_candidates: list[list[str]] = []
    for text, candidate_ids in zip(validation_texts, validation_candidate_ids, strict=True):
        candidate_labels = [retriever_classes[int(index)] for index in candidate_ids]
        validation_candidates.append(candidate_labels)
        for candidate in candidate_labels:
            validation_first.append(text)
            validation_second.append(f"{candidate}: {CONTRACTS[candidate]}")
    validation_encodings = tokenizer(
        validation_first,
        text_pair=validation_second,
        truncation=True,
        max_length=args.max_length,
        padding=False,
    )
    validation_dataset = PairDataset(
        {key: list(value) for key, value in validation_encodings.items()}
    )
    collator = DataCollatorWithPadding(
        tokenizer=tokenizer, pad_to_multiple_of=8, return_tensors="pt"
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
        args.retriever,
        local_files_only=True,
        num_labels=2,
        id2label={0: "reject", 1: "accept"},
        label2id={"reject": 0, "accept": 1},
        ignore_mismatched_sizes=True,
    ).cuda()
    base = getattr(model, model.base_model_prefix)
    if args.freeze_layers:
        for parameter in base.embeddings.parameters():
            parameter.requires_grad = False
        for layer in base.encoder.layer[: args.freeze_layers]:
            for parameter in layer.parameters():
                parameter.requires_grad = False
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = Adafactor(
        trainable,
        lr=args.learning_rate,
        scale_parameter=False,
        relative_step=False,
        warmup_init=False,
        weight_decay=args.weight_decay,
    )
    steps_per_epoch = math.ceil(len(train_loader) / args.gradient_accumulation)
    total_steps = steps_per_epoch * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=math.ceil(total_steps * args.warmup_ratio),
        num_training_steps=total_steps,
    )
    class_weights = torch.tensor(
        [1.0, float(args.negatives_per_positive)], device="cuda"
    )
    scaler = torch.amp.GradScaler("cuda")
    torch.cuda.reset_peak_memory_stats()
    epochs: list[dict[str, Any]] = []
    best_accuracy = -1.0
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        losses: list[float] = []
        epoch_started = time.perf_counter()
        for batch_index, batch in enumerate(train_loader, start=1):
            labels = batch.pop("labels").cuda(non_blocking=True)
            inputs = {key: value.cuda(non_blocking=True) for key, value in batch.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(**inputs).logits
                loss = functional.cross_entropy(logits, labels, weight=class_weights)
            losses.append(float(loss.detach().cpu()))
            scaler.scale(loss / args.gradient_accumulation).backward()
            if batch_index % args.gradient_accumulation == 0 or batch_index == len(train_loader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(trainable, args.max_grad_norm)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)

        model.eval()
        verification_scores: list[np.ndarray] = []
        with torch.inference_mode():
            for batch in validation_loader:
                inputs = {key: value.cuda(non_blocking=True) for key, value in batch.items()}
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    logits = model(**inputs).logits
                verification_scores.append(
                    (logits[:, 1] - logits[:, 0]).float().cpu().numpy()
                )
        scores = np.concatenate(verification_scores).reshape(
            len(validation_rows), args.candidates
        )
        predictions = [
            candidates[int(np.argmax(row_scores))]
            for candidates, row_scores in zip(validation_candidates, scores, strict=True)
        ]
        exact = np.asarray(
            [prediction == expected for prediction, expected in zip(predictions, validation_expected, strict=True)]
        )
        no_action = np.asarray([expected == trainer.NO_ACTION for expected in validation_expected])
        per_operation = {}
        for operation in classes:
            mask = np.asarray([expected == operation for expected in validation_expected])
            if mask.any():
                per_operation[operation] = {
                    "cases": int(mask.sum()),
                    "accuracy": round(float(exact[mask].mean()), 6),
                }
        evaluation = {
            "cases": len(exact),
            "top_1_accuracy": round(float(exact.mean()), 6),
            "errors": int((~exact).sum()),
            "no_action_accuracy": round(float(exact[no_action].mean()), 6),
            "false_supported_on_no_action": round(
                float(np.mean([predictions[index] != trainer.NO_ACTION for index in np.flatnonzero(no_action)])),
                6,
            ),
            "retrieval_top_k_accuracy": round(float(retrieval_hits.mean()), 6),
            "retrieval_misses": int((~retrieval_hits).sum()),
            "per_operation": per_operation,
        }
        epoch_report = {
            "epoch": epoch,
            "train_loss": round(float(np.mean(losses)), 6),
            "train_seconds": round(time.perf_counter() - epoch_started, 3),
            "validation": evaluation,
        }
        epochs.append(epoch_report)
        print(json.dumps(epoch_report, ensure_ascii=False), flush=True)
        if evaluation["top_1_accuracy"] > best_accuracy:
            best_accuracy = float(evaluation["top_1_accuracy"])
            model.save_pretrained(args.output, safe_serialization=True, max_shard_size="1GB")
            tokenizer.save_pretrained(args.output)
            (args.output / "training_identity.json").write_text(
                json.dumps(
                    {
                        "schema": "baxy.mtop-contract-verifier-checkpoint.v1",
                        "retriever": str(args.retriever.resolve()),
                        "mtop_development_sha256": identity.corpus.sha256,
                        "mtop_manifest_sha256": identity.manifest.sha256,
                        "mtop_test_content_read": False,
                        "best_epoch": epoch,
                        "best_validation_top_1_accuracy": best_accuracy,
                        "contracts_sha256": hashlib.sha256(
                            json.dumps(CONTRACTS, sort_keys=True).encode("utf-8")
                        ).hexdigest(),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

    mtop._assert_input_identity_stable(identity)
    checkpoint_files = sorted(path for path in args.output.iterdir() if path.is_file())
    report = {
        "schema": "baxy.mtop-contract-verifier-finetune.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_mtop_test_remains_sealed",
        "source": {
            "retriever": str(args.retriever.resolve()),
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
            "gradient_accumulation": args.gradient_accumulation,
            "freeze_layers": args.freeze_layers,
            "candidates": args.candidates,
            "negatives_per_positive": args.negatives_per_positive,
        },
        "data": {
            "train_utterances": len(train_rows),
            "train_pairs": len(train_dataset),
            "validation_utterances": len(validation_rows),
            "validation_pairs": len(validation_dataset),
            "classes": classes,
            "train_operation_counts": dict(sorted(collections.Counter(label for _row, label in train_rows).items())),
        },
        "epochs": epochs,
        "best_validation_top_1_accuracy": best_accuracy,
        "training_seconds": round(time.perf_counter() - started, 3),
        "cuda": {
            "device": torch.cuda.get_device_name(0),
            "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 1048576, 3),
            "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 1048576, 3),
        },
        "checkpoint": {
            "path": str(args.output.resolve()),
            "files": [
                {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in checkpoint_files
            ],
        },
        "status": "candidate" if best_accuracy >= 0.999 else "rejected_below_0_999",
    }
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retriever", type=Path, default=DEFAULT_RETRIEVER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--eval-batch-size", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--gradient-accumulation", type=int, default=2)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--freeze-layers", type=int, default=8)
    parser.add_argument("--candidates", type=int, default=5)
    parser.add_argument("--negatives-per-positive", type=int, default=3)
    args = parser.parse_args()
    args.retriever = args.retriever.resolve()
    args.output = args.output.resolve()
    args.report = args.report.resolve()
    result = train(args)
    print(
        json.dumps(
            {
                "status": result["status"],
                "best_validation_top_1_accuracy": result["best_validation_top_1_accuracy"],
                "training_seconds": result["training_seconds"],
                "cuda": result["cuda"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
