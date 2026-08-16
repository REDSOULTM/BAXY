"""Select the lowest wake threshold that satisfies a hard FPPH ceiling.

LiveKit's development helper falls back to balanced accuracy when no threshold
meets both its FPPH and minimum-recall heuristics.  That fallback is useful for
diagnosis but unsafe as a product operating point.  This gate never falls back:
it returns the recall-maximizing threshold under the requested FPPH ceiling and
reports a failed gate when recall is insufficient.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_features(value: np.ndarray) -> tuple[np.ndarray, int]:
    """Return `(N, 16, 96)` features and the number of discarded rows."""
    if value.ndim == 3 and value.shape[1:] == (16, 96):
        return np.asarray(value, dtype=np.float32), 0
    if value.ndim == 2 and value.shape[1] == 96:
        complete_rows = (value.shape[0] // 16) * 16
        dropped = value.shape[0] - complete_rows
        return (
            np.asarray(value[:complete_rows], dtype=np.float32).reshape(-1, 16, 96),
            dropped,
        )
    raise ValueError(f"unsupported_feature_shape:{value.shape}")


def select_threshold(
    positive_scores: np.ndarray,
    negative_scores: np.ndarray,
    *,
    validation_hours: float,
    target_fpph: float,
) -> dict[str, float | int | bool]:
    if positive_scores.size == 0 or negative_scores.size == 0:
        raise ValueError("operating_threshold_scores_empty")
    if validation_hours <= 0.0 or target_fpph < 0.0:
        raise ValueError("operating_threshold_constraint_invalid")
    max_false_positives = math.floor(target_fpph * validation_hours + 1e-12)
    sorted_negative = np.sort(np.asarray(negative_scores, dtype=np.float64))[::-1]
    if max_false_positives >= len(sorted_negative):
        threshold = 0.0
    else:
        boundary = sorted_negative[max_false_positives]
        threshold = float(np.nextafter(boundary, math.inf))
    false_positives = int(np.sum(negative_scores >= threshold))
    true_positives = int(np.sum(positive_scores >= threshold))
    fpph = false_positives / validation_hours
    recall = true_positives / len(positive_scores)
    return {
        "threshold": threshold,
        "target_fpph": target_fpph,
        "max_false_positives": max_false_positives,
        "false_positives": false_positives,
        "fpph": fpph,
        "true_positives": true_positives,
        "false_negatives": int(len(positive_scores) - true_positives),
        "recall": recall,
        "meets_target_fpph": fpph <= target_fpph,
    }


def select_recall_floor_threshold(
    positive_scores: np.ndarray,
    negative_scores: np.ndarray,
    *,
    validation_hours: float,
    minimum_recall: float,
) -> dict[str, float | int | bool]:
    """Select the highest proposal threshold that retains a recall floor.

    This is a *stage-one proposal point*, not a safe product operating point.
    Its false-positive rate quantifies how often a second-stage verifier must
    run.  Keeping it distinct prevents a high-FPPH proposal threshold from
    being mislabeled as an approved wake threshold.
    """

    positives = np.asarray(positive_scores, dtype=np.float64)
    negatives = np.asarray(negative_scores, dtype=np.float64)
    if positives.size == 0 or negatives.size == 0:
        raise ValueError("proposal_threshold_scores_empty")
    if validation_hours <= 0.0 or not 0.0 <= minimum_recall <= 1.0:
        raise ValueError("proposal_threshold_constraint_invalid")
    required = math.ceil(minimum_recall * len(positives) - 1e-12)
    if required == 0:
        threshold = float(np.nextafter(np.max(positives), math.inf))
    else:
        threshold = float(np.sort(positives)[::-1][required - 1])
    true_positives = int(np.sum(positives >= threshold))
    false_positives = int(np.sum(negatives >= threshold))
    recall = true_positives / len(positives)
    return {
        "threshold": threshold,
        "minimum_recall": minimum_recall,
        "true_positives": true_positives,
        "false_negatives": int(len(positives) - true_positives),
        "recall": recall,
        "meets_minimum_recall": recall >= minimum_recall,
        "false_positives": false_positives,
        "fpph": false_positives / validation_hours,
        "product_operating_point": False,
        "requires_second_stage_verifier": True,
    }


def predict(session: object, features: np.ndarray, batch_size: int) -> np.ndarray:
    input_name = session.get_inputs()[0].name  # type: ignore[attr-defined]
    scores: list[np.ndarray] = []
    for start in range(0, len(features), batch_size):
        batch = features[start : start + batch_size]
        output = session.run(None, {input_name: batch})[0]  # type: ignore[attr-defined]
        scores.append(np.asarray(output).reshape(-1))
    return np.concatenate(scores).astype(np.float64, copy=False)


def score_quantiles(scores: np.ndarray) -> dict[str, float]:
    return {
        str(q): float(np.quantile(scores, q))
        for q in (0.0, 0.01, 0.05, 0.5, 0.95, 0.99, 1.0)
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--positive-features", type=Path, required=True)
    parser.add_argument(
        "--negative-features", type=Path, action="append", required=True
    )
    parser.add_argument("--clip-duration", type=float, default=2.0)
    parser.add_argument("--target-fpph", type=float, default=0.1)
    parser.add_argument("--minimum-recall", type=float, default=0.95)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0 or args.clip_duration <= 0.0:
        raise ValueError("operating_threshold_runtime_parameter_invalid")
    if not 0.0 <= args.minimum_recall <= 1.0:
        raise ValueError("operating_threshold_minimum_recall_invalid")
    model_path = args.model.resolve(strict=True)
    positive_path = args.positive_features.resolve(strict=True)
    negative_paths = [path.resolve(strict=True) for path in args.negative_features]

    positive, positive_dropped = normalize_features(np.load(positive_path))
    negative_arrays: list[np.ndarray] = []
    negative_sources: list[dict[str, object]] = []
    for path in negative_paths:
        normalized, dropped = normalize_features(np.load(path))
        negative_arrays.append(normalized)
        negative_sources.append(
            {
                "path": path.as_posix(),
                "sha256": sha256(path),
                "clips": len(normalized),
                "dropped_rows": dropped,
            }
        )
    negative = np.concatenate(negative_arrays, axis=0)

    import onnxruntime as ort

    session = ort.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"]
    )
    positive_scores = predict(session, positive, args.batch_size)
    negative_scores = predict(session, negative, args.batch_size)
    validation_hours = len(negative) * args.clip_duration / 3600.0
    operating = select_threshold(
        positive_scores,
        negative_scores,
        validation_hours=validation_hours,
        target_fpph=args.target_fpph,
    )
    operating["minimum_recall"] = args.minimum_recall
    operating["meets_minimum_recall"] = (
        float(operating["recall"]) >= args.minimum_recall
    )
    operating["candidate_operating_gate_passed"] = bool(
        operating["meets_target_fpph"] and operating["meets_minimum_recall"]
    )
    proposal = select_recall_floor_threshold(
        positive_scores,
        negative_scores,
        validation_hours=validation_hours,
        minimum_recall=args.minimum_recall,
    )

    report = {
        "schema": "baxy.livekit-wake-operating-threshold.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "lowest_threshold_with_false_positive_count_at_or_below_ceiling",
        "model": model_path.as_posix(),
        "model_sha256": sha256(model_path),
        "positive_features": {
            "path": positive_path.as_posix(),
            "sha256": sha256(positive_path),
            "clips": len(positive),
            "dropped_rows": positive_dropped,
        },
        "negative_features": negative_sources,
        "clip_duration_seconds": args.clip_duration,
        "validation_hours": validation_hours,
        "operating_point": operating,
        "recall_floor_proposal_point": proposal,
        "score_quantiles": {
            "positive": score_quantiles(positive_scores),
            "negative": score_quantiles(negative_scores),
        },
        "onnxruntime": ort.__version__,
        "blind_human_partition_accessed": False,
        "candidate_frozen": False,
        "effects_executed": 0,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = {
        "output": output.as_posix(),
        "operating_point": operating,
        "recall_floor_proposal_point": proposal,
        "validation_hours": validation_hours,
    }
    sys.stdout.buffer.write(
        (json.dumps(summary, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
