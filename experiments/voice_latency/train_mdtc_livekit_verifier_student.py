"""Train a tiny independent MDTC verifier on frozen LiveKit embeddings."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np


SYNTHETIC_FEATURE_FILES = (
    "positive_features_train.npy",
    "negative_features_train.npy",
    "positive_features_test.npy",
    "negative_features_test.npy",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def roc_auc(positive_scores: np.ndarray, negative_scores: np.ndarray) -> float:
    positive = np.asarray(positive_scores, dtype=np.float64).reshape(-1)
    negative = np.asarray(negative_scores, dtype=np.float64).reshape(-1)
    if positive.size == 0 or negative.size == 0:
        raise ValueError("mdtc_student_auc_partition_empty")
    values = np.concatenate((negative, positive))
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), np.float64)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    positive_rank_sum = ranks[len(negative) :].sum()
    statistic = positive_rank_sum - positive.size * (positive.size + 1) / 2.0
    return float(statistic / (positive.size * negative.size))


def zero_false_operating_point(
    positive_scores: np.ndarray, negative_scores: np.ndarray
) -> dict[str, float | int]:
    positive = np.asarray(positive_scores, dtype=np.float64).reshape(-1)
    negative = np.asarray(negative_scores, dtype=np.float64).reshape(-1)
    if positive.size == 0 or negative.size == 0:
        raise ValueError("mdtc_student_operating_partition_empty")
    if not np.isfinite(positive).all() or not np.isfinite(negative).all():
        raise ValueError("mdtc_student_operating_scores_invalid")
    maximum_negative = float(negative.max())
    threshold = float(np.nextafter(maximum_negative, math.inf))
    accepted = int(np.count_nonzero(positive >= threshold))
    return {
        "threshold": threshold,
        "maximum_negative_score": maximum_negative,
        "minimum_positive_score": float(positive.min()),
        "positive_accepted": accepted,
        "positive_total": int(positive.size),
        "positive_recall": accepted / positive.size,
        "negative_false_accepts": int(np.count_nonzero(negative >= threshold)),
        "score_separation": float(positive.min() - maximum_negative),
    }


def load_feature(path: Path) -> np.ndarray:
    value = np.load(path, allow_pickle=False)
    if value.ndim != 3 or value.shape[1:] != (16, 96):
        raise ValueError(f"mdtc_student_feature_shape_invalid:{path}:{value.shape}")
    if not np.isfinite(value).all():
        raise ValueError(f"mdtc_student_feature_values_invalid:{path}")
    return np.asarray(value, dtype=np.float32)


def load_human_training_partition(
    manifest_path: Path,
    *,
    excluded_speaker_group: str | None,
) -> tuple[np.ndarray, np.ndarray, dict[str, object], dict[str, object]]:
    manifest_path = manifest_path.resolve(strict=True)
    manifest = read_json(manifest_path)
    if manifest.get("schema") != "baxy.human-ctc-aligned-livekit-features.v2":
        raise ValueError("unsupported_mdtc_human_feature_schema")
    if manifest.get("partition") != "development":
        raise ValueError("mdtc_student_human_partition_invalid")
    if manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_student_human_blind_boundary_invalid")
    outputs = manifest.get("outputs")
    records = manifest.get("records")
    if not isinstance(outputs, dict) or not isinstance(records, list):
        raise ValueError("mdtc_student_human_outputs_missing")
    feature_path = Path(str(outputs.get("features"))).resolve(strict=True)
    label_path = Path(str(outputs.get("labels"))).resolve(strict=True)
    if sha256(feature_path) != outputs.get("features_sha256"):
        raise ValueError("mdtc_student_human_feature_hash_mismatch")
    if sha256(label_path) != outputs.get("labels_sha256"):
        raise ValueError("mdtc_student_human_label_hash_mismatch")
    features = load_feature(feature_path)
    labels = np.load(label_path, allow_pickle=False)
    if labels.ndim != 1 or len(labels) != len(features) or len(records) != len(labels):
        raise ValueError("mdtc_student_human_shape_mismatch")
    if not np.isin(labels, (0, 1)).all():
        raise ValueError("mdtc_student_human_labels_invalid")
    record_labels = []
    speaker_groups = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("mdtc_student_human_record_invalid")
        record_labels.append(record.get("teacher_aligned_label"))
        speaker_groups.append(str(record.get("speaker_group")))
    if not np.array_equal(np.asarray(record_labels), labels):
        raise ValueError("mdtc_student_human_record_label_mismatch")
    unique_groups = sorted(set(speaker_groups))
    if excluded_speaker_group is not None and excluded_speaker_group not in unique_groups:
        raise ValueError("mdtc_student_human_excluded_group_missing")
    mask = np.asarray(
        [group != excluded_speaker_group for group in speaker_groups], dtype=bool
    )
    selected_features = features[mask]
    selected_labels = np.asarray(labels[mask], dtype=np.float32)
    if len(selected_labels) == 0 or not np.any(selected_labels == 1):
        raise ValueError("mdtc_student_human_training_partition_empty")
    summary: dict[str, object] = {
        "manifest": manifest_path.as_posix(),
        "manifest_sha256": sha256(manifest_path),
        "excluded_speaker_group": excluded_speaker_group,
        "available_speaker_groups": unique_groups,
        "included_windows": int(len(selected_labels)),
        "included_positive_windows": int(selected_labels.sum()),
        "included_negative_windows": int(len(selected_labels) - selected_labels.sum()),
        "excluded_windows": int(len(labels) - len(selected_labels)),
    }
    return selected_features, selected_labels, summary, manifest


def build_model(torch: object, mdtc_type: object, hidden_dimension: int) -> object:
    nn = torch.nn

    class LiveKitMdtcStudent(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.normalization = nn.LayerNorm(96)
            self.projection = nn.Linear(96, hidden_dimension)
            self.backbone = mdtc_type(
                stack_num=1,
                stack_size=3,
                in_channels=hidden_dimension,
                res_channels=hidden_dimension,
                kernel_size=3,
                causal=True,
            )
            self.output = nn.Linear(hidden_dimension, 1)

        def forward(self, features: object) -> object:
            projected = torch.nn.functional.gelu(
                self.projection(self.normalization(features))
            )
            encoded, _ = self.backbone(projected)
            frame_logits = self.output(encoded).squeeze(-1)
            return frame_logits.max(dim=1).values

    return LiveKitMdtcStudent()


def predict_scores(
    torch: object,
    model: object,
    features: np.ndarray,
    *,
    device: str,
    batch_size: int,
) -> np.ndarray:
    values = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(features), batch_size):
            batch = torch.from_numpy(features[start : start + batch_size]).to(device)
            values.append(torch.sigmoid(model(batch)).cpu().numpy())
    return np.concatenate(values).astype(np.float64)


def train(
    *,
    synthetic_directory: Path,
    hard_feature_manifest_path: Path,
    wekws_directory: Path,
    output_directory: Path,
    hidden_dimension: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    hard_negative_weight: float,
    human_feature_manifest_path: Path | None,
    excluded_human_speaker_group: str | None,
    human_weight: float,
    seed: int,
    device: str,
) -> dict[str, object]:
    if hidden_dimension <= 0 or epochs <= 0 or batch_size <= 0:
        raise ValueError("mdtc_student_shape_or_schedule_invalid")
    if learning_rate <= 0.0 or hard_negative_weight < 1.0 or human_weight < 1.0:
        raise ValueError("mdtc_student_optimization_invalid")
    if human_feature_manifest_path is None and excluded_human_speaker_group is not None:
        raise ValueError("mdtc_student_human_exclusion_without_manifest")
    if device not in {"cpu", "cuda"}:
        raise ValueError("mdtc_student_device_invalid")
    synthetic_directory = synthetic_directory.resolve(strict=True)
    hard_feature_manifest_path = hard_feature_manifest_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_student_output_exists:{output_directory}")
    feature_paths = {
        name: synthetic_directory / name for name in SYNTHETIC_FEATURE_FILES
    }
    missing = [name for name, path in feature_paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"mdtc_student_synthetic_feature_missing:{missing[0]}")
    assembly_path = synthetic_directory / "assembly_manifest.v1.json"
    run_path = synthetic_directory / "development_run_manifest.v1.json"
    assembly = read_json(assembly_path)
    run = read_json(run_path)
    if assembly.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_student_synthetic_blind_boundary_invalid")
    if run.get("assembly_manifest_sha256") != sha256(assembly_path):
        raise ValueError("mdtc_student_synthetic_assembly_hash_mismatch")
    hard_manifest = read_json(hard_feature_manifest_path)
    if hard_manifest.get("schema") != "baxy.mdtc-hard-negative-livekit-features.v1":
        raise ValueError("unsupported_mdtc_hard_feature_schema")
    if hard_manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_student_hard_blind_boundary_invalid")
    hard_outputs = hard_manifest.get("outputs")
    if not isinstance(hard_outputs, dict):
        raise ValueError("mdtc_student_hard_outputs_missing")
    hard_paths: dict[str, Path] = {}
    for split in ("train", "development"):
        value = hard_outputs.get(split)
        if not isinstance(value, dict):
            raise ValueError(f"mdtc_student_hard_output_missing:{split}")
        path = Path(str(value["path"])).resolve(strict=True)
        if sha256(path) != value.get("sha256"):
            raise ValueError(f"mdtc_student_hard_output_hash_mismatch:{split}")
        hard_paths[split] = path

    positive_train = load_feature(feature_paths["positive_features_train.npy"])
    negative_train = load_feature(feature_paths["negative_features_train.npy"])
    positive_development = load_feature(feature_paths["positive_features_test.npy"])
    negative_development = load_feature(feature_paths["negative_features_test.npy"])
    hard_train = load_feature(hard_paths["train"])
    hard_development = load_feature(hard_paths["development"])
    training_feature_parts = [positive_train, negative_train, hard_train]
    training_label_parts = [
        np.ones(len(positive_train), np.float32),
        np.zeros(len(negative_train), np.float32),
        np.zeros(len(hard_train), np.float32),
    ]
    training_weight_parts = [
        np.ones(len(positive_train) + len(negative_train), np.float32),
        np.full(len(hard_train), hard_negative_weight, np.float32),
    ]
    human_summary: dict[str, object] | None = None
    if human_feature_manifest_path is not None:
        human_features, human_labels, human_summary, _ = load_human_training_partition(
            human_feature_manifest_path,
            excluded_speaker_group=excluded_human_speaker_group,
        )
        training_feature_parts.append(human_features)
        training_label_parts.append(human_labels)
        training_weight_parts.append(
            np.full(len(human_labels), human_weight, np.float32)
        )
    train_features = np.concatenate(training_feature_parts)
    train_labels = np.concatenate(training_label_parts)
    train_weights = np.concatenate(training_weight_parts)

    sys.path.insert(0, str(wekws_directory))
    import torch
    import onnxruntime as ort
    from wekws.model.mdtc import MDTC

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    model = build_model(torch, MDTC, hidden_dimension).to(device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4
    )
    generator = torch.Generator().manual_seed(seed)
    dataset = torch.utils.data.TensorDataset(
        torch.from_numpy(train_features),
        torch.from_numpy(train_labels),
        torch.from_numpy(train_weights),
    )
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    best_key: tuple[float, float, float] | None = None
    best_state: dict[str, object] | None = None
    best_epoch: dict[str, object] | None = None
    history: list[dict[str, object]] = []
    training_started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        loss_sum = 0.0
        item_count = 0
        for features, labels, weights in loader:
            features = features.to(device)
            labels = labels.to(device)
            weights = weights.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(features)
            losses = torch.nn.functional.binary_cross_entropy_with_logits(
                logits, labels, reduction="none"
            )
            loss = (losses * weights).sum() / weights.sum()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            loss_sum += float(loss.detach().cpu()) * len(features)
            item_count += len(features)
        positive_scores = predict_scores(
            torch,
            model,
            positive_development,
            device=device,
            batch_size=batch_size,
        )
        negative_scores = predict_scores(
            torch,
            model,
            np.concatenate((negative_development, hard_development)),
            device=device,
            batch_size=batch_size,
        )
        operating = zero_false_operating_point(positive_scores, negative_scores)
        auc = roc_auc(positive_scores, negative_scores)
        epoch_record: dict[str, object] = {
            "epoch": epoch,
            "train_loss": loss_sum / item_count,
            "development_auc": auc,
            "zero_false_operating_point": operating,
        }
        history.append(epoch_record)
        key = (
            float(operating["positive_recall"]),
            auc,
            -float(epoch_record["train_loss"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
            best_epoch = epoch_record
        if epoch == 1 or epoch % 5 == 0:
            print(
                f"PROGRESS|epoch={epoch}/{epochs}|recall={operating['positive_recall']:.6f}|auc={auc:.6f}",
                flush=True,
            )
    training_seconds = time.perf_counter() - training_started
    if best_state is None or best_epoch is None:
        raise RuntimeError("mdtc_student_no_best_state")
    model.load_state_dict(best_state)
    model.eval()
    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mdtc_livekit_verifier_student.pt"
    torch.save(best_state, checkpoint_path)
    # Product inference is ONNX CPU.  Export and compare from the same CPU
    # arithmetic boundary; CUDA and CPU depthwise convolutions can differ by
    # ~1e-3 even when each backend is internally deterministic.
    model = model.cpu()
    onnx_path = output_directory / "mdtc_livekit_verifier_student.onnx"
    dummy = torch.zeros(1, 16, 96, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy,
        onnx_path,
        input_names=["features"],
        output_names=["logit"],
        dynamic_axes={"features": {0: "batch"}, "logit": {0: "batch"}},
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )
    verification_features = positive_development[: min(32, len(positive_development))]
    torch_scores = predict_scores(
        torch, model, verification_features, device="cpu", batch_size=batch_size
    )
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onnx_logits = np.asarray(
        session.run(None, {"features": verification_features})[0]
    ).reshape(-1)
    onnx_scores = 1.0 / (1.0 + np.exp(-onnx_logits))
    maximum_export_difference = float(np.max(np.abs(torch_scores - onnx_scores)))
    if maximum_export_difference > 1e-5:
        raise ValueError("mdtc_student_onnx_export_mismatch")
    commit = subprocess.run(
        ["git", "-C", str(wekws_directory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report: dict[str, object] = {
        "schema": (
            "baxy.mdtc-livekit-verifier-student-development.v2"
            if human_summary is not None
            else "baxy.mdtc-livekit-verifier-student-development.v1"
        ),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "candidate_development_small_streaming_verifier",
        "architecture": {
            "frontend": "frozen_livekit_16x96_embeddings",
            "classifier": "layernorm_linear_gelu_causal_mdtc_max_pool",
            "hidden_dimension": hidden_dimension,
            "mdtc_stacks": 1,
            "mdtc_stack_size": 3,
            "mdtc_kernel_size": 3,
            "receptive_field_frames": int(model.backbone.padding),
            "parameters": parameter_count,
        },
        "sources": {
            "synthetic_directory": synthetic_directory.as_posix(),
            "assembly_manifest_sha256": sha256(assembly_path),
            "development_run_manifest_sha256": sha256(run_path),
            "synthetic_feature_files": {
                name: sha256(path) for name, path in feature_paths.items()
            },
            "hard_feature_manifest": hard_feature_manifest_path.as_posix(),
            "hard_feature_manifest_sha256": sha256(hard_feature_manifest_path),
            "human_feature_partition": human_summary,
            "wekws_directory": wekws_directory.as_posix(),
            "wekws_commit": commit,
            "wekws_license_sha256": sha256(wekws_directory / "LICENSE"),
            "wekws_mdtc_source_sha256": sha256(
                wekws_directory / "wekws" / "model" / "mdtc.py"
            ),
        },
        "data_counts": {
            "positive_train": len(positive_train),
            "synthetic_negative_train": len(negative_train),
            "hard_negative_train": len(hard_train),
            "positive_development": len(positive_development),
            "synthetic_negative_development": len(negative_development),
            "hard_negative_development": len(hard_development),
            "human_train": 0 if human_summary is None else human_summary["included_windows"],
            "human_positive_train": 0
            if human_summary is None
            else human_summary["included_positive_windows"],
            "human_negative_train": 0
            if human_summary is None
            else human_summary["included_negative_windows"],
        },
        "training": {
            "seed": seed,
            "device": device,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "hard_negative_weight": hard_negative_weight,
            "human_weight": human_weight,
            "seconds": training_seconds,
            "best_epoch": best_epoch,
            "history": history,
        },
        "artifacts": {
            "checkpoint": checkpoint_path.as_posix(),
            "checkpoint_sha256": sha256(checkpoint_path),
            "onnx": onnx_path.as_posix(),
            "onnx_sha256": sha256(onnx_path),
            "maximum_export_score_difference": maximum_export_difference,
        },
        "runtime": {
            "python": sys.version,
            "numpy": np.__version__,
            "torch": torch.__version__,
            "onnxruntime": ort.__version__,
        },
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    report_path = output_directory / (
        "development_report.v2.json"
        if human_summary is not None
        else "development_report.v1.json"
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-dir", type=Path, required=True)
    parser.add_argument("--hard-feature-manifest", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hidden-dimension", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--hard-negative-weight", type=float, default=2.0)
    parser.add_argument("--human-feature-manifest", type=Path)
    parser.add_argument("--exclude-human-speaker-group")
    parser.add_argument("--human-weight", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = train(
        synthetic_directory=args.synthetic_dir,
        hard_feature_manifest_path=args.hard_feature_manifest,
        wekws_directory=args.wekws_dir,
        output_directory=args.output_dir,
        hidden_dimension=args.hidden_dimension,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        hard_negative_weight=args.hard_negative_weight,
        human_feature_manifest_path=args.human_feature_manifest,
        excluded_human_speaker_group=args.exclude_human_speaker_group,
        human_weight=args.human_weight,
        seed=args.seed,
        device=args.device,
    )
    print(json.dumps({"artifacts": report["artifacts"], "training": report["training"]["best_epoch"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
