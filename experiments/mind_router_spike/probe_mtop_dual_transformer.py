"""Probe a precision-first / rare-sensitive dual MTOP selector.

Both checkpoints are frozen before this development validation probe.  The
official MTOP test remains sealed.  This script does not change product assets.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
import train_mtop_operation_classifier as trainer  # noqa: E402
from baxy_mind.router import QUERY_PREFIX  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_PRECISION = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-classifier-v4-reviewed-contrast"
)
DEFAULT_SENSITIVE = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-classifier-v7-rare-sensitive"
)
DEFAULT_REPORT = REPO / "artifacts/research/mtop_dual_transformer_probe_v1.json"
RARE_OPERATIONS = {
    "media.control",
    "media.seek.relative",
    "notification.cancel.latest",
    "notification.dismiss",
    "reminder.delete",
    "reminder.list",
    "reminder.resolve.exact",
}


def _infer(checkpoint: Path, texts: list[str], batch_size: int) -> tuple[list[str], Any]:
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint,
        local_files_only=True,
    ).cuda().eval()
    chunks: list[np.ndarray] = []
    with torch.inference_mode():
        for offset in range(0, len(texts), batch_size):
            encoded = tokenizer(
                [QUERY_PREFIX + text for text in texts[offset : offset + batch_size]],
                padding=True,
                truncation=True,
                max_length=96,
                return_tensors="pt",
            )
            encoded = {key: value.cuda(non_blocking=True) for key, value in encoded.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(**encoded).logits
            chunks.append(logits.float().cpu().numpy())
    classes = [str(model.config.id2label[index]) for index in range(model.config.num_labels)]
    del model
    torch.cuda.empty_cache()
    return classes, np.concatenate(chunks, axis=0)


def _metrics(predictions: Any, truth: Any, classes: list[str]) -> dict[str, Any]:
    exact = predictions == truth
    no_action_index = classes.index(trainer.NO_ACTION)
    no_action = truth == no_action_index
    supported = ~no_action
    return {
        "accuracy": round(float(exact.mean()), 6),
        "supported_accuracy": round(float(exact[supported].mean()), 6),
        "no_action_accuracy": round(float(exact[no_action].mean()), 6),
        "false_supported_on_no_action": round(
            float((predictions[no_action] != no_action_index).mean()),
            6,
        ),
    }


def _normalise(scores: Any) -> Any:
    import numpy as np

    return (scores - np.mean(scores, axis=1, keepdims=True)) / np.maximum(
        np.std(scores, axis=1, keepdims=True),
        1e-6,
    )


def probe(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np

    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    validation = [
        (row, str(label))
        for row in rows
        if row["split"] == "validation"
        for label in [trainer.operation_label(row)]
        if label is not None
    ]
    texts = [str(row["text"]) for row, _label in validation]
    labels = [label for _row, label in validation]
    precision_classes, precision_scores_native = _infer(
        args.precision_checkpoint,
        texts,
        args.batch_size,
    )
    sensitive_classes, sensitive_scores_native = _infer(
        args.sensitive_checkpoint,
        texts,
        args.batch_size,
    )
    classes = sorted(set(precision_classes) | set(sensitive_classes))
    class_to_id = {label: index for index, label in enumerate(classes)}

    def align(scores: Any, native: list[str]) -> Any:
        output = np.full((len(scores), len(classes)), -20.0, dtype=np.float32)
        for index, label in enumerate(native):
            output[:, class_to_id[label]] = scores[:, index]
        return output

    precision_scores = align(precision_scores_native, precision_classes)
    sensitive_scores = align(sensitive_scores_native, sensitive_classes)
    truth = np.asarray([class_to_id[label] for label in labels], dtype=np.int64)
    precision_predictions = np.argmax(precision_scores, axis=1)
    sensitive_predictions = np.argmax(sensitive_scores, axis=1)
    precision_exact = precision_predictions == truth
    sensitive_exact = sensitive_predictions == truth

    precision_normal = _normalise(precision_scores)
    sensitive_normal = _normalise(sensitive_scores)
    blends: list[dict[str, Any]] = []
    for step in range(101):
        precision_weight = step / 100.0
        scores = precision_weight * precision_normal + (1.0 - precision_weight) * sensitive_normal
        predictions = np.argmax(scores, axis=1)
        blends.append({"precision_weight": precision_weight, **_metrics(predictions, truth, classes)})
    best_blend = max(blends, key=lambda row: row["accuracy"])

    precision_order = np.argsort(-precision_normal, axis=1)
    sensitive_order = np.argsort(-sensitive_normal, axis=1)
    precision_margin = (
        precision_normal[np.arange(len(truth)), precision_order[:, 0]]
        - precision_normal[np.arange(len(truth)), precision_order[:, 1]]
    )
    sensitive_margin = (
        sensitive_normal[np.arange(len(truth)), sensitive_order[:, 0]]
        - sensitive_normal[np.arange(len(truth)), sensitive_order[:, 1]]
    )
    rare_ids = {class_to_id[label] for label in RARE_OPERATIONS if label in class_to_id}
    threshold_values = [round(value * 0.1, 1) for value in range(0, 41)]
    gates: list[dict[str, Any]] = []
    for rare_only in (True, False):
        for minimum_sensitive_margin in threshold_values:
            for maximum_precision_margin in threshold_values:
                eligible = (
                    (sensitive_predictions != precision_predictions)
                    & (sensitive_margin >= minimum_sensitive_margin)
                    & (precision_margin <= maximum_precision_margin)
                )
                if rare_only:
                    eligible &= np.asarray(
                        [int(prediction) in rare_ids for prediction in sensitive_predictions]
                    )
                predictions = np.where(eligible, sensitive_predictions, precision_predictions)
                gates.append(
                    {
                        "rare_only": rare_only,
                        "minimum_sensitive_margin": minimum_sensitive_margin,
                        "maximum_precision_margin": maximum_precision_margin,
                        "overrides": int(eligible.sum()),
                        **_metrics(predictions, truth, classes),
                    }
                )
    best_gate = max(
        gates,
        key=lambda row: (
            row["accuracy"],
            row["no_action_accuracy"],
            -row["overrides"],
        ),
    )

    report = {
        "schema": "baxy.mtop-dual-transformer-probe.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_mtop_test_remains_sealed",
        "source": {
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
            "precision_checkpoint": str(args.precision_checkpoint.resolve()),
            "sensitive_checkpoint": str(args.sensitive_checkpoint.resolve()),
        },
        "data": {"validation_rows": len(validation), "classes": classes},
        "precision": _metrics(precision_predictions, truth, classes),
        "sensitive": _metrics(sensitive_predictions, truth, classes),
        "oracle": {
            "either_top_1_accuracy": round(
                float((precision_exact | sensitive_exact).mean()),
                6,
            ),
            "precision_only_correct": int((precision_exact & ~sensitive_exact).sum()),
            "sensitive_only_correct": int((sensitive_exact & ~precision_exact).sum()),
            "both_wrong": int((~precision_exact & ~sensitive_exact).sum()),
        },
        "best_validation_blend": best_blend,
        "best_validation_gate": best_gate,
        "all_validation_blends": blends,
        "all_validation_gates": gates,
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precision-checkpoint", type=Path, default=DEFAULT_PRECISION)
    parser.add_argument("--sensitive-checkpoint", type=Path, default=DEFAULT_SENSITIVE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()
    result = probe(args)
    print(
        json.dumps(
            {
                "precision": result["precision"],
                "sensitive": result["sensitive"],
                "oracle": result["oracle"],
                "best_validation_blend": result["best_validation_blend"],
                "best_validation_gate": result["best_validation_gate"],
                "report": str(args.report.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
