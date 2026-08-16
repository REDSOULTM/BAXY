"""Train an attention embedding with Sub-center ArcFace on frozen SSL features."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import time

import numpy as np


_BASE_PATH = Path(__file__).with_name("train_wav2vec2_hidden_wake_mil_head_v1.py")
_BASE_SPEC = importlib.util.spec_from_file_location("_baxy_wake_mil_base_for_scaf_v1", _BASE_PATH)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise RuntimeError("wake_scaf_base_import_invalid")
_BASE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_BASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_scaf_json_invalid:{path}")
    return value


def fixed_sequence(values: np.ndarray, frames: int) -> tuple[np.ndarray, np.ndarray]:
    sequence = np.asarray(values, dtype=np.float32)
    if sequence.ndim != 2 or not len(sequence) or frames < 2 or not np.isfinite(sequence).all():
        raise ValueError("wake_scaf_sequence_invalid")
    if len(sequence) > frames:
        start = (len(sequence) - frames) // 2
        sequence = sequence[start : start + frames]
    output = np.zeros((frames, sequence.shape[1]), dtype=np.float32)
    mask = np.zeros(frames, dtype=np.bool_)
    output[: len(sequence)] = sequence
    mask[: len(sequence)] = True
    return output, mask


def make_model(torch: object, hidden_size: int, embedding_size: int) -> object:
    nn = torch.nn

    class AttentionEmbedding(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.reduction = nn.Linear(hidden_size, 128)
            self.temporal = nn.Conv1d(128, 128, kernel_size=3, padding=1)
            self.activation = nn.PReLU(128)
            self.query = nn.Parameter(torch.empty(128))
            self.output = nn.Linear(128, embedding_size)
            self.dropout = nn.Dropout(0.10)
            nn.init.normal_(self.query, mean=0.0, std=0.02)

        def forward(self, values: object, mask: object) -> object:
            hidden = self.reduction(values)
            hidden = self.temporal(hidden.transpose(1, 2))
            hidden = self.activation(hidden).transpose(1, 2)
            hidden = self.dropout(hidden)
            logits = hidden @ self.query / math.sqrt(hidden.shape[-1])
            logits = logits.masked_fill(~mask, -torch.inf)
            weights = torch.softmax(logits, dim=1)
            pooled = torch.sum(hidden * weights.unsqueeze(-1), dim=1)
            return torch.nn.functional.normalize(self.output(pooled), dim=-1)

    return AttentionEmbedding()


def class_cosines(torch: object, embeddings: object, centers: object) -> object:
    normalized_centers = torch.nn.functional.normalize(centers, dim=-1)
    subcenter_cosines = torch.einsum("bd,ckd->bck", embeddings, normalized_centers)
    return torch.max(subcenter_cosines, dim=-1).values


def subcenter_arcface_logits(
    torch: object,
    embeddings: object,
    centers: object,
    labels: object,
    *,
    margin: float,
    scale: float,
) -> object:
    cosines = class_cosines(torch, embeddings, centers)
    rows = torch.arange(len(labels), device=labels.device)
    target = torch.clamp(cosines[rows, labels], -1.0 + 1e-6, 1.0 - 1e-6)
    target_with_margin = torch.cos(torch.acos(target) + margin)
    logits = cosines.clone()
    logits[rows, labels] = target_with_margin
    return logits * scale


def human_group_margins(
    *,
    aligned_positive_embeddings: np.ndarray,
    scan_embeddings: list[np.ndarray],
    labels: np.ndarray,
    groups: list[str],
) -> tuple[np.ndarray, list[dict[str, object]]]:
    aligned = np.asarray(aligned_positive_embeddings, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    group_array = np.asarray(groups)
    margins = np.empty(len(targets), dtype=np.float64)
    folds = []
    for group in sorted(set(groups)):
        held = group_array == group
        train = ~held
        positive_indexes = np.flatnonzero(train & (targets == 1))
        negative_indexes = np.flatnonzero(train & (targets == 0))
        if not len(positive_indexes) or not len(negative_indexes):
            raise ValueError("wake_scaf_human_fold_class_missing")
        prototype = aligned[positive_indexes].mean(axis=0)
        prototype /= np.linalg.norm(prototype)
        training_negative_scores = np.asarray(
            [
                float(np.max(np.asarray(scan_embeddings[index]) @ prototype))
                for index in negative_indexes
            ]
        )
        threshold = float(np.nextafter(training_negative_scores.max(), math.inf))
        held_indexes = np.flatnonzero(held)
        held_scores = np.asarray(
            [
                float(np.max(np.asarray(scan_embeddings[index]) @ prototype))
                for index in held_indexes
            ]
        )
        held_margins = held_scores - threshold
        margins[held_indexes] = held_margins
        held_labels = targets[held_indexes]
        folds.append(
            {
                "held_group": group,
                "training_negative_threshold": threshold,
                "held_positive_count": int(np.count_nonzero(held_labels == 1)),
                "held_negative_count": int(np.count_nonzero(held_labels == 0)),
                "held_positive_accepted": int(
                    np.count_nonzero(held_margins[held_labels == 1] >= 0.0)
                ),
                "held_negative_false_accepts": int(
                    np.count_nonzero(held_margins[held_labels == 0] >= 0.0)
                ),
            }
        )
    return margins, folds


def margin_metrics(margins: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    from sklearn.metrics import roc_auc_score

    values = np.asarray(margins, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    positives = values[targets == 1]
    negatives = values[targets == 0]
    return {
        "auc": float(roc_auc_score(targets, values)),
        "threshold": 0.0,
        "positive_accepted": int(np.count_nonzero(positives >= 0.0)),
        "positive_total": int(len(positives)),
        "negative_false_accepts": int(np.count_nonzero(negatives >= 0.0)),
        "negative_total": int(len(negatives)),
    }


def train(
    *,
    feature_manifest_path: Path,
    output_root: Path,
    seeds: list[int],
    epochs: int,
    batches_per_epoch: int,
    classes_per_batch: int,
    samples_per_class: int,
    learning_rate: float,
    maximum_frames: int,
    embedding_size: int,
    subcenters: int,
    arcface_margin: float,
    arcface_scale: float,
    human_window_offset_seconds: float,
    human_window_duration_seconds: float,
    prediction_batch_size: int,
    device: str,
) -> dict[str, object]:
    if (
        output_root.exists()
        or not seeds
        or epochs < 1
        or batches_per_epoch < 1
        or classes_per_batch < 2
        or samples_per_class < 1
        or learning_rate <= 0.0
        or maximum_frames < 10
        or embedding_size < 8
        or subcenters < 1
        or not 0.0 < arcface_margin < 1.0
        or arcface_scale <= 1.0
        or human_window_duration_seconds <= 0.0
        or prediction_batch_size < 1
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("wake_scaf_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise ValueError("wake_scaf_partial_output_exists")
    manifest = read_object(feature_manifest_path)
    if (
        manifest.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or manifest.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_scaf_feature_boundary_invalid")
    files = manifest.get("files")
    contract = manifest.get("contract")
    source_records = manifest.get("records")
    if not isinstance(files, dict) or not isinstance(contract, dict) or not isinstance(source_records, list):
        raise ValueError("wake_scaf_feature_manifest_invalid")
    records = []
    for record in source_records:
        if not isinstance(record, dict):
            raise ValueError("wake_scaf_record_invalid")
        records.append(record)
    feature_root = feature_manifest_path.parent
    feature_path = feature_root / str(files["features"])
    offset_path = feature_root / str(files["offsets"])
    if (
        sha256(feature_path) != files.get("features_sha256")
        or sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("wake_scaf_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    hidden_size = int(contract["hidden_size"])
    if features.shape[1] != hidden_size or len(offsets) != len(records) + 1:
        raise ValueError("wake_scaf_feature_shape_invalid")

    synthetic_indexes = [
        index
        for index, record in enumerate(records)
        if str(record["corpus"]).startswith("synthetic_")
        and int(record["feature_frames"]) <= maximum_frames
    ]
    human_indexes = [
        index
        for index, record in enumerate(records)
        if str(record["corpus"]).startswith("human_")
    ]
    class_names = ["target"] + sorted(
        {
            f"negative:{record['phrase_id']}"
            for record in records
            if record["corpus"] == "synthetic_negative"
            and int(record["feature_frames"]) <= maximum_frames
        }
    )
    class_to_id = {name: index for index, name in enumerate(class_names)}
    synthetic_classes = np.asarray(
        [
            0
            if records[index]["corpus"] == "synthetic_positive"
            else class_to_id[f"negative:{records[index]['phrase_id']}"]
            for index in synthetic_indexes
        ],
        dtype=np.int64,
    )
    if len(class_names) < 50 or set(synthetic_classes) != set(range(len(class_names))):
        raise ValueError("wake_scaf_classes_invalid")
    synthetic_groups = {str(records[index]["group"]) for index in synthetic_indexes}
    validation_groups = _BASE.validation_groups(synthetic_groups)
    training_positions = [
        position
        for position, index in enumerate(synthetic_indexes)
        if str(records[index]["group"]) not in validation_groups
    ]
    validation_positions = [
        position
        for position, index in enumerate(synthetic_indexes)
        if str(records[index]["group"]) in validation_groups
    ]
    by_class = {
        class_id: [
            position
            for position in training_positions
            if int(synthetic_classes[position]) == class_id
        ]
        for class_id in range(len(class_names))
    }
    if any(not positions for positions in by_class.values()) or classes_per_batch > len(class_names):
        raise ValueError("wake_scaf_training_class_split_invalid")

    fixed_features = np.zeros(
        (len(synthetic_indexes), maximum_frames, hidden_size), dtype=np.float16
    )
    fixed_masks = np.zeros((len(synthetic_indexes), maximum_frames), dtype=np.bool_)
    for position, index in enumerate(synthetic_indexes):
        sequence, mask = fixed_sequence(
            features[int(offsets[index]) : int(offsets[index + 1])], maximum_frames
        )
        fixed_features[position] = sequence.astype(np.float16)
        fixed_masks[position] = mask

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_scaf_cuda_unavailable")
    torch_device = torch.device(device)

    def synthetic_batch(positions: list[int]) -> tuple[object, object, object]:
        values = torch.from_numpy(fixed_features[positions].astype(np.float32)).to(torch_device)
        masks = torch.from_numpy(fixed_masks[positions]).to(torch_device)
        labels = torch.from_numpy(synthetic_classes[positions]).to(torch_device)
        return values, masks, labels

    def embed_arrays(model: object, arrays: list[np.ndarray]) -> list[np.ndarray]:
        outputs = []
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(arrays), prediction_batch_size):
                selected = arrays[start : start + prediction_batch_size]
                fixed = []
                masks = []
                for values in selected:
                    sequence, mask = fixed_sequence(values, maximum_frames)
                    fixed.append(sequence)
                    masks.append(mask)
                x = torch.from_numpy(np.stack(fixed)).to(torch_device)
                mask_tensor = torch.from_numpy(np.stack(masks)).to(torch_device)
                outputs.extend(model(x, mask_tensor).float().cpu().numpy())
        return outputs

    def synthetic_validation(model: object, centers: object) -> dict[str, object]:
        model.eval()
        scores = []
        target_scores = []
        targets = []
        with torch.inference_mode():
            for start in range(0, len(validation_positions), prediction_batch_size):
                positions = validation_positions[start : start + prediction_batch_size]
                x, mask, labels = synthetic_batch(positions)
                embeddings = model(x, mask)
                cosines = class_cosines(torch, embeddings, centers)
                scores.extend(torch.argmax(cosines, dim=1).cpu().numpy().tolist())
                target_scores.extend(
                    (
                        cosines[:, 0] - torch.max(cosines[:, 1:], dim=1).values
                    ).cpu().numpy().tolist()
                )
                targets.extend(labels.cpu().numpy().tolist())
        class_targets = np.asarray(targets)
        predictions = np.asarray(scores)
        binary_labels = (class_targets == 0).astype(np.int64)
        target_metrics = _BASE.metrics_from_scores(
            np.asarray(target_scores), binary_labels
        )
        return {
            "multiclass_accuracy": float(np.mean(predictions == class_targets)),
            "records": int(len(class_targets)),
            "target_vs_confusables": target_metrics,
        }

    def human_evaluation(model: object) -> tuple[dict[str, object], list[dict[str, object]]]:
        aligned_arrays = []
        scan_arrays_by_record: list[list[np.ndarray]] = []
        labels = []
        groups = []
        for index in human_indexes:
            record = records[index]
            hidden = np.asarray(
                features[int(offsets[index]) : int(offsets[index + 1])], dtype=np.float32
            )
            positive = record["label"] == "positive"
            labels.append(1 if positive else 0)
            groups.append(str(record["group"]))
            if positive:
                onset = float(record["target_onset_seconds"])
                frame_count = max(
                    2, round(human_window_duration_seconds / 0.02)
                )
                centers = np.arange(len(hidden), dtype=np.float64) * 0.02 + 0.0125
                start_seconds = max(0.0, onset + human_window_offset_seconds)
                start_frame = int(np.argmin(np.abs(centers - start_seconds)))
                end_frame = min(len(hidden), start_frame + frame_count)
                aligned_arrays.append(hidden[start_frame:end_frame])
            else:
                aligned_arrays.append(hidden[:2])
            window_frames = max(2, round(human_window_duration_seconds / 0.02))
            starts = list(range(0, max(1, len(hidden) - window_frames + 1)))
            if starts[-1] != max(0, len(hidden) - window_frames):
                starts.append(max(0, len(hidden) - window_frames))
            scan_arrays_by_record.append(
                [hidden[start : min(len(hidden), start + window_frames)] for start in starts]
            )
        positive_positions = [index for index, label in enumerate(labels) if label == 1]
        positive_embeddings = embed_arrays(
            model, [aligned_arrays[index] for index in positive_positions]
        )
        aligned_embeddings = np.zeros((len(human_indexes), embedding_size), dtype=np.float32)
        for index, embedding in zip(positive_positions, positive_embeddings, strict=True):
            aligned_embeddings[index] = embedding
        flat_scans = [array for arrays in scan_arrays_by_record for array in arrays]
        flat_embeddings = embed_arrays(model, flat_scans)
        scan_embeddings = []
        cursor = 0
        for arrays in scan_arrays_by_record:
            scan_embeddings.append(np.stack(flat_embeddings[cursor : cursor + len(arrays)]))
            cursor += len(arrays)
        target_array = np.asarray(labels, dtype=np.int64)
        margins, folds = human_group_margins(
            aligned_positive_embeddings=aligned_embeddings,
            scan_embeddings=scan_embeddings,
            labels=target_array,
            groups=groups,
        )
        metrics = margin_metrics(margins, target_array)
        breakdown = [
            {
                "corpus": records[index]["corpus"],
                "relative_path": records[index]["relative_path"],
                "group": records[index]["group"],
                "label": records[index]["label"],
                "source_label": records[index].get("source_label"),
                "speaker_held_out_margin": float(margin),
                "accepted": bool(margin >= 0.0),
            }
            for index, margin in zip(human_indexes, margins, strict=True)
        ]
        return {**metrics, "folds": folds}, breakdown

    partial_root.mkdir(parents=True)
    started = time.perf_counter()
    runs = []
    best_rank: tuple[float, float, float] | None = None
    best_state = None
    best_centers = None
    best_seed = None
    for seed in seeds:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        model = make_model(torch, hidden_size, embedding_size).to(torch_device)
        centers = torch.nn.Parameter(
            torch.empty(len(class_names), subcenters, embedding_size, device=torch_device)
        )
        torch.nn.init.normal_(centers, mean=0.0, std=0.02)
        optimizer = torch.optim.AdamW(
            [*model.parameters(), centers], lr=learning_rate, weight_decay=1e-4
        )
        generator = random.Random(seed)
        history = []
        for epoch in range(epochs):
            model.train()
            epoch_loss = 0.0
            for _ in range(batches_per_epoch):
                chosen_classes = generator.sample(range(len(class_names)), classes_per_batch)
                positions = []
                for class_id in chosen_classes:
                    choices = by_class[class_id]
                    positions.extend(generator.choice(choices) for _ in range(samples_per_class))
                generator.shuffle(positions)
                x, mask, labels = synthetic_batch(positions)
                optimizer.zero_grad(set_to_none=True)
                embeddings = model(x, mask)
                logits = subcenter_arcface_logits(
                    torch,
                    embeddings,
                    centers,
                    labels,
                    margin=arcface_margin,
                    scale=arcface_scale,
                )
                loss = torch.nn.functional.cross_entropy(logits, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_([*model.parameters(), centers], 5.0)
                optimizer.step()
                epoch_loss += float(loss.detach().cpu())
            if epoch == epochs - 1 or epoch % 5 == 4:
                validation = synthetic_validation(model, centers)
                history.append(
                    {
                        "epoch": epoch + 1,
                        "mean_training_loss": epoch_loss / batches_per_epoch,
                        "synthetic_validation": validation,
                    }
                )
        validation = synthetic_validation(model, centers)
        human_metrics, human_records_report = human_evaluation(model)
        run = {
            "seed": seed,
            "history": history,
            "synthetic_validation": validation,
            "human_speaker_held_out": human_metrics,
            "human_records": human_records_report,
        }
        runs.append(run)
        target = validation["target_vs_confusables"]
        rank = (
            float(target["zero_false_positive_rate"]),
            float(target["auc"]),
            float(validation["multiclass_accuracy"]),
        )
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_seed = seed
            best_state = {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            }
            best_centers = centers.detach().cpu()
    assert best_state is not None and best_centers is not None and best_seed is not None
    model_path = partial_root / "wake-scaf-embedding-v1.pt"
    torch.save(
        {
            "schema": "baxy.wav2vec2-hidden-wake-scaf-embedding.v1",
            "hidden_size": hidden_size,
            "embedding_size": embedding_size,
            "maximum_frames": maximum_frames,
            "class_names": class_names,
            "subcenters": subcenters,
            "state_dict": best_state,
            "centers": best_centers,
        },
        model_path,
    )
    selected_run = next(run for run in runs if run["seed"] == best_seed)
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-scaf-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "features_sha256": files["features_sha256"],
            "offsets_sha256": files["offsets_sha256"],
        },
        "data": {
            "maximum_frames": maximum_frames,
            "synthetic_eligible_records": len(synthetic_indexes),
            "synthetic_training_records": len(training_positions),
            "synthetic_validation_records": len(validation_positions),
            "classes": len(class_names),
            "class_names": class_names,
            "human_records": len(human_indexes),
            "human_evaluation": "speaker_group_held_out_enrollment_and_product_scan",
        },
        "architecture": {
            "input_hidden_size": hidden_size,
            "reduction_size": 128,
            "temporal_convolution_kernel": 3,
            "attention": "learned_scaled_dot_product_query",
            "embedding_size": embedding_size,
            "embedding_normalization": "l2",
        },
        "training": {
            "objective": "subcenter_arcface",
            "subcenters_per_class": subcenters,
            "angular_margin": arcface_margin,
            "scale": arcface_scale,
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "classes_per_batch": classes_per_batch,
            "samples_per_class": samples_per_class,
            "learning_rate": learning_rate,
            "weight_decay": 1e-4,
            "seeds": seeds,
            "selection": "synthetic_validation_target_zero_false_recall_then_auc_then_multiclass_accuracy",
        },
        "human_evaluation_contract": {
            "window_offset_seconds": human_window_offset_seconds,
            "window_duration_seconds": human_window_duration_seconds,
            "hop_seconds": 0.02,
            "enrollment": "mean_l2_normalized_aligned_positive_embeddings_from_other_groups",
            "fold_threshold": "nextafter_max_training_negative_clip_score",
        },
        "runs": runs,
        "selected_seed": best_seed,
        "selected_run": selected_run,
        "artifacts": {
            "model": model_path.name,
            "model_sha256": sha256(model_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "development_only": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    report_path = partial_root / "training.report.v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[3101])
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batches-per-epoch", type=int, default=40)
    parser.add_argument("--classes-per-batch", type=int, default=32)
    parser.add_argument("--samples-per-class", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--maximum-frames", type=int, default=55)
    parser.add_argument("--embedding-size", type=int, default=64)
    parser.add_argument("--subcenters", type=int, default=3)
    parser.add_argument("--arcface-margin", type=float, default=0.2)
    parser.add_argument("--arcface-scale", type=float, default=30.0)
    parser.add_argument("--human-window-offset-seconds", type=float, default=-0.1)
    parser.add_argument("--human-window-duration-seconds", type=float, default=1.1)
    parser.add_argument("--prediction-batch-size", type=int, default=128)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        feature_manifest_path=arguments.feature_manifest,
        output_root=arguments.output_root,
        seeds=arguments.seeds,
        epochs=arguments.epochs,
        batches_per_epoch=arguments.batches_per_epoch,
        classes_per_batch=arguments.classes_per_batch,
        samples_per_class=arguments.samples_per_class,
        learning_rate=arguments.learning_rate,
        maximum_frames=arguments.maximum_frames,
        embedding_size=arguments.embedding_size,
        subcenters=arguments.subcenters,
        arcface_margin=arguments.arcface_margin,
        arcface_scale=arguments.arcface_scale,
        human_window_offset_seconds=arguments.human_window_offset_seconds,
        human_window_duration_seconds=arguments.human_window_duration_seconds,
        prediction_batch_size=arguments.prediction_batch_size,
        device=arguments.device,
    )
    print(
        json.dumps(
            {
                "selected_seed": report["selected_seed"],
                "synthetic_validation": report["selected_run"]["synthetic_validation"],
                "human_speaker_held_out": report["selected_run"]["human_speaker_held_out"],
                "model_sha256": report["artifacts"]["model_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
