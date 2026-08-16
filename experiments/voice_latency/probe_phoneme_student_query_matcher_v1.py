"""Probe a separate text-query matcher over a frozen phoneme student."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from phoneme_student_vocabulary_v2 import (  # noqa: E402
    BLANK_ID,
    CATEGORY_NAMES,
)
from train_mdtc_livekit_verifier_student import (  # noqa: E402
    read_json,
    roc_auc,
    sha256,
)
from train_mdtc_phoneme_distillation_v2 import (  # noqa: E402
    WORD_CLASS_SEQUENCES,
    _word_class_candidate_sequences,
    build_model,
    predict_probabilities,
    word_class_ids,
)
from train_mdtc_phonetic_ctc_group_cv import load_partition  # noqa: E402


def monotonic_sequence_score(
    log_probabilities: np.ndarray, sequence: tuple[int, ...]
) -> np.ndarray:
    values = np.asarray(log_probabilities, dtype=np.float32)
    if values.ndim != 3 or not sequence:
        raise ValueError("query_matcher_monotonic_contract_invalid")
    dynamic = values[:, :, sequence[0]]
    for token in sequence[1:]:
        prefix = np.maximum.accumulate(dynamic, axis=1)
        shifted = np.concatenate(
            (
                np.full((len(values), 1), -np.inf, dtype=np.float32),
                prefix[:, :-1],
            ),
            axis=1,
        )
        dynamic = shifted + values[:, :, token]
    return dynamic.max(axis=1) / len(sequence)


def query_features(probabilities: np.ndarray) -> tuple[np.ndarray, list[str]]:
    values = np.asarray(probabilities, dtype=np.float32)
    if (
        values.ndim != 3
        or values.shape[-1] != len(CATEGORY_NAMES)
        or not np.isfinite(values).all()
    ):
        raise ValueError("query_matcher_probability_contract_invalid")
    log_values = np.log(np.maximum(values, 1e-8))
    aggregates = (
        values.mean(axis=1),
        values.max(axis=1),
        values.std(axis=1),
        np.partition(values, -3, axis=1)[:, -3:, :].mean(axis=1),
    )
    positions = values.argmax(axis=1).astype(np.float32) / max(values.shape[1] - 1, 1)
    hard = values.argmax(axis=-1)
    counts = np.stack(
        [(hard == index).mean(axis=1) for index in range(len(CATEGORY_NAMES))],
        axis=1,
    )
    class_scores = []
    class_names = list(WORD_CLASS_SEQUENCES)
    for class_id in range(1, len(class_names) + 1):
        scores = np.stack(
            [
                monotonic_sequence_score(log_values, sequence)
                for sequence in _word_class_candidate_sequences(class_id)
            ],
            axis=1,
        )
        class_scores.append(scores.max(axis=1))
    score_values = np.stack(class_scores, axis=1)
    margins = score_values[:, :1] - score_values[:, 1:]
    features = np.concatenate((*aggregates, positions, counts, score_values, margins), axis=1)
    names = []
    for aggregate_name in ("mean", "maximum", "standard_deviation", "top3_mean"):
        names.extend(f"{aggregate_name}:{name}" for name in CATEGORY_NAMES)
    names.extend(f"maximum_position:{name}" for name in CATEGORY_NAMES)
    names.extend(f"greedy_frame_fraction:{name}" for name in CATEGORY_NAMES)
    names.extend(f"monotonic_score:{name}" for name in class_names)
    names.extend(f"baxy_margin_over:{name}" for name in class_names[1:])
    if features.shape[1] != len(names):
        raise AssertionError("query_matcher_feature_name_mismatch")
    return features.astype(np.float32), names


def stage1_eligible_negative_mask(
    records: list[dict[str, object]],
    labels: np.ndarray,
    negative_report: dict[str, object],
) -> np.ndarray:
    report_records = negative_report.get("records")
    if not isinstance(report_records, list):
        raise ValueError("query_matcher_negative_records_missing")
    by_file = {
        str(record.get("file")): record
        for record in report_records
        if isinstance(record, dict)
    }
    mask = np.zeros(len(records), dtype=bool)
    for index, (record, label) in enumerate(zip(records, labels, strict=True)):
        if int(label) != 0:
            continue
        relative_path = str(record.get("relative_path"))
        if relative_path.startswith("negative_test/"):
            source = by_file.get(Path(relative_path).name)
            mask[index] = isinstance(source, dict) and bool(source.get("stage1_proposed"))
        else:
            mask[index] = True
    return mask


def binary_metrics(
    probabilities: np.ndarray,
    labels: np.ndarray,
    *,
    negative_mask: np.ndarray,
) -> dict[str, object]:
    scores = np.asarray(probabilities).reshape(-1)
    values = np.asarray(labels).reshape(-1).astype(np.int64)
    if len(scores) != len(values) or len(negative_mask) != len(values):
        raise ValueError("query_matcher_metric_shape_invalid")
    eligible_negative = scores[(values == 0) & negative_mask]
    if not len(eligible_negative):
        raise ValueError("query_matcher_eligible_negatives_missing")
    maximum_negative = float(eligible_negative.max())
    threshold = float(np.nextafter(maximum_negative, np.inf))
    positive_scores = scores[values == 1]
    return {
        "auc_all_examples": roc_auc(scores[values == 1], scores[values == 0]),
        "threshold": threshold,
        "maximum_eligible_negative_score": maximum_negative,
        "eligible_negatives": len(eligible_negative),
        "eligible_negative_false_accepts": int((eligible_negative >= threshold).sum()),
        "positive_accepted": int((positive_scores >= threshold).sum()),
        "positive_total": len(positive_scores),
        "positive_recall": float((positive_scores >= threshold).mean()),
        "minimum_positive_score": float(positive_scores.min()),
        "maximum_positive_score": float(positive_scores.max()),
    }


def aggregate_human_clip_scores(
    scores: np.ndarray,
    records: list[dict[str, object]],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:
    values = np.asarray(scores).reshape(-1)
    if len(values) != len(records):
        raise ValueError("query_matcher_human_score_shape_invalid")
    grouped: dict[tuple[str, str], list[float]] = {}
    for score, record in zip(values, records, strict=True):
        relative_path = str(record.get("relative_path"))
        label = str(record.get("clip_label"))
        key = (relative_path, label)
        grouped.setdefault(key, [])
        if label == "positive" and int(record.get("label", 0)) != 1:
            continue
        grouped[key].append(float(score))
    clips = [
        {
            "relative_path": relative_path,
            "label": label,
            "score": max(clip_scores) if clip_scores else 0.0,
        }
        for (relative_path, label), clip_scores in grouped.items()
    ]
    positive = np.asarray(
        [float(clip["score"]) for clip in clips if clip["label"] == "positive"]
    )
    negative = np.asarray(
        [float(clip["score"]) for clip in clips if clip["label"] == "hard_negative"]
    )
    if len(positive) != 14 or len(negative) != 4:
        raise ValueError("query_matcher_human_clip_partition_invalid")
    return positive, negative, clips


def run(
    *,
    feature_manifest_path: Path,
    negative_report_path: Path,
    checkpoint_path: Path,
    checkpoint_report_path: Path,
    wekws_directory: Path,
    output_path: Path,
    device: str,
) -> dict[str, object]:
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    negative_report_path = negative_report_path.resolve(strict=True)
    checkpoint_path = checkpoint_path.resolve(strict=True)
    checkpoint_report_path = checkpoint_report_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"query_matcher_output_exists:{output_path}")
    feature_manifest = read_json(feature_manifest_path)
    negative_report = read_json(negative_report_path)
    checkpoint_report = read_json(checkpoint_report_path)
    if feature_manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("query_matcher_blind_boundary_invalid")
    if checkpoint_report.get("blind_human_partition_accessed") is not False:
        raise ValueError("query_matcher_checkpoint_blind_boundary_invalid")
    train_features, train_labels, train_records = load_partition(
        feature_manifest, "base_train"
    )
    development_features, development_labels, development_records = load_partition(
        feature_manifest, "base_development"
    )
    human_features, _, human_records = load_partition(
        feature_manifest, "human_development"
    )

    sys.path.insert(0, str(wekws_directory))
    import torch
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, balanced_accuracy_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from wekws.model.mdtc import MDTC

    architecture = checkpoint_report.get("architecture")
    if not isinstance(architecture, dict):
        raise ValueError("query_matcher_checkpoint_architecture_missing")
    model = build_model(
        torch,
        MDTC,
        architecture_type=str(architecture["architecture_type"]),
        hidden_dimension=int(architecture["hidden_dimension"]),
        stack_count=int(architecture["stack_count"]),
        stack_size=int(architecture["stack_size"]),
        kernel_size=int(architecture["kernel_size"]),
        recurrent_layers=int(architecture["recurrent_layers"]),
    ).to(device)
    state = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    started = time.perf_counter()
    partition_probabilities = {
        "base_train": predict_probabilities(
            torch, model, train_features, device=device, batch_size=256
        ),
        "base_development": predict_probabilities(
            torch, model, development_features, device=device, batch_size=256
        ),
        "human_development": predict_probabilities(
            torch, model, human_features, device=device, batch_size=256
        ),
    }
    inference_seconds = time.perf_counter() - started
    train_query, feature_names = query_features(partition_probabilities["base_train"])
    development_query, _ = query_features(
        partition_probabilities["base_development"]
    )
    human_query, _ = query_features(partition_probabilities["human_development"])
    train_classes = word_class_ids(train_records, train_labels)
    development_classes = word_class_ids(development_records, development_labels)
    development_negative_mask = stage1_eligible_negative_mask(
        development_records, development_labels, negative_report
    )

    candidates = {
        "logistic_c0p1": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000),
        ),
        "logistic_c1": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000),
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=20260804,
        ),
    }
    results = {}
    for name, classifier in candidates.items():
        fit_started = time.perf_counter()
        classifier.fit(train_query, train_classes)
        development_class_probabilities = classifier.predict_proba(development_query)
        human_class_probabilities = classifier.predict_proba(human_query)
        class_values = tuple(int(value) for value in classifier.classes_)
        target_column = class_values.index(1)
        development_target = development_class_probabilities[:, target_column]
        human_target = human_class_probabilities[:, target_column]
        development_binary = binary_metrics(
            development_target,
            development_labels,
            negative_mask=development_negative_mask,
        )
        threshold = float(development_binary["threshold"])
        human_positive, human_negative, human_clips = aggregate_human_clip_scores(
            human_target, human_records
        )
        results[name] = {
            "fit_seconds": time.perf_counter() - fit_started,
            "development_multiclass_accuracy": accuracy_score(
                development_classes, classifier.predict(development_query)
            ),
            "development_multiclass_balanced_accuracy": balanced_accuracy_score(
                development_classes, classifier.predict(development_query)
            ),
            "development": development_binary,
            "human_development_at_development_threshold": {
                "positive_accepted": int((human_positive >= threshold).sum()),
                "positive_total": len(human_positive),
                "hard_negative_false_accepts": int((human_negative >= threshold).sum()),
                "hard_negative_total": len(human_negative),
                "margin_auc": roc_auc(human_positive, human_negative),
                "clips": human_clips,
            },
        }
    report = {
        "schema": "baxy.phoneme-student-query-matcher-probe.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "frozen_phoneme_student_posterior_query_features_then_multiclass_matcher",
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "negative_report": negative_report_path.as_posix(),
            "negative_report_sha256": sha256(negative_report_path),
            "checkpoint": checkpoint_path.as_posix(),
            "checkpoint_sha256": sha256(checkpoint_path),
            "checkpoint_report": checkpoint_report_path.as_posix(),
            "checkpoint_report_sha256": sha256(checkpoint_report_path),
        },
        "features": {
            "count": len(feature_names),
            "names": feature_names,
        },
        "runtime": {
            "device": device,
            "student_inference_seconds": inference_seconds,
        },
        "candidates": results,
        "human_development_used_for_training_or_selection": False,
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
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--negative-report", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-report", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = run(
        feature_manifest_path=arguments.feature_manifest,
        negative_report_path=arguments.negative_report,
        checkpoint_path=arguments.checkpoint,
        checkpoint_report_path=arguments.checkpoint_report,
        wekws_directory=arguments.wekws_dir,
        output_path=arguments.output,
        device=arguments.device,
    )
    print(json.dumps({"output": arguments.output.as_posix(), "candidates": report["candidates"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
