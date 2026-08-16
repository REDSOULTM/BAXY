"""Train HyperSpotter with multi-negative Spanish word ranking."""

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
        raise RuntimeError(f"mswc_hyperspotter_listwise_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LOGMEL = load_component(
    "extract_mswc_hyperspotter_logmel_v1.py",
    "_baxy_hyperspotter_listwise_logmel_v2",
)
_PAIR = load_component(
    "train_mswc_spanish_qbye_similarity_cnn_v4.py",
    "_baxy_hyperspotter_listwise_pairs_v2",
)
_EVALUATOR = load_component(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1.py",
    "_baxy_hyperspotter_listwise_metrics_v2",
)


def sample_listwise_examples(
    *,
    words: list[str],
    indexes_by_word: dict[str, list[int]],
    hard_negatives: dict[str, list[str]],
    count: int,
    hard_candidates: int,
    random_candidates: int,
    rng: random.Random,
) -> tuple[list[int], list[str], list[list[str]]]:
    if count < 1 or hard_candidates < 1 or random_candidates < 0:
        raise ValueError("mswc_hyperspotter_listwise_sample_schedule_invalid")
    total_negatives = hard_candidates + random_candidates
    if total_negatives >= len(words):
        raise ValueError("mswc_hyperspotter_listwise_sample_candidates_invalid")
    audio_indexes = []
    spoken_words = []
    candidate_words = []
    for _ in range(count):
        spoken = rng.choice(words)
        hard_pool = hard_negatives[spoken]
        if len(hard_pool) < hard_candidates:
            raise ValueError("mswc_hyperspotter_listwise_hard_pool_invalid")
        selected_hard = rng.sample(hard_pool, hard_candidates)
        excluded = {spoken, *selected_hard}
        random_pool = [word for word in words if word not in excluded]
        selected_random = rng.sample(random_pool, random_candidates)
        negatives = [*selected_hard, *selected_random]
        rng.shuffle(negatives)
        audio_indexes.append(rng.choice(indexes_by_word[spoken]))
        spoken_words.append(spoken)
        candidate_words.append([spoken, *negatives])
    return audio_indexes, spoken_words, candidate_words


def validation_schedule(
    *,
    words: list[str],
    indexes_by_word: dict[str, list[int]],
    hard_negatives: dict[str, list[str]],
    examples: int,
    negative_candidates: int,
    seed: int,
) -> tuple[list[int], list[str], list[list[str]]]:
    if examples < len(words) or negative_candidates < 1:
        raise ValueError("mswc_hyperspotter_listwise_validation_schedule_invalid")
    rng = random.Random(seed)
    pools = {word: list(indexes_by_word[word]) for word in words}
    for pool in pools.values():
        rng.shuffle(pool)
    audio_indexes = []
    spoken_words = []
    for round_index in range(max(len(pool) for pool in pools.values())):
        for word in words:
            pool = pools[word]
            if round_index < len(pool):
                audio_indexes.append(pool[round_index])
                spoken_words.append(word)
                if len(audio_indexes) == examples:
                    break
        if len(audio_indexes) == examples:
            break
    if len(audio_indexes) < examples:
        raise ValueError("mswc_hyperspotter_listwise_validation_examples_missing")
    candidates = [
        [word, *hard_negatives[word][:negative_candidates]] for word in spoken_words
    ]
    return audio_indexes, spoken_words, candidates


