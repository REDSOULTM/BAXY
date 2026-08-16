"""Evaluate a frozen similarity-matrix CNN on train-only MSWC research words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_qbye_similarity_tuning_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SEQUENCE = load_component(
    "evaluate_mswc_spanish_qbye_sequence_tuning_v3.py",
    "_baxy_qbye_similarity_tuning_sequence_v4",
)
_TRAIN = load_component(
    "train_mswc_spanish_qbye_similarity_cnn_v4.py",
    "_baxy_qbye_similarity_tuning_model_v4",
)
_BASELINE = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py",
    "_baxy_qbye_similarity_tuning_hash_v4",
)
_FIXED = load_component(
    "train_mswc_spanish_qbye_angular_prototypical_v1.py",
    "_baxy_qbye_similarity_tuning_fixed_v4",
)


def maximum_pair_scores(
    *,
    pair_scores: np.ndarray,
    query_rows: list[int],
    class_indexes: list[int],
    shape: tuple[int, int],
    floor: float,
) -> np.ndarray:
    if len(pair_scores) != len(query_rows) or len(pair_scores) != len(class_indexes):
        raise ValueError("mswc_qbye_similarity_tuning_pair_shape_invalid")
    result = np.full(shape, floor, dtype=np.float64)
    for score, query_row, class_index in zip(
        pair_scores, query_rows, class_indexes, strict=True
    ):
        result[query_row, class_index] = max(
            result[query_row, class_index], float(score)
        )
    return result


def evaluate(
    *,
    feature_manifest_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    maximum_shortlist: int,
    prediction_batch_size: int,
    device: str,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or maximum_shortlist < 1
        or prediction_batch_size < 1
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_qbye_similarity_tuning_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    checkpoint_path = checkpoint_path.resolve(strict=True)
    output_path = output_path.resolve()
    manifest = _SEQUENCE.read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    feature_contract = manifest.get("contract")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-sequence-features.v3"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(feature_contract, dict)
    ):
        raise ValueError("mswc_qbye_similarity_tuning_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict) or not isinstance(
            record.get("greedy_ctc_token_ids"), list
        ):
            raise ValueError("mswc_qbye_similarity_tuning_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _SEQUENCE.split_research_words(
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
    class_to_index = {name: index for index, name in enumerate(class_names)}
    enrollment_classes = [str(records[index]["class_name"]) for index in enrollment_indexes]
    query_classes = [str(records[index]["class_name"]) for index in query_indexes]
    if len(enrollment_indexes) != tuning_classes * 2 or len(query_indexes) != tuning_classes * 6:
        raise ValueError("mswc_qbye_similarity_tuning_partition_invalid")
    enrollment_sequences = [
        [int(value) for value in records[index]["greedy_ctc_token_ids"]]
        for index in enrollment_indexes
    ]
    query_sequences = [
        [int(value) for value in records[index]["greedy_ctc_token_ids"]]
        for index in query_indexes
    ]
    edit_scores = _SEQUENCE.edit_score_matrix(
        enrollment_sequences=enrollment_sequences,
        enrollment_classes=enrollment_classes,
        query_sequences=query_sequences,
        class_names=class_names,
        aggregation="maximum",
    )
    enrollment_indexes_by_class = {
        name: [
            index
            for index, class_name in zip(
                enrollment_indexes, enrollment_classes, strict=True
            )
            if class_name == name
        ]
        for name in class_names
    }
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    hidden_descriptor = files.get("hidden")
    if (
        not isinstance(hidden_descriptor, dict)
        or _BASELINE.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_qbye_similarity_tuning_files_invalid")
    hidden_path = root / str(hidden_descriptor["path"])
    if _BASELINE.sha256(hidden_path) != hidden_descriptor.get("sha256"):
        raise ValueError("mswc_qbye_similarity_tuning_hidden_hash_mismatch")
    offsets = np.load(offset_path)
    hidden = np.load(hidden_path, mmap_mode="r")
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(hidden):
        raise ValueError("mswc_qbye_similarity_tuning_feature_shape_invalid")

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_similarity_tuning_cuda_unavailable")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema") != "baxy.mswc-spanish-qbye-similarity-cnn.v4"
        or int(checkpoint["layer"]) != int(feature_contract["hidden_layer"])
        or int(checkpoint["hidden_size"]) != int(feature_contract["hidden_size"])
    ):
        raise ValueError("mswc_qbye_similarity_tuning_checkpoint_invalid")
    torch_device = torch.device(device)
    model = _TRAIN.make_similarity_model(
        torch, int(checkpoint["hidden_size"]), int(checkpoint["projection_size"])
    ).to(torch_device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    pair_query_indexes = []
    pair_enrollment_indexes = []
    pair_query_rows = []
    pair_class_indexes = []
    for query_row, query_index in enumerate(query_indexes):
        selected = np.argpartition(
            edit_scores[query_row], -maximum_shortlist
        )[-maximum_shortlist:]
        for class_index in selected:
            for enrollment_index in enrollment_indexes_by_class[
                class_names[int(class_index)]
            ]:
                pair_query_indexes.append(query_index)
                pair_enrollment_indexes.append(enrollment_index)
                pair_query_rows.append(query_row)
                pair_class_indexes.append(int(class_index))

    def fixed_batch(indexes: list[int]) -> tuple[np.ndarray, np.ndarray]:
        fixed = []
        masks = []
        for index in indexes:
            sequence, mask = _FIXED.fixed_sequence(
                hidden[int(offsets[index]) : int(offsets[index + 1])],
                int(checkpoint["maximum_frames"]),
            )
            fixed.append(sequence)
            masks.append(mask)
        return np.stack(fixed), np.stack(masks)

    pair_logits = []
    with torch.inference_mode():
        for start in range(0, len(pair_query_indexes), prediction_batch_size):
            query_values, query_masks = fixed_batch(
                pair_query_indexes[start : start + prediction_batch_size]
            )
            enrollment_values, enrollment_masks = fixed_batch(
                pair_enrollment_indexes[start : start + prediction_batch_size]
            )
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = model(
                    torch.from_numpy(query_values).to(torch_device),
                    torch.from_numpy(query_masks).to(torch_device),
                    torch.from_numpy(enrollment_values).to(torch_device),
                    torch.from_numpy(enrollment_masks).to(torch_device),
                )
            pair_logits.append(logits.float().cpu().numpy())
    cnn_scores = maximum_pair_scores(
        pair_scores=np.concatenate(pair_logits),
        query_rows=pair_query_rows,
        class_indexes=pair_class_indexes,
        shape=edit_scores.shape,
        floor=-100.0,
    )
    targets = np.asarray([class_to_index[name] for name in query_classes], dtype=np.int64)
    runs = []
    for shortlist in (5, 10, 20, 40):
        if shortlist > maximum_shortlist:
            continue
        active = np.zeros_like(cnn_scores, dtype=np.bool_)
        for row in range(len(edit_scores)):
            chosen = np.argpartition(edit_scores[row], -shortlist)[-shortlist:]
            active[row, chosen] = True
        proposal_recall = float(np.mean(active[np.arange(len(active)), targets]))
        for edit_weight in (0.0, 0.25, 0.5, 1.0, 2.0):
            scores = np.where(active, cnn_scores + edit_weight * edit_scores, -100.0)
            metrics = _SEQUENCE.score_metrics(
                scores=scores,
                class_names=class_names,
                query_classes=query_classes,
            )
            runs.append(
                {
                    "method": "greedy_edit_shortlist_then_similarity_cnn",
                    "shortlist_classes": shortlist,
                    "edit_weight": edit_weight,
                    "proposal_recall": proposal_recall,
                    "metrics": metrics,
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
        "schema": "baxy.mswc-spanish-qbye-similarity-cnn-tuning.v4",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_tuning_of_greedy_shortlist_and_frame_similarity_cnn",
        "sources": {
            "feature_manifest_sha256": _BASELINE.sha256(feature_manifest_path),
            "checkpoint_sha256": _BASELINE.sha256(checkpoint_path),
        },
        "contract": {
            "split_seed": split_seed,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "maximum_shortlist": maximum_shortlist,
            "enrollment_aggregation": "maximum_of_two_distinct_speaker_pair_logits",
            "non_proposed_score": -100.0,
            "selection_rank": "zero_false_recall_then_top1_then_auc_then_negative_eer_after_quality_floor",
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
    parser.add_argument("--maximum-shortlist", type=int, default=40)
    parser.add_argument("--prediction-batch-size", type=int, default=128)
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
        maximum_shortlist=args.maximum_shortlist,
        prediction_batch_size=args.prediction_batch_size,
        device=args.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
