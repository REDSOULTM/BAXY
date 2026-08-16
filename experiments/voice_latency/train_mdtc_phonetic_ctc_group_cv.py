"""Train and speaker-group cross-validate a tiny causal phonetic CTC verifier."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate_livekit_embedding_separability import aggregate_clips  # noqa: E402
from train_mdtc_livekit_verifier_student import (  # noqa: E402
    read_json,
    roc_auc,
    sha256,
    zero_false_operating_point,
)


BLANK_ID = 0
TARGET_IDS = (1, 2, 3, 4, 5)
VOCABULARY = {
    "<blank>": BLANK_ID,
    "B": 1,
    "A": 2,
    "K": 3,
    "S": 4,
    "I": 5,
}


def load_partition(
    manifest: dict[str, object], name: str
) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("mdtc_phonetic_ctc_outputs_missing")
    value = outputs.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"mdtc_phonetic_ctc_partition_missing:{name}")
    feature_path = Path(str(value.get("features"))).resolve(strict=True)
    label_path = Path(str(value.get("labels"))).resolve(strict=True)
    if sha256(feature_path) != value.get("features_sha256"):
        raise ValueError(f"mdtc_phonetic_ctc_feature_hash_mismatch:{name}")
    if sha256(label_path) != value.get("labels_sha256"):
        raise ValueError(f"mdtc_phonetic_ctc_label_hash_mismatch:{name}")
    features = np.load(feature_path, allow_pickle=False)
    labels = np.load(label_path, allow_pickle=False)
    records_value = value.get("records")
    if not isinstance(records_value, list):
        raise ValueError(f"mdtc_phonetic_ctc_records_missing:{name}")
    records = []
    for record in records_value:
        if not isinstance(record, dict):
            raise ValueError("mdtc_phonetic_ctc_record_invalid")
        records.append(record)
    if (
        features.ndim != 3
        or features.shape[1:] != (198, 80)
        or labels.ndim != 1
        or len(features) != len(labels)
        or len(records) != len(labels)
        or not np.isin(labels, (0, 1)).all()
    ):
        raise ValueError(f"mdtc_phonetic_ctc_partition_contract_invalid:{name}")
    return np.asarray(features, dtype=np.float32), labels.astype(np.int64), records


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

    class PhoneticCtcStudent(nn.Module):
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
            self.output = nn.Linear(hidden_dimension, len(VOCABULARY))

        def forward(self, features: object) -> object:
            projected = torch.nn.functional.gelu(
                self.projection(self.normalization(features))
            )
            encoded, _ = self.backbone(projected)
            return self.output(encoded)

    return PhoneticCtcStudent()


def ctc_training_losses(torch: object, logits: object, labels: object) -> object:
    log_probabilities = torch.nn.functional.log_softmax(logits.float(), dim=-1)
    batch_size, frames, _ = log_probabilities.shape
    losses = -log_probabilities[:, :, BLANK_ID].mean(dim=1)
    positive = labels == 1
    if bool(positive.any()):
        positive_count = int(positive.sum().item())
        targets = torch.tensor(
            TARGET_IDS,
            dtype=torch.long,
            device=log_probabilities.device,
        ).repeat(positive_count, 1)
        input_lengths = torch.full(
            (positive_count,), frames, dtype=torch.long, device=log_probabilities.device
        )
        target_lengths = torch.full(
            (positive_count,),
            len(TARGET_IDS),
            dtype=torch.long,
            device=log_probabilities.device,
        )
        positive_losses = torch.nn.functional.ctc_loss(
            log_probabilities[positive].transpose(0, 1),
            targets,
            input_lengths,
            target_lengths,
            blank=BLANK_ID,
            reduction="none",
            zero_infinity=True,
        ) / len(TARGET_IDS)
        losses = losses.clone()
        losses[positive] = positive_losses
    return losses


def ctc_target_margins(torch: object, logits: object) -> object:
    log_probabilities = torch.nn.functional.log_softmax(logits.float(), dim=-1)
    batch_size, frames, _ = log_probabilities.shape
    targets = torch.tensor(
        TARGET_IDS, dtype=torch.long, device=log_probabilities.device
    ).repeat(batch_size, 1)
    input_lengths = torch.full(
        (batch_size,), frames, dtype=torch.long, device=log_probabilities.device
    )
    target_lengths = torch.full(
        (batch_size,),
        len(TARGET_IDS),
        dtype=torch.long,
        device=log_probabilities.device,
    )
    target_log_probability = -torch.nn.functional.ctc_loss(
        log_probabilities.transpose(0, 1),
        targets,
        input_lengths,
        target_lengths,
        blank=BLANK_ID,
        reduction="none",
        zero_infinity=True,
    )
    blank_log_probability = log_probabilities[:, :, BLANK_ID].sum(dim=1)
    return (target_log_probability - blank_log_probability) / len(TARGET_IDS)


def predict_margins(
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
            values.append(ctc_target_margins(torch, model(batch)).cpu().numpy())
    return np.concatenate(values).astype(np.float64)


def train_fold(
    *,
    torch: object,
    mdtc_type: object,
    base_train_features: np.ndarray,
    base_train_labels: np.ndarray,
    base_train_weights: np.ndarray,
    base_development_features: np.ndarray,
    base_development_labels: np.ndarray,
    human_features: np.ndarray,
    human_labels: np.ndarray,
    human_groups: np.ndarray,
    held_out_group: str,
    output_path: Path,
    hidden_dimension: int,
    stack_count: int,
    stack_size: int,
    kernel_size: int,
    epochs: int,
    patience: int,
    batch_size: int,
    learning_rate: float,
    human_weight: float,
    seed: int,
    device: str,
) -> tuple[dict[str, object], object]:
    included = human_groups != held_out_group
    train_features = np.concatenate((base_train_features, human_features[included]))
    train_labels = np.concatenate((base_train_labels, human_labels[included]))
    train_weights = np.concatenate(
        (
            base_train_weights,
            np.full(np.count_nonzero(included), human_weight, np.float32),
        )
    )
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    model = build_model(
        torch,
        mdtc_type,
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
    best_state = None
    best_epoch = None
    history = []
    epochs_without_improvement = 0
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        weighted_loss_sum = 0.0
        weight_sum = 0.0
        for features, labels, weights in loader:
            features = features.to(device)
            labels = labels.to(device)
            weights = weights.to(device)
            optimizer.zero_grad(set_to_none=True)
            losses = ctc_training_losses(torch, model(features), labels)
            loss = (losses * weights).sum() / weights.sum()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            weighted_loss_sum += float((losses.detach() * weights).sum().cpu())
            weight_sum += float(weights.sum().cpu())
        scores = predict_margins(
            torch,
            model,
            base_development_features,
            device=device,
            batch_size=batch_size,
        )
        positive_scores = scores[base_development_labels == 1]
        negative_scores = scores[base_development_labels == 0]
        operating = zero_false_operating_point(positive_scores, negative_scores)
        auc = roc_auc(positive_scores, negative_scores)
        epoch_record = {
            "epoch": epoch,
            "train_loss": weighted_loss_sum / weight_sum,
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
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        print(
            f"EPOCH|held={held_out_group}|{epoch}/{epochs}|recall={operating['positive_recall']:.6f}|auc={auc:.6f}",
            flush=True,
        )
        if epochs_without_improvement >= patience:
            break
    if best_state is None or best_epoch is None:
        raise RuntimeError("mdtc_phonetic_ctc_no_best_state")
    model.load_state_dict(best_state)
    model.eval()
    torch.save(best_state, output_path)
    report = {
        "held_out_speaker_group": held_out_group,
        "included_human_windows": int(np.count_nonzero(included)),
        "excluded_human_windows": int(np.count_nonzero(~included)),
        "parameters": parameter_count,
        "receptive_field_frames": int(model.backbone.padding),
        "training_seconds": time.perf_counter() - started,
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "history": history,
        "checkpoint": output_path.as_posix(),
        "checkpoint_sha256": sha256(output_path),
    }
    return report, model


def run(
    *,
    feature_manifest_path: Path,
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
    hard_negative_weight: float,
    human_weight: float,
    seed: int,
    device: str,
) -> dict[str, object]:
    if min(hidden_dimension, stack_count, stack_size, kernel_size, epochs, patience, batch_size) <= 0:
        raise ValueError("mdtc_phonetic_ctc_schedule_invalid")
    if learning_rate <= 0 or hard_negative_weight < 1 or human_weight < 1:
        raise ValueError("mdtc_phonetic_ctc_optimization_invalid")
    if device not in {"cpu", "cuda"}:
        raise ValueError("mdtc_phonetic_ctc_device_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_phonetic_ctc_output_exists:{output_directory}")
    manifest = read_json(feature_manifest_path)
    if manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_mdtc_phonetic_ctc_feature_schema")
    if manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_phonetic_ctc_blind_boundary_invalid")
    base_train_features, base_train_labels, base_train_records = load_partition(
        manifest, "base_train"
    )
    base_development_features, base_development_labels, _ = load_partition(
        manifest, "base_development"
    )
    human_features, human_labels, human_records = load_partition(
        manifest, "human_development"
    )
    human_groups = np.asarray(
        [str(record.get("speaker_group")) for record in human_records]
    )
    groups = sorted(set(human_groups.tolist()))
    base_train_weights = np.asarray(
        [
            hard_negative_weight if "source_speaker_id" in record else 1.0
            for record in base_train_records
        ],
        dtype=np.float32,
    )
    sys.path.insert(0, str(wekws_directory))
    import torch
    from wekws.model.mdtc import MDTC

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    output_directory.mkdir(parents=True)
    folds = []
    out_of_fold_clips = []
    for index, group in enumerate(groups):
        print(f"FOLD|{index + 1}/{len(groups)}|held={group}", flush=True)
        checkpoint_path = output_directory / f"fold_{index + 1:02d}_{group}.pt"
        fold, model = train_fold(
            torch=torch,
            mdtc_type=MDTC,
            base_train_features=base_train_features,
            base_train_labels=base_train_labels,
            base_train_weights=base_train_weights,
            base_development_features=base_development_features,
            base_development_labels=base_development_labels,
            human_features=human_features,
            human_labels=human_labels,
            human_groups=human_groups,
            held_out_group=group,
            output_path=checkpoint_path,
            hidden_dimension=hidden_dimension,
            stack_count=stack_count,
            stack_size=stack_size,
            kernel_size=kernel_size,
            epochs=epochs,
            patience=patience,
            batch_size=batch_size,
            learning_rate=learning_rate,
            human_weight=human_weight,
            seed=seed,
            device=device,
        )
        development_scores = predict_margins(
            torch,
            model,
            base_development_features,
            device=device,
            batch_size=batch_size,
        )
        threshold = float(
            np.nextafter(
                development_scores[base_development_labels == 0].max(), math.inf
            )
        )
        held_mask = human_groups == group
        held_scores = predict_margins(
            torch,
            model,
            human_features[held_mask],
            device=device,
            batch_size=batch_size,
        )
        held_records = [
            record for item, record in zip(held_mask, human_records, strict=True) if item
        ]
        clips = aggregate_clips(
            held_records, held_scores, calibration_threshold=threshold
        )
        fold["calibration_threshold"] = threshold
        fold["clips"] = clips
        folds.append(fold)
        out_of_fold_clips.extend(clips)
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    positive_scores = np.asarray(
        [clip["score"] for clip in out_of_fold_clips if clip["clip_label"] == "positive"]
    )
    negative_scores = np.asarray(
        [clip["score"] for clip in out_of_fold_clips if clip["clip_label"] == "hard_negative"]
    )
    positive_margins = np.asarray(
        [clip["calibrated_margin"] for clip in out_of_fold_clips if clip["clip_label"] == "positive"]
    )
    negative_margins = np.asarray(
        [clip["calibrated_margin"] for clip in out_of_fold_clips if clip["clip_label"] == "hard_negative"]
    )
    commit = subprocess.run(
        ["git", "-C", str(wekws_directory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report: dict[str, object] = {
        "schema": "baxy.mdtc-phonetic-ctc-speaker-group-cross-validation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_leave_one_speaker_group_out",
        "architecture": {
            "frontend": "80_bin_kaldi_fbank_25ms_10ms",
            "classifier": "causal_mdtc_ctc_exact_b_a_k_s_i",
            "vocabulary": VOCABULARY,
            "hidden_dimension": hidden_dimension,
            "stack_count": stack_count,
            "stack_size": stack_size,
            "kernel_size": kernel_size,
        },
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "wekws_directory": wekws_directory.as_posix(),
            "wekws_commit": commit,
            "wekws_license_sha256": sha256(wekws_directory / "LICENSE"),
            "wekws_mdtc_source_sha256": sha256(
                wekws_directory / "wekws" / "model" / "mdtc.py"
            ),
        },
        "training": {
            "epochs": epochs,
            "patience": patience,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "hard_negative_weight": hard_negative_weight,
            "human_weight": human_weight,
            "seed": seed,
            "device": device,
        },
        "metrics": {
            "speaker_groups": len(groups),
            "positive_clips": int(len(positive_scores)),
            "hard_negative_clips": int(len(negative_scores)),
            "raw_clip_auc": roc_auc(positive_scores, negative_scores),
            "raw_zero_false_operating_point": zero_false_operating_point(
                positive_scores, negative_scores
            ),
            "calibrated_margin_auc": roc_auc(positive_margins, negative_margins),
            "positive_accepted_at_fold_calibration": int(
                np.count_nonzero(positive_margins >= 0)
            ),
            "positive_total": int(len(positive_margins)),
            "negative_false_at_fold_calibration": int(
                np.count_nonzero(negative_margins >= 0)
            ),
            "negative_total": int(len(negative_margins)),
        },
        "folds": folds,
        "candidate_development_use": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    report_path = output_directory / "cross_validation_report.v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hidden-dimension", type=int, default=32)
    parser.add_argument("--stack-count", type=int, default=3)
    parser.add_argument("--stack-size", type=int, default=4)
    parser.add_argument("--kernel-size", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--hard-negative-weight", type=float, default=2.0)
    parser.add_argument("--human-weight", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        feature_manifest_path=args.feature_manifest,
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
        hard_negative_weight=args.hard_negative_weight,
        human_weight=args.human_weight,
        seed=args.seed,
        device=args.device,
    )
    print(json.dumps({"metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
