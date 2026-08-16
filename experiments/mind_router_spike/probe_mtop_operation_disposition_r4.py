"""Evaluate a joint MTOP operation/disposition checkpoint on opened validation.

The official MTOP test partition and BAXY blind reserve remain sealed.  R4 is
identified only by the source ids in the existing product-validation artifact.
This probe performs classifier inference only and cannot dispatch operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
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


DEFAULT_CHECKPOINT = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-disposition-classifier-v10"
)
DEFAULT_R4 = (
    REPO
    / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
)
DEFAULT_REPORT = (
    REPO
    / "artifacts/research/mtop_operation_disposition_classifier_v10_r4.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    if not total:
        raise ValueError("empty evaluation slice")
    joint = sum(bool(row["joint_correct"]) for row in records)
    operation_rows = [
        row for row in records if row["operation_correct"] is not None
    ]
    operation = sum(bool(row["operation_correct"]) for row in operation_rows)
    disposition = sum(bool(row["disposition_correct"]) for row in records)
    by_expected_disposition = {
        name: {
            "cases": len(rows),
            "joint_correct": sum(bool(row["joint_correct"]) for row in rows),
            "joint_accuracy": round(
                sum(bool(row["joint_correct"]) for row in rows) / len(rows),
                6,
            ),
        }
        for name in sorted({str(row["expected_disposition"]) for row in records})
        for rows in [[
            row for row in records if row["expected_disposition"] == name
        ]]
    }
    return {
        "cases": total,
        "joint_correct": joint,
        "joint_accuracy": round(joint / total, 6),
        "operation_correct": operation if operation_rows else None,
        "operation_accuracy": (
            round(operation / len(operation_rows), 6)
            if operation_rows
            else None
        ),
        "disposition_correct": disposition,
        "disposition_accuracy": round(disposition / total, 6),
        "by_expected_disposition": by_expected_disposition,
        "error_pairs": [
            {"count": count, "pair": pair}
            for pair, count in Counter(
                (
                    f"{row['expected_operation']}|{row['expected_disposition']}"
                    f" -> {row['predicted_operation']}|"
                    f"{row['predicted_disposition']}"
                )
                for row in records
                if not row["joint_correct"]
            ).most_common()
        ],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if args.report.exists():
        raise RuntimeError(f"refusing to overwrite report: {args.report}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA evaluation is unavailable")
    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    labelled = [
        (row, str(operation))
        for row in rows
        for operation in [trainer.operation_label(row)]
        if row["split"] == "validation" and operation is not None
    ]
    r4_source = json.loads(args.r4.read_text(encoding="utf-8"))
    r4_ids = {str(row["source_id"]) for row in r4_source["samples"]}
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).cuda().eval()
    labels = [
        str(model.config.id2label[index])
        for index in range(model.config.num_labels)
    ]
    predictions: list[str] = []
    with torch.inference_mode():
        for offset in range(0, len(labelled), args.batch_size):
            batch = labelled[offset : offset + args.batch_size]
            texts = [str(row["text"]) for row, _operation in batch]
            if args.condition_on_operation:
                encoded = tokenizer(
                    texts,
                    text_pair=[
                        f"authenticated operation nomination: {operation}"
                        for _row, operation in batch
                    ],
                    padding=True,
                    truncation=True,
                    max_length=112,
                    return_tensors="pt",
                )
            else:
                encoded = tokenizer(
                    texts,
                    padding=True,
                    truncation=True,
                    max_length=96,
                    return_tensors="pt",
                )
            encoded = {
                name: value.cuda(non_blocking=True)
                for name, value in encoded.items()
            }
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(**encoded).logits
            predictions.extend(
                labels[int(index)]
                for index in np.argmax(
                    logits.float().cpu().numpy(),
                    axis=1,
                )
            )
    records = []
    for (row, operation), predicted in zip(
        labelled,
        predictions,
        strict=True,
    ):
        expected = trainer.training_label(
            row,
            operation,
            args.label_mode,
        )
        expected_disposition = trainer.disposition_from_training_label(
            expected,
            args.label_mode,
        )
        predicted_operation = (
            trainer.operation_from_training_label(
                predicted,
                args.label_mode,
            )
            if args.label_mode != "disposition"
            else None
        )
        predicted_disposition = trainer.disposition_from_training_label(
            predicted,
            args.label_mode,
        )
        records.append(
            {
                "source_id": row["source_id"],
                "in_r4": str(row["source_id"]) in r4_ids,
                "expected_operation": operation,
                "expected_disposition": expected_disposition,
                "predicted_operation": predicted_operation,
                "predicted_disposition": predicted_disposition,
                "joint_correct": predicted == expected,
                "operation_correct": (
                    predicted_operation == operation
                    if predicted_operation is not None
                    else None
                ),
                "disposition_correct": (
                    predicted_disposition == expected_disposition
                ),
            }
        )
    r4_records = [row for row in records if row["in_r4"]]
    if len(r4_records) != len(r4_ids):
        raise RuntimeError("R4 source ids escaped the labelled validation population")
    report = {
        "schema": "baxy.mtop-operation-disposition-r4.v2",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_validation_only_test_and_blind_reserve_sealed",
        "authority": "classifier_evaluation_only_no_core_or_provider",
        "contains_utterance_text": False,
        "effects_executed": 0,
        "sources": {
            "checkpoint": str(args.checkpoint),
            "checkpoint_config_sha256": _sha256(args.checkpoint / "config.json"),
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "r4_sha256": _sha256(args.r4),
            "mtop_test_content_read": False,
            "baxy_blind_reserve_opened": False,
            "label_mode": args.label_mode,
            "condition_on_operation": args.condition_on_operation,
        },
        "all_validation": _metrics(records),
        "r4": _metrics(r4_records),
        "records": records,
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--r4", type=Path, default=DEFAULT_R4)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--label-mode",
        choices=("operation-disposition", "disposition"),
        default="operation-disposition",
    )
    parser.add_argument("--condition-on-operation", action="store_true")
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve(strict=True)
    args.r4 = args.r4.resolve(strict=True)
    args.report = args.report.resolve()
    report = run(args)
    print(
        json.dumps(
            {
                "all_validation": report["all_validation"],
                "r4": report["r4"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
