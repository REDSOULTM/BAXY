"""Distill the accepted cached teacher into the small HyperSpotter ranker."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
        raise RuntimeError(f"mswc_hyper_distill_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_HYPER = load_component(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1.py",
    "_baxy_mswc_hyper_distill_model_v3",
)
_TEACHER = load_component(
    "evaluate_mswc_spanish_calibrated_selector_reserved_v11.py",
    "_baxy_mswc_hyper_distill_teacher_v3",
)


def validation_rows(
    query_words: list[str], query_hashes: list[str], *, validation_per_word: int
) -> tuple[np.ndarray, np.ndarray]:
    if (
        not query_words
        or len(query_words) != len(query_hashes)
        or validation_per_word < 1
    ):
        raise ValueError("mswc_hyper_distill_split_invalid")
    by_word: dict[str, list[int]] = {}
    for index, word in enumerate(query_words):
        by_word.setdefault(word, []).append(index)
    training: list[int] = []
    validation: list[int] = []
    for word in sorted(by_word):
        indexes = sorted(by_word[word], key=lambda index: query_hashes[index])
        if len(indexes) <= validation_per_word:
            raise ValueError("mswc_hyper_distill_word_examples_invalid")
        training.extend(indexes[:-validation_per_word])
        validation.extend(indexes[-validation_per_word:])
    return (
        np.asarray(sorted(training), dtype=np.int64),
        np.asarray(sorted(validation), dtype=np.int64),
    )


def checkpoint_rank(metrics: dict[str, object]) -> tuple[float, ...]:
    zero_false_recall = float(metrics["true_pairs_accepted_at_zero_false_pairs"]) / float(
        metrics["true_pairs"]
    )
    return (
        float(metrics["hard_candidate_top1_accuracy"]),
        float(metrics["pair_auc"]),
        -float(metrics["equal_error_rate"]),
        zero_false_recall,
    )


def train(
    *,
    feature_manifest_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    initializer_checkpoint_path: Path,
    teacher_hyper_ctc_cache_path: Path,
    teacher_whisper_cache_path: Path,
    teacher_forced_alignment_cache_path: Path,
    teacher_shortlist_cache_path: Path,
    teacher_silence_prior_cache_path: Path,
    teacher_report_path: Path,
    output_directory: Path,
    epochs: int,
    audio_batch_size: int,
    learning_rate: float,
    validation_per_word: int,
    teacher_temperature: float,
    distillation_weight: float,
    binary_loss_weight: float,
    margin_loss_weight: float,
    ranking_margin: float,
    seed: int,
    unfreeze_audio_encoder: bool,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or audio_batch_size < 1
        or learning_rate <= 0.0
        or validation_per_word < 1
        or teacher_temperature <= 0.0
        or distillation_weight < 0.0
        or binary_loss_weight < 0.0
        or margin_loss_weight < 0.0
        or ranking_margin < 0.0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_hyper_distill_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    official_checkpoint_path = official_checkpoint_path.resolve(strict=True)
    initializer_checkpoint_path = initializer_checkpoint_path.resolve(strict=True)
    teacher_paths = {
        "hyper_ctc_cache": teacher_hyper_ctc_cache_path.resolve(strict=True),
        "whisper_cache": teacher_whisper_cache_path.resolve(strict=True),
        "forced_alignment_cache": teacher_forced_alignment_cache_path.resolve(
            strict=True
        ),
        "shortlist_cache": teacher_shortlist_cache_path.resolve(strict=True),
        "silence_prior_cache": teacher_silence_prior_cache_path.resolve(strict=True),
        "report": teacher_report_path.resolve(strict=True),
    }
    output_directory = output_directory.resolve()
    manifest = _HYPER._LOGMEL.read_object(feature_manifest_path)
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
        or contract.get("included_partitions")
        != ["open_keyword_enrollment", "open_keyword_query"]
    ):
        raise ValueError("mswc_hyper_distill_feature_boundary_invalid")
    records = []
    index_by_hash: dict[str, int] = {}
    for index, raw in enumerate(records_raw):
        if not isinstance(raw, dict):
            raise ValueError("mswc_hyper_distill_record_invalid")
        records.append(raw)
        audio_hash = str(raw["audio_sha256"])
        if audio_hash in index_by_hash:
            raise ValueError("mswc_hyper_distill_audio_duplicate")
        index_by_hash[audio_hash] = index
    teacher_report = _HYPER._LOGMEL.read_object(teacher_paths["report"])
    report_sources = teacher_report.get("sources")
    if (
        teacher_report.get("schema")
        != "baxy.mswc-spanish-calibrated-selector-tuning.v10"
        or teacher_report.get("accepted") is not True
        or teacher_report.get("research_reserved_examples_scored") is not False
        or not isinstance(report_sources, dict)
        or report_sources.get("hyper_ctc_cache_sha256")
        != _HYPER._LOGMEL.sha256(teacher_paths["hyper_ctc_cache"])
        or report_sources.get("whisper_cache_sha256")
        != _HYPER._LOGMEL.sha256(teacher_paths["whisper_cache"])
        or report_sources.get("forced_alignment_cache_sha256")
        != _HYPER._LOGMEL.sha256(teacher_paths["forced_alignment_cache"])
        or report_sources.get("shortlist_cache_sha256")
        != _HYPER._LOGMEL.sha256(teacher_paths["shortlist_cache"])
        or report_sources.get("silence_prior_cache_sha256")
        != _HYPER._LOGMEL.sha256(teacher_paths["silence_prior_cache"])
    ):
        raise ValueError("mswc_hyper_distill_teacher_boundary_invalid")
    bundle = _TEACHER.load_signal_bundle(
        hyper_ctc_cache_path=teacher_paths["hyper_ctc_cache"],
        whisper_cache_path=teacher_paths["whisper_cache"],
        forced_alignment_cache_path=teacher_paths["forced_alignment_cache"],
        shortlist_cache_path=teacher_paths["shortlist_cache"],
        silence_prior_cache_path=teacher_paths["silence_prior_cache"],
    )
    teacher_dataset = _TEACHER.build_selector_dataset(bundle)
    teacher_scores = np.asarray(
        teacher_dataset["calibrated_fusion"], dtype=np.float32
    )
    query_hashes = bundle["query_hashes"].astype(str).tolist()
    query_words = bundle["query_words"].astype(str).tolist()
    candidate_indexes = bundle["candidate_indexes"].astype(np.int64)
    class_names = bundle["class_names"].astype(str).tolist()
    query_feature_indexes = []
    for audio_hash, word in zip(query_hashes, query_words, strict=True):
        feature_index = index_by_hash.get(audio_hash)
        if feature_index is None:
            raise ValueError("mswc_hyper_distill_feature_alignment_missing")
        record = records[feature_index]
        if (
            record.get("partition") != "open_keyword_query"
            or str(record.get("class_name")) != word
        ):
            raise ValueError("mswc_hyper_distill_feature_alignment_invalid")
        query_feature_indexes.append(feature_index)
    if (
        teacher_scores.shape != candidate_indexes.shape
        or teacher_scores.shape != (2400, 41)
        or len(set(query_words)) != 400
    ):
        raise ValueError("mswc_hyper_distill_teacher_shape_invalid")
    training_rows, validation = validation_rows(
        query_words, query_hashes, validation_per_word=validation_per_word
    )
    feature_root = feature_manifest_path.parent
    feature_path = feature_root / str(files["logmel"])
    offset_path = feature_root / str(files["offsets"])
    if (
        _HYPER._LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _HYPER._LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_hyper_distill_feature_hash_invalid")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("mswc_hyper_distill_feature_shape_invalid")
    model, tokenizer, torch, torch_device = _HYPER.load_hyperspotter_model(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        initial_checkpoint_path=official_checkpoint_path,
        adapted_checkpoint_path=initializer_checkpoint_path,
        expected_upstream_commit=str(sources["hyperspotter_upstream_commit"]),
        device=device,
    )
    import torch.nn as nn

    for parameter in model.parameters():
        parameter.requires_grad = False
    trainable_modules = [
        model.text_encoder,
        model.embedding_2_ms,
        model.perceiver_classifier,
    ]
    if unfreeze_audio_encoder:
        trainable_modules.append(model.audio_encoder)
    for module in trainable_modules:
        for parameter in module.parameters():
            parameter.requires_grad = True
    trainable_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    if not trainable_parameters:
        raise ValueError("mswc_hyper_distill_trainable_parameters_missing")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.set_float32_matmul_precision("high")
    optimizer = torch.optim.AdamW(
        trainable_parameters, lr=learning_rate, weight_decay=1e-4
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    binary_loss = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(40.0, device=torch_device))
    class_token_ids = tokenizer(class_names)["input_ids"]
    class_token_lengths = torch.tensor(
        [len(values) for values in class_token_ids], dtype=torch.long
    )
    class_token_values = nn.utils.rnn.pad_sequence(
        [
            torch.tensor(values, dtype=torch.long, device=torch_device)
            for values in class_token_ids
        ],
        padding_value=tokenizer.pad_token_id,
        batch_first=True,
    )

    def feature_batch(rows: np.ndarray) -> tuple[object, object]:
        indexes = [query_feature_indexes[int(row)] for row in rows]
        lengths = [int(offsets[index + 1] - offsets[index]) for index in indexes]
        maximum = max(lengths)
        values = np.zeros((len(indexes), maximum, 80), dtype=np.float32)
        for batch_row, (index, length) in enumerate(zip(indexes, lengths, strict=True)):
            values[batch_row, :length] = features[
                int(offsets[index]) : int(offsets[index + 1])
            ]
        return (
            torch.from_numpy(values).to(torch_device),
            torch.tensor(lengths, dtype=torch.long, device=torch_device),
        )

    def logits_for(rows: np.ndarray) -> object:
        audio, audio_lengths = feature_batch(rows)
        selected = torch.from_numpy(candidate_indexes[rows])
        flat = selected.reshape(-1)
        text_weights = model.get_text_weights(
            class_token_values[flat.to(torch_device)], class_token_lengths[flat]
        )
        encoded, encoded_lengths = model.audio_encoder(
            audio.transpose(1, 2), audio_lengths
        )
        encoded = encoded[:, : int(encoded_lengths.max()), :]
        mask = (
            torch.arange(encoded.shape[1], device=torch_device)[None, :]
            < encoded_lengths[:, None]
        )
        width = selected.shape[1]
        return model.perceiver_classifier(
            encoded.repeat_interleave(width, dim=0),
            text_weights,
            mask=mask.repeat_interleave(width, dim=0),
        ).reshape(len(rows), width)

    def score(rows: np.ndarray) -> np.ndarray:
        model.eval()
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(rows), audio_batch_size):
                selected_rows = rows[start : start + audio_batch_size]
                with torch.autocast(
                    device_type=device, dtype=torch.float16, enabled=device == "cuda"
                ):
                    logits = logits_for(selected_rows)
                outputs.append(logits.float().cpu().numpy())
        return np.concatenate(outputs)

    def metrics(rows: np.ndarray, scores: np.ndarray) -> dict[str, object]:
        return _HYPER.hard_pair_metrics(
            scores=scores,
            query_words=[query_words[int(row)] for row in rows],
        )

    initializer_validation_scores = score(validation)
    initializer_validation = metrics(validation, initializer_validation_scores)
    teacher_validation = metrics(validation, teacher_scores[validation])
    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mswc-hyperspotter-teacher-distilled-v3.pt"
    history = []
    best_rank: tuple[float, ...] | None = None
    generator = np.random.default_rng(seed + 1)
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        if not unfreeze_audio_encoder:
            model.audio_encoder.eval()
        order = generator.permutation(training_rows)
        losses = []
        supervised_losses = []
        distillation_losses = []
        for start in range(0, len(order), audio_batch_size):
            rows = order[start : start + audio_batch_size]
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = logits_for(rows)
                targets = torch.zeros(len(rows), dtype=torch.long, device=torch_device)
                supervised = torch.nn.functional.cross_entropy(logits, targets)
                soft_targets = torch.softmax(
                    torch.from_numpy(teacher_scores[rows]).to(torch_device)
                    / teacher_temperature,
                    dim=1,
                )
                distilled = torch.nn.functional.kl_div(
                    torch.log_softmax(logits / teacher_temperature, dim=1),
                    soft_targets,
                    reduction="batchmean",
                ) * teacher_temperature**2
                labels = torch.zeros_like(logits)
                labels[:, 0] = 1.0
                absolute = binary_loss(logits, labels)
                relative = torch.relu(
                    ranking_margin - logits[:, :1] + logits[:, 1:]
                ).mean()
                loss = (
                    supervised
                    + distillation_weight * distilled
                    + binary_loss_weight * absolute
                    + margin_loss_weight * relative
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
            supervised_losses.append(float(supervised.detach().cpu()))
            distillation_losses.append(float(distilled.detach().cpu()))
        validation_scores = score(validation)
        validation_metrics = metrics(validation, validation_scores)
        rank = checkpoint_rank(validation_metrics)
        selected = best_rank is None or rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.mswc-hyperspotter-teacher-distilled.v3",
                    "initial_checkpoint_sha256": _HYPER._LOGMEL.sha256(
                        official_checkpoint_path
                    ),
                    "initializer_checkpoint_sha256": _HYPER._LOGMEL.sha256(
                        initializer_checkpoint_path
                    ),
                    "feature_manifest_sha256": _HYPER._LOGMEL.sha256(
                        feature_manifest_path
                    ),
                    "teacher_report_sha256": _HYPER._LOGMEL.sha256(
                        teacher_paths["report"]
                    ),
                    "upstream_commit": sources["hyperspotter_upstream_commit"],
                    "seed": seed,
                    "best_epoch": epoch,
                    "model_state_dict": {
                        name: value.detach().cpu()
                        for name, value in model.state_dict().items()
                    },
                },
                checkpoint_path,
            )
        entry = {
            "epoch": epoch,
            "mean_loss": float(np.mean(losses)),
            "mean_supervised_loss": float(np.mean(supervised_losses)),
            "mean_distillation_loss": float(np.mean(distillation_losses)),
            "validation": validation_metrics,
            "checkpoint_selected": selected,
        }
        history.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    best_entry = next(
        entry for entry in history if entry["epoch"] == checkpoint["best_epoch"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-hyperspotter-teacher-distillation-training.v3",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "tuning_only_teacher_distillation_with_audio_disjoint_validation",
        "sources": {
            "feature_manifest_sha256": _HYPER._LOGMEL.sha256(feature_manifest_path),
            "official_checkpoint_sha256": _HYPER._LOGMEL.sha256(
                official_checkpoint_path
            ),
            "initializer_checkpoint_sha256": _HYPER._LOGMEL.sha256(
                initializer_checkpoint_path
            ),
            **{
                f"teacher_{name}_sha256": _HYPER._LOGMEL.sha256(path)
                for name, path in teacher_paths.items()
            },
        },
        "contract": {
            "word_classes": len(set(query_words)),
            "training_queries": len(training_rows),
            "validation_queries": len(validation),
            "validation_examples_per_word": validation_per_word,
            "candidate_count": teacher_scores.shape[1],
            "epochs": epochs,
            "audio_batch_size": audio_batch_size,
            "learning_rate": learning_rate,
            "teacher_temperature": teacher_temperature,
            "distillation_weight": distillation_weight,
            "binary_loss_weight": binary_loss_weight,
            "margin_loss_weight": margin_loss_weight,
            "ranking_margin": ranking_margin,
            "audio_encoder_frozen": not unfreeze_audio_encoder,
            "selection_rank": "top1_then_auc_then_negative_eer_then_zero_false_recall",
        },
        "initializer_validation": initializer_validation,
        "teacher_validation": teacher_validation,
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation": best_entry["validation"],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _HYPER._LOGMEL.sha256(checkpoint_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "research_tuning_examples_scored": True,
        "research_reserved_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
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
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--initializer-checkpoint", type=Path, required=True)
    parser.add_argument("--teacher-hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--teacher-whisper-cache", type=Path, required=True)
    parser.add_argument("--teacher-forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--teacher-shortlist-cache", type=Path, required=True)
    parser.add_argument("--teacher-silence-prior-cache", type=Path, required=True)
    parser.add_argument("--teacher-report", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--audio-batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--validation-per-word", type=int, default=2)
    parser.add_argument("--teacher-temperature", type=float, default=2.0)
    parser.add_argument("--distillation-weight", type=float, default=0.5)
    parser.add_argument("--binary-loss-weight", type=float, default=0.10)
    parser.add_argument("--margin-loss-weight", type=float, default=0.25)
    parser.add_argument("--ranking-margin", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=15301)
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
        teacher_hyper_ctc_cache_path=args.teacher_hyper_ctc_cache,
        teacher_whisper_cache_path=args.teacher_whisper_cache,
        teacher_forced_alignment_cache_path=args.teacher_forced_alignment_cache,
        teacher_shortlist_cache_path=args.teacher_shortlist_cache,
        teacher_silence_prior_cache_path=args.teacher_silence_prior_cache,
        teacher_report_path=args.teacher_report,
        output_directory=args.output_directory,
        epochs=args.epochs,
        audio_batch_size=args.audio_batch_size,
        learning_rate=args.learning_rate,
        validation_per_word=args.validation_per_word,
        teacher_temperature=args.teacher_temperature,
        distillation_weight=args.distillation_weight,
        binary_loss_weight=args.binary_loss_weight,
        margin_loss_weight=args.margin_loss_weight,
        ranking_margin=args.ranking_margin,
        seed=args.seed,
        unfreeze_audio_encoder=args.unfreeze_audio_encoder,
        device=args.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