def train(
    *,
    feature_manifest_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    initializer_checkpoint_path: Path,
    output_directory: Path,
    seed: int,
    validation_classes: int,
    epochs: int,
    batches_per_epoch: int,
    audio_batch_size: int,
    hard_candidates: int,
    random_candidates: int,
    hard_negative_neighbors: int,
    validation_examples: int,
    validation_negative_candidates: int,
    learning_rate: float,
    binary_loss_weight: float,
    margin_loss_weight: float,
    ranking_margin: float,
    unfreeze_audio_encoder: bool,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or batches_per_epoch < 1
        or audio_batch_size < 1
        or hard_candidates < 1
        or random_candidates < 0
        or learning_rate <= 0.0
        or binary_loss_weight < 0.0
        or margin_loss_weight < 0.0
        or ranking_margin < 0.0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_hyperspotter_listwise_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    official_checkpoint_path = official_checkpoint_path.resolve(strict=True)
    initializer_checkpoint_path = initializer_checkpoint_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    manifest = _LOGMEL.read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    contract = manifest.get("contract")
    sources = manifest.get("sources")
    if (
        manifest.get("schema") != "baxy.mswc-hyperspotter-logmel.v1"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(contract, dict)
        or not isinstance(sources, dict)
        or contract.get("included_partitions") != ["metric_training"]
    ):
        raise ValueError("mswc_hyperspotter_listwise_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_hyperspotter_listwise_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    training_words, validation_words = _PAIR.split_metric_words(
        words, seed=seed, validation_classes=validation_classes
    )
    training_word_list = sorted(training_words)
    validation_word_list = sorted(validation_words)
    indexes_by_word = {
        word: [
            index
            for index, record in enumerate(records)
            if str(record["class_name"]) == word
        ]
        for word in words
    }
    if any(len(indexes) < 2 for indexes in indexes_by_word.values()):
        raise ValueError("mswc_hyperspotter_listwise_examples_missing")
    if hard_negative_neighbors < hard_candidates:
        raise ValueError("mswc_hyperspotter_listwise_neighbors_invalid")
    training_hard = _PAIR.hard_negative_map(
        training_words, neighbors=hard_negative_neighbors
    )
    validation_hard = _PAIR.hard_negative_map(
        validation_words, neighbors=validation_negative_candidates
    )
    validation_indexes, validation_spoken, validation_candidates = validation_schedule(
        words=validation_word_list,
        indexes_by_word=indexes_by_word,
        hard_negatives=validation_hard,
        examples=validation_examples,
        negative_candidates=validation_negative_candidates,
        seed=seed + 1,
    )
    root = feature_manifest_path.parent
    feature_path = root / str(files["logmel"])
    offset_path = root / str(files["offsets"])
    if (
        _LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_hyperspotter_listwise_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("mswc_hyperspotter_listwise_feature_shape_invalid")

    import torch
    import torch.nn as nn

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_hyperspotter_listwise_cuda_unavailable")
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
        or initializer.get("schema")
        not in {
            "baxy.mswc-hyperspotter-spanish.v1",
            "baxy.mswc-hyperspotter-listwise.v2",
        }
        or initializer.get("initial_checkpoint_sha256")
        != _LOGMEL.sha256(official_checkpoint_path)
        or not isinstance(initializer.get("model_state_dict"), dict)
    ):
        raise ValueError("mswc_hyperspotter_listwise_initializer_invalid")
    model = lightning_model.model
    model.load_state_dict(initializer["model_state_dict"])
    for parameter in model.parameters():
        parameter.requires_grad = False
    trainable_modules = [model.text_encoder, model.embedding_2_ms, model.perceiver_classifier]
    if unfreeze_audio_encoder:
        trainable_modules.append(model.audio_encoder)
    for module in trainable_modules:
        for parameter in module.parameters():
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
    optimizer = torch.optim.AdamW(
        trainable_parameters, lr=learning_rate, weight_decay=1e-4
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    cross_entropy = torch.nn.CrossEntropyLoss()
    binary_loss = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(
            [hard_candidates + random_candidates],
            dtype=torch.float32,
            device=torch_device,
        )
    )

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

    def listwise_logits(indexes: list[int], candidates: list[list[str]]) -> object:
        if not candidates or any(len(row) != len(candidates[0]) for row in candidates):
            raise ValueError("mswc_hyperspotter_listwise_candidate_shape_invalid")
        audio, audio_lengths = feature_batch(indexes)
        flat_keywords = [keyword for row in candidates for keyword in row]
        ids = lightning_model.tokenizer(flat_keywords)["input_ids"]
        lengths = torch.tensor([len(value) for value in ids], dtype=torch.long)
        values = nn.utils.rnn.pad_sequence(
            [torch.tensor(value, dtype=torch.long, device=torch_device) for value in ids],
            padding_value=lightning_model.tokenizer.pad_token_id,
            batch_first=True,
        )
        encoded, encoded_lengths = model.audio_encoder(
            audio.transpose(1, 2), audio_lengths
        )
        encoded = encoded[:, : int(encoded_lengths.max()), :]
        mask = (
            torch.arange(encoded.shape[1], device=torch_device)[None, :]
            < encoded_lengths[:, None]
        )
        candidate_count = len(candidates[0])
        text_weights = model.get_text_weights(values, lengths)
        logits = model.perceiver_classifier(
            encoded.repeat_interleave(candidate_count, dim=0),
            text_weights,
            mask=mask.repeat_interleave(candidate_count, dim=0),
        )
        return logits.reshape(len(indexes), candidate_count)

    def evaluate_validation() -> dict[str, object]:
        model.eval()
        batches = []
        with torch.inference_mode():
            for start in range(0, len(validation_indexes), audio_batch_size):
                with torch.autocast(
                    device_type=device, dtype=torch.float16, enabled=device == "cuda"
                ):
                    logits = listwise_logits(
                        validation_indexes[start : start + audio_batch_size],
                        validation_candidates[start : start + audio_batch_size],
                    )
                batches.append(logits.float().cpu().numpy())
        return _EVALUATOR.hard_pair_metrics(
            scores=np.concatenate(batches), query_words=validation_spoken
        )

    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mswc-hyperspotter-listwise-v2.pt"
    history = []
    best_rank = None
    started = time.perf_counter()
    training_rng = random.Random(seed + 2)
    candidate_count = 1 + hard_candidates + random_candidates
    for epoch in range(1, epochs + 1):
        model.train()
        if not unfreeze_audio_encoder:
            model.audio_encoder.eval()
        losses = []
        ranking_losses = []
        binary_losses = []
        margin_losses = []
        for _ in range(batches_per_epoch):
            indexes, _, candidates = sample_listwise_examples(
                words=training_word_list,
                indexes_by_word=indexes_by_word,
                hard_negatives=training_hard,
                count=audio_batch_size,
                hard_candidates=hard_candidates,
                random_candidates=random_candidates,
                rng=training_rng,
            )
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = listwise_logits(indexes, candidates)
                targets = torch.zeros(len(indexes), dtype=torch.long, device=torch_device)
                rank_loss = cross_entropy(logits, targets)
                labels = torch.zeros_like(logits)
                labels[:, 0] = 1.0
                absolute_loss = binary_loss(logits, labels)
                relative_loss = torch.relu(
                    ranking_margin - logits[:, :1] + logits[:, 1:]
                ).mean()
                loss = (
                    rank_loss
                    + binary_loss_weight * absolute_loss
                    + margin_loss_weight * relative_loss
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
            ranking_losses.append(float(rank_loss.detach().cpu()))
            binary_losses.append(float(absolute_loss.detach().cpu()))
            margin_losses.append(float(relative_loss.detach().cpu()))
        metrics = evaluate_validation()
        zero_false_recall = (
            float(metrics["true_pairs_accepted_at_zero_false_pairs"])
            / float(metrics["true_pairs"])
        )
        rank = (
            float(metrics["hard_candidate_top1_accuracy"]),
            float(metrics["pair_auc"]),
            -float(metrics["equal_error_rate"]),
            zero_false_recall,
        )
        selected = best_rank is None or rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.mswc-hyperspotter-listwise.v2",
                    "initial_checkpoint_sha256": _LOGMEL.sha256(
                        official_checkpoint_path
                    ),
                    "initializer_checkpoint_sha256": _LOGMEL.sha256(
                        initializer_checkpoint_path
                    ),
                    "feature_manifest_sha256": _LOGMEL.sha256(feature_manifest_path),
                    "upstream_commit": sources["hyperspotter_upstream_commit"],
                    "seed": seed,
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
            "mean_ranking_loss": float(np.mean(ranking_losses)),
            "mean_binary_loss": float(np.mean(binary_losses)),
            "mean_margin_loss": float(np.mean(margin_losses)),
            "validation": metrics,
            "zero_false_true_pair_recall": zero_false_recall,
            "checkpoint_selected": selected,
        }
        history.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    best_entry = next(
        entry for entry in history if entry["epoch"] == checkpoint["best_epoch"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-hyperspotter-listwise-training.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "spanish_mswc_internal_word_holdout_multi_negative_text_audio_ranking",
        "sources": {
            "feature_manifest_sha256": _LOGMEL.sha256(feature_manifest_path),
            "official_checkpoint_sha256": _LOGMEL.sha256(official_checkpoint_path),
            "initializer_checkpoint_sha256": _LOGMEL.sha256(initializer_checkpoint_path),
            "hyperspotter_upstream_commit": sources["hyperspotter_upstream_commit"],
        },
        "contract": {
            "seed": seed,
            "training_word_classes": len(training_words),
            "validation_word_classes": len(validation_words),
            "examples_per_word_available": contract["examples_per_class"],
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "audio_batch_size": audio_batch_size,
            "candidate_count": candidate_count,
            "hard_candidates": hard_candidates,
            "random_candidates": random_candidates,
            "hard_negative_neighbors": hard_negative_neighbors,
            "validation_examples": validation_examples,
            "validation_negative_candidates": validation_negative_candidates,
            "learning_rate": learning_rate,
            "binary_loss_weight": binary_loss_weight,
            "margin_loss_weight": margin_loss_weight,
            "ranking_margin": ranking_margin,
            "audio_encoder_frozen": not unfreeze_audio_encoder,
            "objective": "cross_entropy_plus_balanced_binary_and_pairwise_margin",
        },
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation": best_entry["validation"],
            "zero_false_true_pair_recall": best_entry[
                "zero_false_true_pair_recall"
            ],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _LOGMEL.sha256(checkpoint_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "research_v3_examples_scored": False,
        "official_test_audio_accessed": False,
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
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--initializer-checkpoint", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=9501)
    parser.add_argument("--validation-classes", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batches-per-epoch", type=int, default=100)
    parser.add_argument("--audio-batch-size", type=int, default=8)
    parser.add_argument("--hard-candidates", type=int, default=12)
    parser.add_argument("--random-candidates", type=int, default=4)
    parser.add_argument("--hard-negative-neighbors", type=int, default=32)
    parser.add_argument("--validation-examples", type=int, default=1600)
    parser.add_argument("--validation-negative-candidates", type=int, default=40)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--binary-loss-weight", type=float, default=0.25)
    parser.add_argument("--margin-loss-weight", type=float, default=0.25)
    parser.add_argument("--ranking-margin", type=float, default=1.0)
    parser.add_argument("--unfreeze-audio-encoder", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = train(
        feature_manifest_path=args.feature_manifest,
        hyperspotter_root=args.hyperspotter_root,
        hyperspotter_site_packages=args.hyperspotter_site_packages,
        official_checkpoint_path=args.official_checkpoint,
        initializer_checkpoint_path=args.initializer_checkpoint,
        output_directory=args.output_directory,
        seed=args.seed,
        validation_classes=args.validation_classes,
        epochs=args.epochs,
        batches_per_epoch=args.batches_per_epoch,
        audio_batch_size=args.audio_batch_size,
        hard_candidates=args.hard_candidates,
        random_candidates=args.random_candidates,
        hard_negative_neighbors=args.hard_negative_neighbors,
        validation_examples=args.validation_examples,
        validation_negative_candidates=args.validation_negative_candidates,
        learning_rate=args.learning_rate,
        binary_loss_weight=args.binary_loss_weight,
        margin_loss_weight=args.margin_loss_weight,
        ranking_margin=args.ranking_margin,
        unfreeze_audio_encoder=args.unfreeze_audio_encoder,
        device=args.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
