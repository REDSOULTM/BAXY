"""Train a temporal multiple-instance wake head on frozen Wav2Vec2 features."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_mil_json_invalid:{path}")
    return value


def validation_groups(groups: set[str], modulus: int = 5) -> set[str]:
    if modulus < 2:
        raise ValueError("wake_mil_split_modulus_invalid")
    selected = {
        group
        for group in groups
        if int.from_bytes(hashlib.sha256(group.encode("utf-8")).digest()[:8], "big")
        % modulus
        == 0
    }
    if not selected or selected == groups:
        raise ValueError("wake_mil_group_split_invalid")
    return selected


def metrics_from_scores(scores: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    from sklearn.metrics import roc_auc_score

    values = np.asarray(scores, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    positives = values[targets == 1]
    negatives = values[targets == 0]
    if not len(positives) or not len(negatives) or not np.isfinite(values).all():
        raise ValueError("wake_mil_metrics_invalid")
    threshold = float(np.nextafter(negatives.max(), math.inf))
    accepted = int(np.count_nonzero(positives >= threshold))
    return {
        "auc": float(roc_auc_score(targets, values)),
        "zero_false_threshold": threshold,
        "zero_false_positive_accepted": accepted,
        "positive_total": int(len(positives)),
        "zero_false_positive_rate": accepted / len(positives),
        "negative_total": int(len(negatives)),
    }


def threshold_metrics(
    scores: np.ndarray, labels: np.ndarray, threshold: float
) -> dict[str, object]:
    positives = np.asarray(scores)[np.asarray(labels) == 1]
    negatives = np.asarray(scores)[np.asarray(labels) == 0]
    return {
        "threshold": threshold,
        "positive_accepted": int(np.count_nonzero(positives >= threshold)),
        "positive_total": int(len(positives)),
        "negative_false_accepts": int(np.count_nonzero(negatives >= threshold)),
        "negative_total": int(len(negatives)),
    }


def make_model(torch: object, hidden_size: int, topk_frames: int = 3) -> object:
    nn = torch.nn

    class TemporalMilHead(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.projection = nn.Sequential(
                nn.Linear(hidden_size, 192),
                nn.LayerNorm(192),
                nn.GELU(),
                nn.Dropout(0.10),
            )
            self.temporal = nn.Sequential(
                nn.Conv1d(192, 128, kernel_size=5, padding=2),
                nn.GELU(),
                nn.Dropout(0.10),
                nn.Conv1d(128, 64, kernel_size=3, padding=1),
                nn.GELU(),
                nn.Conv1d(64, 1, kernel_size=1),
            )

        def forward(self, values: object, mask: object) -> object:
            projected = self.projection(values).transpose(1, 2)
            frame_logits = self.temporal(projected).squeeze(1)
            frame_logits = frame_logits.masked_fill(~mask, -torch.inf)
            if bool((mask.sum(dim=1) < topk_frames).any()):
                raise ValueError("wake_mil_sequence_too_short")
            return torch.topk(frame_logits, topk_frames, dim=1).values.mean(dim=1)

    return TemporalMilHead()


def train(
    *,
    feature_manifest_path: Path,
    output_root: Path,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seeds: list[int],
    device: str,
) -> dict[str, object]:
    if (
        output_root.exists()
        or epochs < 1
        or batch_size < 1
        or learning_rate <= 0.0
        or not seeds
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("wake_mil_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    feature_root = feature_manifest_path.parent
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise ValueError("wake_mil_partial_output_exists")
    source = read_object(feature_manifest_path)
    if (
        source.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or source.get("blind_human_audio_accessed") is not False
        or source.get("candidate_model_training_started") is not False
    ):
        raise ValueError("wake_mil_feature_boundary_invalid")
    files = source.get("files")
    contract = source.get("contract")
    records = source.get("records")
    if not isinstance(files, dict) or not isinstance(contract, dict) or not isinstance(records, list):
        raise ValueError("wake_mil_feature_manifest_invalid")
    feature_path = feature_root / str(files["features"])
    offset_path = feature_root / str(files["offsets"])
    if (
        sha256(feature_path) != files.get("features_sha256")
        or sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("wake_mil_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("wake_mil_feature_offsets_invalid")
    hidden_size = int(contract["hidden_size"])
    if features.shape[1] != hidden_size:
        raise ValueError("wake_mil_hidden_size_invalid")
    synthetic_indexes = [
        index
        for index, record in enumerate(records)
        if str(record["corpus"]).startswith("synthetic_")
    ]
    human_indexes = [
        index
        for index, record in enumerate(records)
        if str(record["corpus"]).startswith("human_")
    ]
    groups = {str(records[index]["group"]) for index in synthetic_indexes}
    held_groups = validation_groups(groups)
    train_indexes = [
        index
        for index in synthetic_indexes
        if str(records[index]["group"]) not in held_groups
    ]
    validation_indexes = [
        index
        for index in synthetic_indexes
        if str(records[index]["group"]) in held_groups
    ]

    import torch
    from torch.nn.utils.rnn import pad_sequence

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_mil_cuda_unavailable")
    torch_device = torch.device(device)

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
            [1.0 if records[index]["label"] == "positive" else 0.0 for index in indexes],
            dtype=torch.float32,
        )
        return padded.to(torch_device), mask.to(torch_device), labels.to(torch_device)

    def predict(model: object, indexes: list[int]) -> tuple[np.ndarray, np.ndarray]:
        model.eval()
        values = []
        labels = []
        with torch.inference_mode():
            for start in range(0, len(indexes), batch_size):
                selected = indexes[start : start + batch_size]
                x, mask, y = batch(selected)
                values.extend(model(x, mask).float().cpu().numpy().tolist())
                labels.extend(y.cpu().numpy().astype(np.int64).tolist())
        return np.asarray(values), np.asarray(labels)

    partial_root.mkdir(parents=True)
    runs = []
    best_rank: tuple[float, float] | None = None
    best_state = None
    best_seed = None
    started = time.perf_counter()
    for seed in seeds:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        model = make_model(torch, hidden_size).to(torch_device)
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=learning_rate, weight_decay=1e-4
        )
        loss_function = torch.nn.BCEWithLogitsLoss()
        generator = torch.Generator().manual_seed(seed)
        history = []
        for epoch in range(epochs):
            model.train()
            permutation = torch.randperm(len(train_indexes), generator=generator).tolist()
            epoch_loss = 0.0
            examples = 0
            for start in range(0, len(permutation), batch_size):
                chosen = [train_indexes[index] for index in permutation[start : start + batch_size]]
                x, mask, y = batch(chosen)
                optimizer.zero_grad(set_to_none=True)
                logits = model(x, mask)
                loss = loss_function(logits, y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
                epoch_loss += float(loss.detach().cpu()) * len(chosen)
                examples += len(chosen)
            if epoch == epochs - 1 or epoch % 5 == 4:
                validation_scores, validation_labels = predict(
                    model, validation_indexes
                )
                validation_metrics = metrics_from_scores(
                    validation_scores, validation_labels
                )
                history.append(
                    {
                        "epoch": epoch + 1,
                        "train_loss": epoch_loss / examples,
                        "synthetic_validation": validation_metrics,
                    }
                )
        train_scores, train_labels = predict(model, train_indexes)
        validation_scores, validation_labels = predict(model, validation_indexes)
        human_scores, human_labels = predict(model, human_indexes)
        train_metrics = metrics_from_scores(train_scores, train_labels)
        validation_metrics = metrics_from_scores(validation_scores, validation_labels)
        human_metrics = metrics_from_scores(human_scores, human_labels)
        synthetic_threshold = float(validation_metrics["zero_false_threshold"])
        run = {
            "seed": seed,
            "history": history,
            "synthetic_train": train_metrics,
            "synthetic_validation": validation_metrics,
            "human_at_synthetic_zero_false_threshold": threshold_metrics(
                human_scores, human_labels, synthetic_threshold
            ),
            "human_development_oracle": human_metrics,
        }
        runs.append(run)
        rank = (
            float(validation_metrics["zero_false_positive_rate"]),
            float(validation_metrics["auc"]),
        )
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_seed = seed
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    assert best_state is not None and best_seed is not None
    model_path = partial_root / "wake-mil-head-v1.pt"
    torch.save(
        {
            "schema": "baxy.wav2vec2-hidden-wake-mil-head.v1",
            "hidden_size": hidden_size,
            "topk_frames": 3,
            "state_dict": best_state,
        },
        model_path,
    )
    best_run = next(run for run in runs if run["seed"] == best_seed)
    human_breakdown = []
    selected_model = make_model(torch, hidden_size).to(torch_device)
    selected_model.load_state_dict(best_state)
    selected_scores, selected_labels = predict(selected_model, human_indexes)
    human_threshold = float(best_run["human_development_oracle"]["zero_false_threshold"])
    for index, score in zip(human_indexes, selected_scores, strict=True):
        human_breakdown.append(
            {
                "corpus": records[index]["corpus"],
                "relative_path": records[index]["relative_path"],
                "group": records[index]["group"],
                "label": records[index]["label"],
                "source_label": records[index].get("source_label"),
                "score": float(score),
                "accepted_at_human_oracle_threshold": bool(score >= human_threshold),
            }
        )
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-mil-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "features_sha256": files["features_sha256"],
            "offsets_sha256": files["offsets_sha256"],
        },
        "split": {
            "method": "sha256_persona_modulo_5",
            "synthetic_train_groups": sorted(groups - held_groups),
            "synthetic_validation_groups": sorted(held_groups),
            "synthetic_train_records": len(train_indexes),
            "synthetic_validation_records": len(validation_indexes),
            "human_development_records": len(human_indexes),
        },
        "architecture": {
            "input_hidden_size": hidden_size,
            "projection_size": 192,
            "temporal_channels": [128, 64],
            "temporal_kernels": [5, 3, 1],
            "clip_pooling": "top_3_frame_logits_mean",
            "loss": "binary_cross_entropy_with_logits",
        },
        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "weight_decay": 1e-4,
            "seeds": seeds,
            "selection": "synthetic_validation_zero_false_recall_then_auc",
        },
        "runs": runs,
        "selected_seed": best_seed,
        "selected_run": best_run,
        "human_records": human_breakdown,
        "artifacts": {
            "model": model_path.name,
            "model_sha256": sha256(model_path),
        },
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    report_path = partial_root / "training.report.v1.json"
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
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1701, 1702, 1703])
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        feature_manifest_path=arguments.feature_manifest,
        output_root=arguments.output_root,
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        learning_rate=arguments.learning_rate,
        seeds=arguments.seeds,
        device=arguments.device,
    )
    print(
        json.dumps(
            {
                "selected_seed": report["selected_seed"],
                "synthetic_validation": report["selected_run"]["synthetic_validation"],
                "human_development_oracle": report["selected_run"]["human_development_oracle"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
