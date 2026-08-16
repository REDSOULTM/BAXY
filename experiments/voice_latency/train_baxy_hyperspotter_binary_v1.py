"""Fine-tune HyperSpotter for BAXY with speaker-disjoint synthetic data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.machinery
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import types

import numpy as np


ALIASES = ("baxy", "baxi", "basi", "bakse")
EXPECTED_UPSTREAM_COMMIT = "08d226c93563f997008ba510421a5ab7d6b65b25"


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_hyperspotter_binary_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LOGMEL = load_component(
    "extract_baxy_hyperspotter_logmel_v1.py",
    "_baxy_hyperspotter_binary_logmel_v1",
)
_METRICS = load_component(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1.py",
    "_baxy_hyperspotter_binary_metrics_v1",
)


def split_personas(
    persona_ids: set[str], *, seed: int, validation_personas: int
) -> tuple[set[str], set[str]]:
    if validation_personas < 1 or validation_personas >= len(persona_ids):
        raise ValueError("baxy_hyperspotter_binary_persona_schedule_invalid")
    ordered = sorted(persona_ids)
    random.Random(seed).shuffle(ordered)
    validation = set(ordered[:validation_personas])
    training = set(ordered[validation_personas:])
    if training & validation or training | validation != persona_ids:
        raise AssertionError("baxy_hyperspotter_binary_persona_split_invalid")
    return training, validation


def balanced_batch_indexes(
    *,
    positive_indexes: list[int],
    negative_indexes: list[int],
    batch_size: int,
    rng: random.Random,
) -> tuple[list[int], list[float]]:
    if batch_size < 2 or batch_size % 2 or not positive_indexes or not negative_indexes:
        raise ValueError("baxy_hyperspotter_binary_batch_schedule_invalid")
    half = batch_size // 2
    pairs = [
        *([(rng.choice(positive_indexes), 1.0) for _ in range(half)]),
        *( [(rng.choice(negative_indexes), 0.0) for _ in range(half)]),
    ]
    rng.shuffle(pairs)
    return [index for index, _ in pairs], [label for _, label in pairs]


def binary_metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, object]:
    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    auc, eer, eer_threshold = _METRICS.binary_auc_eer(
        targets=labels, scores=scores
    )
    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    zero_false_threshold = float(np.nextafter(np.max(negatives), math.inf))
    return {
        "auc": auc,
        "equal_error_rate": eer,
        "equal_error_threshold": eer_threshold,
        "positive_examples": len(positives),
        "negative_examples": len(negatives),
        "zero_false_threshold": zero_false_threshold,
        "positive_accepted_at_zero_false": int(
            np.count_nonzero(positives >= zero_false_threshold)
        ),
        "zero_false_positive_recall": float(
            np.mean(positives >= zero_false_threshold)
        ),
        "positive_score_mean": float(np.mean(positives)),
        "negative_score_mean": float(np.mean(negatives)),
    }


def train(
    *,
    feature_manifest_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    output_directory: Path,
    seed: int,
    validation_personas: int,
    epochs: int,
    batches_per_epoch: int,
    batch_size: int,
    validation_batch_size: int,
    learning_rate: float,
    weight_decay: float,
    feature_noise_std: float,
    time_mask_frames: int,
    frequency_mask_bins: int,
    unfreeze_audio_encoder: bool,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or batches_per_epoch < 1
        or batch_size < 2
        or batch_size % 2
        or validation_batch_size < 1
        or learning_rate <= 0.0
        or weight_decay < 0.0
        or feature_noise_std < 0.0
        or time_mask_frames < 0
        or frequency_mask_bins < 0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("baxy_hyperspotter_binary_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    official_checkpoint_path = official_checkpoint_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    manifest = _LOGMEL.read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    sources = manifest.get("sources")
    if (
        manifest.get("schema") != "baxy.baxy-hyperspotter-logmel.v1"
        or manifest.get("human_development_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(sources, dict)
        or sources.get("hyperspotter_upstream_commit") != EXPECTED_UPSTREAM_COMMIT
    ):
        raise ValueError("baxy_hyperspotter_binary_manifest_boundary_invalid")
    records: list[dict[str, object]] = []
    for raw in records_raw:
        if (
            not isinstance(raw, dict)
            or raw.get("label") not in {"positive", "adversarial_negative"}
            or not isinstance(raw.get("persona_id"), str)
        ):
            raise ValueError("baxy_hyperspotter_binary_record_invalid")
        records.append(raw)
    persona_ids = {str(record["persona_id"]) for record in records}
    training_personas, validation_persona_set = split_personas(
        persona_ids, seed=seed, validation_personas=validation_personas
    )
    training_indexes = [
        index
        for index, record in enumerate(records)
        if record["persona_id"] in training_personas
    ]
    validation_indexes = [
        index
        for index, record in enumerate(records)
        if record["persona_id"] in validation_persona_set
    ]
    positive_training = [
        index for index in training_indexes if records[index]["label"] == "positive"
    ]
    negative_training = [
        index
        for index in training_indexes
        if records[index]["label"] == "adversarial_negative"
    ]
    validation_labels = np.asarray(
        [records[index]["label"] == "positive" for index in validation_indexes],
        dtype=np.int64,
    )
    if (
        not positive_training
        or not negative_training
        or set(validation_labels.tolist()) != {0, 1}
    ):
        raise ValueError("baxy_hyperspotter_binary_split_labels_invalid")

    root = feature_manifest_path.parent
    feature_path = root / str(files["logmel"])
    offset_path = root / str(files["offsets"])
    if (
        _LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("baxy_hyperspotter_binary_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("baxy_hyperspotter_binary_feature_shape_invalid")

    import torch
    import torch.nn as nn

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("baxy_hyperspotter_binary_cuda_unavailable")
    for name, value in (
        ("float_", np.float64),
        ("complex_", np.complex128),
        ("string_", np.bytes_),
        ("unicode_", np.str_),
    ):
        if not hasattr(np, name):
            setattr(np, name, value)
    wandb_stub = types.ModuleType("wandb")
    wandb_stub.__spec__ = importlib.machinery.ModuleSpec("wandb", loader=None)
    wandb_stub.Settings = lambda **_kwargs: None
    whisper_stub = types.ModuleType("whisper")
    whisper_stub.__spec__ = importlib.machinery.ModuleSpec("whisper", loader=None)
    whisper_stub.load_model = lambda *_args, **_kwargs: None
    sys.modules["wandb"] = wandb_stub
    sys.modules["whisper"] = whisper_stub
    if str(hyperspotter_site_packages) not in sys.path:
        sys.path.append(str(hyperspotter_site_packages))
    if str(hyperspotter_root) not in sys.path:
        sys.path.insert(0, str(hyperspotter_root))
    pandas_was_loaded = "pandas" in sys.modules
    pandas_module = sys.modules.get("pandas")
    if not pandas_was_loaded:
        sys.modules["pandas"] = None
    try:
        from src.models import ConformerLightning
    finally:
        if not pandas_was_loaded:
            sys.modules.pop("pandas", None)
        elif pandas_module is not None:
            sys.modules["pandas"] = pandas_module

    ConformerLightning.set_decoders = lambda _self, _cfg: None
    previous_directory = Path.cwd()
    original_torch_load = torch.load

    def trusted_checkpoint_load(*args: object, **kwargs: object) -> object:
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    try:
        os.chdir(hyperspotter_root)
        torch.load = trusted_checkpoint_load
        lightning_model = ConformerLightning.load_from_checkpoint(
            str(official_checkpoint_path), map_location="cpu"
        )
    finally:
        torch.load = original_torch_load
        os.chdir(previous_directory)

    model = lightning_model.model
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.perceiver_classifier.parameters():
        parameter.requires_grad = True
    if unfreeze_audio_encoder:
        for parameter in model.audio_encoder.parameters():
            parameter.requires_grad = True
    trainable_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.set_float32_matmul_precision("high")
    torch_device = torch.device(device)
    model = model.to(torch_device)

    keyword_ids = lightning_model.tokenizer(list(ALIASES))["input_ids"]
    keyword_lengths = torch.tensor([len(value) for value in keyword_ids], dtype=torch.long)
    keyword_values = nn.utils.rnn.pad_sequence(
        [torch.tensor(value, dtype=torch.long, device=torch_device) for value in keyword_ids],
        padding_value=lightning_model.tokenizer.pad_token_id,
        batch_first=True,
    )
    with torch.inference_mode():
        alias_weights = model.get_text_weights(keyword_values, keyword_lengths).detach()

    optimizer = torch.optim.AdamW(
        trainable_parameters, lr=learning_rate, weight_decay=weight_decay
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    loss_function = torch.nn.BCEWithLogitsLoss()
    training_rng = random.Random(seed + 1)
    augmentation_rng = np.random.default_rng(seed + 2)

    def feature_batch(
        indexes: list[int], *, augment: bool
    ) -> tuple[object, object]:
        lengths = [int(offsets[index + 1] - offsets[index]) for index in indexes]
        maximum = max(lengths)
        values = np.zeros((len(indexes), maximum, 80), dtype=np.float32)
        for row, index in enumerate(indexes):
            length = lengths[row]
            values[row, :length] = features[
                int(offsets[index]) : int(offsets[index + 1])
            ]
            if augment:
                if feature_noise_std:
                    values[row, :length] += augmentation_rng.normal(
                        0.0, feature_noise_std, size=(length, 80)
                    ).astype(np.float32)
                if time_mask_frames and length > 1:
                    width = int(augmentation_rng.integers(0, min(time_mask_frames, length - 1) + 1))
                    if width:
                        start = int(augmentation_rng.integers(0, length - width + 1))
                        values[row, start : start + width] = 0.0
                if frequency_mask_bins:
                    width = int(augmentation_rng.integers(0, min(frequency_mask_bins, 79) + 1))
                    if width:
                        start = int(augmentation_rng.integers(0, 80 - width + 1))
                        values[row, :length, start : start + width] = 0.0
        return (
            torch.from_numpy(values).to(torch_device),
            torch.tensor(lengths, dtype=torch.long, device=torch_device),
        )

    def logits_for(indexes: list[int], *, augment: bool) -> object:
        audio, audio_lengths = feature_batch(indexes, augment=augment)
        return model.run_classifier(audio, alias_weights, audio_lengths)

    def evaluate_validation() -> dict[str, object]:
        model.eval()
        score_batches = []
        with torch.inference_mode():
            for start in range(0, len(validation_indexes), validation_batch_size):
                indexes = validation_indexes[start : start + validation_batch_size]
                with torch.autocast(
                    device_type=device, dtype=torch.float16, enabled=device == "cuda"
                ):
                    logits = logits_for(indexes, augment=False)
                score_batches.append(logits.max(dim=1).values.float().cpu().numpy())
        return binary_metrics(validation_labels, np.concatenate(score_batches))

    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "baxy-hyperspotter-binary-v1.pt"
    history: list[dict[str, object]] = []
    best_rank: tuple[float, float, float] | None = None
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        model.text_encoder.eval()
        model.embedding_2_ms.eval()
        if not unfreeze_audio_encoder:
            model.audio_encoder.eval()
        losses = []
        for _ in range(batches_per_epoch):
            indexes, batch_labels = balanced_batch_indexes(
                positive_indexes=positive_training,
                negative_indexes=negative_training,
                batch_size=batch_size,
                rng=training_rng,
            )
            optimizer.zero_grad(set_to_none=True)
            labels = torch.tensor(
                batch_labels, dtype=torch.float32, device=torch_device
            )[:, None].expand(-1, len(ALIASES))
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = logits_for(indexes, augment=True)
                loss = loss_function(logits, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        validation = evaluate_validation()
        rank = (
            float(validation["auc"]),
            float(validation["zero_false_positive_recall"]),
            -float(validation["equal_error_rate"]),
        )
        selected = best_rank is None or rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.baxy-hyperspotter-binary.v1",
                    "official_checkpoint_sha256": _LOGMEL.sha256(
                        official_checkpoint_path
                    ),
                    "feature_manifest_sha256": _LOGMEL.sha256(feature_manifest_path),
                    "upstream_commit": EXPECTED_UPSTREAM_COMMIT,
                    "seed": seed,
                    "aliases": list(ALIASES),
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
            "validation": validation,
            "checkpoint_selected": selected,
        }
        history.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    best_entry = next(
        entry for entry in history if entry["epoch"] == checkpoint["best_epoch"]
    )
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-binary-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic_baxy_vs_adversarial_speaker_disjoint",
        "sources": {
            "feature_manifest_sha256": _LOGMEL.sha256(feature_manifest_path),
            "official_checkpoint_sha256": _LOGMEL.sha256(official_checkpoint_path),
            "hyperspotter_upstream_commit": EXPECTED_UPSTREAM_COMMIT,
        },
        "contract": {
            "seed": seed,
            "aliases": list(ALIASES),
            "training_personas": len(training_personas),
            "validation_personas": len(validation_persona_set),
            "training_positive_examples": len(positive_training),
            "training_negative_examples": len(negative_training),
            "validation_examples": len(validation_indexes),
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "feature_noise_std": feature_noise_std,
            "time_mask_frames": time_mask_frames,
            "frequency_mask_bins": frequency_mask_bins,
            "audio_encoder_frozen": not unfreeze_audio_encoder,
            "text_encoder_frozen": True,
            "objective": "balanced_per_alias_binary_cross_entropy",
        },
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation": best_entry["validation"],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _LOGMEL.sha256(checkpoint_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
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
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=9701)
    parser.add_argument("--validation-personas", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batches-per-epoch", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--validation-batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--feature-noise-std", type=float, default=0.01)
    parser.add_argument("--time-mask-frames", type=int, default=8)
    parser.add_argument("--frequency-mask-bins", type=int, default=4)
    parser.add_argument("--unfreeze-audio-encoder", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        feature_manifest_path=arguments.feature_manifest,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        output_directory=arguments.output_directory,
        seed=arguments.seed,
        validation_personas=arguments.validation_personas,
        epochs=arguments.epochs,
        batches_per_epoch=arguments.batches_per_epoch,
        batch_size=arguments.batch_size,
        validation_batch_size=arguments.validation_batch_size,
        learning_rate=arguments.learning_rate,
        weight_decay=arguments.weight_decay,
        feature_noise_std=arguments.feature_noise_std,
        time_mask_frames=arguments.time_mask_frames,
        frequency_mask_bins=arguments.frequency_mask_bins,
        unfreeze_audio_encoder=arguments.unfreeze_audio_encoder,
        device=arguments.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
