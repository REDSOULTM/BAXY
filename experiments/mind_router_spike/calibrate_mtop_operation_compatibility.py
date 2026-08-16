"""Calibrate a conservative compatibility threshold on MTOP validation only."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    train_mtop_operation_classifier as trainer,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_CHECKPOINT = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-compatibility-verifier-v16"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts/research/mtop_operation_compatibility_verifier_v16_calibration.json"
)


def _select_threshold(
    compatible_scores: np.ndarray,
    incompatible_scores: np.ndarray,
) -> dict[str, float] | None:
    """Choose the threshold maximizing the weaker of accept and reject."""

    values = np.unique(
        np.concatenate(
            (
                np.asarray([0.0, 1.0], dtype=np.float64),
                compatible_scores.astype(np.float64),
                incompatible_scores.astype(np.float64),
            )
        )
    )
    thresholds = np.unique(
        np.concatenate((values, (values[:-1] + values[1:]) / 2.0))
    )
    best: tuple[tuple[float, float, float], dict[str, float]] | None = None
    for threshold in thresholds:
        compatible_accuracy = float(np.mean(compatible_scores >= threshold))
        incompatible_accuracy = float(np.mean(incompatible_scores < threshold))
        weakest = min(compatible_accuracy, incompatible_accuracy)
        metrics = {
            "threshold": float(threshold),
            "compatible_accuracy": compatible_accuracy,
            "incompatible_accuracy": incompatible_accuracy,
            "minimum_accuracy": weakest,
        }
        rank = (
            weakest,
            (compatible_accuracy + incompatible_accuracy) / 2.0,
            -abs(float(threshold) - 0.5),
        )
        if best is None or rank > best[0]:
            best = (rank, metrics)
    return None if best is None else best[1]


def _score(
    model: Any,
    tokenizer: Any,
    rows: list[tuple[dict[str, Any], str]],
    *,
    compatible_id: int,
    batch_size: int,
    max_length: int,
    device: Any,
) -> np.ndarray:
    import torch

    scores: list[np.ndarray] = []
    model.eval()
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        encoded = tokenizer(
            [str(row["text"]) for row, _label in batch],
            text_pair=[
                "authenticated operation nomination: "
                + str(trainer._conditioned_operation(row))
                for row, _label in batch
            ],
            truncation=True,
            max_length=max_length,
            padding=True,
            return_tensors="pt",
        )
        with torch.inference_mode():
            logits = model(
                **{key: value.to(device) for key, value in encoded.items()}
            ).logits
            probability = torch.softmax(logits, dim=-1)[:, compatible_id]
        scores.append(probability.detach().cpu().numpy())
    return np.concatenate(scores).astype(np.float64)


def calibrate(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    rows, manifest, identity = trainer.mtop._load_development(
        trainer.mtop.DEVELOPMENT_CORPUS,
        trainer.mtop.MANIFEST,
    )
    operations = [(row, trainer.operation_label(row)) for row in rows]
    condition_operations = tuple(
        sorted(
            {
                str(operation)
                for _row, operation in operations
                if operation not in {None, trainer.NO_ACTION}
            }
        )
    )
    compatible_rows = [
        (row, "compatible")
        for row, operation in operations
        if row["split"] == "validation"
        and operation not in {None, trainer.NO_ACTION}
    ]
    incompatible_rows = trainer._wrong_operation_pairs(
        compatible_rows,
        condition_operations,
        count=1,
        negative_label="incompatible",
    )
    tokenizer = AutoTokenizer.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    )
    compatible_id = int(model.config.label2id["compatible"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    compatible_scores = _score(
        model,
        tokenizer,
        compatible_rows,
        compatible_id=compatible_id,
        batch_size=args.batch_size,
        max_length=args.max_length,
        device=device,
    )
    incompatible_scores = _score(
        model,
        tokenizer,
        incompatible_rows,
        compatible_id=compatible_id,
        batch_size=args.batch_size,
        max_length=args.max_length,
        device=device,
    )
    selected = _select_threshold(compatible_scores, incompatible_scores)
    if selected is None:
        raise RuntimeError("compatibility calibration produced no threshold")
    argmax = {
        "threshold": 0.5,
        "compatible_accuracy": float(np.mean(compatible_scores >= 0.5)),
        "incompatible_accuracy": float(np.mean(incompatible_scores < 0.5)),
    }
    report = {
        "schema": "baxy.mtop-operation-compatibility-calibration.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_validation_only_mtop_test_remains_sealed",
        "source": {
            "checkpoint": str(args.checkpoint.resolve()),
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
        },
        "data": {
            "compatible_pairs": len(compatible_rows),
            "incompatible_pairs": len(incompatible_rows),
            "operations": len(condition_operations),
            "utterance_text_persisted": False,
        },
        "argmax": {key: round(value, 9) for key, value in argmax.items()},
        "selected": {key: round(value, 9) for key, value in selected.items()},
        "score_quantiles": {
            label: {
                str(quantile): round(float(np.quantile(scores, quantile)), 9)
                for quantile in (0.0, 0.01, 0.05, 0.5, 0.95, 0.99, 1.0)
            }
            for label, scores in (
                ("compatible", compatible_scores),
                ("incompatible", incompatible_scores),
            )
        },
        "status": (
            "candidate"
            if selected["compatible_accuracy"] >= 0.99
            and selected["incompatible_accuracy"] >= 0.99
            else "rejected_below_0_99"
        ),
    }
    trainer.mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--max-length", type=int, default=112)
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve(strict=True)
    args.output = args.output.resolve()
    report = calibrate(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
