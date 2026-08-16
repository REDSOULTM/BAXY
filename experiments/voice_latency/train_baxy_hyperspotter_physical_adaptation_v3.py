"""Adapt HyperSpotter to attested room audio with speaker-disjoint hard negatives.

The campaign mixes the original synthetic speaker-disjoint corpus with RAW
WASAPI room captures.  Physical records from the eight frozen validation
personas are never sampled for training.  The blind human partition is never
opened, and checkpoint selection is driven by zero-false physical validation
recall before aggregate AUC.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import time
import types

import numpy as np


EXPECTED_UPSTREAM_COMMIT = "08d226c93563f997008ba510421a5ab7d6b65b25"
SYNTHETIC_SCHEMA = "baxy.baxy-hyperspotter-logmel.v1"
PHYSICAL_SCHEMA = "baxy.baxy-hyperspotter-physical-runtime-logmel.v2"
AUXILIARY_SCHEMA = "baxy.controlled-raw-runtime-logmel.v1"


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_physical_adaptation_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "train_baxy_hyperspotter_binary_v1.py",
    "_baxy_hyperspotter_physical_adaptation_base_v3",
)
ALIASES = _BASE.ALIASES


def mixed_domain_batch_indexes(
    *,
    synthetic_positive: list[int],
    synthetic_negative: list[int],
    physical_positive: list[int],
    physical_negative: list[int],
    batch_size: int,
    rng: random.Random,
) -> tuple[list[tuple[str, int]], list[float]]:
    if (
        batch_size < 4
        or batch_size % 4
        or not synthetic_positive
        or not synthetic_negative
        or not physical_positive
        or not physical_negative
    ):
        raise ValueError("baxy_physical_adaptation_batch_schedule_invalid")
    quarter = batch_size // 4
    pairs: list[tuple[tuple[str, int], float]] = [
        *[(('synthetic', rng.choice(synthetic_positive)), 1.0) for _ in range(quarter)],
        *[(('synthetic', rng.choice(synthetic_negative)), 0.0) for _ in range(quarter)],
        *[(('physical', rng.choice(physical_positive)), 1.0) for _ in range(quarter)],
        *[(('physical', rng.choice(physical_negative)), 0.0) for _ in range(quarter)],
    ]
    rng.shuffle(pairs)
    return [selection for selection, _ in pairs], [label for _, label in pairs]


def partition_indexes(
    records: list[dict[str, object]],
    *,
    training_personas: set[str],
    validation_personas: set[str],
) -> tuple[list[int], list[int]]:
    training: list[int] = []
    validation: list[int] = []
    for index, record in enumerate(records):
        persona = record.get("persona_id")
        if not isinstance(persona, str):
            raise ValueError("baxy_physical_adaptation_persona_invalid")
        if persona in training_personas:
            training.append(index)
        elif persona in validation_personas:
            validation.append(index)
        else:
            raise ValueError("baxy_physical_adaptation_persona_outside_split")
    if not training or not validation:
        raise ValueError("baxy_physical_adaptation_partition_empty")
    return training, validation


def candidate_rank(
    physical: dict[str, object], synthetic: dict[str, object]
) -> tuple[float, float, float, float, float]:
    """Safety-first ranking frozen before training begins."""
    return (
        float(physical["zero_false_positive_recall"]),
        float(physical["auc"]),
        -float(physical["equal_error_rate"]),
        float(synthetic["auc"]),
        float(synthetic["zero_false_positive_recall"]),
    )


def replace_physical_with_auxiliary(
    selections: list[tuple[str, int]],
    labels: list[float],
    *,
    auxiliary_positive: list[int],
    auxiliary_negative: list[int],
    probability: float,
    rng: random.Random,
) -> list[tuple[str, int]]:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("baxy_physical_adaptation_auxiliary_probability_invalid")
    if probability and (not auxiliary_positive or not auxiliary_negative):
        raise ValueError("baxy_physical_adaptation_auxiliary_labels_invalid")
    result = list(selections)
    for index, ((domain, _), label) in enumerate(zip(selections, labels)):
        if domain != "physical" or rng.random() >= probability:
            continue
        pool = auxiliary_positive if label == 1.0 else auxiliary_negative
        result[index] = ("auxiliary", rng.choice(pool))
    return result


def _load_store(
    manifest_path: Path,
    *,
    expected_schema: str,
    allow_human_development: bool = False,
) -> dict[str, object]:
    manifest_path = manifest_path.resolve(strict=True)
    manifest = _BASE._LOGMEL.read_object(manifest_path)
    records = manifest.get("records")
    files = manifest.get("files")
    sources = manifest.get("sources")
    if (
        manifest.get("schema") != expected_schema
        or manifest.get("human_development_audio_accessed")
        not in ({False, True} if allow_human_development else {False})
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records, list)
        or not isinstance(files, dict)
        or not isinstance(sources, dict)
    ):
        raise ValueError("baxy_physical_adaptation_manifest_boundary_invalid")
    if (
        expected_schema == SYNTHETIC_SCHEMA
        and sources.get("hyperspotter_upstream_commit") != EXPECTED_UPSTREAM_COMMIT
    ):
        raise ValueError("baxy_physical_adaptation_upstream_commit_invalid")
    if expected_schema == PHYSICAL_SCHEMA and manifest.get("development_only") is not True:
        raise ValueError("baxy_physical_adaptation_physical_role_invalid")
    normalized: list[dict[str, object]] = []
    for record in records:
        if (
            not isinstance(record, dict)
            or record.get("label") not in {"positive", "adversarial_negative"}
            or not isinstance(record.get("persona_id"), str)
        ):
            raise ValueError("baxy_physical_adaptation_record_invalid")
        normalized.append(record)
    root = manifest_path.parent
    feature_path = root / str(files.get("logmel"))
    offset_path = root / str(files.get("offsets"))
    if (
        _BASE._LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _BASE._LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("baxy_physical_adaptation_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(normalized) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("baxy_physical_adaptation_feature_shape_invalid")
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "records": normalized,
        "features": features,
        "offsets": offsets,
    }


def train(
    *,
    synthetic_feature_manifest_path: Path,
    physical_feature_manifest_path: Path,
    auxiliary_feature_manifest_path: Path | None,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    initializer_checkpoint_path: Path,
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
    freeze_audio_encoder: bool,
    auxiliary_replacement_probability: float,
    device: str,
) -> dict[str, object]:
    if (
        epochs < 1
        or batches_per_epoch < 1
        or batch_size < 4
        or batch_size % 4
        or validation_batch_size < 1
        or learning_rate <= 0.0
        or weight_decay < 0.0
        or feature_noise_std < 0.0
        or time_mask_frames < 0
        or frequency_mask_bins < 0
        or not 0.0 <= auxiliary_replacement_probability <= 1.0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("baxy_physical_adaptation_schedule_invalid")
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    official_checkpoint_path = official_checkpoint_path.resolve(strict=True)
    initializer_checkpoint_path = initializer_checkpoint_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError("baxy_physical_adaptation_output_exists")

    stores = {
        "synthetic": _load_store(
            synthetic_feature_manifest_path, expected_schema=SYNTHETIC_SCHEMA
        ),
        "physical": _load_store(
            physical_feature_manifest_path, expected_schema=PHYSICAL_SCHEMA
        ),
    }
    if auxiliary_feature_manifest_path is not None:
        stores["auxiliary"] = _load_store(
            auxiliary_feature_manifest_path, expected_schema=AUXILIARY_SCHEMA
        )
    synthetic_records = stores["synthetic"]["records"]
    physical_records = stores["physical"]["records"]
    persona_ids = {str(record["persona_id"]) for record in synthetic_records}
    training_personas, validation_persona_set = _BASE.split_personas(
        persona_ids, seed=seed, validation_personas=validation_personas
    )
    synthetic_training, synthetic_validation = partition_indexes(
        synthetic_records,
        training_personas=training_personas,
        validation_personas=validation_persona_set,
    )
    physical_training, physical_validation = partition_indexes(
        physical_records,
        training_personas=training_personas,
        validation_personas=validation_persona_set,
    )

    def indexes_with_label(
        records: list[dict[str, object]], indexes: list[int], label: str
    ) -> list[int]:
        return [index for index in indexes if records[index]["label"] == label]

    training_pools = {
        "synthetic_positive": indexes_with_label(
            synthetic_records, synthetic_training, "positive"
        ),
        "synthetic_negative": indexes_with_label(
            synthetic_records, synthetic_training, "adversarial_negative"
        ),
        "physical_positive": indexes_with_label(
            physical_records, physical_training, "positive"
        ),
        "physical_negative": indexes_with_label(
            physical_records, physical_training, "adversarial_negative"
        ),
    }
    if any(not indexes for indexes in training_pools.values()):
        raise ValueError("baxy_physical_adaptation_training_labels_invalid")
    auxiliary_pools: dict[str, list[int]] | None = None
    if "auxiliary" in stores:
        auxiliary_records = stores["auxiliary"]["records"]
        auxiliary_pools = {
            "positive": indexes_with_label(
                auxiliary_records, list(range(len(auxiliary_records))), "positive"
            ),
            "negative": indexes_with_label(
                auxiliary_records,
                list(range(len(auxiliary_records))),
                "adversarial_negative",
            ),
        }
        if any(not indexes for indexes in auxiliary_pools.values()):
            raise ValueError("baxy_physical_adaptation_auxiliary_labels_invalid")

    import torch
    import torch.nn as nn

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("baxy_physical_adaptation_cuda_unavailable")
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
    initializer = torch.load(
        initializer_checkpoint_path, map_location="cpu", weights_only=False
    )
    if (
        not isinstance(initializer, dict)
        or initializer.get("upstream_commit") != EXPECTED_UPSTREAM_COMMIT
        or initializer.get("aliases") != list(ALIASES)
        or not isinstance(initializer.get("model_state_dict"), dict)
    ):
        raise ValueError("baxy_physical_adaptation_initializer_invalid")

    model = lightning_model.model
    model.load_state_dict(initializer["model_state_dict"], strict=True)
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.perceiver_classifier.parameters():
        parameter.requires_grad = True
    if not freeze_audio_encoder:
        for parameter in model.audio_encoder.parameters():
            parameter.requires_grad = True
    trainable_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    trainable_parameter_count = sum(parameter.numel() for parameter in trainable_parameters)

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
        selections: list[tuple[str, int]], *, augment: bool
    ) -> tuple[object, object]:
        lengths = []
        for domain, index in selections:
            offsets = stores[domain]["offsets"]
            lengths.append(int(offsets[index + 1] - offsets[index]))
        maximum = max(lengths)
        values = np.zeros((len(selections), maximum, 80), dtype=np.float32)
        for row, ((domain, index), length) in enumerate(zip(selections, lengths)):
            store = stores[domain]
            offsets = store["offsets"]
            features = store["features"]
            values[row, :length] = features[
                int(offsets[index]) : int(offsets[index + 1])
            ]
            if augment:
                if feature_noise_std:
                    values[row, :length] += augmentation_rng.normal(
                        0.0, feature_noise_std, size=(length, 80)
                    ).astype(np.float32)
                if time_mask_frames and length > 1:
                    width = int(
                        augmentation_rng.integers(
                            0, min(time_mask_frames, length - 1) + 1
                        )
                    )
                    if width:
                        start = int(augmentation_rng.integers(0, length - width + 1))
                        values[row, start : start + width] = 0.0
                if frequency_mask_bins:
                    width = int(
                        augmentation_rng.integers(
                            0, min(frequency_mask_bins, 79) + 1
                        )
                    )
                    if width:
                        start = int(augmentation_rng.integers(0, 80 - width + 1))
                        values[row, :length, start : start + width] = 0.0
        return (
            torch.from_numpy(values).to(torch_device),
            torch.tensor(lengths, dtype=torch.long, device=torch_device),
        )

    def logits_for(
        selections: list[tuple[str, int]], *, augment: bool
    ) -> object:
        audio, audio_lengths = feature_batch(selections, augment=augment)
        return model.run_classifier(audio, alias_weights, audio_lengths)

    def evaluate_partition(domain: str, indexes: list[int]) -> dict[str, object]:
        records = stores[domain]["records"]
        labels = np.asarray(
            [records[index]["label"] == "positive" for index in indexes],
            dtype=np.int64,
        )
        if set(labels.tolist()) != {0, 1}:
            raise ValueError("baxy_physical_adaptation_validation_labels_invalid")
        batches = []
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(indexes), validation_batch_size):
                selections = [
                    (domain, index)
                    for index in indexes[start : start + validation_batch_size]
                ]
                with torch.autocast(
                    device_type=device, dtype=torch.float16, enabled=device == "cuda"
                ):
                    logits = logits_for(selections, augment=False)
                batches.append(logits.float().cpu().numpy())
        matrix = np.concatenate(batches)
        result = _BASE.binary_metrics(labels, matrix.max(axis=1))
        result["per_alias"] = {
            alias: _BASE.binary_metrics(labels, matrix[:, alias_index])
            for alias_index, alias in enumerate(ALIASES)
        }
        return result

    def evaluate() -> dict[str, object]:
        return {
            "physical": evaluate_partition("physical", physical_validation),
            "synthetic": evaluate_partition("synthetic", synthetic_validation),
        }

    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "baxy-hyperspotter-physical-adaptation-v3.pt"
    started = time.perf_counter()
    baseline = evaluate()
    best_rank = candidate_rank(baseline["physical"], baseline["synthetic"])
    torch.save(
        {
            "schema": "baxy.baxy-hyperspotter-physical-adaptation.v3",
            "official_checkpoint_sha256": _BASE._LOGMEL.sha256(official_checkpoint_path),
            "initializer_checkpoint_sha256": _BASE._LOGMEL.sha256(
                initializer_checkpoint_path
            ),
            "synthetic_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                stores["synthetic"]["manifest_path"]
            ),
            "physical_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                stores["physical"]["manifest_path"]
            ),
            "upstream_commit": EXPECTED_UPSTREAM_COMMIT,
            "seed": seed,
            "aliases": list(ALIASES),
            "best_epoch": 0,
            "model_state_dict": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
        },
        checkpoint_path,
    )
    history: list[dict[str, object]] = []
    for epoch in range(1, epochs + 1):
        model.train()
        model.text_encoder.eval()
        model.embedding_2_ms.eval()
        if freeze_audio_encoder:
            model.audio_encoder.eval()
        losses = []
        for _ in range(batches_per_epoch):
            selections, labels = mixed_domain_batch_indexes(
                **training_pools, batch_size=batch_size, rng=training_rng
            )
            if auxiliary_pools is not None:
                selections = replace_physical_with_auxiliary(
                    selections,
                    labels,
                    auxiliary_positive=auxiliary_pools["positive"],
                    auxiliary_negative=auxiliary_pools["negative"],
                    probability=auxiliary_replacement_probability,
                    rng=training_rng,
                )
            optimizer.zero_grad(set_to_none=True)
            target = torch.tensor(
                labels, dtype=torch.float32, device=torch_device
            )[:, None].expand(-1, len(ALIASES))
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = logits_for(selections, augment=True)
                loss = loss_function(logits, target)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        validation = evaluate()
        rank = candidate_rank(validation["physical"], validation["synthetic"])
        selected = rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.baxy-hyperspotter-physical-adaptation.v3",
                    "official_checkpoint_sha256": _BASE._LOGMEL.sha256(
                        official_checkpoint_path
                    ),
                    "initializer_checkpoint_sha256": _BASE._LOGMEL.sha256(
                        initializer_checkpoint_path
                    ),
                    "synthetic_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                        stores["synthetic"]["manifest_path"]
                    ),
                    "physical_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                        stores["physical"]["manifest_path"]
                    ),
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
    if checkpoint["best_epoch"] == 0:
        selected_validation = baseline
    else:
        selected_validation = next(
            entry["validation"]
            for entry in history
            if entry["epoch"] == checkpoint["best_epoch"]
        )
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-physical-adaptation-training.v3",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic_plus_wasapi_raw_physical_speaker_disjoint_hardnegative",
        "sources": {
            "synthetic_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                stores["synthetic"]["manifest_path"]
            ),
            "physical_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                stores["physical"]["manifest_path"]
            ),
            "auxiliary_feature_manifest_sha256": (
                None
                if "auxiliary" not in stores
                else _BASE._LOGMEL.sha256(stores["auxiliary"]["manifest_path"])
            ),
            "official_checkpoint_sha256": _BASE._LOGMEL.sha256(
                official_checkpoint_path
            ),
            "initializer_checkpoint_sha256": _BASE._LOGMEL.sha256(
                initializer_checkpoint_path
            ),
            "hyperspotter_upstream_commit": EXPECTED_UPSTREAM_COMMIT,
        },
        "contract": {
            "seed": seed,
            "aliases": list(ALIASES),
            "training_personas": sorted(training_personas),
            "validation_personas": sorted(validation_persona_set),
            "synthetic_training_examples": len(synthetic_training),
            "physical_training_examples": len(physical_training),
            "auxiliary_training_examples": (
                0 if "auxiliary" not in stores else len(stores["auxiliary"]["records"])
            ),
            "synthetic_validation_examples": len(synthetic_validation),
            "physical_validation_examples": len(physical_validation),
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "batch_size": batch_size,
            "domain_class_quarters_per_batch": True,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "feature_noise_std": feature_noise_std,
            "time_mask_frames": time_mask_frames,
            "frequency_mask_bins": frequency_mask_bins,
            "audio_encoder_frozen": freeze_audio_encoder,
            "text_encoder_frozen": True,
            "trainable_parameters": trainable_parameter_count,
            "auxiliary_replacement_probability": auxiliary_replacement_probability,
            "objective": "balanced_domain_and_class_per_alias_binary_cross_entropy",
            "selection_rank": [
                "physical_zero_false_recall",
                "physical_auc",
                "negative_physical_eer",
                "synthetic_auc",
                "synthetic_zero_false_recall",
            ],
        },
        "baseline": baseline,
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation": selected_validation,
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _BASE._LOGMEL.sha256(checkpoint_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "development_only": True,
        "effects_executed": 0,
    }
    (output_directory / "training.report.v3.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-feature-manifest", type=Path, required=True)
    parser.add_argument("--physical-feature-manifest", type=Path, required=True)
    parser.add_argument("--auxiliary-feature-manifest", type=Path)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--initializer-checkpoint", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=9701)
    parser.add_argument("--validation-personas", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batches-per-epoch", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--validation-batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-6)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--feature-noise-std", type=float, default=0.01)
    parser.add_argument("--time-mask-frames", type=int, default=8)
    parser.add_argument("--frequency-mask-bins", type=int, default=4)
    parser.add_argument("--freeze-audio-encoder", action="store_true")
    parser.add_argument("--auxiliary-replacement-probability", type=float, default=0.0)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        synthetic_feature_manifest_path=arguments.synthetic_feature_manifest,
        physical_feature_manifest_path=arguments.physical_feature_manifest,
        auxiliary_feature_manifest_path=arguments.auxiliary_feature_manifest,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        initializer_checkpoint_path=arguments.initializer_checkpoint,
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
        freeze_audio_encoder=arguments.freeze_audio_encoder,
        auxiliary_replacement_probability=arguments.auxiliary_replacement_probability,
        device=arguments.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
