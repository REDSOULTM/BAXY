"""Tune aggregate phonetic-sequence and metric QbyE fusion on train-only words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_qbye_sequence_tuning_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASELINE = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py",
    "_baxy_qbye_sequence_tuning_baseline_v3",
)
_TRAINER = load_component(
    "train_mswc_spanish_qbye_angular_prototypical_v1.py",
    "_baxy_qbye_sequence_tuning_trainer_v3",
)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_sequence_tuning_json_invalid:{path}")
    return value


def split_research_words(
    words: set[str], *, seed: int, tuning_classes: int
) -> tuple[set[str], set[str]]:
    ordered = sorted(
        words,
        key=lambda word: (
            hashlib.sha256(f"{seed}\x1f{word}".encode("utf-8")).hexdigest(),
            word,
        ),
    )
    if len(ordered) < tuning_classes + 2 or tuning_classes < 2:
        raise ValueError("mswc_qbye_sequence_tuning_word_split_invalid")
    return set(ordered[:tuning_classes]), set(ordered[tuning_classes:])


def edit_distance(left: list[int], right: list[int]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, 1):
        current = [left_index]
        for right_index, right_value in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def edit_similarity(left: list[int], right: list[int]) -> float:
    denominator = max(len(left), len(right), 1)
    return 1.0 - edit_distance(left, right) / denominator


def score_metrics(
    *, scores: np.ndarray, class_names: list[str], query_classes: list[str]
) -> dict[str, object]:
    values = np.asarray(scores, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape != (len(query_classes), len(class_names))
        or len(class_names) < 2
        or not np.isfinite(values).all()
        or set(query_classes) != set(class_names)
    ):
        raise ValueError("mswc_qbye_sequence_tuning_scores_invalid")
    class_to_index = {name: index for index, name in enumerate(class_names)}
    targets = np.asarray([class_to_index[name] for name in query_classes], dtype=np.int64)
    true_scores = values[np.arange(len(values)), targets]
    impostor_mask = np.ones_like(values, dtype=np.bool_)
    impostor_mask[np.arange(len(values)), targets] = False
    maximum_impostors = np.max(np.where(impostor_mask, values, -np.inf), axis=1)
    margins = true_scores - maximum_impostors
    predictions = np.argmax(values, axis=1)
    impostor_scores = values[impostor_mask]
    zero_false_threshold = float(np.nextafter(impostor_scores.max(), math.inf))
    from sklearn.metrics import roc_auc_score, roc_curve

    binary_labels = np.concatenate(
        [
            np.ones(len(true_scores), dtype=np.int64),
            np.zeros(len(impostor_scores), dtype=np.int64),
        ]
    )
    binary_scores = np.concatenate([true_scores, impostor_scores])
    false_positive_rate, true_positive_rate, thresholds = roc_curve(
        binary_labels, binary_scores
    )
    false_negative_rate = 1.0 - true_positive_rate
    equal_index = int(np.argmin(np.abs(false_positive_rate - false_negative_rate)))
    per_class_accuracy = []
    for class_index in range(len(class_names)):
        mask = targets == class_index
        per_class_accuracy.append(float(np.mean(predictions[mask] == class_index)))
    return {
        "classes": len(class_names),
        "queries": len(query_classes),
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


def edit_score_matrix(
    *,
    enrollment_sequences: list[list[int]],
    enrollment_classes: list[str],
    query_sequences: list[list[int]],
    class_names: list[str],
    aggregation: str,
) -> np.ndarray:
    if aggregation not in {"maximum", "mean"}:
        raise ValueError("mswc_qbye_sequence_tuning_edit_aggregation_invalid")
    templates = {
        name: [
            sequence
            for sequence, class_name in zip(
                enrollment_sequences, enrollment_classes, strict=True
            )
            if class_name == name
        ]
        for name in class_names
    }
    result = np.empty((len(query_sequences), len(class_names)), dtype=np.float64)
    for query_index, query in enumerate(query_sequences):
        for class_index, name in enumerate(class_names):
            similarities = [edit_similarity(query, template) for template in templates[name]]
            result[query_index, class_index] = (
                max(similarities)
                if aggregation == "maximum"
                else float(np.mean(similarities))
            )
    return result


def evaluate(
    *,
    feature_manifest_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    prediction_batch_size: int,
    device: str,
) -> dict[str, object]:
    started = time.perf_counter()
    if output_path.exists() or prediction_batch_size < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("mswc_qbye_sequence_tuning_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    checkpoint_path = checkpoint_path.resolve(strict=True)
    output_path = output_path.resolve()
    manifest = read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    contract = manifest.get("contract")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-sequence-features.v3"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(contract, dict)
    ):
        raise ValueError("mswc_qbye_sequence_tuning_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict) or not isinstance(
            record.get("greedy_ctc_token_ids"), list
        ):
            raise ValueError("mswc_qbye_sequence_tuning_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = split_research_words(
        words, seed=split_seed, tuning_classes=tuning_classes
    )
    enrollment_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_enrollment"
        and str(record["class_name"]) in tuning_words
    ]
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_query"
        and str(record["class_name"]) in tuning_words
    ]
    class_names = sorted(tuning_words)
    enrollment_classes = [str(records[index]["class_name"]) for index in enrollment_indexes]
    query_classes = [str(records[index]["class_name"]) for index in query_indexes]
    if (
        len(enrollment_indexes) != tuning_classes * 2
        or len(query_indexes) != tuning_classes * 6
        or set(enrollment_classes) != tuning_words
        or set(query_classes) != tuning_words
    ):
        raise ValueError("mswc_qbye_sequence_tuning_partition_invalid")
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    hidden_descriptor = files.get("hidden")
    if (
        not isinstance(hidden_descriptor, dict)
        or _BASELINE.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_qbye_sequence_tuning_files_invalid")
    hidden_path = root / str(hidden_descriptor["path"])
    if _BASELINE.sha256(hidden_path) != hidden_descriptor.get("sha256"):
        raise ValueError("mswc_qbye_sequence_tuning_hidden_hash_mismatch")
    offsets = np.load(offset_path)
    hidden = np.load(hidden_path, mmap_mode="r")
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(hidden):
        raise ValueError("mswc_qbye_sequence_tuning_feature_shape_invalid")

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_sequence_tuning_cuda_unavailable")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema") != "baxy.mswc-spanish-qbye-angleproto.v1"
        or int(checkpoint["layer"]) != int(contract["hidden_layer"])
    ):
        raise ValueError("mswc_qbye_sequence_tuning_checkpoint_invalid")
    torch_device = torch.device(device)
    model = _TRAINER.make_model(
        torch, int(checkpoint["hidden_size"]), int(checkpoint["embedding_size"])
    ).to(torch_device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    def embeddings(indexes: list[int]) -> np.ndarray:
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(indexes), prediction_batch_size):
                selected = indexes[start : start + prediction_batch_size]
                fixed = []
                masks = []
                for index in selected:
                    sequence, mask = _TRAINER.fixed_sequence(
                        hidden[int(offsets[index]) : int(offsets[index + 1])],
                        int(checkpoint["maximum_frames"]),
                    )
                    fixed.append(sequence)
                    masks.append(mask)
                outputs.append(
                    model(
                        torch.from_numpy(np.stack(fixed)).to(torch_device),
                        torch.from_numpy(np.stack(masks)).to(torch_device),
                    )
                    .float()
                    .cpu()
                    .numpy()
                )
        return np.concatenate(outputs)

    enrollment_embeddings = _BASELINE.l2_normalize(embeddings(enrollment_indexes))
    query_embeddings = _BASELINE.l2_normalize(embeddings(query_indexes))
    prototypes = []
    for name in class_names:
        indexes = [
            index for index, value in enumerate(enrollment_classes) if value == name
        ]
        prototypes.append(_BASELINE.l2_normalize(enrollment_embeddings[indexes].mean(axis=0)))
    embedding_scores = query_embeddings @ np.stack(prototypes).T
    enrollment_sequences = [
        [int(value) for value in records[index]["greedy_ctc_token_ids"]]
        for index in enrollment_indexes
    ]
    query_sequences = [
        [int(value) for value in records[index]["greedy_ctc_token_ids"]]
        for index in query_indexes
    ]
    runs = [
        {
            "method": "hard_tail_metric_embedding",
            "metrics": score_metrics(
                scores=embedding_scores,
                class_names=class_names,
                query_classes=query_classes,
            ),
        }
    ]
    for aggregation in ("maximum", "mean"):
        edit_scores = edit_score_matrix(
            enrollment_sequences=enrollment_sequences,
            enrollment_classes=enrollment_classes,
            query_sequences=query_sequences,
            class_names=class_names,
            aggregation=aggregation,
        )
        runs.append(
            {
                "method": f"greedy_ctc_normalized_edit_{aggregation}",
                "metrics": score_metrics(
                    scores=edit_scores,
                    class_names=class_names,
                    query_classes=query_classes,
                ),
            }
        )
        for embedding_weight in (0.25, 0.5, 0.75):
            fused_scores = (
                embedding_weight * embedding_scores
                + (1.0 - embedding_weight) * (2.0 * edit_scores - 1.0)
            )
            runs.append(
                {
                    "method": "metric_embedding_greedy_ctc_edit_fusion",
                    "edit_aggregation": aggregation,
                    "embedding_weight": embedding_weight,
                    "metrics": score_metrics(
                        scores=fused_scores,
                        class_names=class_names,
                        query_classes=query_classes,
                    ),
                }
            )
    viable = [
        run
        for run in runs
        if float(run["metrics"]["top1_accuracy"]) >= 0.85
        and float(run["metrics"]["pair_auc"]) >= 0.99
        and float(run["metrics"]["equal_error_rate"]) <= 0.05
    ]
    ranked = viable if viable else runs
    selected = max(
        ranked,
        key=lambda run: (
            int(run["metrics"]["true_pairs_accepted_at_zero_false_pairs"]),
            float(run["metrics"]["top1_accuracy"]),
            float(run["metrics"]["pair_auc"]),
            -float(run["metrics"]["equal_error_rate"]),
        ),
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-sequence-tuning.v3",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_tuning_of_metric_and_greedy_phonetic_sequence_fusion",
        "sources": {
            "feature_manifest_sha256": _BASELINE.sha256(feature_manifest_path),
            "checkpoint_sha256": _BASELINE.sha256(checkpoint_path),
        },
        "contract": {
            "split_seed": split_seed,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "selection_rank": "zero_false_recall_then_top1_then_auc_then_negative_eer_after_quality_floor",
            "quality_floor": {"top1_accuracy": 0.85, "pair_auc": 0.99, "equal_error_rate": 0.05},
        },
        "runs": runs,
        "selected": selected,
        "runtime_seconds": time.perf_counter() - started,
        "research_tuning_examples_scored": True,
        "research_reserved_examples_scored": False,
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
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--prediction-batch-size", type=int, default=256)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        feature_manifest_path=args.feature_manifest,
        checkpoint_path=args.checkpoint,
        output_path=args.output,
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        prediction_batch_size=args.prediction_batch_size,
        device=args.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
