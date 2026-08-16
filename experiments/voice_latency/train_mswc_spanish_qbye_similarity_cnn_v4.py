"""Train a frame-similarity CNN matcher on speaker-disjoint MSWC word pairs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_qbye_similarity_cnn_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASELINE = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py",
    "_baxy_qbye_similarity_cnn_baseline_v4",
)
_TRAINER = load_component(
    "train_mswc_spanish_qbye_angular_prototypical_v1.py",
    "_baxy_qbye_similarity_cnn_sequence_v4",
)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_similarity_cnn_json_invalid:{path}")
    return value


def split_metric_words(
    words: set[str], *, seed: int, validation_classes: int
) -> tuple[set[str], set[str]]:
    ordered = sorted(
        words,
        key=lambda word: (
            hashlib.sha256(f"{seed}\x1f{word}".encode("utf-8")).hexdigest(),
            word,
        ),
    )
    if validation_classes < 2 or len(ordered) <= validation_classes:
        raise ValueError("mswc_qbye_similarity_cnn_split_invalid")
    return set(ordered[:-validation_classes]), set(ordered[-validation_classes:])


def edit_distance(left: str, right: str) -> int:
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


def normalized_word_distance(left: str, right: str) -> float:
    return edit_distance(left, right) / max(len(left), len(right), 1)


def hard_negative_map(words: set[str], *, neighbors: int) -> dict[str, list[str]]:
    if neighbors < 1 or len(words) <= neighbors:
        raise ValueError("mswc_qbye_similarity_cnn_neighbors_invalid")
    ordered = sorted(words)
    return {
        word: sorted(
            (candidate for candidate in ordered if candidate != word),
            key=lambda candidate: (
                normalized_word_distance(word, candidate),
                candidate,
            ),
        )[:neighbors]
        for word in ordered
    }


def make_similarity_model(torch: object, hidden_size: int, projection_size: int) -> object:
    class SimilarityCnn(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.projection = torch.nn.Sequential(
                torch.nn.LayerNorm(hidden_size),
                torch.nn.Linear(hidden_size, projection_size),
                torch.nn.GELU(),
            )
            self.matcher = torch.nn.Sequential(
                torch.nn.Conv2d(2, 16, kernel_size=3, padding=1),
                torch.nn.PReLU(16),
                torch.nn.Conv2d(16, 16, kernel_size=3, padding=1),
                torch.nn.PReLU(16),
                torch.nn.MaxPool2d(2),
                torch.nn.Conv2d(16, 32, kernel_size=3, padding=1),
                torch.nn.PReLU(32),
                torch.nn.Conv2d(32, 32, kernel_size=3, padding=1),
                torch.nn.PReLU(32),
            )
            self.head = torch.nn.Sequential(
                torch.nn.Linear(64, 64),
                torch.nn.PReLU(64),
                torch.nn.Dropout(0.1),
                torch.nn.Linear(64, 1),
            )

        def forward(
            self,
            left: object,
            left_mask: object,
            right: object,
            right_mask: object,
        ) -> object:
            left_projected = torch.nn.functional.normalize(
                self.projection(left), dim=-1
            )
            right_projected = torch.nn.functional.normalize(
                self.projection(right), dim=-1
            )
            similarity = torch.einsum(
                "btd,bsd->bts", left_projected, right_projected
            )
            valid = left_mask[:, :, None] * right_mask[:, None, :]
            left_length = left_mask.sum(dim=1, keepdim=True).clamp_min(2.0) - 1.0
            right_length = right_mask.sum(dim=1, keepdim=True).clamp_min(2.0) - 1.0
            positions = torch.arange(
                left.shape[1], dtype=left.dtype, device=left.device
            )[None, :]
            left_position = positions / left_length
            right_position = positions / right_length
            diagonal = 1.0 - torch.abs(
                left_position[:, :, None] - right_position[:, None, :]
            )
            image = torch.stack(
                (
                    torch.where(valid > 0.0, similarity, -1.0),
                    torch.where(valid > 0.0, diagonal, 0.0),
                ),
                dim=1,
            )
            encoded = self.matcher(image)
            average = torch.nn.functional.adaptive_avg_pool2d(encoded, 1).flatten(1)
            maximum = torch.nn.functional.adaptive_max_pool2d(encoded, 1).flatten(1)
            return self.head(torch.cat((average, maximum), dim=1)).squeeze(1)

    return SimilarityCnn()


def sample_pairs(
    *,
    words: list[str],
    indexes_by_word: dict[str, list[int]],
    hard_negatives: dict[str, list[str]],
    count: int,
    hard_negative_probability: float,
    rng: random.Random,
) -> tuple[list[int], list[int], np.ndarray]:
    if count < 2 or not 0.0 <= hard_negative_probability <= 1.0:
        raise ValueError("mswc_qbye_similarity_cnn_pair_schedule_invalid")
    left_indexes = []
    right_indexes = []
    labels = np.zeros(count, dtype=np.float32)
    positive_count = count // 2
    for pair_index in range(count):
        left_word = rng.choice(words)
        if pair_index < positive_count:
            left_index, right_index = rng.sample(indexes_by_word[left_word], 2)
            labels[pair_index] = 1.0
        else:
            right_word = (
                rng.choice(hard_negatives[left_word])
                if rng.random() < hard_negative_probability
                else rng.choice(words)
            )
            while right_word == left_word:
                right_word = rng.choice(words)
            left_index = rng.choice(indexes_by_word[left_word])
            right_index = rng.choice(indexes_by_word[right_word])
        if rng.random() < 0.5:
            left_index, right_index = right_index, left_index
        left_indexes.append(left_index)
        right_indexes.append(right_index)
    order = list(range(count))
    rng.shuffle(order)
    return (
        [left_indexes[index] for index in order],
        [right_indexes[index] for index in order],
        labels[order],
    )


def pair_metrics(labels: np.ndarray, logits: np.ndarray) -> dict[str, float]:
    targets = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(logits, dtype=np.float64)
    if (
        targets.shape != scores.shape
        or set(targets.tolist()) != {0, 1}
        or not np.isfinite(scores).all()
    ):
        raise ValueError("mswc_qbye_similarity_cnn_pair_metrics_invalid")
    from sklearn.metrics import roc_auc_score, roc_curve

    false_positive_rate, true_positive_rate, _ = roc_curve(targets, scores)
    false_negative_rate = 1.0 - true_positive_rate
    equal_index = int(np.argmin(np.abs(false_positive_rate - false_negative_rate)))
    return {
        "pair_auc": float(roc_auc_score(targets, scores)),
        "equal_error_rate": float(
            (false_positive_rate[equal_index] + false_negative_rate[equal_index]) / 2.0
        ),
        "accuracy_at_zero_logit": float(np.mean((scores >= 0.0) == targets)),
    }


def train(
    *,
    feature_manifest_path: Path,
    output_directory: Path,
    layer: int,
    seed: int,
    validation_classes: int,
    projection_size: int,
    maximum_frames: int,
    epochs: int,
    batches_per_epoch: int,
    batch_size: int,
    validation_pairs: int,
    learning_rate: float,
    hard_negative_probability: float,
    hard_negative_neighbors: int,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or projection_size < 8
        or maximum_frames < 2
        or epochs < 1
        or batches_per_epoch < 1
        or batch_size < 2
        or validation_pairs < 2
        or learning_rate <= 0.0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_qbye_similarity_cnn_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_directory = output_directory.resolve()
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
        raise ValueError("mswc_qbye_similarity_cnn_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_qbye_similarity_cnn_record_invalid")
        records.append(record)
    metric_indexes = [
        index for index, record in enumerate(records) if record["partition"] == "metric_training"
    ]
    metric_words = {str(records[index]["class_name"]) for index in metric_indexes}
    training_words, validation_words = split_metric_words(
        metric_words, seed=seed, validation_classes=validation_classes
    )
    indexes_by_word = {
        word: [
            index
            for index in metric_indexes
            if str(records[index]["class_name"]) == word
        ]
        for word in metric_words
    }
    if any(len(indexes) < 2 for indexes in indexes_by_word.values()):
        raise ValueError("mswc_qbye_similarity_cnn_examples_missing")
    training_hard = hard_negative_map(
        training_words, neighbors=hard_negative_neighbors
    )
    validation_hard = hard_negative_map(
        validation_words,
        neighbors=min(hard_negative_neighbors, len(validation_words) - 1),
    )
    root = feature_manifest_path.parent
    offsets_path = root / str(files["offsets"])
    features_by_layer = files.get("features_by_layer")
    if (
        not isinstance(features_by_layer, dict)
        or _BASELINE.sha256(offsets_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_qbye_similarity_cnn_files_invalid")
    descriptor = features_by_layer.get(str(layer))
    if not isinstance(descriptor, dict):
        raise ValueError("mswc_qbye_similarity_cnn_layer_missing")
    feature_path = root / str(descriptor["path"])
    if _BASELINE.sha256(feature_path) != descriptor.get("sha256"):
        raise ValueError("mswc_qbye_similarity_cnn_feature_hash_mismatch")
    offsets = np.load(offsets_path)
    features = np.load(feature_path, mmap_mode="r")
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("mswc_qbye_similarity_cnn_feature_shape_invalid")
    hidden_size = int(contract["hidden_size"])

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_similarity_cnn_cuda_unavailable")
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.set_float32_matmul_precision("high")
    torch_device = torch.device(device)
    model = make_similarity_model(torch, hidden_size, projection_size).to(torch_device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    loss_function = torch.nn.BCEWithLogitsLoss()

    def fixed_batch(indexes: list[int]) -> tuple[np.ndarray, np.ndarray]:
        fixed = []
        masks = []
        for index in indexes:
            sequence, mask = _TRAINER.fixed_sequence(
                features[int(offsets[index]) : int(offsets[index + 1])],
                maximum_frames,
            )
            fixed.append(sequence)
            masks.append(mask)
        return np.stack(fixed), np.stack(masks)

    validation_rng = random.Random(seed + 1)
    validation_left, validation_right, validation_labels = sample_pairs(
        words=sorted(validation_words),
        indexes_by_word=indexes_by_word,
        hard_negatives=validation_hard,
        count=validation_pairs,
        hard_negative_probability=hard_negative_probability,
        rng=validation_rng,
    )

    def predict_pairs(left_indexes: list[int], right_indexes: list[int]) -> np.ndarray:
        model.eval()
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(left_indexes), batch_size * 2):
                left_values, left_masks = fixed_batch(
                    left_indexes[start : start + batch_size * 2]
                )
                right_values, right_masks = fixed_batch(
                    right_indexes[start : start + batch_size * 2]
                )
                with torch.autocast(
                    device_type=device,
                    dtype=torch.float16,
                    enabled=device == "cuda",
                ):
                    logits = model(
                        torch.from_numpy(left_values).to(torch_device),
                        torch.from_numpy(left_masks).to(torch_device),
                        torch.from_numpy(right_values).to(torch_device),
                        torch.from_numpy(right_masks).to(torch_device),
                    )
                outputs.append(logits.float().cpu().numpy())
        return np.concatenate(outputs)

    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mswc-spanish-qbye-similarity-cnn-v4.pt"
    history = []
    best_rank = None
    started = time.perf_counter()
    training_rng = random.Random(seed + 2)
    training_word_list = sorted(training_words)
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for _ in range(batches_per_epoch):
            left_indexes, right_indexes, labels = sample_pairs(
                words=training_word_list,
                indexes_by_word=indexes_by_word,
                hard_negatives=training_hard,
                count=batch_size,
                hard_negative_probability=hard_negative_probability,
                rng=training_rng,
            )
            left_values, left_masks = fixed_batch(left_indexes)
            right_values, right_masks = fixed_batch(right_indexes)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device,
                dtype=torch.float16,
                enabled=device == "cuda",
            ):
                logits = model(
                    torch.from_numpy(left_values).to(torch_device),
                    torch.from_numpy(left_masks).to(torch_device),
                    torch.from_numpy(right_values).to(torch_device),
                    torch.from_numpy(right_masks).to(torch_device),
                )
                loss = loss_function(
                    logits, torch.from_numpy(labels).to(torch_device)
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        validation_logits = predict_pairs(validation_left, validation_right)
        metrics = pair_metrics(validation_labels, validation_logits)
        rank = (
            metrics["pair_auc"],
            -metrics["equal_error_rate"],
            metrics["accuracy_at_zero_logit"],
        )
        selected = best_rank is None or rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.mswc-spanish-qbye-similarity-cnn.v4",
                    "feature_manifest_sha256": _BASELINE.sha256(feature_manifest_path),
                    "layer": layer,
                    "hidden_size": hidden_size,
                    "projection_size": projection_size,
                    "maximum_frames": maximum_frames,
                    "seed": seed,
                    "best_epoch": epoch,
                    "state_dict": {
                        key: value.detach().cpu() for key, value in model.state_dict().items()
                    },
                },
                checkpoint_path,
            )
        entry = {
            "epoch": epoch,
            "mean_training_loss": float(np.mean(losses)),
            "validation_pairs": metrics,
            "checkpoint_selected": selected,
        }
        history.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    checkpoint_hash = _BASELINE.sha256(checkpoint_path)
    best_entry = next(
        entry for entry in history if entry["epoch"] == checkpoint["best_epoch"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-similarity-cnn-training.v4",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "metric_training_internal_word_holdout_frame_similarity_cnn",
        "sources": {
            "feature_manifest_sha256": _BASELINE.sha256(feature_manifest_path),
            "feature_layer_sha256": descriptor["sha256"],
        },
        "contract": {
            "layer": layer,
            "seed": seed,
            "training_word_classes": len(training_words),
            "validation_word_classes": len(validation_words),
            "projection_size": projection_size,
            "maximum_frames": maximum_frames,
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "batch_size": batch_size,
            "validation_pairs": validation_pairs,
            "learning_rate": learning_rate,
            "hard_negative_probability": hard_negative_probability,
            "hard_negative_neighbors": hard_negative_neighbors,
            "matching_image": "projected_frame_cosine_similarity_plus_relative_diagonal_prior",
            "objective": "balanced_binary_same_word_cross_speaker_classification",
        },
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation_pairs": best_entry["validation_pairs"],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": checkpoint_hash,
        },
        "runtime_seconds": time.perf_counter() - started,
        "open_keyword_tuning_examples_scored": False,
        "research_v3_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    (output_directory / "training.report.v4.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--layer", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7501)
    parser.add_argument("--validation-classes", type=int, default=100)
    parser.add_argument("--projection-size", type=int, default=64)
    parser.add_argument("--maximum-frames", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batches-per-epoch", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--validation-pairs", type=int, default=8192)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--hard-negative-probability", type=float, default=0.75)
    parser.add_argument("--hard-negative-neighbors", type=int, default=16)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = train(
        feature_manifest_path=args.feature_manifest,
        output_directory=args.output_directory,
        layer=args.layer,
        seed=args.seed,
        validation_classes=args.validation_classes,
        projection_size=args.projection_size,
        maximum_frames=args.maximum_frames,
        epochs=args.epochs,
        batches_per_epoch=args.batches_per_epoch,
        batch_size=args.batch_size,
        validation_pairs=args.validation_pairs,
        learning_rate=args.learning_rate,
        hard_negative_probability=args.hard_negative_probability,
        hard_negative_neighbors=args.hard_negative_neighbors,
        device=args.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
