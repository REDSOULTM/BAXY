"""Adapt the official HyperSpotter text-conditioned detector on Spanish MSWC."""

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


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_hyperspotter_train_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LOGMEL = load_component(
    "extract_mswc_hyperspotter_logmel_v1.py",
    "_baxy_hyperspotter_train_logmel_v1",
)
_PAIR = load_component(
    "train_mswc_spanish_qbye_similarity_cnn_v4.py",
    "_baxy_hyperspotter_train_pairs_v1",
)


def sample_examples(
    *,
    words: list[str],
    indexes_by_word: dict[str, list[int]],
    hard_negatives: dict[str, list[str]],
    count: int,
    hard_negative_probability: float,
    rng: random.Random,
) -> tuple[list[int], list[str], np.ndarray]:
    if count < 2 or not 0.0 <= hard_negative_probability <= 1.0:
        raise ValueError("mswc_hyperspotter_train_sample_schedule_invalid")
    audio_indexes = []
    keywords = []
    targets = np.zeros(count, dtype=np.float32)
    for index in range(count):
        spoken_word = rng.choice(words)
        audio_indexes.append(rng.choice(indexes_by_word[spoken_word]))
        if index < count // 2:
            keywords.append(spoken_word)
            targets[index] = 1.0
        else:
            keyword = (
                rng.choice(hard_negatives[spoken_word])
                if rng.random() < hard_negative_probability
                else rng.choice(words)
            )
            while keyword == spoken_word:
                keyword = rng.choice(words)
            keywords.append(keyword)
    order = list(range(count))
    rng.shuffle(order)
    return (
        [audio_indexes[index] for index in order],
        [keywords[index] for index in order],
        targets[order],
    )


