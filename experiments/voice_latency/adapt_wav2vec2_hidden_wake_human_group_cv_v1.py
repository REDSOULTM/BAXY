"""Adapt the synthetic wake MIL head with speaker-held-out human development data.

This is a development-only experiment.  Every reported human score is produced
by a fold whose training set excludes the complete speaker/source group for that
record.  The blind human corpus is neither located nor opened here.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import time
from typing import NamedTuple

import numpy as np


_BASE_PATH = Path(__file__).with_name("train_wav2vec2_hidden_wake_mil_head_v1.py")
_BASE_SPEC = importlib.util.spec_from_file_location("_baxy_wake_mil_base_v1", _BASE_PATH)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise RuntimeError("wake_human_cv_base_import_invalid")
_BASE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_BASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_human_cv_json_invalid:{path}")
    return value


def human_group_folds(
    records: list[dict[str, object]], human_indexes: list[int]
) -> list[tuple[str, list[int], list[int]]]:
    groups = sorted({str(records[index]["group"]) for index in human_indexes})
    if len(groups) < 3:
        raise ValueError("wake_human_cv_groups_insufficient")
    folds = []
    for held_group in groups:
        held = [
            index
            for index in human_indexes
            if str(records[index]["group"]) == held_group
        ]
        training = [index for index in human_indexes if index not in held]
        training_labels = {str(records[index]["label"]) for index in training}
        if not held or training_labels != {"negative", "positive"}:
            raise ValueError("wake_human_cv_fold_labels_invalid")
        folds.append((held_group, training, held))
    return folds


def calibrated_margin(score: float, negative_training_scores: np.ndarray) -> float:
    negatives = np.asarray(negative_training_scores, dtype=np.float64)
    if not len(negatives) or not np.isfinite(negatives).all() or not math.isfinite(score):
        raise ValueError("wake_human_cv_calibration_invalid")
    threshold = float(np.nextafter(negatives.max(), math.inf))
    return float(score - threshold)


def aggregate_metrics(scores: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    from sklearn.metrics import roc_auc_score

    values = np.asarray(scores, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    positives = values[targets == 1]
    negatives = values[targets == 0]
    if not len(positives) or not len(negatives) or not np.isfinite(values).all():
        raise ValueError("wake_human_cv_metrics_invalid")
    return {
        "auc": float(roc_auc_score(targets, values)),
        "threshold": 0.0,
        "positive_accepted": int(np.count_nonzero(positives >= 0.0)),
        "positive_total": int(len(positives)),
        "negative_false_accepts": int(np.count_nonzero(negatives >= 0.0)),
        "negative_total": int(len(negatives)),
    }


def adaptation_rank(metrics: dict[str, object]) -> tuple[int, int, float]:
    """Prefer safety, then recall, then ranking quality."""

    return (
        -int(metrics["negative_false_accepts"]),
        int(metrics["positive_accepted"]),
        float(metrics["auc"]),
    )


class AdaptationConfig(NamedTuple):
    learning_rate: float
    epochs: int
    l2_sp: float
    scope: str
    replay_weight: float

    @property
    def key(self) -> str:
        return (
            f"lr={self.learning_rate:g}|epochs={self.epochs}|l2sp={self.l2_sp:g}"
            f"|scope={self.scope}|replay={self.replay_weight:g}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "l2_sp": self.l2_sp,
            "scope": self.scope,
            "synthetic_replay_weight": self.replay_weight,
        }


def train(
    *,
    feature_manifest_path: Path,
    synthetic_model_path: Path,
    output_root: Path,
    learning_rates: list[float],
    epoch_options: list[int],
    l2_sp_options: list[float],
    scopes: list[str],
    replay_weights: list[float],
    replay_batch_size: int,
    prediction_batch_size: int,
    seed: int,
    device: str,
) -> dict[str, object]:
    if (
        output_root.exists()
        or not learning_rates
        or not epoch_options
        or not l2_sp_options
        or not scopes
        or not replay_weights
        or any(value <= 0.0 for value in learning_rates)
        or any(value < 1 for value in epoch_options)
        or any(value < 0.0 for value in l2_sp_options)
        or any(value not in {"temporal", "all"} for value in scopes)
        or any(value < 0.0 for value in replay_weights)
        or replay_batch_size < 2
        or prediction_batch_size < 1
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("wake_human_cv_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    synthetic_model_path = synthetic_model_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise ValueError("wake_human_cv_partial_output_exists")

    source = read_object(feature_manifest_path)
    if (
        source.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or source.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_human_cv_feature_boundary_invalid")
    files = source.get("files")
    contract = source.get("contract")
    records = source.get("records")
    if not isinstance(files, dict) or not isinstance(contract, dict) or not isinstance(records, list):
        raise ValueError("wake_human_cv_feature_manifest_invalid")
    typed_records: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("wake_human_cv_record_invalid")
        typed_records.append(record)

    feature_root = feature_manifest_path.parent
    feature_path = feature_root / str(files["features"])
    offset_path = feature_root / str(files["offsets"])
    if (
        sha256(feature_path) != files.get("features_sha256")
        or sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("wake_human_cv_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(typed_records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("wake_human_cv_feature_offsets_invalid")
    hidden_size = int(contract["hidden_size"])
    if features.ndim != 2 or features.shape[1] != hidden_size:
        raise ValueError("wake_human_cv_hidden_size_invalid")

    import torch
    from torch.nn.utils.rnn import pad_sequence

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_human_cv_cuda_unavailable")
    torch_device = torch.device(device)
    checkpoint = torch.load(synthetic_model_path, map_location="cpu", weights_only=False)
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema") != "baxy.wav2vec2-hidden-wake-mil-head.v1"
        or int(checkpoint.get("hidden_size", -1)) != hidden_size
        or int(checkpoint.get("topk_frames", -1)) != 3
        or not isinstance(checkpoint.get("state_dict"), dict)
    ):
        raise ValueError("wake_human_cv_checkpoint_invalid")
    initial_state = {
        str(key): value.detach().cpu().clone()
        for key, value in checkpoint["state_dict"].items()
    }

    synthetic_indexes = [
        index
        for index, record in enumerate(typed_records)
        if str(record["corpus"]).startswith("synthetic_")
    ]
    human_indexes = [
        index
        for index, record in enumerate(typed_records)
        if str(record["corpus"]).startswith("human_")
    ]
    positive_synthetic = [
        index for index in synthetic_indexes if typed_records[index]["label"] == "positive"
    ]
    negative_synthetic = [
        index for index in synthetic_indexes if typed_records[index]["label"] == "negative"
    ]
    if not positive_synthetic or not negative_synthetic:
        raise ValueError("wake_human_cv_synthetic_labels_invalid")
    folds = human_group_folds(typed_records, human_indexes)

    def batch(indexes: list[int]) -> tuple[object, object, object]:
        sequences = [
            torch.from_numpy(
                np.asarray(features[offsets[index] : offsets[index + 1]], dtype=np.float32)
            )
            for index in indexes
        ]
        padded = pad_sequence(sequences, batch_first=True)
        lengths = torch.tensor([len(sequence) for sequence in sequences])
        mask = torch.arange(padded.shape[1])[None, :] < lengths[:, None]
        labels = torch.tensor(
            [1.0 if typed_records[index]["label"] == "positive" else 0.0 for index in indexes],
            dtype=torch.float32,
        )
        return padded.to(torch_device), mask.to(torch_device), labels.to(torch_device)

    def predict(model: object, indexes: list[int]) -> tuple[np.ndarray, np.ndarray]:
        model.eval()
        scores: list[float] = []
        labels: list[int] = []
        with torch.inference_mode():
            for start in range(0, len(indexes), prediction_batch_size):
                selected = indexes[start : start + prediction_batch_size]
                x, mask, y = batch(selected)
                scores.extend(model(x, mask).float().cpu().numpy().tolist())
                labels.extend(y.cpu().numpy().astype(np.int64).tolist())
        return np.asarray(scores), np.asarray(labels)

    def deterministic_seed(config_key: str, group: str) -> int:
        material = f"{seed}|{config_key}|{group}".encode("utf-8")
        return int.from_bytes(hashlib.sha256(material).digest()[:4], "big")

    def fit_model(
        config: AdaptationConfig, training_indexes: list[int], fit_seed: int
    ) -> object:
        random.seed(fit_seed)
        np.random.seed(fit_seed)
        torch.manual_seed(fit_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(fit_seed)
        model = _BASE.make_model(torch, hidden_size).to(torch_device)
        model.load_state_dict(initial_state)
        if config.scope == "temporal":
            for parameter in model.projection.parameters():
                parameter.requires_grad = False
        trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
        reference = [parameter.detach().clone() for parameter in trainable]
        optimizer = torch.optim.AdamW(trainable, lr=config.learning_rate, weight_decay=0.0)
        human_x, human_mask, human_y = batch(training_indexes)
        positive_count = int(torch.count_nonzero(human_y).item())
        negative_count = len(training_indexes) - positive_count
        if not positive_count or not negative_count:
            raise ValueError("wake_human_cv_training_labels_invalid")
        positive_weight = 0.5 / positive_count
        negative_weight = 0.5 / negative_count
        replay_half = replay_batch_size // 2
        generator = torch.Generator().manual_seed(fit_seed)
        for _ in range(config.epochs):
            model.train()
            optimizer.zero_grad(set_to_none=True)
            human_logits = model(human_x, human_mask)
            human_losses = torch.nn.functional.binary_cross_entropy_with_logits(
                human_logits, human_y, reduction="none"
            )
            human_weights = torch.where(
                human_y > 0.5,
                torch.full_like(human_y, positive_weight),
                torch.full_like(human_y, negative_weight),
            )
            loss = torch.sum(human_losses * human_weights)
            if config.replay_weight > 0.0:
                positive_order = torch.randperm(len(positive_synthetic), generator=generator)
                negative_order = torch.randperm(len(negative_synthetic), generator=generator)
                replay_indexes = [
                    positive_synthetic[index]
                    for index in positive_order[:replay_half].tolist()
                ] + [
                    negative_synthetic[index]
                    for index in negative_order[:replay_half].tolist()
                ]
                replay_x, replay_mask, replay_y = batch(replay_indexes)
                replay_logits = model(replay_x, replay_mask)
                replay_loss = torch.nn.functional.binary_cross_entropy_with_logits(
                    replay_logits, replay_y
                )
                loss = loss + config.replay_weight * replay_loss
            if config.l2_sp > 0.0:
                penalty = torch.zeros((), device=torch_device)
                for parameter, starting_value in zip(trainable, reference, strict=True):
                    penalty = penalty + torch.mean((parameter - starting_value) ** 2)
                loss = loss + config.l2_sp * penalty
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable, 5.0)
            optimizer.step()
        return model

    configs = [
        AdaptationConfig(lr, epochs, l2_sp, scope, replay_weight)
        for lr in learning_rates
        for epochs in epoch_options
        for l2_sp in l2_sp_options
        for scope in scopes
        for replay_weight in replay_weights
    ]
    if len({config.key for config in configs}) != len(configs):
        raise ValueError("wake_human_cv_duplicate_configs")

    partial_root.mkdir(parents=True)
    started = time.perf_counter()
    results: list[dict[str, object]] = []
    best_config: AdaptationConfig | None = None
    best_rank: tuple[int, int, float] | None = None
    for config in configs:
        held_scores: list[float] = []
        held_labels: list[int] = []
        held_records: list[dict[str, object]] = []
        fold_reports: list[dict[str, object]] = []
        for held_group, training_indexes, held_indexes in folds:
            model = fit_model(
                config,
                training_indexes,
                deterministic_seed(config.key, held_group),
            )
            training_scores, training_labels = predict(model, training_indexes)
            negative_training_scores = training_scores[training_labels == 0]
            threshold = float(np.nextafter(negative_training_scores.max(), math.inf))
            raw_scores, labels = predict(model, held_indexes)
            margins = raw_scores - threshold
            fold_reports.append(
                {
                    "held_group": held_group,
                    "training_records": len(training_indexes),
                    "held_records": len(held_indexes),
                    "training_negative_calibration_threshold": threshold,
                    "held_positive_count": int(np.count_nonzero(labels == 1)),
                    "held_negative_count": int(np.count_nonzero(labels == 0)),
                    "held_positive_accepted": int(np.count_nonzero(margins[labels == 1] >= 0.0)),
                    "held_negative_false_accepts": int(np.count_nonzero(margins[labels == 0] >= 0.0)),
                }
            )
            for index, raw_score, margin, label in zip(
                held_indexes, raw_scores, margins, labels, strict=True
            ):
                held_scores.append(float(margin))
                held_labels.append(int(label))
                held_records.append(
                    {
                        "corpus": typed_records[index]["corpus"],
                        "relative_path": typed_records[index]["relative_path"],
                        "group": typed_records[index]["group"],
                        "label": typed_records[index]["label"],
                        "source_label": typed_records[index].get("source_label"),
                        "raw_score": float(raw_score),
                        "calibrated_margin": float(margin),
                        "accepted": bool(margin >= 0.0),
                    }
                )
        metrics = aggregate_metrics(np.asarray(held_scores), np.asarray(held_labels))
        result = {
            "config": config.as_dict(),
            "config_key": config.key,
            "speaker_held_out_metrics": metrics,
            "folds": fold_reports,
            "held_records": held_records,
        }
        results.append(result)
        rank = adaptation_rank(metrics)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_config = config
    assert best_config is not None
    selected_result = next(result for result in results if result["config_key"] == best_config.key)

    final_model = fit_model(best_config, human_indexes, deterministic_seed(best_config.key, "all_human"))
    human_scores, human_labels = predict(final_model, human_indexes)
    final_threshold = float(np.nextafter(human_scores[human_labels == 0].max(), math.inf))
    model_path = partial_root / "wake-human-adapted-mil-head-v1.pt"
    torch.save(
        {
            "schema": "baxy.wav2vec2-hidden-wake-human-adapted-mil-head.v1",
            "hidden_size": hidden_size,
            "topk_frames": 3,
            "development_threshold": final_threshold,
            "adaptation_config": best_config.as_dict(),
            "source_model_sha256": sha256(synthetic_model_path),
            "state_dict": {
                key: value.detach().cpu() for key, value in final_model.state_dict().items()
            },
        },
        model_path,
    )

    synthetic_groups = {str(typed_records[index]["group"]) for index in synthetic_indexes}
    synthetic_validation_groups = _BASE.validation_groups(synthetic_groups)
    synthetic_validation_indexes = [
        index
        for index in synthetic_indexes
        if str(typed_records[index]["group"]) in synthetic_validation_groups
    ]
    synthetic_scores, synthetic_labels = predict(final_model, synthetic_validation_indexes)
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-human-group-cv.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "features_sha256": files["features_sha256"],
            "offsets_sha256": files["offsets_sha256"],
            "synthetic_model_sha256": sha256(synthetic_model_path),
        },
        "method": {
            "human_evaluation": "leave_one_complete_speaker_or_source_group_out",
            "fold_calibration": "nextafter_max_training_human_negative",
            "aggregate_score": "held_raw_score_minus_fold_training_negative_threshold",
            "selection": "fewest_false_accepts_then_positive_accepts_then_auc",
            "human_groups": [group for group, _, _ in folds],
            "human_records": len(human_indexes),
            "synthetic_replay_batch_size": replay_batch_size,
            "seed": seed,
        },
        "grid": [config.as_dict() for config in configs],
        "results": results,
        "selected_config": best_config.as_dict(),
        "selected_config_key": best_config.key,
        "selected_speaker_held_out_metrics": selected_result["speaker_held_out_metrics"],
        "final_development_fit": {
            "threshold": final_threshold,
            "human_training_metrics": _BASE.threshold_metrics(
                human_scores, human_labels, final_threshold
            ),
            "synthetic_validation_oracle": _BASE.metrics_from_scores(
                synthetic_scores, synthetic_labels
            ),
        },
        "artifacts": {
            "model": model_path.name,
            "model_sha256": sha256(model_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "development_only": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    report_path = partial_root / "human-group-cv.report.v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--synthetic-model", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--learning-rates", type=float, nargs="+", default=[1e-5, 3e-5, 1e-4])
    parser.add_argument("--epochs", type=int, nargs="+", default=[25, 50, 100])
    parser.add_argument("--l2-sp", type=float, nargs="+", default=[1e-4, 1e-3])
    parser.add_argument("--scopes", choices=("temporal", "all"), nargs="+", default=["temporal"])
    parser.add_argument("--replay-weights", type=float, nargs="+", default=[0.1])
    parser.add_argument("--replay-batch-size", type=int, default=64)
    parser.add_argument("--prediction-batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=2803)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        feature_manifest_path=arguments.feature_manifest,
        synthetic_model_path=arguments.synthetic_model,
        output_root=arguments.output_root,
        learning_rates=arguments.learning_rates,
        epoch_options=arguments.epochs,
        l2_sp_options=arguments.l2_sp,
        scopes=arguments.scopes,
        replay_weights=arguments.replay_weights,
        replay_batch_size=arguments.replay_batch_size,
        prediction_batch_size=arguments.prediction_batch_size,
        seed=arguments.seed,
        device=arguments.device,
    )
    print(
        json.dumps(
            {
                "selected_config": report["selected_config"],
                "speaker_held_out_metrics": report["selected_speaker_held_out_metrics"],
                "model_sha256": report["artifacts"]["model_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
