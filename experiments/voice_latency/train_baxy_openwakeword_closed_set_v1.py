"""Train a closed-set BAXY wake classifier on frozen openWakeWord embeddings."""

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


SCHEMA = "baxy.openwakeword-runtime-embeddings.v1"
EXPECTED_OPENWAKEWORD_COMMIT = "368c03716d1e92591906a84949bc477f3a834455"
EMBEDDING_FRAMES = 28
EMBEDDING_DIMENSION = 96


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_openwakeword_trainer_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "train_baxy_hyperspotter_binary_v1.py",
    "_baxy_openwakeword_trainer_metrics_v1",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def group_key(record: dict[str, object]) -> str:
    domain = record.get("domain")
    if domain == "wasapi_raw_physical":
        value = record.get("record_id")
    elif domain == "synthetic_clean":
        value = f"{record.get('label')}:{record.get('source_index')}"
    else:
        raise ValueError("baxy_openwakeword_trainer_domain_invalid")
    if not isinstance(value, str):
        raise ValueError("baxy_openwakeword_trainer_group_invalid")
    return f"{domain}:{value}"


def grouped_indexes(
    records: list[dict[str, object]], indexes: list[int]
) -> list[list[int]]:
    groups: dict[str, list[int]] = {}
    contracts: dict[str, tuple[object, object]] = {}
    for index in indexes:
        record = records[index]
        key = group_key(record)
        contract = (record.get("label"), record.get("persona_id"))
        if key in contracts and contracts[key] != contract:
            raise ValueError("baxy_openwakeword_trainer_group_drift")
        contracts[key] = contract
        groups.setdefault(key, []).append(index)
    return [groups[key] for key in sorted(groups)]


def balanced_domain_batch(
    pools: dict[str, list[list[int]]],
    *,
    batch_size: int,
    rng: random.Random,
) -> tuple[list[int], list[float], list[str]]:
    names = (
        "synthetic_positive",
        "synthetic_negative",
        "physical_positive",
        "physical_negative",
    )
    if batch_size < 4 or batch_size % 4 or any(not pools.get(name) for name in names):
        raise ValueError("baxy_openwakeword_trainer_batch_invalid")
    pairs: list[tuple[int, float, str]] = []
    quarter = batch_size // 4
    for name in names:
        label = 1.0 if name.endswith("positive") else 0.0
        domain = name.split("_", 1)[0]
        for _ in range(quarter):
            group = rng.choice(pools[name])
            pairs.append((rng.choice(group), label, domain))
    rng.shuffle(pairs)
    return (
        [index for index, _, _ in pairs],
        [label for _, label, _ in pairs],
        [domain for _, _, domain in pairs],
    )


