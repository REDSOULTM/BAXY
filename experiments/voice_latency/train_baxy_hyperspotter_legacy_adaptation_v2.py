"""Adapt the BAXY HyperSpotter output head on legacy human development.

Only the 1.5K-parameter final normalization/projection head is updated.  Each
batch mixes speaker-disjoint synthetic data with the legacy human partition;
the expanded human partition is scored exactly once after the fixed schedule.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import random
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_legacy_adaptation_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "train_baxy_hyperspotter_binary_v1.py",
    "_baxy_legacy_adaptation_base_v2",
)
_EVALUATOR = load_component(
    "evaluate_baxy_hyperspotter_human_development_v1.py",
    "_baxy_legacy_adaptation_evaluator_v2",
)
_HUMAN = load_component(
    "extract_baxy_hyperspotter_human_logmel_v1.py",
    "_baxy_legacy_adaptation_human_v2",
)


def mixed_batch_indexes(
    *,
    synthetic_positive: list[int],
    synthetic_negative: list[int],
    human_positive: list[int],
    human_negative: list[int],
    batch_size: int,
    human_examples: int,
    rng: random.Random,
) -> tuple[list[tuple[str, int]], list[float]]:
    if (
        batch_size < 4
        or batch_size % 2
        or human_examples < 2
        or human_examples % 2
        or human_examples >= batch_size
        or (batch_size - human_examples) % 2
        or not all(
            (synthetic_positive, synthetic_negative, human_positive, human_negative)
        )
    ):
        raise ValueError("baxy_legacy_adaptation_batch_schedule_invalid")
    human_half = human_examples // 2
    synthetic_half = (batch_size - human_examples) // 2
    values = [
        *[("synthetic", rng.choice(synthetic_positive), 1.0) for _ in range(synthetic_half)],
        *[("synthetic", rng.choice(synthetic_negative), 0.0) for _ in range(synthetic_half)],
        *[("human", rng.choice(human_positive), 1.0) for _ in range(human_half)],
        *[("human", rng.choice(human_negative), 0.0) for _ in range(human_half)],
    ]
    rng.shuffle(values)
    return (
        [(source, index) for source, index, _ in values],
        [label for _, _, label in values],
    )


def conservative_zero_false_threshold(
    synthetic_scores: np.ndarray,
    synthetic_labels: np.ndarray,
    human_scores: np.ndarray,
    human_labels: np.ndarray,
) -> float:
    negative_scores = np.concatenate(
        (
            np.asarray(synthetic_scores)[np.asarray(synthetic_labels) == 0],
            np.asarray(human_scores)[np.asarray(human_labels) == 0],
        )
    ).astype(np.float64)
    if not len(negative_scores) or not np.isfinite(negative_scores).all():
        raise ValueError("baxy_legacy_adaptation_threshold_invalid")
    return float(np.nextafter(np.max(negative_scores), math.inf))


def train(
    *,
    synthetic_feature_manifest_path: Path,
    human_feature_manifest_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    initializer_checkpoint_path: Path,
    output_directory: Path,
    validation_personas: int,
    epochs: int,
    batches_per_epoch: int,
    batch_size: int,
    human_examples_per_batch: int,
    validation_batch_size: int,
    learning_rate: float,
    weight_decay: float,
    feature_noise_std: float,
    time_mask_frames: int,
    frequency_mask_bins: int,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or batches_per_epoch < 1
        or validation_batch_size < 1
        or learning_rate <= 0.0
        or weight_decay < 0.0
        or feature_noise_std < 0.0
        or time_mask_frames < 0
        or frequency_mask_bins < 0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("baxy_legacy_adaptation_schedule_invalid")
    synthetic_feature_manifest_path = synthetic_feature_manifest_path.resolve(
        strict=True
    )
    human_feature_manifest_path = human_feature_manifest_path.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    official_checkpoint_path = official_checkpoint_path.resolve(strict=True)
    initializer_checkpoint_path = initializer_checkpoint_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    synthetic_manifest = _BASE._LOGMEL.read_object(
        synthetic_feature_manifest_path
    )
    human_manifest = _BASE._LOGMEL.read_object(human_feature_manifest_path)
    if (
        synthetic_manifest.get("schema") != "baxy.baxy-hyperspotter-logmel.v1"
        or synthetic_manifest.get("human_development_audio_accessed") is not False
        or synthetic_manifest.get("blind_human_audio_accessed") is not False
        or human_manifest.get("schema")
        != "baxy.baxy-hyperspotter-human-logmel.v1"
        or human_manifest.get("human_development_audio_accessed") is not True
        or human_manifest.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("baxy_legacy_adaptation_manifest_boundary_invalid")
    synthetic_records = synthetic_manifest.get("records")
    human_records = human_manifest.get("records")
    if not isinstance(synthetic_records, list) or not isinstance(human_records, list):
        raise ValueError("baxy_legacy_adaptation_records_invalid")

    def load_arrays(
        manifest_path: Path, manifest: dict[str, object], record_count: int
    ) -> tuple[np.ndarray, np.ndarray]:
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("baxy_legacy_adaptation_files_invalid")
        root = manifest_path.parent
        feature_path = root / str(files["logmel"])
        offset_path = root / str(files["offsets"])
        if (
            _BASE._LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
            or _BASE._LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
        ):
            raise ValueError("baxy_legacy_adaptation_feature_hash_mismatch")
        features = np.load(feature_path, mmap_mode="r")
        offsets = np.load(offset_path)
        if len(offsets) != record_count + 1 or int(offsets[-1]) != len(features):
            raise ValueError("baxy_legacy_adaptation_feature_shape_invalid")
        return features, offsets

    synthetic_features, synthetic_offsets = load_arrays(
        synthetic_feature_manifest_path,
        synthetic_manifest,
        len(synthetic_records),
    )
    human_features, human_offsets = load_arrays(
        human_feature_manifest_path, human_manifest, len(human_records)
    )

    model, tokenizer, torch, torch_device, initializer = _EVALUATOR.load_candidate(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        official_checkpoint_path=official_checkpoint_path,
        candidate_checkpoint_path=initializer_checkpoint_path,
        device=device,
    )
    seed = int(initializer["seed"])
    personas = {str(record["persona_id"]) for record in synthetic_records}
    training_personas, validation_persona_set = _BASE.split_personas(
        personas, seed=seed, validation_personas=validation_personas
    )
    synthetic_training = [
        index
        for index, record in enumerate(synthetic_records)
        if record["persona_id"] in training_personas
    ]
    synthetic_validation = [
        index
        for index, record in enumerate(synthetic_records)
        if record["persona_id"] in validation_persona_set
    ]
    synthetic_positive = [
        index
        for index in synthetic_training
        if synthetic_records[index]["label"] == "positive"
    ]
    synthetic_negative = [
        index
        for index in synthetic_training
        if synthetic_records[index]["label"] == "adversarial_negative"
    ]
    legacy_indexes = [
        index
        for index, record in enumerate(human_records)
        if record["corpus"] == "human_legacy"
    ]
    expanded_indexes = [
        index
        for index, record in enumerate(human_records)
        if record["corpus"] == "human_expanded"
    ]
    human_positive = [
        index for index in legacy_indexes if human_records[index]["label"] == "positive"
    ]
    human_negative = [
        index for index in legacy_indexes if human_records[index]["label"] != "positive"
    ]
    if (
        len(legacy_indexes) != 18
        or len(expanded_indexes) != 12
        or len(human_positive) != 14
        or len(human_negative) != 4
    ):
        raise ValueError("baxy_legacy_adaptation_human_partition_invalid")

    import torch.nn as nn

    for parameter in model.parameters():
        parameter.requires_grad = False
    final_head = model.perceiver_classifier.to_logits
    for parameter in final_head.parameters():
        parameter.requires_grad = True
    trainable_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    if sum(parameter.numel() for parameter in trainable_parameters) > 2_000:
        raise ValueError("baxy_legacy_adaptation_trainable_boundary_invalid")
    keyword_ids = tokenizer(list(_BASE.ALIASES))["input_ids"]
    keyword_lengths = torch.tensor([len(value) for value in keyword_ids], dtype=torch.long)
    keyword_values = nn.utils.rnn.pad_sequence(
        [torch.tensor(value, dtype=torch.long, device=torch_device) for value in keyword_ids],
        padding_value=tokenizer.pad_token_id,
        batch_first=True,
    )
    with torch.inference_mode():
        alias_weights = model.get_text_weights(keyword_values, keyword_lengths).detach()

    torch.manual_seed(seed + 100)
    np.random.seed(seed + 100)
    random.seed(seed + 100)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed + 100)
        torch.set_float32_matmul_precision("high")
    optimizer = torch.optim.AdamW(
        trainable_parameters, lr=learning_rate, weight_decay=weight_decay
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    loss_function = torch.nn.BCEWithLogitsLoss()
    sampling_rng = random.Random(seed + 101)
    augmentation_rng = np.random.default_rng(seed + 102)

    sources = {
        "synthetic": (synthetic_features, synthetic_offsets),
        "human": (human_features, human_offsets),
    }

    def feature_batch(
        selections: list[tuple[str, int]], *, augment: bool
    ) -> tuple[object, object]:
        lengths = [
            int(sources[source][1][index + 1] - sources[source][1][index])
            for source, index in selections
        ]
        values = np.zeros((len(selections), max(lengths), 80), dtype=np.float32)
        for row, (source, index) in enumerate(selections):
            features, offsets = sources[source]
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
                    width = int(
                        augmentation_rng.integers(
                            0, min(time_mask_frames, length - 1) + 1
                        )
                    )
                    if width:
                        start = int(
                            augmentation_rng.integers(0, length - width + 1)
                        )
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

    def score(selections: list[tuple[str, int]]) -> np.ndarray:
        model.eval()
        batches = []
        with torch.inference_mode():
            for start in range(0, len(selections), validation_batch_size):
                current = selections[start : start + validation_batch_size]
                audio, lengths = feature_batch(current, augment=False)
                with torch.autocast(
                    device_type=device, dtype=torch.float16, enabled=device == "cuda"
                ):
                    logits = model.run_classifier(audio, alias_weights, lengths)
                batches.append(logits.max(dim=1).values.float().cpu().numpy())
        return np.concatenate(batches)

    synthetic_validation_labels = np.asarray(
        [synthetic_records[index]["label"] == "positive" for index in synthetic_validation],
        dtype=np.int64,
    )
    legacy_labels = np.asarray(
        [human_records[index]["label"] == "positive" for index in legacy_indexes],
        dtype=np.int64,
    )
    expanded_labels = np.asarray(
        [human_records[index]["label"] == "positive" for index in expanded_indexes],
        dtype=np.int64,
    )
    synthetic_selections = [("synthetic", index) for index in synthetic_validation]
    legacy_selections = [("human", index) for index in legacy_indexes]
    expanded_selections = [("human", index) for index in expanded_indexes]
    before_synthetic_scores = score(synthetic_selections)
    before_legacy_scores = score(legacy_selections)
    baseline = {
        "synthetic_validation": _BASE.binary_metrics(
            synthetic_validation_labels, before_synthetic_scores
        ),
        "legacy_adaptation_partition": _BASE.binary_metrics(
            legacy_labels, before_legacy_scores
        ),
        "expanded_partition_scored": False,
    }

    history = []
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        model.audio_encoder.eval()
        model.text_encoder.eval()
        model.embedding_2_ms.eval()
        losses = []
        for _ in range(batches_per_epoch):
            selections, labels = mixed_batch_indexes(
                synthetic_positive=synthetic_positive,
                synthetic_negative=synthetic_negative,
                human_positive=human_positive,
                human_negative=human_negative,
                batch_size=batch_size,
                human_examples=human_examples_per_batch,
                rng=sampling_rng,
            )
            optimizer.zero_grad(set_to_none=True)
            audio, lengths = feature_batch(selections, augment=True)
            targets = torch.tensor(
                labels, dtype=torch.float32, device=torch_device
            )[:, None].expand(-1, len(_BASE.ALIASES))
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = model.run_classifier(audio, alias_weights, lengths)
                loss = loss_function(logits, targets)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        synthetic_scores = score(synthetic_selections)
        legacy_scores = score(legacy_selections)
        entry = {
            "epoch": epoch,
            "mean_training_loss": float(np.mean(losses)),
            "synthetic_validation": _BASE.binary_metrics(
                synthetic_validation_labels, synthetic_scores
            ),
            "legacy_adaptation_partition": _BASE.binary_metrics(
                legacy_labels, legacy_scores
            ),
            "expanded_partition_scored": False,
        }
        history.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)

    final_synthetic_scores = score(synthetic_selections)
    final_legacy_scores = score(legacy_selections)
    fixed_threshold = conservative_zero_false_threshold(
        final_synthetic_scores,
        synthetic_validation_labels,
        final_legacy_scores,
        legacy_labels,
    )
    # The expanded partition remains untouched until the fixed epoch schedule
    # and operating threshold above are complete.
    expanded_scores = score(expanded_selections)
    expanded_decisions = expanded_scores.astype(np.float64) >= fixed_threshold
    expanded_metrics = _BASE.binary_metrics(expanded_labels, expanded_scores)
    expanded_fixed = {
        "threshold": fixed_threshold,
        "positive_hits": int(
            np.count_nonzero(expanded_decisions & (expanded_labels == 1))
        ),
        "false_hits": int(
            np.count_nonzero(expanded_decisions & (expanded_labels == 0))
        ),
    }
    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "baxy-hyperspotter-legacy-adaptation-v2.pt"
    torch.save(
        {
            "schema": "baxy.baxy-hyperspotter-binary.v1",
            "official_checkpoint_sha256": _BASE._LOGMEL.sha256(
                official_checkpoint_path
            ),
            "feature_manifest_sha256": _BASE._LOGMEL.sha256(
                synthetic_feature_manifest_path
            ),
            "human_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                human_feature_manifest_path
            ),
            "initializer_checkpoint_sha256": _BASE._LOGMEL.sha256(
                initializer_checkpoint_path
            ),
            "upstream_commit": _BASE.EXPECTED_UPSTREAM_COMMIT,
            "seed": seed,
            "aliases": list(_BASE.ALIASES),
            "best_epoch": epochs,
            "fixed_threshold": fixed_threshold,
            "model_state_dict": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
        },
        checkpoint_path,
    )
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-legacy-adaptation-training.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "legacy_human_head_adaptation_expanded_partition_one_shot",
        "sources": {
            "synthetic_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                synthetic_feature_manifest_path
            ),
            "human_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                human_feature_manifest_path
            ),
            "official_checkpoint_sha256": _BASE._LOGMEL.sha256(
                official_checkpoint_path
            ),
            "initializer_checkpoint_sha256": _BASE._LOGMEL.sha256(
                initializer_checkpoint_path
            ),
        },
        "contract": {
            "seed": seed,
            "aliases": list(_BASE.ALIASES),
            "training_personas": len(training_personas),
            "synthetic_validation_personas": len(validation_persona_set),
            "legacy_human_examples": len(legacy_indexes),
            "expanded_human_examples": len(expanded_indexes),
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "batch_size": batch_size,
            "human_examples_per_batch": human_examples_per_batch,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "feature_noise_std": feature_noise_std,
            "time_mask_frames": time_mask_frames,
            "frequency_mask_bins": frequency_mask_bins,
            "trainable_parameters": sum(
                parameter.numel() for parameter in trainable_parameters
            ),
            "trainable_module": "perceiver_classifier.to_logits",
            "expanded_partition_selection_access": False,
            "checkpoint_selection": "fixed_final_epoch",
            "fixed_threshold_source": "maximum_of_synthetic_validation_and_legacy_training_negatives",
        },
        "baseline": baseline,
        "history": history,
        "selected": {
            "best_epoch": epochs,
            "validation": {
                **history[-1]["synthetic_validation"],
                "zero_false_threshold": fixed_threshold,
            },
            "legacy_adaptation_partition": history[-1][
                "legacy_adaptation_partition"
            ],
            "expanded_one_shot": {
                "metrics": expanded_metrics,
                "fixed_threshold": expanded_fixed,
            },
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _BASE._LOGMEL.sha256(checkpoint_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": True,
        "expanded_partition_scored_after_selection_once": True,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    (output_directory / "training.report.v2.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-feature-manifest", type=Path, required=True)
    parser.add_argument("--human-feature-manifest", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--initializer-checkpoint", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--validation-personas", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batches-per-epoch", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--human-examples-per-batch", type=int, default=8)
    parser.add_argument("--validation-batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--feature-noise-std", type=float, default=0.02)
    parser.add_argument("--time-mask-frames", type=int, default=12)
    parser.add_argument("--frequency-mask-bins", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        synthetic_feature_manifest_path=arguments.synthetic_feature_manifest,
        human_feature_manifest_path=arguments.human_feature_manifest,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        initializer_checkpoint_path=arguments.initializer_checkpoint,
        output_directory=arguments.output_directory,
        validation_personas=arguments.validation_personas,
        epochs=arguments.epochs,
        batches_per_epoch=arguments.batches_per_epoch,
        batch_size=arguments.batch_size,
        human_examples_per_batch=arguments.human_examples_per_batch,
        validation_batch_size=arguments.validation_batch_size,
        learning_rate=arguments.learning_rate,
        weight_decay=arguments.weight_decay,
        feature_noise_std=arguments.feature_noise_std,
        time_mask_frames=arguments.time_mask_frames,
        frequency_mask_bins=arguments.frequency_mask_bins,
        device=arguments.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
