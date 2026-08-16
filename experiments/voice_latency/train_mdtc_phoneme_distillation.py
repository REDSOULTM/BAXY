"""Distill the phoneme teacher into a tiny causal MDTC acoustic model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate_livekit_embedding_separability import aggregate_clips  # noqa: E402
from evaluate_mdtc_confusable_ctc_dual_gate import (  # noqa: E402
    combined_margins,
    zero_false_rectangle,
)
from train_mdtc_confusable_ctc_group_cv import (  # noqa: E402
    BLANK_ID,
    CONFUSABLE_IDS,
    TARGET_IDS,
    fixed_sequence_log_probability,
)
from train_mdtc_livekit_verifier_student import (  # noqa: E402
    read_json,
    roc_auc,
    sha256,
)
from train_mdtc_phonetic_ctc_group_cv import load_partition  # noqa: E402


CATEGORY_COUNT = 11


def load_teacher_partition(
    manifest: dict[str, object], name: str, expected_count: int
) -> np.ndarray:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("mdtc_distillation_teacher_outputs_missing")
    value = outputs.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"mdtc_distillation_teacher_partition_missing:{name}")
    path = Path(str(value.get("path"))).resolve(strict=True)
    if sha256(path) != value.get("sha256"):
        raise ValueError(f"mdtc_distillation_teacher_hash_mismatch:{name}")
    probabilities = np.load(path, allow_pickle=False)
    if probabilities.shape != (expected_count, 99, CATEGORY_COUNT):
        raise ValueError(f"mdtc_distillation_teacher_shape_invalid:{name}")
    values = np.asarray(probabilities, dtype=np.float32)
    if not np.isfinite(values).all() or not np.allclose(
        values.sum(axis=-1), 1.0, atol=2e-3
    ):
        raise ValueError(f"mdtc_distillation_teacher_values_invalid:{name}")
    return values


def build_model(
    torch: object,
    mdtc_type: object,
    *,
    hidden_dimension: int,
    stack_count: int,
    stack_size: int,
    kernel_size: int,
) -> object:
    nn = torch.nn

    class DistilledPhonemeStudent(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.normalization = nn.LayerNorm(80)
            self.projection = nn.Linear(80, hidden_dimension)
            self.backbone = mdtc_type(
                stack_num=stack_count,
                stack_size=stack_size,
                in_channels=hidden_dimension,
                res_channels=hidden_dimension,
                kernel_size=kernel_size,
                causal=True,
            )
            self.output = nn.Linear(hidden_dimension, CATEGORY_COUNT)

        def forward(self, features: object) -> object:
            downsampled = features[:, 1::2]
            projected = torch.nn.functional.gelu(
                self.projection(self.normalization(downsampled))
            )
            encoded, _ = self.backbone(projected)
            return self.output(encoded)

    return DistilledPhonemeStudent()


def posterior_distillation_losses(
    torch: object,
    logits: object,
    teacher_probabilities: object,
    *,
    speech_frame_weight: float,
) -> object:
    if speech_frame_weight < 1:
        raise ValueError("mdtc_distillation_speech_weight_invalid")
    log_probabilities = torch.nn.functional.log_softmax(logits.float(), dim=-1)
    teacher = teacher_probabilities.float()
    if log_probabilities.shape != teacher.shape:
        raise ValueError("mdtc_distillation_probability_shape_mismatch")
    cross_entropy = -(teacher * log_probabilities).sum(dim=-1)
    frame_weights = 1.0 + (speech_frame_weight - 1.0) * (
        1.0 - teacher[:, :, BLANK_ID]
    )
    return (cross_entropy * frame_weights).sum(dim=1) / frame_weights.sum(dim=1)


def logits_pairs(torch: object, logits: object) -> object:
    log_probabilities = torch.nn.functional.log_softmax(logits.float(), dim=-1)
    target = fixed_sequence_log_probability(torch, log_probabilities, TARGET_IDS)
    confusables = torch.stack(
        [
            fixed_sequence_log_probability(torch, log_probabilities, sequence)
            for sequence in CONFUSABLE_IDS
        ],
        dim=1,
    )
    blank = log_probabilities[:, :, BLANK_ID].sum(dim=1)
    return torch.stack(
        (
            (target - blank) / len(TARGET_IDS),
            (target - confusables.max(dim=1).values) / len(TARGET_IDS),
        ),
        dim=1,
    )


def predict_pairs(
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
            values.append(logits_pairs(torch, model(batch)).cpu().numpy())
    return np.concatenate(values).astype(np.float64)


def development_metrics(
    pairs: np.ndarray, labels: np.ndarray
) -> tuple[dict[str, object], float, np.ndarray]:
    operating = zero_false_rectangle(pairs[labels == 1], pairs[labels == 0])
    margins = combined_margins(pairs, operating)
    auc = roc_auc(margins[labels == 1], margins[labels == 0])
    return operating, auc, margins


def run(
    *,
    feature_manifest_path: Path,
    teacher_manifest_path: Path,
    wekws_directory: Path,
    output_directory: Path,
    hidden_dimension: int,
    stack_count: int,
    stack_size: int,
    kernel_size: int,
    epochs: int,
    patience: int,
    batch_size: int,
    learning_rate: float,
    speech_frame_weight: float,
    seed: int,
    device: str,
) -> dict[str, object]:
    if min(hidden_dimension, stack_count, stack_size, kernel_size, epochs, patience, batch_size) <= 0:
        raise ValueError("mdtc_distillation_schedule_invalid")
    if learning_rate <= 0 or speech_frame_weight < 1:
        raise ValueError("mdtc_distillation_optimization_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    teacher_manifest_path = teacher_manifest_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_distillation_output_exists:{output_directory}")
    feature_manifest = read_json(feature_manifest_path)
    teacher_manifest = read_json(teacher_manifest_path)
    if feature_manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_mdtc_distillation_feature_schema")
    if teacher_manifest.get("schema") != "baxy.phoneme-teacher-relevant-posteriors.v1":
        raise ValueError("unsupported_mdtc_distillation_teacher_schema")
    teacher_sources = teacher_manifest.get("sources")
    if not isinstance(teacher_sources, dict) or teacher_sources.get(
        "feature_manifest_sha256"
    ) != sha256(feature_manifest_path):
        raise ValueError("mdtc_distillation_teacher_feature_mismatch")
    if (
        feature_manifest.get("blind_human_partition_accessed") is not False
        or teacher_manifest.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("mdtc_distillation_blind_boundary_invalid")
    train_features, train_labels, _ = load_partition(
        feature_manifest, "base_train"
    )
    development_features, development_labels, _ = load_partition(
        feature_manifest, "base_development"
    )
    human_features, _, human_records = load_partition(
        feature_manifest, "human_development"
    )
    train_teacher = load_teacher_partition(
        teacher_manifest, "base_train", len(train_features)
    )
    development_teacher = load_teacher_partition(
        teacher_manifest, "base_development", len(development_features)
    )
    sys.path.insert(0, str(wekws_directory))
    import torch
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
    model = build_model(
        torch,
        MDTC,
        hidden_dimension=hidden_dimension,
        stack_count=stack_count,
        stack_size=stack_size,
        kernel_size=kernel_size,
    ).to(device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=5e-5
    )
    generator = torch.Generator().manual_seed(seed)
    dataset = torch.utils.data.TensorDataset(
        torch.from_numpy(train_features), torch.from_numpy(train_teacher)
    )
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    best_key = None
    best_state = None
    best_epoch = None
    history = []
    stale = 0
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        loss_sum = 0.0
        item_count = 0
        for features, teacher in loader:
            features = features.to(device)
            teacher = teacher.to(device)
            optimizer.zero_grad(set_to_none=True)
            losses = posterior_distillation_losses(
                torch,
                model(features),
                teacher,
                speech_frame_weight=speech_frame_weight,
            )
            loss = losses.mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            loss_sum += float(loss.detach().cpu()) * len(features)
            item_count += len(features)
        model.eval()
        development_loss_sum = 0.0
        with torch.inference_mode():
            for start in range(0, len(development_features), batch_size):
                features = torch.from_numpy(
                    development_features[start : start + batch_size]
                ).to(device)
                teacher = torch.from_numpy(
                    development_teacher[start : start + batch_size]
                ).to(device)
                losses = posterior_distillation_losses(
                    torch,
                    model(features),
                    teacher,
                    speech_frame_weight=speech_frame_weight,
                )
                development_loss_sum += float(losses.sum().cpu())
        pairs = predict_pairs(
            torch,
            model,
            development_features,
            device=device,
            batch_size=batch_size,
        )
        operating, auc, _ = development_metrics(pairs, development_labels)
        epoch_record = {
            "epoch": epoch,
            "train_distillation_loss": loss_sum / item_count,
            "development_distillation_loss": development_loss_sum
            / len(development_features),
            "development_dual_gate_auc": auc,
            "development_zero_false_operating_point": operating,
        }
        history.append(epoch_record)
        key = (
            float(operating["positive_recall"]),
            auc,
            -float(epoch_record["development_distillation_loss"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
            best_epoch = epoch_record
            stale = 0
        else:
            stale += 1
        print(
            f"EPOCH|{epoch}/{epochs}|recall={operating['positive_recall']:.6f}|auc={auc:.6f}|distill={epoch_record['development_distillation_loss']:.6f}",
            flush=True,
        )
        if stale >= patience:
            break
    if best_state is None or best_epoch is None:
        raise RuntimeError("mdtc_distillation_no_best_state")
    model.load_state_dict(best_state)
    model.eval()
    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mdtc_phoneme_distilled_student.pt"
    torch.save(best_state, checkpoint_path)
    development_pairs = predict_pairs(
        torch,
        model,
        development_features,
        device=device,
        batch_size=batch_size,
    )
    operating, development_auc, _ = development_metrics(
        development_pairs, development_labels
    )
    human_pairs = predict_pairs(
        torch,
        model,
        human_features,
        device=device,
        batch_size=batch_size,
    )
    human_margins = combined_margins(human_pairs, operating)
    human_clips = aggregate_clips(
        human_records, human_margins, calibration_threshold=0.0
    )
    positive_scores = np.asarray(
        [clip["score"] for clip in human_clips if clip["clip_label"] == "positive"]
    )
    negative_scores = np.asarray(
        [clip["score"] for clip in human_clips if clip["clip_label"] == "hard_negative"]
    )
    commit = subprocess.run(
        ["git", "-C", str(wekws_directory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report: dict[str, object] = {
        "schema": "baxy.mdtc-phoneme-distillation-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_teacher_student_without_human_training",
        "architecture": {
            "frontend": "80_bin_kaldi_fbank_downsampled_20ms",
            "classifier": "causal_mdtc_11_teacher_categories",
            "hidden_dimension": hidden_dimension,
            "stack_count": stack_count,
            "stack_size": stack_size,
            "kernel_size": kernel_size,
            "parameters": parameter_count,
            "receptive_field_frames": int(model.backbone.padding),
        },
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "teacher_manifest": teacher_manifest_path.as_posix(),
            "teacher_manifest_sha256": sha256(teacher_manifest_path),
            "wekws_directory": wekws_directory.as_posix(),
            "wekws_commit": commit,
            "wekws_license_sha256": sha256(wekws_directory / "LICENSE"),
            "wekws_mdtc_source_sha256": sha256(
                wekws_directory / "wekws" / "model" / "mdtc.py"
            ),
        },
        "training": {
            "epochs_requested": epochs,
            "epochs_completed": len(history),
            "patience": patience,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "speech_frame_weight": speech_frame_weight,
            "seed": seed,
            "device": device,
            "seconds": time.perf_counter() - started,
            "best_epoch": best_epoch,
            "history": history,
        },
        "artifacts": {
            "checkpoint": checkpoint_path.as_posix(),
            "checkpoint_sha256": sha256(checkpoint_path),
        },
        "development": {
            "zero_false_operating_point": operating,
            "combined_margin_auc": development_auc,
        },
        "human_development_unseen": {
            "positive_clips": int(len(positive_scores)),
            "hard_negative_clips": int(len(negative_scores)),
            "combined_margin_auc": roc_auc(positive_scores, negative_scores),
            "positive_accepted": int(np.count_nonzero(positive_scores >= 0)),
            "positive_total": int(len(positive_scores)),
            "negative_false_accepts": int(np.count_nonzero(negative_scores >= 0)),
            "negative_total": int(len(negative_scores)),
            "clips": human_clips,
        },
        "human_development_used_for_training": False,
        "candidate_development_use": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    report_path = output_directory / "development_report.v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--teacher-manifest", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hidden-dimension", type=int, default=32)
    parser.add_argument("--stack-count", type=int, default=3)
    parser.add_argument("--stack-size", type=int, default=4)
    parser.add_argument("--kernel-size", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--speech-frame-weight", type=float, default=16.0)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        feature_manifest_path=args.feature_manifest,
        teacher_manifest_path=args.teacher_manifest,
        wekws_directory=args.wekws_dir,
        output_directory=args.output_dir,
        hidden_dimension=args.hidden_dimension,
        stack_count=args.stack_count,
        stack_size=args.stack_size,
        kernel_size=args.kernel_size,
        epochs=args.epochs,
        patience=args.patience,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        speech_frame_weight=args.speech_frame_weight,
        seed=args.seed,
        device=args.device,
    )
    print(
        json.dumps(
            {
                "development": report["development"],
                "human": report["human_development_unseen"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
