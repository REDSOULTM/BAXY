"""Evaluate adapted HyperSpotter on disjoint train-split Spanish research words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.machinery
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import types

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_hyperspotter_tuning_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LOGMEL = load_component(
    "extract_mswc_hyperspotter_logmel_v1.py",
    "_baxy_hyperspotter_tuning_logmel_v1",
)
_SEQUENCE = load_component(
    "evaluate_mswc_spanish_qbye_sequence_tuning_v3.py",
    "_baxy_hyperspotter_tuning_split_v1",
)
_PAIR = load_component(
    "train_mswc_spanish_qbye_similarity_cnn_v4.py",
    "_baxy_hyperspotter_tuning_pairs_v1",
)


def candidate_matrix(
    *,
    query_words: list[str],
    class_names: list[str],
    hard_negatives: dict[str, list[str]],
    negative_candidates: int,
) -> np.ndarray:
    if negative_candidates < 1:
        raise ValueError("mswc_hyperspotter_tuning_candidates_invalid")
    class_to_index = {name: index for index, name in enumerate(class_names)}
    result = np.empty(
        (len(query_words), negative_candidates + 1), dtype=np.int64
    )
    for row, word in enumerate(query_words):
        candidates = hard_negatives.get(word)
        if word not in class_to_index or candidates is None or len(candidates) < negative_candidates:
            raise ValueError("mswc_hyperspotter_tuning_candidate_word_invalid")
        selected = [word, *candidates[:negative_candidates]]
        if len(set(selected)) != len(selected):
            raise ValueError("mswc_hyperspotter_tuning_candidate_duplicate")
        result[row] = [class_to_index[name] for name in selected]
    return result


def binary_auc_eer(
    *, targets: np.ndarray, scores: np.ndarray
) -> tuple[float, float, float]:
    labels = np.asarray(targets, dtype=np.int64)
    values = np.asarray(scores, dtype=np.float64)
    if (
        labels.shape != values.shape
        or set(labels.tolist()) != {0, 1}
        or not np.isfinite(values).all()
    ):
        raise ValueError("mswc_hyperspotter_tuning_binary_metrics_invalid")
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    sorted_labels = labels[order]
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and sorted_values[stop] == sorted_values[start]:
            stop += 1
        ranks[start:stop] = (start + 1 + stop) / 2.0
        start = stop
    positives = int(labels.sum())
    negatives = len(labels) - positives
    positive_rank_sum = float(ranks[sorted_labels == 1].sum())
    auc = (
        positive_rank_sum - positives * (positives + 1) / 2.0
    ) / (positives * negatives)

    descending = np.argsort(-values, kind="mergesort")
    descending_values = values[descending]
    descending_labels = labels[descending]
    cumulative_positive = np.cumsum(descending_labels)
    cumulative_negative = np.cumsum(1 - descending_labels)
    group_ends = np.flatnonzero(
        np.r_[descending_values[1:] != descending_values[:-1], True]
    )
    true_positive_rate = np.r_[
        0.0, cumulative_positive[group_ends] / positives
    ]
    false_positive_rate = np.r_[
        0.0, cumulative_negative[group_ends] / negatives
    ]
    thresholds = np.r_[np.inf, descending_values[group_ends]]
    false_negative_rate = 1.0 - true_positive_rate
    equal_index = int(
        np.argmin(np.abs(false_positive_rate - false_negative_rate))
    )
    eer = float(
        (false_positive_rate[equal_index] + false_negative_rate[equal_index])
        / 2.0
    )
    return float(auc), eer, float(thresholds[equal_index])


def hard_pair_metrics(
    *, scores: np.ndarray, query_words: list[str]
) -> dict[str, object]:
    values = np.asarray(scores, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[0] != len(query_words)
        or values.shape[1] < 2
        or not np.isfinite(values).all()
    ):
        raise ValueError("mswc_hyperspotter_tuning_scores_invalid")
    positive = values[:, 0]
    negative = values[:, 1:]
    maximum_negative = np.max(negative, axis=1)
    margins = positive - maximum_negative
    labels = np.concatenate(
        (
            np.ones(len(positive), dtype=np.int64),
            np.zeros(negative.size, dtype=np.int64),
        )
    )
    flat_scores = np.concatenate((positive, negative.reshape(-1)))
    pair_auc, equal_error_rate, equal_error_threshold = binary_auc_eer(
        targets=labels, scores=flat_scores
    )
    zero_false_threshold = float(np.nextafter(np.max(negative), math.inf))
    per_word = []
    for word in sorted(set(query_words)):
        mask = np.asarray([value == word for value in query_words], dtype=np.bool_)
        per_word.append(float(np.mean(margins[mask] > 0.0)))
    return {
        "query_audio": len(query_words),
        "hard_negative_pairs": int(negative.size),
        "hard_candidate_top1_accuracy": float(np.mean(margins > 0.0)),
        "macro_word_hard_candidate_top1_accuracy": float(np.mean(per_word)),
        "pair_auc": pair_auc,
        "equal_error_rate": equal_error_rate,
        "equal_error_threshold": equal_error_threshold,
        "accuracy_at_zero_logit": float(np.mean((flat_scores >= 0.0) == labels)),
        "positive_recall_at_zero_logit": float(np.mean(positive >= 0.0)),
        "hard_negative_rejection_at_zero_logit": float(np.mean(negative < 0.0)),
        "mean_true_minus_maximum_hard_negative_margin": float(np.mean(margins)),
        "median_true_minus_maximum_hard_negative_margin": float(np.median(margins)),
        "positive_margin_queries": int(np.count_nonzero(margins > 0.0)),
        "zero_false_pair_threshold": zero_false_threshold,
        "true_pairs_accepted_at_zero_false_pairs": int(
            np.count_nonzero(positive >= zero_false_threshold)
        ),
        "true_pairs": len(positive),
    }


def load_hyperspotter_model(
    *,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    initial_checkpoint_path: Path,
    adapted_checkpoint_path: Path,
    expected_upstream_commit: str,
    device: str,
) -> tuple[object, object, object, object]:
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_hyperspotter_tuning_cuda_unavailable")
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
        # torchmetrics treats pandas as optional. Mask the incompatible pandas
        # wheel bundled by the upstream CPU environment while importing its
        # Lightning classes into the current CUDA/NumPy runtime.
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
            str(initial_checkpoint_path), map_location="cpu"
        )
    finally:
        torch.load = original_torch_load
        os.chdir(previous_directory)
    checkpoint = torch.load(
        adapted_checkpoint_path, map_location="cpu", weights_only=False
    )
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema")
        not in {
            "baxy.mswc-hyperspotter-spanish.v1",
            "baxy.mswc-hyperspotter-listwise.v2",
        }
        or checkpoint.get("initial_checkpoint_sha256")
        != _LOGMEL.sha256(initial_checkpoint_path)
        or checkpoint.get("upstream_commit") != expected_upstream_commit
        or not isinstance(checkpoint.get("model_state_dict"), dict)
    ):
        raise ValueError("mswc_hyperspotter_tuning_checkpoint_invalid")
    model = lightning_model.model
    model.load_state_dict(checkpoint["model_state_dict"])
    torch_device = torch.device(device)
    model = model.to(torch_device)
    model.eval()
    return model, lightning_model.tokenizer, torch, torch_device


def score_hyperspotter_candidates(
    *,
    model: object,
    tokenizer: object,
    torch: object,
    torch_device: object,
    features: np.ndarray,
    offsets: np.ndarray,
    query_indexes: list[int],
    candidate_indexes: np.ndarray,
    class_names: list[str],
    prediction_batch_size: int,
    device: str,
    progress_label: str = "HYPERSPOTTER_TUNING",
) -> np.ndarray:
    import torch.nn as nn

    keyword_ids = tokenizer(class_names)["input_ids"]
    keyword_lengths = torch.tensor(
        [len(value) for value in keyword_ids], dtype=torch.long
    )
    keyword_values = nn.utils.rnn.pad_sequence(
        [
            torch.tensor(value, dtype=torch.long, device=torch_device)
            for value in keyword_ids
        ],
        padding_value=tokenizer.pad_token_id,
        batch_first=True,
    )
    with torch.inference_mode():
        text_weights = model.get_text_weights(keyword_values, keyword_lengths)

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

    score_batches = []
    with torch.inference_mode():
        for start in range(0, len(query_indexes), prediction_batch_size):
            stop = min(start + prediction_batch_size, len(query_indexes))
            audio, audio_lengths = feature_batch(query_indexes[start:stop])
            batch_candidates = torch.from_numpy(
                candidate_indexes[start:stop]
            ).to(torch_device)
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                encoded, encoded_lengths = model.audio_encoder(
                    audio.transpose(1, 2), audio_lengths
                )
                encoded = encoded[:, : int(encoded_lengths.max()), :]
                mask = (
                    torch.arange(encoded.shape[1], device=torch_device)[None, :]
                    < encoded_lengths[:, None]
                )
                candidate_count = batch_candidates.shape[1]
                paired_audio = encoded.repeat_interleave(candidate_count, dim=0)
                paired_mask = mask.repeat_interleave(candidate_count, dim=0)
                paired_weights = text_weights[batch_candidates.reshape(-1)]
                logits = model.perceiver_classifier(
                    paired_audio, paired_weights, mask=paired_mask
                ).reshape(stop - start, candidate_count)
            score_batches.append(logits.float().cpu().numpy())
            if stop % 400 == 0 or stop == len(query_indexes):
                print(f"{progress_label}|{stop}/{len(query_indexes)}", flush=True)
    return np.concatenate(score_batches)


def evaluate(
    *,
    feature_manifest_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    initial_checkpoint_path: Path,
    adapted_checkpoint_path: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    hard_negative_candidates: int,
    prediction_batch_size: int,
    device: str,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or tuning_classes < 2
        or hard_negative_candidates < 1
        or prediction_batch_size < 1
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_hyperspotter_tuning_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    initial_checkpoint_path = initial_checkpoint_path.resolve(strict=True)
    adapted_checkpoint_path = adapted_checkpoint_path.resolve(strict=True)
    output_path = output_path.resolve()
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
        or contract.get("included_partitions")
        != ["open_keyword_enrollment", "open_keyword_query"]
    ):
        raise ValueError("mswc_hyperspotter_tuning_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_hyperspotter_tuning_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _SEQUENCE.split_research_words(
        words, seed=split_seed, tuning_classes=tuning_classes
    )
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record.get("partition") == "open_keyword_query"
        and str(record["class_name"]) in tuning_words
    ]
    query_words = [str(records[index]["class_name"]) for index in query_indexes]
    if (
        len(query_indexes) != tuning_classes * 6
        or set(query_words) != tuning_words
        or any(
            sum(word == candidate for candidate in query_words) != 6
            for word in tuning_words
        )
    ):
        raise ValueError("mswc_hyperspotter_tuning_partition_invalid")
    class_names = sorted(tuning_words)
    hard_negatives = _PAIR.hard_negative_map(
        tuning_words, neighbors=hard_negative_candidates
    )
    candidates = candidate_matrix(
        query_words=query_words,
        class_names=class_names,
        hard_negatives=hard_negatives,
        negative_candidates=hard_negative_candidates,
    )
    root = feature_manifest_path.parent
    feature_path = root / str(files["logmel"])
    offset_path = root / str(files["offsets"])
    if (
        _LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_hyperspotter_tuning_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("mswc_hyperspotter_tuning_feature_shape_invalid")

    model, tokenizer, torch, torch_device = load_hyperspotter_model(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        initial_checkpoint_path=initial_checkpoint_path,
        adapted_checkpoint_path=adapted_checkpoint_path,
        expected_upstream_commit=str(sources["hyperspotter_upstream_commit"]),
        device=device,
    )
    scores = score_hyperspotter_candidates(
        model=model,
        tokenizer=tokenizer,
        torch=torch,
        torch_device=torch_device,
        features=features,
        offsets=offsets,
        query_indexes=query_indexes,
        candidate_indexes=candidates,
        class_names=class_names,
        prediction_batch_size=prediction_batch_size,
        device=device,
    )
    metrics = hard_pair_metrics(scores=scores, query_words=query_words)
    quality_floor = {
        "hard_candidate_top1_accuracy_minimum": 0.94,
        "pair_auc_minimum": 0.99,
        "equal_error_rate_maximum": 0.05,
        "zero_false_true_pair_recall_minimum": 0.20,
    }
    zero_false_recall = (
        float(metrics["true_pairs_accepted_at_zero_false_pairs"])
        / float(metrics["true_pairs"])
    )
    accepted = (
        float(metrics["hard_candidate_top1_accuracy"])
        >= quality_floor["hard_candidate_top1_accuracy_minimum"]
        and float(metrics["pair_auc"]) >= quality_floor["pair_auc_minimum"]
        and float(metrics["equal_error_rate"])
        <= quality_floor["equal_error_rate_maximum"]
        and zero_false_recall
        >= quality_floor["zero_false_true_pair_recall_minimum"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-hyperspotter-spanish-tuning.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_disjoint_spanish_text_conditioned_detection_tuning",
        "sources": {
            "feature_manifest_sha256": _LOGMEL.sha256(feature_manifest_path),
            "initial_checkpoint_sha256": _LOGMEL.sha256(initial_checkpoint_path),
            "adapted_checkpoint_sha256": _LOGMEL.sha256(adapted_checkpoint_path),
            "hyperspotter_upstream_commit": sources["hyperspotter_upstream_commit"],
        },
        "contract": {
            "split_seed": split_seed,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "query_examples_per_word": 6,
            "hard_negative_candidates_per_query": hard_negative_candidates,
            "hard_negative_selection": "lowest_normalized_text_edit_distance_with_lexical_tiebreak",
            "positive_candidate_position": 0,
            "audio_enrollment_required": False,
            "quality_floor": quality_floor,
        },
        "metrics": metrics,
        "zero_false_true_pair_recall": zero_false_recall,
        "accepted": accepted,
        "runtime_seconds": time.perf_counter() - started,
        "individual_examples_exported": False,
        "research_tuning_examples_scored": True,
        "research_reserved_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
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
    parser.add_argument("--adapted-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--hard-negative-candidates", type=int, default=40)
    parser.add_argument("--prediction-batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        feature_manifest_path=args.feature_manifest,
        hyperspotter_root=args.hyperspotter_root,
        hyperspotter_site_packages=args.hyperspotter_site_packages,
        initial_checkpoint_path=args.initial_checkpoint,
        adapted_checkpoint_path=args.adapted_checkpoint,
        output_path=args.output,
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        hard_negative_candidates=args.hard_negative_candidates,
        prediction_batch_size=args.prediction_batch_size,
        device=args.device,
    )
    print(
        json.dumps(
            {
                "accepted": report["accepted"],
                "metrics": report["metrics"],
                "zero_false_true_pair_recall": report["zero_false_true_pair_recall"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