def reduce_group_scores(
    records: list[dict[str, object]],
    indexes: list[int],
    scores: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if len(indexes) != len(scores):
        raise ValueError("baxy_openwakeword_trainer_score_count_invalid")
    groups: dict[str, tuple[int, list[float]]] = {}
    for index, score in zip(indexes, scores):
        record = records[index]
        label = int(record.get("label") == "positive")
        key = group_key(record)
        if key in groups and groups[key][0] != label:
            raise ValueError("baxy_openwakeword_trainer_group_label_drift")
        groups.setdefault(key, (label, []))[1].append(float(score))
    ordered = sorted(groups)
    return (
        np.asarray([groups[key][0] for key in ordered], dtype=np.int64),
        np.asarray([max(groups[key][1]) for key in ordered], dtype=np.float64),
    )


def candidate_rank(
    physical: dict[str, object], synthetic: dict[str, object]
) -> tuple[float, float, float, float, float]:
    return (
        float(physical["zero_false_positive_recall"]),
        float(physical["auc"]),
        -float(physical["equal_error_rate"]),
        float(synthetic["zero_false_positive_recall"]),
        float(synthetic["auc"]),
    )


def build_model(model_type: str, *, dropout: float) -> object:
    import torch
    import torch.nn as nn

    if model_type == "dnn":
        return nn.Sequential(
            nn.Flatten(),
            nn.Linear(EMBEDDING_FRAMES * EMBEDDING_DIMENSION, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128, 1),
        )

    class RecurrentNet(nn.Module):
        def __init__(self, *, convolutional: bool) -> None:
            super().__init__()
            self.normalization = nn.LayerNorm(EMBEDDING_DIMENSION)
            self.convolution = (
                nn.Sequential(
                    nn.Conv1d(EMBEDDING_DIMENSION, 128, kernel_size=3, padding=1),
                    nn.GELU(),
                    nn.Dropout(dropout),
                )
                if convolutional
                else None
            )
            input_dimension = 128 if convolutional else EMBEDDING_DIMENSION
            recurrent = nn.GRU if model_type == "conv_gru" else nn.LSTM
            self.recurrent = recurrent(
                input_dimension,
                64,
                num_layers=2,
                bidirectional=True,
                batch_first=True,
                dropout=dropout,
            )
            self.output = nn.Sequential(
                nn.LayerNorm(128),
                nn.Linear(128, 64),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(64, 1),
            )

        def forward(self, values: object) -> object:
            values = self.normalization(values)
            if self.convolution is not None:
                values = self.convolution(values.transpose(1, 2)).transpose(1, 2)
            _, hidden = self.recurrent(values)
            if isinstance(hidden, tuple):
                hidden = hidden[0]
            summary = torch.cat((hidden[-2], hidden[-1]), dim=1)
            return self.output(summary)

    if model_type in {"lstm", "conv_gru"}:
        return RecurrentNet(convolutional=model_type == "conv_gru")
    raise ValueError("baxy_openwakeword_trainer_model_invalid")


def train(
    *,
    feature_manifest_path: Path,
    output_directory: Path,
    seed: int,
    validation_personas: int,
    model_type: str,
    epochs: int,
    batches_per_epoch: int,
    batch_size: int,
    validation_batch_size: int,
    learning_rate: float,
    weight_decay: float,
    dropout: float,
    feature_noise_std: float,
    time_mask_frames: int,
    ranking_weight: float,
    ranking_margin: float,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or batches_per_epoch < 1
        or batch_size < 4
        or batch_size % 4
        or validation_batch_size < 1
        or learning_rate <= 0.0
        or weight_decay < 0.0
        or not 0.0 <= dropout < 1.0
        or feature_noise_std < 0.0
        or time_mask_frames < 0
        or ranking_weight < 0.0
        or ranking_margin < 0.0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("baxy_openwakeword_trainer_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    manifest = json.loads(feature_manifest_path.read_text(encoding="utf-8-sig"))
    records_raw = manifest.get("records")
    files = manifest.get("files")
    sources = manifest.get("sources")
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("human_development_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or manifest.get("development_only") is not True
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(sources, dict)
        or sources.get("openwakeword_commit") != EXPECTED_OPENWAKEWORD_COMMIT
    ):
        raise ValueError("baxy_openwakeword_trainer_manifest_boundary_invalid")
    records: list[dict[str, object]] = []
    for record in records_raw:
        if (
            not isinstance(record, dict)
            or record.get("domain") not in {"synthetic_clean", "wasapi_raw_physical"}
            or record.get("label") not in {"positive", "adversarial_negative"}
            or not isinstance(record.get("persona_id"), str)
        ):
            raise ValueError("baxy_openwakeword_trainer_record_invalid")
        records.append(record)
    feature_path = feature_manifest_path.parent / str(files.get("embeddings"))
    if sha256(feature_path) != files.get("embeddings_sha256"):
        raise ValueError("baxy_openwakeword_trainer_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    if features.shape != (len(records), EMBEDDING_FRAMES, EMBEDDING_DIMENSION):
        raise ValueError("baxy_openwakeword_trainer_feature_shape_invalid")

    personas = {
        str(record["persona_id"])
        for record in records
        if record["domain"] == "synthetic_clean"
    }
    training_personas, validation_persona_set = _BASE.split_personas(
        personas, seed=seed, validation_personas=validation_personas
    )
    training = [
        index
        for index, record in enumerate(records)
        if record["persona_id"] in training_personas
    ]
    validation = [
        index
        for index, record in enumerate(records)
        if record["persona_id"] in validation_persona_set
    ]

    def select(domain: str, label: str, indexes: list[int]) -> list[list[int]]:
        return grouped_indexes(
            records,
            [
                index
                for index in indexes
                if records[index]["domain"] == domain
                and records[index]["label"] == label
            ],
        )

    pools = {
        "synthetic_positive": select("synthetic_clean", "positive", training),
        "synthetic_negative": select(
            "synthetic_clean", "adversarial_negative", training
        ),
        "physical_positive": select(
            "wasapi_raw_physical", "positive", training
        ),
        "physical_negative": select(
            "wasapi_raw_physical", "adversarial_negative", training
        ),
    }
    validation_indexes = {
        "synthetic": [
            index
            for index in validation
            if records[index]["domain"] == "synthetic_clean"
        ],
        "physical": [
            index
            for index in validation
            if records[index]["domain"] == "wasapi_raw_physical"
        ],
    }
    if any(not pool for pool in pools.values()) or any(
        not indexes for indexes in validation_indexes.values()
    ):
        raise ValueError("baxy_openwakeword_trainer_split_invalid")

    import torch
    import torch.nn.functional as functional

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("baxy_openwakeword_trainer_cuda_unavailable")
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.set_float32_matmul_precision("high")
    torch_device = torch.device(device)
    model = build_model(model_type, dropout=dropout).to(torch_device)
    optimizer = torch.optim.AdamW(
        model.parameters(), learning_rate, weight_decay=weight_decay
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    rng = random.Random(seed + 1)
    augmentation_rng = np.random.default_rng(seed + 2)

    def tensor_for(indexes: list[int], *, augment: bool) -> object:
        values = np.asarray(features[indexes], dtype=np.float32)
        if augment:
            if feature_noise_std:
                values += augmentation_rng.normal(
                    0.0, feature_noise_std, values.shape
                ).astype(np.float32)
            if time_mask_frames:
                for row in values:
                    width = int(
                        augmentation_rng.integers(0, time_mask_frames + 1)
                    )
                    if width:
                        start = int(
                            augmentation_rng.integers(
                                0, EMBEDDING_FRAMES - width + 1
                            )
                        )
                        row[start : start + width] = 0.0
        return torch.from_numpy(values).to(torch_device)

    def evaluate(indexes: list[int]) -> dict[str, object]:
        outputs: list[np.ndarray] = []
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(indexes), validation_batch_size):
                batch_indexes = indexes[start : start + validation_batch_size]
                with torch.autocast(
                    device_type=device,
                    dtype=torch.float16,
                    enabled=device == "cuda",
                ):
                    logits = model(tensor_for(batch_indexes, augment=False))
                outputs.append(logits[:, 0].float().cpu().numpy())
        labels, scores = reduce_group_scores(
            records, indexes, np.concatenate(outputs)
        )
        if set(labels.tolist()) != {0, 1}:
            raise ValueError("baxy_openwakeword_trainer_validation_labels_invalid")
        result = _BASE.binary_metrics(labels, scores)
        result["window_examples"] = len(indexes)
        result["source_examples"] = len(labels)
        return result

    def evaluate_all() -> dict[str, dict[str, object]]:
        return {
            domain: evaluate(indexes)
            for domain, indexes in validation_indexes.items()
        }

    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "baxy-openwakeword-closed-set-v1.pt"
    started = time.perf_counter()
    history: list[dict[str, object]] = []
    best_rank: tuple[float, float, float, float, float] | None = None
    for epoch in range(1, epochs + 1):
        model.train()
        losses: list[float] = []
        for _ in range(batches_per_epoch):
            indexes, labels, domains = balanced_domain_batch(
                pools, batch_size=batch_size, rng=rng
            )
            targets = torch.tensor(labels, dtype=torch.float32, device=torch_device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device,
                dtype=torch.float16,
                enabled=device == "cuda",
            ):
                logits = model(tensor_for(indexes, augment=True))[:, 0]
                loss = functional.binary_cross_entropy_with_logits(logits, targets)
                if ranking_weight:
                    ranking_losses = []
                    for domain in ("synthetic", "physical"):
                        mask = torch.tensor(
                            [value == domain for value in domains],
                            dtype=torch.bool,
                            device=torch_device,
                        )
                        positive = logits[mask & (targets == 1.0)]
                        negative = logits[mask & (targets == 0.0)]
                        ranking_losses.append(
                            functional.softplus(
                                negative[:, None] - positive[None, :] + ranking_margin
                            ).mean()
                        )
                    loss = loss + ranking_weight * torch.stack(ranking_losses).mean()
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        validation_metrics = evaluate_all()
        rank = candidate_rank(
            validation_metrics["physical"], validation_metrics["synthetic"]
        )
        selected = best_rank is None or rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.openwakeword-closed-set-checkpoint.v1",
                    "feature_manifest_sha256": sha256(feature_manifest_path),
                    "seed": seed,
                    "model_type": model_type,
                    "dropout": dropout,
                    "best_epoch": epoch,
                    "model_state_dict": {
                        key: value.detach().cpu()
                        for key, value in model.state_dict().items()
                    },
                },
                checkpoint_path,
            )
        entry = {
            "epoch": epoch,
            "mean_training_loss": float(np.mean(losses)),
            "validation": validation_metrics,
            "checkpoint_selected": selected,
        }
        history.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval().cpu()
    onnx_path = output_directory / "baxy-openwakeword-closed-set-v1.onnx"
    example = torch.zeros(1, EMBEDDING_FRAMES, EMBEDDING_DIMENSION)
    with torch.inference_mode():
        reference = model(example).numpy()
    torch.onnx.export(
        model,
        example,
        str(onnx_path),
        input_names=["embeddings"],
        output_names=["wake_logit"],
        dynamic_axes={"embeddings": {0: "batch"}, "wake_logit": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    actual = session.run(None, {"embeddings": example.numpy()})[0]
    parity_error = float(np.max(np.abs(reference - actual)))
    if parity_error > 1e-4:
        raise ValueError("baxy_openwakeword_trainer_onnx_parity_invalid")

    selected_entry = next(
        entry
        for entry in history
        if entry["epoch"] == checkpoint["best_epoch"]
    )
    report: dict[str, object] = {
        "schema": "baxy.openwakeword-closed-set-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "speaker_disjoint_closed_set_wake_development",
        "sources": {
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "openwakeword_commit": EXPECTED_OPENWAKEWORD_COMMIT,
        },
        "contract": {
            "seed": seed,
            "training_personas": sorted(training_personas),
            "validation_personas": sorted(validation_persona_set),
            "model_type": model_type,
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "batch_size": batch_size,
            "balanced_domain_and_class": True,
            "source_uniform_window_sampling": True,
            "source_score_reduction": "maximum_runtime_window_logit",
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "dropout": dropout,
            "feature_noise_std": feature_noise_std,
            "time_mask_frames": time_mask_frames,
            "ranking_weight": ranking_weight,
            "ranking_margin": ranking_margin,
            "selection_rank": [
                "physical_zero_false_recall",
                "physical_auc",
                "negative_physical_eer",
                "synthetic_zero_false_recall",
                "synthetic_auc",
            ],
        },
        "pool_source_counts": {key: len(value) for key, value in pools.items()},
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation": selected_entry["validation"],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": sha256(checkpoint_path),
            "onnx": onnx_path.name,
            "onnx_sha256": sha256(onnx_path),
            "onnx_parity_max_abs_error": parity_error,
        },
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "development_only": True,
        "effects_executed": 0,
    }
    (output_directory / "training.report.v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=9701)
    parser.add_argument("--validation-personas", type=int, default=8)
    parser.add_argument(
        "--model-type", choices=("dnn", "lstm", "conv_gru"), default="conv_gru"
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batches-per-epoch", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--validation-batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.15)
    parser.add_argument("--feature-noise-std", type=float, default=0.05)
    parser.add_argument("--time-mask-frames", type=int, default=2)
    parser.add_argument("--ranking-weight", type=float, default=0.25)
    parser.add_argument("--ranking-margin", type=float, default=1.0)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        feature_manifest_path=arguments.feature_manifest,
        output_directory=arguments.output_directory,
        seed=arguments.seed,
        validation_personas=arguments.validation_personas,
        model_type=arguments.model_type,
        epochs=arguments.epochs,
        batches_per_epoch=arguments.batches_per_epoch,
        batch_size=arguments.batch_size,
        validation_batch_size=arguments.validation_batch_size,
        learning_rate=arguments.learning_rate,
        weight_decay=arguments.weight_decay,
        dropout=arguments.dropout,
        feature_noise_std=arguments.feature_noise_std,
        time_mask_frames=arguments.time_mask_frames,
        ranking_weight=arguments.ranking_weight,
        ranking_margin=arguments.ranking_margin,
        device=arguments.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
