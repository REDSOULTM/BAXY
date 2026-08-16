"""Train the SCAF wake embedding on real-word MSWC hidden features."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import random
import time

import numpy as np


_SCAF_PATH = Path(__file__).with_name(
    "train_wav2vec2_hidden_wake_scaf_embedding_v1.py"
)
_SCAF_SPEC = importlib.util.spec_from_file_location(
    "_baxy_wake_scaf_components_v1", _SCAF_PATH
)
if _SCAF_SPEC is None or _SCAF_SPEC.loader is None:
    raise RuntimeError("mswc_scaf_component_import_invalid")
_SCAF = importlib.util.module_from_spec(_SCAF_SPEC)
_SCAF_SPEC.loader.exec_module(_SCAF)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_scaf_json_invalid:{path}")
    return value


def split_positions(
    records: list[dict[str, object]], class_names: list[str]
) -> tuple[list[int], list[int], np.ndarray]:
    class_to_id = {name: index for index, name in enumerate(class_names)}
    if len(class_to_id) != len(class_names):
        raise ValueError("mswc_scaf_duplicate_classes")
    labels = []
    training = []
    development = []
    for position, record in enumerate(records):
        class_name = str(record["class_name"])
        if class_name not in class_to_id:
            raise ValueError("mswc_scaf_unknown_class")
        labels.append(class_to_id[class_name])
        split = record["split"]
        if split == "train":
            training.append(position)
        elif split == "development":
            development.append(position)
        else:
            raise ValueError("mswc_scaf_split_invalid")
    if set(training).intersection(development) or len(training) + len(development) != len(records):
        raise ValueError("mswc_scaf_split_overlap")
    return training, development, np.asarray(labels, dtype=np.int64)


def train(
    *,
    mswc_feature_manifest_path: Path,
    human_feature_manifest_path: Path,
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
        raise ValueError("mswc_scaf_schedule_invalid")
    mswc_feature_manifest_path = mswc_feature_manifest_path.resolve(strict=True)
    human_feature_manifest_path = human_feature_manifest_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise ValueError("mswc_scaf_partial_output_exists")
    mswc = read_object(mswc_feature_manifest_path)
    human = read_object(human_feature_manifest_path)
    if (
        mswc.get("schema") != "baxy.mswc-wav2vec2-hidden-features.v1"
        or human.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or mswc.get("test_audio_accessed") is not False
        or mswc.get("blind_human_audio_accessed") is not False
        or human.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("mswc_scaf_boundary_invalid")
    mswc_files = mswc.get("files")
    mswc_contract = mswc.get("contract")
    mswc_records_raw = mswc.get("records")
    human_files = human.get("files")
    human_contract = human.get("contract")
    human_records_raw = human.get("records")
    if not all(
        isinstance(value, dict)
        for value in (mswc_files, mswc_contract, human_files, human_contract)
    ) or not isinstance(mswc_records_raw, list) or not isinstance(human_records_raw, list):
        raise ValueError("mswc_scaf_manifest_invalid")
    mswc_records = []
    human_records = []
    for source, target in (
        (mswc_records_raw, mswc_records),
        (human_records_raw, human_records),
    ):
        for record in source:
            if not isinstance(record, dict):
                raise ValueError("mswc_scaf_record_invalid")
            target.append(record)
    hidden_size = int(mswc_contract["hidden_size"])
    if (
        int(mswc_contract["layer"]) != int(human_contract["layer"])
        or hidden_size != int(human_contract["hidden_size"])
    ):
        raise ValueError("mswc_scaf_hidden_contract_mismatch")

    def load_arrays(
        manifest_path: Path, files: dict[str, object], expected_records: int
    ) -> tuple[np.ndarray, np.ndarray]:
        root = manifest_path.parent
        feature_path = root / str(files["features"])
        offset_path = root / str(files["offsets"])
        if (
            _SCAF.sha256(feature_path) != files.get("features_sha256")
            or _SCAF.sha256(offset_path) != files.get("offsets_sha256")
        ):
            raise ValueError("mswc_scaf_feature_hash_mismatch")
        features = np.load(feature_path, mmap_mode="r")
        offsets = np.load(offset_path)
        if (
            features.ndim != 2
            or features.shape[1] != hidden_size
            or len(offsets) != expected_records + 1
            or int(offsets[-1]) != len(features)
        ):
            raise ValueError("mswc_scaf_feature_shape_invalid")
        return features, offsets

    mswc_features, mswc_offsets = load_arrays(
        mswc_feature_manifest_path, mswc_files, len(mswc_records)
    )
    human_features, human_offsets = load_arrays(
        human_feature_manifest_path, human_files, len(human_records)
    )
    class_names = sorted({str(record["class_name"]) for record in mswc_records})
    training_positions, development_positions, class_labels = split_positions(
        mswc_records, class_names
    )
    if len(class_names) < 40 or classes_per_batch > len(class_names):
        raise ValueError("mswc_scaf_class_count_invalid")
    by_class = {
        class_id: [
            position
            for position in training_positions
            if int(class_labels[position]) == class_id
        ]
        for class_id in range(len(class_names))
    }
    if any(not positions for positions in by_class.values()):
        raise ValueError("mswc_scaf_training_class_missing")

    fixed_features = np.zeros(
        (len(mswc_records), maximum_frames, hidden_size), dtype=np.float16
    )
    fixed_masks = np.zeros((len(mswc_records), maximum_frames), dtype=np.bool_)
    for position in range(len(mswc_records)):
        sequence, mask = _SCAF.fixed_sequence(
            mswc_features[
                int(mswc_offsets[position]) : int(mswc_offsets[position + 1])
            ],
            maximum_frames,
        )
        fixed_features[position] = sequence.astype(np.float16)
        fixed_masks[position] = mask

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_scaf_cuda_unavailable")
    torch_device = torch.device(device)

    def metric_batch(positions: list[int]) -> tuple[object, object, object]:
        values = torch.from_numpy(fixed_features[positions].astype(np.float32)).to(torch_device)
        masks = torch.from_numpy(fixed_masks[positions]).to(torch_device)
        labels = torch.from_numpy(class_labels[positions]).to(torch_device)
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
                    sequence, mask = _SCAF.fixed_sequence(values, maximum_frames)
                    fixed.append(sequence)
                    masks.append(mask)
                x = torch.from_numpy(np.stack(fixed)).to(torch_device)
                mask_tensor = torch.from_numpy(np.stack(masks)).to(torch_device)
                outputs.extend(model(x, mask_tensor).float().cpu().numpy())
        return outputs

    def metric_validation(model: object, centers: object) -> dict[str, object]:
        predictions = []
        targets = []
        losses = []
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(development_positions), prediction_batch_size):
                positions = development_positions[start : start + prediction_batch_size]
                x, mask, labels = metric_batch(positions)
                embeddings = model(x, mask)
                cosines = _SCAF.class_cosines(torch, embeddings, centers)
                predictions.extend(torch.argmax(cosines, dim=1).cpu().numpy().tolist())
                targets.extend(labels.cpu().numpy().tolist())
                losses.append(float(torch.nn.functional.cross_entropy(cosines * arcface_scale, labels).cpu()))
        prediction_array = np.asarray(predictions)
        target_array = np.asarray(targets)
        per_class = []
        for class_id, class_name in enumerate(class_names):
            mask = target_array == class_id
            per_class.append(
                {
                    "class_name": class_name,
                    "records": int(np.count_nonzero(mask)),
                    "accuracy": float(np.mean(prediction_array[mask] == class_id)),
                }
            )
        return {
            "accuracy": float(np.mean(prediction_array == target_array)),
            "macro_class_accuracy": float(np.mean([item["accuracy"] for item in per_class])),
            "mean_cross_entropy": float(np.mean(losses)),
            "records": int(len(target_array)),
            "per_class": per_class,
        }

    human_indexes = [
        index
        for index, record in enumerate(human_records)
        if str(record["corpus"]).startswith("human_")
    ]
    if len(human_indexes) != 30:
        raise ValueError("mswc_scaf_human_count_invalid")

    def human_evaluation(model: object) -> tuple[dict[str, object], list[dict[str, object]]]:
        aligned_arrays = []
        scans_by_record: list[list[np.ndarray]] = []
        labels = []
        groups = []
        window_frames = max(2, round(human_window_duration_seconds / 0.02))
        for index in human_indexes:
            record = human_records[index]
            hidden = np.asarray(
                human_features[
                    int(human_offsets[index]) : int(human_offsets[index + 1])
                ],
                dtype=np.float32,
            )
            positive = record["label"] == "positive"
            labels.append(1 if positive else 0)
            groups.append(str(record["group"]))
            if positive:
                onset = float(record["target_onset_seconds"])
                centers = np.arange(len(hidden), dtype=np.float64) * 0.02 + 0.0125
                start_seconds = max(0.0, onset + human_window_offset_seconds)
                start_frame = int(np.argmin(np.abs(centers - start_seconds)))
                aligned_arrays.append(hidden[start_frame : min(len(hidden), start_frame + window_frames)])
            else:
                aligned_arrays.append(hidden[:2])
            starts = list(range(0, max(1, len(hidden) - window_frames + 1)))
            final_start = max(0, len(hidden) - window_frames)
            if starts[-1] != final_start:
                starts.append(final_start)
            scans_by_record.append(
                [hidden[start : min(len(hidden), start + window_frames)] for start in starts]
            )
        positive_positions = [index for index, label in enumerate(labels) if label == 1]
        positive_embeddings = embed_arrays(
            model, [aligned_arrays[index] for index in positive_positions]
        )
        aligned_embeddings = np.zeros((len(human_indexes), embedding_size), dtype=np.float32)
        for index, embedding in zip(positive_positions, positive_embeddings, strict=True):
            aligned_embeddings[index] = embedding
        flat_arrays = [array for arrays in scans_by_record for array in arrays]
        flat_embeddings = embed_arrays(model, flat_arrays)
        scan_embeddings = []
        cursor = 0
        for arrays in scans_by_record:
            scan_embeddings.append(np.stack(flat_embeddings[cursor : cursor + len(arrays)]))
            cursor += len(arrays)
        target_array = np.asarray(labels, dtype=np.int64)
        margins, folds = _SCAF.human_group_margins(
            aligned_positive_embeddings=aligned_embeddings,
            scan_embeddings=scan_embeddings,
            labels=target_array,
            groups=groups,
        )
        metrics = _SCAF.margin_metrics(margins, target_array)
        return (
            {**metrics, "folds": folds},
            [
                {
                    "corpus": human_records[index]["corpus"],
                    "relative_path": human_records[index]["relative_path"],
                    "group": human_records[index]["group"],
                    "label": human_records[index]["label"],
                    "source_label": human_records[index].get("source_label"),
                    "speaker_held_out_margin": float(margin),
                    "accepted": bool(margin >= 0.0),
                }
                for index, margin in zip(human_indexes, margins, strict=True)
            ],
        )

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
        model = _SCAF.make_model(torch, hidden_size, embedding_size).to(torch_device)
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
                x, mask, labels = metric_batch(positions)
                optimizer.zero_grad(set_to_none=True)
                embeddings = model(x, mask)
                logits = _SCAF.subcenter_arcface_logits(
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
                validation = metric_validation(model, centers)
                history.append(
                    {
                        "epoch": epoch + 1,
                        "mean_training_loss": epoch_loss / batches_per_epoch,
                        "metric_development": validation,
                    }
                )
        validation = metric_validation(model, centers)
        human_metrics, human_breakdown = human_evaluation(model)
        run = {
            "seed": seed,
            "history": history,
            "metric_development": validation,
            "human_speaker_held_out": human_metrics,
            "human_records": human_breakdown,
        }
        runs.append(run)
        rank = (
            float(validation["macro_class_accuracy"]),
            float(validation["accuracy"]),
            -float(validation["mean_cross_entropy"]),
        )
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_seed = seed
            best_state = {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            }
            best_centers = centers.detach().cpu()
    assert best_state is not None and best_centers is not None and best_seed is not None
    model_path = partial_root / "mswc-wake-scaf-embedding-v1.pt"
    torch.save(
        {
            "schema": "baxy.mswc-wake-scaf-embedding.v1",
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
        "schema": "baxy.mswc-wake-scaf-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "mswc_feature_manifest_sha256": _SCAF.sha256(mswc_feature_manifest_path),
            "mswc_features_sha256": mswc_files["features_sha256"],
            "mswc_offsets_sha256": mswc_files["offsets_sha256"],
            "human_feature_manifest_sha256": _SCAF.sha256(human_feature_manifest_path),
            "human_features_sha256": human_files["features_sha256"],
            "human_offsets_sha256": human_files["offsets_sha256"],
        },
        "data": {
            "metric_corpus": "MSWC_microset_CC-BY-4.0_real_human_words",
            "metric_layer": int(mswc_contract["layer"]),
            "training_records": len(training_positions),
            "development_records": len(development_positions),
            "classes": len(class_names),
            "class_names": class_names,
            "test_audio_accessed": False,
            "speaker_reidentification_attempted": False,
            "human_baxy_records": len(human_indexes),
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
            "selection": "MSWC_official_development_macro_accuracy_then_accuracy_then_cross_entropy",
        },
        "human_evaluation_contract": {
            "window_offset_seconds": human_window_offset_seconds,
            "window_duration_seconds": human_window_duration_seconds,
            "hop_seconds": 0.02,
            "enrollment": "other_group_human_baxy_positive_mean_embedding",
            "cross_validation": "leave_one_complete_speaker_or_source_group_out",
            "fold_threshold": "nextafter_max_training_negative_clip_score",
        },
        "runs": runs,
        "selected_seed": best_seed,
        "selected_run": selected_run,
        "artifacts": {
            "model": model_path.name,
            "model_sha256": _SCAF.sha256(model_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "development_only": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "test_audio_accessed": False,
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
    parser.add_argument("--mswc-feature-manifest", type=Path, required=True)
    parser.add_argument("--human-feature-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[3501])
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
        mswc_feature_manifest_path=arguments.mswc_feature_manifest,
        human_feature_manifest_path=arguments.human_feature_manifest,
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
                "metric_development": report["selected_run"]["metric_development"],
                "human_speaker_held_out": report["selected_run"]["human_speaker_held_out"],
                "model_sha256": report["artifacts"]["model_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