def train(
    *,
    feature_manifest_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    initial_checkpoint_path: Path,
    output_directory: Path,
    seed: int,
    validation_classes: int,
    epochs: int,
    batches_per_epoch: int,
    batch_size: int,
    validation_examples: int,
    learning_rate: float,
    hard_negative_probability: float,
    hard_negative_neighbors: int,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or batches_per_epoch < 1
        or batch_size < 2
        or validation_examples < 2
        or learning_rate <= 0.0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_hyperspotter_train_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    initial_checkpoint_path = initial_checkpoint_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    manifest = _LOGMEL.read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    contract = manifest.get("contract")
    if (
        manifest.get("schema") != "baxy.mswc-hyperspotter-logmel.v1"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(contract, dict)
        or contract.get("included_partitions") != ["metric_training"]
    ):
        raise ValueError("mswc_hyperspotter_train_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_hyperspotter_train_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    training_words, validation_words = _PAIR.split_metric_words(
        words, seed=seed, validation_classes=validation_classes
    )
    indexes_by_word = {
        word: [
            index
            for index, record in enumerate(records)
            if str(record["class_name"]) == word
        ]
        for word in words
    }
    if any(len(indexes) < 2 for indexes in indexes_by_word.values()):
        raise ValueError("mswc_hyperspotter_train_examples_missing")
    training_hard = _PAIR.hard_negative_map(
        training_words, neighbors=hard_negative_neighbors
    )
    validation_hard = _PAIR.hard_negative_map(
        validation_words,
        neighbors=min(hard_negative_neighbors, len(validation_words) - 1),
    )
    root = feature_manifest_path.parent
    feature_path = root / str(files["logmel"])
    offset_path = root / str(files["offsets"])
    if (
        _LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_hyperspotter_train_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("mswc_hyperspotter_train_feature_shape_invalid")

    import torch
    import torch.nn as nn

    # The official research environment contributes Lightning and its pure-Python
    # dependencies.  Torch/torchaudio remain those of the already validated CUDA
    # environment.  HyperSpotter's Conformer path never calls Whisper or wandb,
    # so lightweight stubs avoid importing their incompatible legacy extras.
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
    sys.path.append(str(hyperspotter_site_packages))
    sys.path.insert(0, str(hyperspotter_root))
    from src.models import ConformerLightning

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_hyperspotter_train_cuda_unavailable")
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
            str(initial_checkpoint_path), map_location="cpu"
        )
    finally:
        torch.load = original_torch_load
        os.chdir(previous_directory)
    model = lightning_model.model
    for parameter in model.parameters():
        parameter.requires_grad = False
    for module in (model.text_encoder, model.embedding_2_ms, model.perceiver_classifier):
        for parameter in module.parameters():
            parameter.requires_grad = True
    trainable_parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not trainable_parameters:
        raise ValueError("mswc_hyperspotter_train_parameters_empty")
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.set_float32_matmul_precision("high")
    torch_device = torch.device(device)
    model = model.to(torch_device)
    optimizer = torch.optim.AdamW(trainable_parameters, lr=learning_rate, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    loss_function = torch.nn.BCEWithLogitsLoss()

    def feature_batch(indexes: list[int]) -> tuple[object, object]:
        lengths = [int(offsets[index + 1] - offsets[index]) for index in indexes]
        maximum = max(lengths)
        values = np.zeros((len(indexes), maximum, 80), dtype=np.float32)
        for row, index in enumerate(indexes):
            values[row, : lengths[row]] = features[
                int(offsets[index]) : int(offsets[index + 1])
            ]
        return (
            torch.from_numpy(values).to(torch_device),
            torch.tensor(lengths, dtype=torch.long, device=torch_device),
        )

    def keyword_batch(keywords: list[str]) -> tuple[object, object]:
        ids = lightning_model.tokenizer(keywords)["input_ids"]
        lengths = torch.tensor(
            [len(value) for value in ids], dtype=torch.long
        )
        values = nn.utils.rnn.pad_sequence(
            [torch.tensor(value, dtype=torch.long, device=torch_device) for value in ids],
            padding_value=lightning_model.tokenizer.pad_token_id,
            batch_first=True,
        )
        return values, lengths

    def logits_for(indexes: list[int], keywords: list[str]) -> object:
        audio, audio_lengths = feature_batch(indexes)
        keyword_ids, keyword_lengths = keyword_batch(keywords)
        _, _, _, logits = model(
            audio, audio_lengths, keyword_ids, keyword_lengths
        )
        return logits.squeeze(1)

    validation_rng = random.Random(seed + 1)
    validation_indexes, validation_keywords, validation_targets = sample_examples(
        words=sorted(validation_words),
        indexes_by_word=indexes_by_word,
        hard_negatives=validation_hard,
        count=validation_examples,
        hard_negative_probability=hard_negative_probability,
        rng=validation_rng,
    )

    def evaluate_validation() -> dict[str, float]:
        model.eval()
        logits = []
        with torch.inference_mode():
            for start in range(0, len(validation_indexes), batch_size * 2):
                with torch.autocast(
                    device_type=device,
                    dtype=torch.float16,
                    enabled=device == "cuda",
                ):
                    values = logits_for(
                        validation_indexes[start : start + batch_size * 2],
                        validation_keywords[start : start + batch_size * 2],
                    )
                logits.append(values.float().cpu().numpy())
        return _PAIR.pair_metrics(validation_targets, np.concatenate(logits))

    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mswc-hyperspotter-spanish-v1.pt"
    history = []
    best_rank = None
    started = time.perf_counter()
    training_rng = random.Random(seed + 2)
    training_word_list = sorted(training_words)
    for epoch in range(1, epochs + 1):
        model.train()
        model.audio_encoder.eval()
        losses = []
        for _ in range(batches_per_epoch):
            indexes, keywords, targets = sample_examples(
                words=training_word_list,
                indexes_by_word=indexes_by_word,
                hard_negatives=training_hard,
                count=batch_size,
                hard_negative_probability=hard_negative_probability,
                rng=training_rng,
            )
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device,
                dtype=torch.float16,
                enabled=device == "cuda",
            ):
                logits = logits_for(indexes, keywords)
                loss = loss_function(
                    logits,
                    torch.from_numpy(targets).to(torch_device),
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        metrics = evaluate_validation()
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
                    "schema": "baxy.mswc-hyperspotter-spanish.v1",
                    "initial_checkpoint_sha256": _LOGMEL.sha256(initial_checkpoint_path),
                    "feature_manifest_sha256": _LOGMEL.sha256(feature_manifest_path),
                    "upstream_commit": manifest["sources"]["hyperspotter_upstream_commit"],
                    "seed": seed,
                    "best_epoch": epoch,
                    "model_state_dict": {
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
    best_entry = next(
        entry for entry in history if entry["epoch"] == checkpoint["best_epoch"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-hyperspotter-spanish-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "spanish_mswc_internal_word_holdout_adaptation_of_official_hyperspotter",
        "sources": {
            "feature_manifest_sha256": _LOGMEL.sha256(feature_manifest_path),
            "initial_checkpoint_sha256": _LOGMEL.sha256(initial_checkpoint_path),
            "hyperspotter_upstream_commit": manifest["sources"]["hyperspotter_upstream_commit"],
            "hyperspotter_site_packages": hyperspotter_site_packages.as_posix(),
        },
        "contract": {
            "seed": seed,
            "training_word_classes": len(training_words),
            "validation_word_classes": len(validation_words),
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "batch_size": batch_size,
            "validation_examples": validation_examples,
            "learning_rate": learning_rate,
            "hard_negative_probability": hard_negative_probability,
            "hard_negative_neighbors": hard_negative_neighbors,
            "audio_encoder_frozen": True,
            "trainable_modules": [
                "text_encoder",
                "text_to_matched_filter",
                "perceiver_classifier",
            ],
            "objective": "balanced_binary_text_keyword_presence_with_cross_word_negatives",
        },
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation_pairs": best_entry["validation_pairs"],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _LOGMEL.sha256(checkpoint_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "research_v3_examples_scored": False,
        "official_test_audio_accessed": False,
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
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=9501)
    parser.add_argument("--validation-classes", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batches-per-epoch", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--validation-examples", type=int, default=4096)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--hard-negative-probability", type=float, default=0.75)
    parser.add_argument("--hard-negative-neighbors", type=int, default=16)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = train(
        feature_manifest_path=args.feature_manifest,
        hyperspotter_root=args.hyperspotter_root,
        hyperspotter_site_packages=args.hyperspotter_site_packages,
        initial_checkpoint_path=args.initial_checkpoint,
        output_directory=args.output_directory,
        seed=args.seed,
        validation_classes=args.validation_classes,
        epochs=args.epochs,
        batches_per_epoch=args.batches_per_epoch,
        batch_size=args.batch_size,
        validation_examples=args.validation_examples,
        learning_rate=args.learning_rate,
        hard_negative_probability=args.hard_negative_probability,
        hard_negative_neighbors=args.hard_negative_neighbors,
        device=args.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
