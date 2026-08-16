"""Distill the accepted teacher into a tiny temporal-phoneme CTC matcher."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import random
import sys
import time

import numpy as np


INPUT_CHANNELS = 8


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_ctc_cnn_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TEACHER = load_component(
    "evaluate_mswc_spanish_calibrated_selector_reserved_v11.py",
    "_baxy_mswc_ctc_cnn_teacher_v15",
)
_SPLIT = load_component(
    "train_mswc_hyperspotter_teacher_distillation_v3.py",
    "_baxy_mswc_ctc_cnn_split_v15",
)
_TEMPORAL = load_component(
    "build_mswc_spanish_ctc_temporal_features_v13.py",
    "_baxy_mswc_ctc_cnn_temporal_v15",
)


def make_model(torch: object, *, manual_features: int) -> object:
    nn = torch.nn

    class ResidualDepthwise(nn.Module):
        def __init__(self, channels: int) -> None:
            super().__init__()
            self.depthwise = nn.Conv2d(
                channels, channels, kernel_size=3, padding=1, groups=channels
            )
            self.pointwise = nn.Conv2d(channels, channels, kernel_size=1)
            self.norm = nn.BatchNorm2d(channels)
            self.activation = nn.GELU()

        def forward(self, values: object) -> object:
            residual = values
            values = self.depthwise(values)
            values = self.pointwise(values)
            values = self.norm(values)
            return self.activation(values + residual)

    class TemporalPhonemeMatcher(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.stem = nn.Sequential(
                nn.Conv2d(INPUT_CHANNELS, 32, kernel_size=3, padding=1),
                nn.BatchNorm2d(32),
                nn.GELU(),
            )
            self.blocks = nn.Sequential(
                ResidualDepthwise(32),
                nn.Conv2d(32, 48, kernel_size=3, stride=(2, 1), padding=1),
                nn.BatchNorm2d(48),
                nn.GELU(),
                ResidualDepthwise(48),
                nn.Conv2d(48, 64, kernel_size=3, stride=(2, 1), padding=1),
                nn.BatchNorm2d(64),
                nn.GELU(),
                ResidualDepthwise(64),
            )
            self.output = nn.Sequential(
                nn.Linear(128 + manual_features, 96),
                nn.GELU(),
                nn.Dropout(0.10),
                nn.Linear(96, 1),
            )

        def forward(self, matrices: object, manual: object) -> object:
            hidden = self.blocks(self.stem(matrices))
            average = torch.mean(hidden, dim=(2, 3))
            maximum = torch.amax(hidden, dim=(2, 3))
            return self.output(torch.cat([average, maximum, manual], dim=1)).squeeze(1)

    return TemporalPhonemeMatcher()


def fixed_log_probabilities(values: np.ndarray, maximum_frames: int) -> np.ndarray:
    source = np.asarray(values, dtype=np.float32)
    if source.ndim != 2 or not len(source) or maximum_frames < 2:
        raise ValueError("mswc_ctc_cnn_log_probabilities_invalid")
    if len(source) <= maximum_frames:
        return source
    start = (len(source) - maximum_frames) // 2
    return source[start : start + maximum_frames]


def pair_matrix(
    *,
    log_probabilities: np.ndarray,
    sequence: list[int],
    blank_id: int,
    maximum_frames: int,
    maximum_tokens: int,
) -> np.ndarray:
    values = fixed_log_probabilities(log_probabilities, maximum_frames)
    tokens = [int(token) for token in sequence[:maximum_tokens]]
    if (
        not tokens
        or any(token < 0 or token >= values.shape[1] for token in tokens)
        or not 0 <= blank_id < values.shape[1]
    ):
        raise ValueError("mswc_ctc_cnn_sequence_invalid")
    frames = len(values)
    length = len(tokens)
    output = np.zeros(
        (INPUT_CHANNELS, maximum_frames, maximum_tokens), dtype=np.float32
    )
    token_values = values[:, tokens]
    blank = values[:, blank_id : blank_id + 1]
    frame_maximum = np.max(values, axis=1, keepdims=True)
    probabilities = np.exp(values)
    entropy = -np.sum(probabilities * values, axis=1, keepdims=True)
    mask = np.ones((frames, length), dtype=np.float32)
    output[0, :frames, :length] = np.clip(token_values, -20.0, 0.0) / 10.0
    output[1, :frames, :length] = np.clip(token_values - blank, -20.0, 20.0) / 10.0
    output[2, :frames, :length] = np.clip(
        token_values - frame_maximum, -20.0, 0.0
    ) / 10.0
    output[3, :frames, :length] = np.linspace(0.0, 1.0, frames)[:, None]
    output[4, :frames, :length] = np.linspace(0.0, 1.0, length)[None, :]
    output[5, :frames, :length] = np.broadcast_to(
        np.clip(blank, -20.0, 0.0) / 10.0, (frames, length)
    )
    output[6, :frames, :length] = np.broadcast_to(entropy / 4.0, (frames, length))
    output[7, :frames, :length] = mask
    if not np.isfinite(output).all():
        raise ValueError("mswc_ctc_cnn_pair_matrix_invalid")
    return output


def train(
    *,
    ctc_feature_manifest_path: Path,
    temporal_feature_cache_path: Path,
    teacher_hyper_ctc_cache_path: Path,
    teacher_whisper_cache_path: Path,
    teacher_forced_alignment_cache_path: Path,
    teacher_shortlist_cache_path: Path,
    teacher_silence_prior_cache_path: Path,
    teacher_report_path: Path,
    tokenizer_directory: Path,
    phonemizer_site_packages: Path,
    output_directory: Path,
    epochs: int,
    query_batch_size: int,
    learning_rate: float,
    validation_per_word: int,
    teacher_temperature: float,
    distillation_weight: float,
    maximum_frames: int,
    maximum_tokens: int,
    seed: int,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or query_batch_size < 1
        or learning_rate <= 0.0
        or validation_per_word < 1
        or teacher_temperature <= 0.0
        or distillation_weight < 0.0
        or maximum_frames < 8
        or maximum_tokens < 4
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_ctc_cnn_schedule_invalid")
    ctc_feature_manifest_path = ctc_feature_manifest_path.resolve(strict=True)
    temporal_feature_cache_path = temporal_feature_cache_path.resolve(strict=True)
    tokenizer_directory = tokenizer_directory.resolve(strict=True)
    phonemizer_site_packages = phonemizer_site_packages.resolve(strict=True)
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
    manifest = _TEMPORAL._SEQUENCE.read_object(ctc_feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    sources = manifest.get("sources")
    contract = manifest.get("contract")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-sequence-features.v3"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(sources, dict)
        or not isinstance(contract, dict)
    ):
        raise ValueError("mswc_ctc_cnn_feature_boundary_invalid")
    records = []
    index_by_hash: dict[str, int] = {}
    for index, raw in enumerate(records_raw):
        if not isinstance(raw, dict):
            raise ValueError("mswc_ctc_cnn_record_invalid")
        records.append(raw)
        audio_hash = str(raw["audio_sha256"])
        if audio_hash in index_by_hash:
            raise ValueError("mswc_ctc_cnn_audio_duplicate")
        index_by_hash[audio_hash] = index
    teacher_report = _TEMPORAL._SEQUENCE.read_object(teacher_paths["report"])
    report_sources = teacher_report.get("sources")
    if (
        teacher_report.get("schema")
        != "baxy.mswc-spanish-calibrated-selector-tuning.v10"
        or teacher_report.get("accepted") is not True
        or teacher_report.get("research_reserved_examples_scored") is not False
        or not isinstance(report_sources, dict)
        or any(
            report_sources.get(report_name)
            != _TEMPORAL._HASH.sha256(teacher_paths[path_name])
            for path_name, report_name in {
                "hyper_ctc_cache": "hyper_ctc_cache_sha256",
                "whisper_cache": "whisper_cache_sha256",
                "forced_alignment_cache": "forced_alignment_cache_sha256",
                "shortlist_cache": "shortlist_cache_sha256",
                "silence_prior_cache": "silence_prior_cache_sha256",
            }.items()
        )
    ):
        raise ValueError("mswc_ctc_cnn_teacher_boundary_invalid")
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
    query_hashes = bundle["query_hashes"].astype(str)
    query_words = bundle["query_words"].astype(str)
    candidate_indexes = bundle["candidate_indexes"].astype(np.int64)
    class_names = bundle["class_names"].astype(str)
    with np.load(temporal_feature_cache_path, allow_pickle=False) as temporal_cache:
        if (
            temporal_cache["schema"].tolist()
            != ["baxy.mswc-ctc-temporal-features.v1"]
            or not np.array_equal(
                temporal_cache["query_audio_sha256"].astype(str), query_hashes
            )
            or not np.array_equal(
                temporal_cache["query_words"].astype(str), query_words
            )
            or not np.array_equal(
                temporal_cache["candidate_words"].astype(str),
                bundle["candidate_words"].astype(str),
            )
            or temporal_cache["feature_names"].astype(str).tolist()
            != list(_TEMPORAL.FEATURE_NAMES)
        ):
            raise ValueError("mswc_ctc_cnn_temporal_alignment_invalid")
        manual_features = temporal_cache["features"].astype(np.float32)
    if (
        teacher_scores.shape != (2400, 41)
        or manual_features.shape
        != (2400, 41, len(_TEMPORAL.FEATURE_NAMES))
        or len(set(query_words.tolist())) != 400
    ):
        raise ValueError("mswc_ctc_cnn_shape_invalid")
    query_record_indexes = []
    for audio_hash, word in zip(query_hashes, query_words, strict=True):
        record_index = index_by_hash.get(str(audio_hash))
        if record_index is None:
            raise ValueError("mswc_ctc_cnn_audio_missing")
        record = records[record_index]
        if (
            record.get("partition") != "open_keyword_query"
            or str(record.get("class_name")) != str(word)
        ):
            raise ValueError("mswc_ctc_cnn_audio_alignment_invalid")
        query_record_indexes.append(record_index)
    offset_path = ctc_feature_manifest_path.parent / str(files["offsets"])
    descriptor = files.get("ctc_log_probabilities")
    if (
        not isinstance(descriptor, dict)
        or _TEMPORAL._HASH.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_ctc_cnn_offset_invalid")
    probability_path = ctc_feature_manifest_path.parent / str(descriptor["path"])
    if _TEMPORAL._HASH.sha256(probability_path) != descriptor.get("sha256"):
        raise ValueError("mswc_ctc_cnn_probability_hash_invalid")
    offsets = np.load(offset_path)
    log_probabilities = np.load(probability_path, mmap_mode="r")
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(log_probabilities):
        raise ValueError("mswc_ctc_cnn_probability_shape_invalid")
    if _TEMPORAL._HASH.sha256(tokenizer_directory / "vocab.json") != sources.get(
        "model_vocabulary_sha256"
    ):
        raise ValueError("mswc_ctc_cnn_vocabulary_invalid")
    if str(phonemizer_site_packages) not in sys.path:
        sys.path.append(str(phonemizer_site_packages))
    from audit_voxcpm2_gguf_pilot import configure_espeak_backend

    if configure_espeak_backend() is None:
        raise ValueError("mswc_ctc_cnn_espeak_unavailable")
    from transformers import Wav2Vec2PhonemeCTCTokenizer

    tokenizer = Wav2Vec2PhonemeCTCTokenizer.from_pretrained(
        str(tokenizer_directory),
        local_files_only=True,
        phonemizer_lang="es",
    )
    sequences = [
        [int(token) for token in values]
        for values in tokenizer(class_names.tolist())["input_ids"]
    ]
    if max(map(len, sequences)) > maximum_tokens:
        raise ValueError("mswc_ctc_cnn_maximum_tokens_insufficient")
    blank_id = int(contract["ctc_blank_id"])
    training_rows, validation_rows = _SPLIT.validation_rows(
        query_words.tolist(),
        query_hashes.tolist(),
        validation_per_word=validation_per_word,
    )
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_ctc_cnn_cuda_unavailable")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.set_float32_matmul_precision("high")
    torch_device = torch.device(device)
    model = make_model(torch, manual_features=manual_features.shape[2]).to(torch_device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")

    def matrices_for(rows: np.ndarray) -> tuple[object, object]:
        matrices = []
        manual = []
        for query_row in rows:
            record_index = query_record_indexes[int(query_row)]
            start = int(offsets[record_index])
            end = int(offsets[record_index + 1])
            query_values = np.asarray(log_probabilities[start:end], dtype=np.float32)
            for candidate_index in candidate_indexes[int(query_row)]:
                matrices.append(
                    pair_matrix(
                        log_probabilities=query_values,
                        sequence=sequences[int(candidate_index)],
                        blank_id=blank_id,
                        maximum_frames=maximum_frames,
                        maximum_tokens=maximum_tokens,
                    )
                )
            manual.append(manual_features[int(query_row)])
        return (
            torch.from_numpy(np.stack(matrices)).to(torch_device),
            torch.from_numpy(np.concatenate(manual, axis=0)).to(torch_device),
        )

    def logits_for(rows: np.ndarray) -> object:
        matrices, manual = matrices_for(rows)
        return model(matrices, manual).reshape(len(rows), 41)

    def score(rows: np.ndarray) -> np.ndarray:
        model.eval()
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(rows), query_batch_size):
                selected = rows[start : start + query_batch_size]
                with torch.autocast(
                    device_type=device, dtype=torch.float16, enabled=device == "cuda"
                ):
                    outputs.append(logits_for(selected).float().cpu().numpy())
        return np.concatenate(outputs)

    def metrics(rows: np.ndarray, values: np.ndarray) -> dict[str, object]:
        return _TEACHER._TUNING._FUSION._HYPER.hard_pair_metrics(
            scores=values,
            query_words=[str(query_words[int(row)]) for row in rows],
        )

    teacher_validation = metrics(validation_rows, teacher_scores[validation_rows])
    ctc_validation = metrics(
        validation_rows, bundle["ctc_scores"][validation_rows]
    )
    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mswc-ctc-alignment-cnn-distilled-v15.pt"
    generator = np.random.default_rng(seed + 1)
    history = []
    best_rank: tuple[float, ...] | None = None
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        order = generator.permutation(training_rows)
        losses = []
        supervised_losses = []
        distillation_losses = []
        for start in range(0, len(order), query_batch_size):
            rows = order[start : start + query_batch_size]
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = logits_for(rows)
                labels = torch.zeros(len(rows), dtype=torch.long, device=torch_device)
                supervised = torch.nn.functional.cross_entropy(logits, labels)
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
                loss = supervised + distillation_weight * distilled
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
            supervised_losses.append(float(supervised.detach().cpu()))
            distillation_losses.append(float(distilled.detach().cpu()))
        validation_scores = score(validation_rows)
        validation_metrics = metrics(validation_rows, validation_scores)
        rank = _SPLIT.checkpoint_rank(validation_metrics)
        selected = best_rank is None or rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.mswc-ctc-alignment-cnn-distilled.v15",
                    "state_dict": {
                        name: value.detach().cpu()
                        for name, value in model.state_dict().items()
                    },
                    "manual_feature_names": list(_TEMPORAL.FEATURE_NAMES),
                    "maximum_frames": maximum_frames,
                    "maximum_tokens": maximum_tokens,
                    "input_channels": INPUT_CHANNELS,
                    "seed": seed,
                    "best_epoch": epoch,
                    "ctc_feature_manifest_sha256": _TEMPORAL._HASH.sha256(
                        ctc_feature_manifest_path
                    ),
                    "teacher_report_sha256": _TEMPORAL._HASH.sha256(
                        teacher_paths["report"]
                    ),
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
        "schema": "baxy.mswc-ctc-alignment-cnn-distillation-training.v15",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "tuning_only_temporal_phoneme_teacher_distillation",
        "sources": {
            "ctc_feature_manifest_sha256": _TEMPORAL._HASH.sha256(
                ctc_feature_manifest_path
            ),
            "temporal_feature_cache_sha256": _TEMPORAL._HASH.sha256(
                temporal_feature_cache_path
            ),
            **{
                f"teacher_{name}_sha256": _TEMPORAL._HASH.sha256(path)
                for name, path in teacher_paths.items()
            },
            "tokenizer_vocabulary_sha256": _TEMPORAL._HASH.sha256(
                tokenizer_directory / "vocab.json"
            ),
        },
        "contract": {
            "architecture": "depthwise_residual_2d_cnn_over_time_by_phoneme_matrix",
            "parameter_count": parameter_count,
            "input_channels": INPUT_CHANNELS,
            "maximum_frames": maximum_frames,
            "maximum_tokens": maximum_tokens,
            "manual_feature_names": list(_TEMPORAL.FEATURE_NAMES),
            "word_classes": len(set(query_words.tolist())),
            "training_queries": len(training_rows),
            "validation_queries": len(validation_rows),
            "validation_examples_per_word": validation_per_word,
            "epochs": epochs,
            "query_batch_size": query_batch_size,
            "learning_rate": learning_rate,
            "teacher_temperature": teacher_temperature,
            "distillation_weight": distillation_weight,
            "selection_rank": "top1_then_auc_then_negative_eer_then_zero_false_recall",
        },
        "ctc_validation": ctc_validation,
        "teacher_validation": teacher_validation,
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation": best_entry["validation"],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _TEMPORAL._HASH.sha256(checkpoint_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "research_tuning_examples_scored": True,
        "research_reserved_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    (output_directory / "training.report.v15.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ctc-feature-manifest", type=Path, required=True)
    parser.add_argument("--temporal-feature-cache", type=Path, required=True)
    parser.add_argument("--teacher-hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--teacher-whisper-cache", type=Path, required=True)
    parser.add_argument("--teacher-forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--teacher-shortlist-cache", type=Path, required=True)
    parser.add_argument("--teacher-silence-prior-cache", type=Path, required=True)
    parser.add_argument("--teacher-report", type=Path, required=True)
    parser.add_argument("--tokenizer-directory", type=Path, required=True)
    parser.add_argument("--phonemizer-site-packages", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--query-batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--validation-per-word", type=int, default=2)
    parser.add_argument("--teacher-temperature", type=float, default=2.0)
    parser.add_argument("--distillation-weight", type=float, default=0.5)
    parser.add_argument("--maximum-frames", type=int, default=100)
    parser.add_argument("--maximum-tokens", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20301)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = train(
        ctc_feature_manifest_path=args.ctc_feature_manifest,
        temporal_feature_cache_path=args.temporal_feature_cache,
        teacher_hyper_ctc_cache_path=args.teacher_hyper_ctc_cache,
        teacher_whisper_cache_path=args.teacher_whisper_cache,
        teacher_forced_alignment_cache_path=args.teacher_forced_alignment_cache,
        teacher_shortlist_cache_path=args.teacher_shortlist_cache,
        teacher_silence_prior_cache_path=args.teacher_silence_prior_cache,
        teacher_report_path=args.teacher_report,
        tokenizer_directory=args.tokenizer_directory,
        phonemizer_site_packages=args.phonemizer_site_packages,
        output_directory=args.output_directory,
        epochs=args.epochs,
        query_batch_size=args.query_batch_size,
        learning_rate=args.learning_rate,
        validation_per_word=args.validation_per_word,
        teacher_temperature=args.teacher_temperature,
        distillation_weight=args.distillation_weight,
        maximum_frames=args.maximum_frames,
        maximum_tokens=args.maximum_tokens,
        seed=args.seed,
        device=args.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
