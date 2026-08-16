"""Evaluate frozen SSL pooling on word-disjoint Spanish MSWC QbyE data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_baseline_json_invalid:{path}")
    return value


def split_open_words(words: set[str], *, seed: int) -> tuple[set[str], set[str]]:
    ordered = sorted(
        words,
        key=lambda word: (
            hashlib.sha256(f"{seed}\x1f{word}".encode("utf-8")).hexdigest(),
            word,
        ),
    )
    if len(ordered) != 200:
        raise ValueError("mswc_qbye_baseline_open_word_count_invalid")
    return set(ordered[:100]), set(ordered[100:])


def l2_normalize(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    norms = np.linalg.norm(array, axis=-1, keepdims=True)
    if not np.isfinite(array).all() or np.any(norms <= 1e-12):
        raise ValueError("mswc_qbye_baseline_embedding_invalid")
    return array / norms


def qbye_metrics(
    *,
    enrollment_embeddings: np.ndarray,
    enrollment_classes: list[str],
    query_embeddings: np.ndarray,
    query_classes: list[str],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    enrollment = l2_normalize(enrollment_embeddings)
    queries = l2_normalize(query_embeddings)
    class_names = sorted(set(enrollment_classes))
    if set(class_names) != set(query_classes) or len(class_names) < 2:
        raise ValueError("mswc_qbye_baseline_class_contract_invalid")
    prototypes = []
    for class_name in class_names:
        indexes = [
            index for index, value in enumerate(enrollment_classes) if value == class_name
        ]
        prototypes.append(l2_normalize(enrollment[indexes].mean(axis=0)))
    prototype_array = np.stack(prototypes)
    scores = queries @ prototype_array.T
    class_to_index = {name: index for index, name in enumerate(class_names)}
    targets = np.asarray([class_to_index[name] for name in query_classes], dtype=np.int64)
    true_scores = scores[np.arange(len(scores)), targets]
    impostor_mask = np.ones_like(scores, dtype=np.bool_)
    impostor_mask[np.arange(len(scores)), targets] = False
    maximum_impostors = np.max(np.where(impostor_mask, scores, -np.inf), axis=1)
    margins = true_scores - maximum_impostors
    predictions = np.argmax(scores, axis=1)
    impostor_scores = scores[impostor_mask]
    zero_false_threshold = float(np.nextafter(impostor_scores.max(), math.inf))

    from sklearn.metrics import roc_auc_score, roc_curve

    binary_labels = np.concatenate(
        [np.ones(len(true_scores), dtype=np.int64), np.zeros(len(impostor_scores), dtype=np.int64)]
    )
    binary_scores = np.concatenate([true_scores, impostor_scores])
    false_positive_rate, true_positive_rate, thresholds = roc_curve(
        binary_labels, binary_scores
    )
    false_negative_rate = 1.0 - true_positive_rate
    equal_index = int(np.argmin(np.abs(false_positive_rate - false_negative_rate)))
    per_class_accuracy = []
    for class_index, class_name in enumerate(class_names):
        mask = targets == class_index
        per_class_accuracy.append(float(np.mean(predictions[mask] == class_index)))
    metrics: dict[str, object] = {
        "classes": len(class_names),
        "enrollments": len(enrollment),
        "queries": len(queries),
        "top1_accuracy": float(np.mean(predictions == targets)),
        "macro_class_accuracy": float(np.mean(per_class_accuracy)),
        "mean_true_minus_maximum_impostor_margin": float(np.mean(margins)),
        "median_true_minus_maximum_impostor_margin": float(np.median(margins)),
        "positive_margin_queries": int(np.count_nonzero(margins > 0.0)),
        "pair_auc": float(roc_auc_score(binary_labels, binary_scores)),
        "equal_error_rate": float(
            (false_positive_rate[equal_index] + false_negative_rate[equal_index]) / 2.0
        ),
        "equal_error_threshold": float(thresholds[equal_index]),
        "zero_false_pair_threshold": zero_false_threshold,
        "true_pairs_accepted_at_zero_false_pairs": int(
            np.count_nonzero(true_scores >= zero_false_threshold)
        ),
        "true_pairs": len(true_scores),
        "impostor_pairs": len(impostor_scores),
    }
    breakdown = [
        {
            "class_name": class_name,
            "true_score": float(true_score),
            "maximum_impostor_score": float(impostor_score),
            "margin": float(margin),
            "top1_correct": bool(prediction == target),
        }
        for class_name, true_score, impostor_score, margin, prediction, target in zip(
            query_classes,
            true_scores,
            maximum_impostors,
            margins,
            predictions,
            targets,
            strict=True,
        )
    ]
    return metrics, breakdown


def pooled_embedding(values: np.ndarray, pooling: str) -> np.ndarray:
    frames = np.asarray(values, dtype=np.float32)
    if frames.ndim != 2 or not len(frames):
        raise ValueError("mswc_qbye_baseline_frames_invalid")
    if pooling == "mean":
        return frames.mean(axis=0, dtype=np.float64)
    if pooling == "mean_std":
        return np.concatenate(
            [frames.mean(axis=0, dtype=np.float64), frames.std(axis=0, dtype=np.float64)]
        )
    raise ValueError(f"mswc_qbye_baseline_pooling_invalid:{pooling}")


def evaluate(
    *,
    feature_manifest_path: Path,
    output_path: Path,
    layers: list[int],
    open_partition: str,
    open_split_seed: int,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or not layers
        or layers != sorted(set(layers))
        or open_partition not in {"tuning", "selection"}
    ):
        raise ValueError("mswc_qbye_baseline_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_path = output_path.resolve()
    manifest = read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    contract = manifest.get("contract")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-wav2vec2-features.v1"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(contract, dict)
    ):
        raise ValueError("mswc_qbye_baseline_boundary_invalid")
    features_by_layer_raw = files.get("features_by_layer")
    if not isinstance(features_by_layer_raw, dict):
        raise ValueError("mswc_qbye_baseline_files_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_qbye_baseline_record_invalid")
        records.append(record)
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    if sha256(offset_path) != files.get("offsets_sha256"):
        raise ValueError("mswc_qbye_baseline_offsets_hash_mismatch")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1:
        raise ValueError("mswc_qbye_baseline_offsets_shape_invalid")

    training_indexes = [
        index for index, record in enumerate(records) if record["partition"] == "metric_training"
    ]
    all_open_words = {
        str(record["class_name"])
        for record in records
        if str(record["partition"]).startswith("open_keyword_")
    }
    tuning_words, selection_words = split_open_words(
        all_open_words, seed=open_split_seed
    )
    active_words = tuning_words if open_partition == "tuning" else selection_words
    enrollment_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_enrollment"
        and str(record["class_name"]) in active_words
    ]
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_query"
        and str(record["class_name"]) in active_words
    ]
    if not training_indexes or not enrollment_indexes or not query_indexes:
        raise ValueError("mswc_qbye_baseline_partition_empty")

    runs = []
    for layer in layers:
        descriptor = features_by_layer_raw.get(str(layer))
        if not isinstance(descriptor, dict):
            raise ValueError(f"mswc_qbye_baseline_layer_missing:{layer}")
        feature_path = root / str(descriptor["path"])
        if sha256(feature_path) != descriptor.get("sha256"):
            raise ValueError(f"mswc_qbye_baseline_feature_hash_mismatch:{layer}")
        features = np.load(feature_path, mmap_mode="r")
        if features.ndim != 2 or int(offsets[-1]) != len(features):
            raise ValueError("mswc_qbye_baseline_feature_shape_invalid")
        for pooling in ("mean", "mean_std"):
            training_sum = None
            for index in training_indexes:
                embedding = pooled_embedding(
                    features[int(offsets[index]) : int(offsets[index + 1])], pooling
                )
                if training_sum is None:
                    training_sum = np.zeros_like(embedding)
                training_sum += embedding
            assert training_sum is not None
            training_center = training_sum / len(training_indexes)
            enrollment_raw = np.stack(
                [
                    pooled_embedding(
                        features[int(offsets[index]) : int(offsets[index + 1])], pooling
                    )
                    for index in enrollment_indexes
                ]
            )
            query_raw = np.stack(
                [
                    pooled_embedding(
                        features[int(offsets[index]) : int(offsets[index + 1])], pooling
                    )
                    for index in query_indexes
                ]
            )
            enrollment_classes = [str(records[index]["class_name"]) for index in enrollment_indexes]
            query_classes = [str(records[index]["class_name"]) for index in query_indexes]
            for centered in (False, True):
                enrollment = enrollment_raw - training_center if centered else enrollment_raw
                queries = query_raw - training_center if centered else query_raw
                metrics, breakdown = qbye_metrics(
                    enrollment_embeddings=enrollment,
                    enrollment_classes=enrollment_classes,
                    query_embeddings=queries,
                    query_classes=query_classes,
                )
                runs.append(
                    {
                        "layer": layer,
                        "pooling": pooling,
                        "training_global_center_subtracted": centered,
                        "metrics": metrics,
                        "queries": breakdown,
                    }
                )
    best = max(
        runs,
        key=lambda run: (
            float(run["metrics"]["top1_accuracy"]),
            float(run["metrics"]["pair_auc"]),
        ),
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-ssl-baseline.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_word_disjoint_query_by_example_baseline",
        "sources": {"feature_manifest_sha256": sha256(feature_manifest_path)},
        "contract": {
            "layers": layers,
            "pooling": ["mean", "mean_std"],
            "normalization": "l2_after_optional_training_global_center_subtraction",
            "prototype": "normalized_mean_of_four_distinct_speaker_enrollments",
            "query": "one_distinct_unenrolled_speaker_clip",
            "word_classes": "evaluation_classes_never_seen_in_metric_training",
            "open_split_seed": open_split_seed,
            "open_partition": open_partition,
            "open_partition_classes": len(active_words),
            "selection_partition_accessed": open_partition == "selection",
        },
        "runs": runs,
        "selected_run": {
            key: best[key]
            for key in ("layer", "pooling", "training_global_center_subtracted", "metrics")
        },
        "runtime_seconds": time.perf_counter() - started,
        "candidate_training_started": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
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
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--layers", type=int, nargs="+", default=[2, 16])
    parser.add_argument("--open-partition", choices=("tuning", "selection"), default="tuning")
    parser.add_argument("--open-split-seed", type=int, default=9107)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        feature_manifest_path=args.feature_manifest,
        output_path=args.output,
        layers=args.layers,
        open_partition=args.open_partition,
        open_split_seed=args.open_split_seed,
    )
    print(json.dumps(report["selected_run"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
