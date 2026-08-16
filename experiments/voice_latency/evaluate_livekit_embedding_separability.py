"""Test whether frozen LiveKit embeddings retain speaker-invariant BAXY evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_mdtc_livekit_verifier_student import (  # noqa: E402
    SYNTHETIC_FEATURE_FILES,
    load_feature,
    read_json,
    roc_auc,
    sha256,
    zero_false_operating_point,
)


def representation(features: np.ndarray, kind: str) -> np.ndarray:
    values = np.asarray(features, dtype=np.float32)
    if values.ndim != 3 or values.shape[1:] != (16, 96):
        raise ValueError("livekit_separability_feature_shape_invalid")
    if kind == "flat":
        return values.reshape(len(values), -1)
    if kind == "statistics":
        return np.concatenate(
            (
                values.mean(axis=1),
                values.std(axis=1),
                values.max(axis=1),
                values.min(axis=1),
            ),
            axis=1,
        )
    raise ValueError("livekit_separability_representation_invalid")


def weighted_cosine_prototype_scores(
    train_features: np.ndarray,
    train_labels: np.ndarray,
    train_weights: np.ndarray,
    evaluation_features: np.ndarray,
) -> np.ndarray:
    train = np.asarray(train_features, dtype=np.float64)
    labels = np.asarray(train_labels).reshape(-1)
    weights = np.asarray(train_weights, dtype=np.float64).reshape(-1)
    evaluation = np.asarray(evaluation_features, dtype=np.float64)
    if len(train) != len(labels) or len(train) != len(weights):
        raise ValueError("livekit_separability_prototype_shape_invalid")
    centroids = []
    for label in (0, 1):
        mask = labels == label
        if not np.any(mask):
            raise ValueError("livekit_separability_prototype_class_empty")
        centroids.append(np.average(train[mask], axis=0, weights=weights[mask]))
    normalized_evaluation = evaluation / np.maximum(
        np.linalg.norm(evaluation, axis=1, keepdims=True), 1e-12
    )
    normalized_centroids = np.stack(centroids)
    normalized_centroids /= np.maximum(
        np.linalg.norm(normalized_centroids, axis=1, keepdims=True), 1e-12
    )
    cosine = normalized_evaluation @ normalized_centroids.T
    return cosine[:, 1] - cosine[:, 0]


def aggregate_clips(
    records: list[dict[str, object]],
    scores: np.ndarray,
    *,
    calibration_threshold: float,
) -> list[dict[str, object]]:
    values = np.asarray(scores, dtype=np.float64).reshape(-1)
    if len(records) != len(values):
        raise ValueError("livekit_separability_clip_score_shape_invalid")
    def record_path(record: dict[str, object]) -> str:
        value = record.get("output_relative_path", record.get("relative_path"))
        if not isinstance(value, str) or not value:
            raise ValueError("livekit_separability_clip_path_missing")
        return value

    output = []
    for path in sorted({record_path(record) for record in records}):
        indexes = [
            index
            for index, record in enumerate(records)
            if record_path(record) == path
        ]
        groups = {str(records[index].get("speaker_group")) for index in indexes}
        labels = {str(records[index].get("clip_label")) for index in indexes}
        if len(groups) != 1 or len(labels) != 1:
            raise ValueError("livekit_separability_clip_contract_invalid")
        score = float(values[indexes].max())
        output.append(
            {
                "output_relative_path": path,
                "speaker_group": next(iter(groups)),
                "clip_label": next(iter(labels)),
                "score": score,
                "calibrated_margin": score - calibration_threshold,
            }
        )
    return output


def load_inputs(
    synthetic_directory: Path,
    hard_feature_manifest_path: Path,
    human_feature_manifest_path: Path,
) -> dict[str, object]:
    synthetic_directory = synthetic_directory.resolve(strict=True)
    synthetic = {
        name: load_feature(synthetic_directory / name)
        for name in SYNTHETIC_FEATURE_FILES
    }
    hard_feature_manifest_path = hard_feature_manifest_path.resolve(strict=True)
    hard = read_json(hard_feature_manifest_path)
    if hard.get("schema") != "baxy.mdtc-hard-negative-livekit-features.v1":
        raise ValueError("unsupported_livekit_separability_hard_schema")
    hard_outputs = hard.get("outputs")
    if not isinstance(hard_outputs, dict):
        raise ValueError("livekit_separability_hard_outputs_missing")
    hard_features = {}
    for split in ("train", "development"):
        value = hard_outputs.get(split)
        if not isinstance(value, dict):
            raise ValueError("livekit_separability_hard_split_missing")
        path = Path(str(value.get("path"))).resolve(strict=True)
        if sha256(path) != value.get("sha256"):
            raise ValueError("livekit_separability_hard_hash_mismatch")
        hard_features[split] = load_feature(path)
    human_feature_manifest_path = human_feature_manifest_path.resolve(strict=True)
    human = read_json(human_feature_manifest_path)
    if human.get("schema") != "baxy.human-ctc-aligned-livekit-features.v2":
        raise ValueError("unsupported_livekit_separability_human_schema")
    if human.get("blind_human_partition_accessed") is not False:
        raise ValueError("livekit_separability_blind_boundary_invalid")
    human_outputs = human.get("outputs")
    records_value = human.get("records")
    if not isinstance(human_outputs, dict) or not isinstance(records_value, list):
        raise ValueError("livekit_separability_human_outputs_missing")
    human_feature_path = Path(str(human_outputs.get("features"))).resolve(strict=True)
    human_label_path = Path(str(human_outputs.get("labels"))).resolve(strict=True)
    if sha256(human_feature_path) != human_outputs.get("features_sha256"):
        raise ValueError("livekit_separability_human_feature_hash_mismatch")
    if sha256(human_label_path) != human_outputs.get("labels_sha256"):
        raise ValueError("livekit_separability_human_label_hash_mismatch")
    human_features = load_feature(human_feature_path)
    human_labels = np.load(human_label_path, allow_pickle=False).astype(np.int64)
    human_records = []
    for record in records_value:
        if not isinstance(record, dict):
            raise ValueError("livekit_separability_human_record_invalid")
        human_records.append(record)
    if len(human_features) != len(human_labels) or len(human_records) != len(human_labels):
        raise ValueError("livekit_separability_human_shape_mismatch")
    return {
        "synthetic": synthetic,
        "hard": hard_features,
        "human_features": human_features,
        "human_labels": human_labels,
        "human_records": human_records,
        "source_hashes": {
            "hard_feature_manifest_sha256": sha256(hard_feature_manifest_path),
            "human_feature_manifest_sha256": sha256(human_feature_manifest_path),
        },
    }


def run(
    *,
    synthetic_directory: Path,
    hard_feature_manifest_path: Path,
    human_feature_manifest_path: Path,
    output_path: Path,
    hard_negative_weight: float,
    human_weight: float,
    seed: int,
) -> dict[str, object]:
    from sklearn.linear_model import RidgeClassifier, SGDClassifier
    from sklearn.preprocessing import StandardScaler

    if hard_negative_weight < 1 or human_weight < 1:
        raise ValueError("livekit_separability_weight_invalid")
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"livekit_separability_output_exists:{output_path}")
    inputs = load_inputs(
        synthetic_directory, hard_feature_manifest_path, human_feature_manifest_path
    )
    synthetic = inputs["synthetic"]
    hard = inputs["hard"]
    human_features = inputs["human_features"]
    human_labels = inputs["human_labels"]
    human_records = inputs["human_records"]
    groups = sorted({str(record.get("speaker_group")) for record in human_records})
    model_specs = (
        ("cosine_prototype_statistics", "statistics", "prototype"),
        ("ridge_statistics", "statistics", "ridge"),
        ("sgd_logistic_statistics", "statistics", "sgd_logistic"),
        ("ridge_flat", "flat", "ridge"),
    )
    base_train_features = np.concatenate(
        (
            synthetic["positive_features_train.npy"],
            synthetic["negative_features_train.npy"],
            hard["train"],
        )
    )
    base_train_labels = np.concatenate(
        (
            np.ones(len(synthetic["positive_features_train.npy"]), np.int64),
            np.zeros(
                len(synthetic["negative_features_train.npy"]) + len(hard["train"]),
                np.int64,
            ),
        )
    )
    base_train_weights = np.concatenate(
        (
            np.ones(
                len(synthetic["positive_features_train.npy"])
                + len(synthetic["negative_features_train.npy"]),
                np.float64,
            ),
            np.full(len(hard["train"]), hard_negative_weight, np.float64),
        )
    )
    calibration_positive = synthetic["positive_features_test.npy"]
    calibration_negative = np.concatenate(
        (synthetic["negative_features_test.npy"], hard["development"])
    )
    model_reports = []
    for model_name, representation_kind, estimator_kind in model_specs:
        started = time.perf_counter()
        folds = []
        out_of_fold_clips = []
        for group in groups:
            held_mask = np.asarray(
                [str(record.get("speaker_group")) == group for record in human_records],
                dtype=bool,
            )
            train_features = np.concatenate(
                (base_train_features, human_features[~held_mask])
            )
            train_labels = np.concatenate(
                (base_train_labels, human_labels[~held_mask])
            )
            train_weights = np.concatenate(
                (
                    base_train_weights,
                    np.full(np.count_nonzero(~held_mask), human_weight, np.float64),
                )
            )
            represented_train = representation(train_features, representation_kind)
            scaler = StandardScaler().fit(
                represented_train, sample_weight=train_weights
            )
            scaled_train = scaler.transform(represented_train)
            if estimator_kind == "prototype":
                def score(features: np.ndarray) -> np.ndarray:
                    return weighted_cosine_prototype_scores(
                        scaled_train,
                        train_labels,
                        train_weights,
                        scaler.transform(representation(features, representation_kind)),
                    )
            else:
                if estimator_kind == "sgd_logistic":
                    estimator = SGDClassifier(
                        loss="log_loss",
                        alpha=1e-4,
                        max_iter=1000,
                        tol=1e-4,
                        random_state=seed,
                    )
                else:
                    estimator = RidgeClassifier(alpha=1.0)
                estimator.fit(scaled_train, train_labels, sample_weight=train_weights)

                def score(features: np.ndarray) -> np.ndarray:
                    return np.asarray(
                        estimator.decision_function(
                            scaler.transform(representation(features, representation_kind))
                        ),
                        dtype=np.float64,
                    )
            calibration_positive_scores = score(calibration_positive)
            calibration_negative_scores = score(calibration_negative)
            threshold = float(
                np.nextafter(calibration_negative_scores.max(), math.inf)
            )
            held_scores = score(human_features[held_mask])
            held_records = [
                record for index, record in enumerate(human_records) if held_mask[index]
            ]
            held_clips = aggregate_clips(
                held_records, held_scores, calibration_threshold=threshold
            )
            out_of_fold_clips.extend(held_clips)
            folds.append(
                {
                    "held_out_speaker_group": group,
                    "calibration_threshold": threshold,
                    "calibration_auc": roc_auc(
                        calibration_positive_scores, calibration_negative_scores
                    ),
                    "clips": held_clips,
                }
            )
        positive_scores = np.asarray(
            [clip["score"] for clip in out_of_fold_clips if clip["clip_label"] == "positive"]
        )
        negative_scores = np.asarray(
            [clip["score"] for clip in out_of_fold_clips if clip["clip_label"] == "hard_negative"]
        )
        positive_margins = np.asarray(
            [clip["calibrated_margin"] for clip in out_of_fold_clips if clip["clip_label"] == "positive"]
        )
        negative_margins = np.asarray(
            [clip["calibrated_margin"] for clip in out_of_fold_clips if clip["clip_label"] == "hard_negative"]
        )
        model_reports.append(
            {
                "model": model_name,
                "representation": representation_kind,
                "fit_seconds": time.perf_counter() - started,
                "metrics": {
                    "raw_clip_auc": roc_auc(positive_scores, negative_scores),
                    "raw_zero_false_operating_point": zero_false_operating_point(
                        positive_scores, negative_scores
                    ),
                    "calibrated_margin_auc": roc_auc(
                        positive_margins, negative_margins
                    ),
                    "positive_accepted_at_fold_calibration": int(
                        np.count_nonzero(positive_margins >= 0)
                    ),
                    "positive_total": int(len(positive_margins)),
                    "negative_false_at_fold_calibration": int(
                        np.count_nonzero(negative_margins >= 0)
                    ),
                    "negative_total": int(len(negative_margins)),
                },
                "folds": folds,
            }
        )
        print(
            f"MODEL|{model_name}|accepted={model_reports[-1]['metrics']['positive_accepted_at_fold_calibration']}/14|false={model_reports[-1]['metrics']['negative_false_at_fold_calibration']}/4",
            flush=True,
        )
    report: dict[str, object] = {
        "schema": "baxy.livekit-embedding-speaker-generalization-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_leave_one_speaker_group_out_separability_diagnostic",
        "sources": {
            "synthetic_directory": synthetic_directory.resolve(strict=True).as_posix(),
            "hard_feature_manifest": hard_feature_manifest_path.resolve(strict=True).as_posix(),
            "human_feature_manifest": human_feature_manifest_path.resolve(strict=True).as_posix(),
            **inputs["source_hashes"],
        },
        "weights": {
            "hard_negative": hard_negative_weight,
            "human": human_weight,
        },
        "seed": seed,
        "models": model_reports,
        "conclusion_contract": (
            "diagnostic_only; failure supports replacing the frozen embedding frontend; "
            "success does not authorize blind or product promotion"
        ),
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-dir", type=Path, required=True)
    parser.add_argument("--hard-feature-manifest", type=Path, required=True)
    parser.add_argument("--human-feature-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hard-negative-weight", type=float, default=2.0)
    parser.add_argument("--human-weight", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=20260804)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        synthetic_directory=args.synthetic_dir,
        hard_feature_manifest_path=args.hard_feature_manifest,
        human_feature_manifest_path=args.human_feature_manifest,
        output_path=args.output,
        hard_negative_weight=args.hard_negative_weight,
        human_weight=args.human_weight,
        seed=args.seed,
    )
    print(json.dumps({model["model"]: model["metrics"] for model in report["models"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
