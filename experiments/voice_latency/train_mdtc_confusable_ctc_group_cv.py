"""Train tiny MDTC CTC with explicit BAXI-versus-confusable competition."""

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
from train_mdtc_phonetic_ctc_group_cv import load_partition  # noqa: E402


VOCABULARY = {
    "<blank>": 0,
    "B": 1,
    "V": 2,
    "F": 3,
    "P": 4,
    "A": 5,
    "K": 6,
    "S": 7,
    "SH": 8,
    "I": 9,
}
BLANK_ID = VOCABULARY["<blank>"]
TARGET_IDS = (1, 5, 6, 7, 9)
CONFUSABLE_IDS = (
    (2, 5, 6, 7, 9),
    (3, 5, 6, 7, 9),
    (4, 5, 6, 7, 9),
    (1, 5, 6, 8, 9),
)
PHRASE_SEQUENCES = {
    "vaxi": CONFUSABLE_IDS[0],
    "viplav_vaxi": CONFUSABLE_IDS[0],
    "faxi": CONFUSABLE_IDS[1],
    "mahesh_faxi": CONFUSABLE_IDS[1],
    "paxi": CONFUSABLE_IDS[2],
    "bakshi": CONFUSABLE_IDS[3],
    "tarang_bakshi": CONFUSABLE_IDS[3],
    "upendra_bakshi": CONFUSABLE_IDS[3],
}
HUMAN_GROUP_SEQUENCES = {
    "viplav_vaxi": CONFUSABLE_IDS[0],
    "mahesh_faxi": CONFUSABLE_IDS[1],
    "tarang_bakshi": CONFUSABLE_IDS[3],
    "upendra_bakshi": CONFUSABLE_IDS[3],
}


def target_arrays(
    records: list[dict[str, object]], labels: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    label_values = np.asarray(labels).reshape(-1)
    if len(records) != len(label_values):
        raise ValueError("mdtc_confusable_ctc_target_shape_invalid")
    targets = np.zeros((len(records), len(TARGET_IDS)), dtype=np.int64)
    lengths = np.zeros(len(records), dtype=np.int64)
    for index, (record, label) in enumerate(
        zip(records, label_values, strict=True)
    ):
        sequence = None
        if int(label) == 1:
            sequence = TARGET_IDS
        else:
            phrase = record.get("phrase_id")
            group = record.get("speaker_group")
            if isinstance(phrase, str):
                sequence = PHRASE_SEQUENCES.get(phrase)
            if sequence is None and isinstance(group, str):
                sequence = HUMAN_GROUP_SEQUENCES.get(group)
        if sequence is not None:
            targets[index] = sequence
            lengths[index] = len(sequence)
    return targets, lengths


def explicit_confusable_mask(
    targets: np.ndarray, target_lengths: np.ndarray
) -> np.ndarray:
    values = np.asarray(targets)
    lengths = np.asarray(target_lengths).reshape(-1)
    if values.shape != (len(lengths), len(TARGET_IDS)):
        raise ValueError("mdtc_confusable_ctc_mask_shape_invalid")
    return (lengths > 0) & np.any(
        values != np.asarray(TARGET_IDS, dtype=values.dtype), axis=1
    )


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

    class ConfusableCtcStudent(nn.Module):
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

    return ConfusableCtcStudent()


def training_losses(
    torch: object,
    logits: object,
    targets: object,
    target_lengths: object,
) -> object:
    log_probabilities = torch.nn.functional.log_softmax(logits.float(), dim=-1)
    _, frames, _ = log_probabilities.shape
    losses = -log_probabilities[:, :, BLANK_ID].mean(dim=1)
    labeled = target_lengths > 0
    if bool(labeled.any()):
        labeled_count = int(labeled.sum().item())
        input_lengths = torch.full(
            (labeled_count,), frames, dtype=torch.long, device=logits.device
        )
        ctc_losses = torch.nn.functional.ctc_loss(
            log_probabilities[labeled].transpose(0, 1),
            targets[labeled],
            input_lengths,
            target_lengths[labeled],
            blank=BLANK_ID,
            reduction="none",
            zero_infinity=True,
        ) / target_lengths[labeled]
        losses = losses.clone()
        losses[labeled] = ctc_losses
    return losses


def fixed_sequence_log_probability(
    torch: object, log_probabilities: object, sequence: tuple[int, ...]
) -> object:
    batch_size, frames, _ = log_probabilities.shape
    targets = torch.tensor(
        sequence, dtype=torch.long, device=log_probabilities.device
    ).repeat(batch_size, 1)
    input_lengths = torch.full(
        (batch_size,), frames, dtype=torch.long, device=log_probabilities.device
    )
    target_lengths = torch.full(
        (batch_size,), len(sequence), dtype=torch.long, device=log_probabilities.device
    )
    return -torch.nn.functional.ctc_loss(
        log_probabilities.transpose(0, 1),
        targets,
        input_lengths,
        target_lengths,
        blank=BLANK_ID,
        reduction="none",
        zero_infinity=True,
    )


def confusable_margins(torch: object, logits: object) -> object:
    log_probabilities = torch.nn.functional.log_softmax(logits.float(), dim=-1)
    target = fixed_sequence_log_probability(torch, log_probabilities, TARGET_IDS)
    confusables = torch.stack(
        [
            fixed_sequence_log_probability(torch, log_probabilities, sequence)
            for sequence in CONFUSABLE_IDS
        ],
        dim=1,
    )
    return (target - confusables.max(dim=1).values) / len(TARGET_IDS)


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
            values.append(confusable_margins(torch, model(batch)).cpu().numpy())
    return np.concatenate(values).astype(np.float64)


def train_fold(
    *,
    torch: object,
    mdtc_type: object,
    base_train_features: np.ndarray,
    base_train_targets: np.ndarray,
    base_train_target_lengths: np.ndarray,
    base_train_weights: np.ndarray,
    development_features: np.ndarray,
    development_labels: np.ndarray,
    human_features: np.ndarray,
    human_targets: np.ndarray,
    human_target_lengths: np.ndarray,
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
    confusable_weight: float,
    seed: int,
    device: str,
) -> tuple[dict[str, object], object]:
    included = human_groups != held_out_group
    features = np.concatenate((base_train_features, human_features[included]))
    targets = np.concatenate((base_train_targets, human_targets[included]))
    target_lengths = np.concatenate(
        (base_train_target_lengths, human_target_lengths[included])
    )
    human_weights = np.full(np.count_nonzero(included), human_weight, np.float32)
    human_weights[
        explicit_confusable_mask(
            human_targets[included], human_target_lengths[included]
        )
    ] *= confusable_weight
    weights = np.concatenate(
        (
            base_train_weights,
            human_weights,
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
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=5e-5
    )
    generator = torch.Generator().manual_seed(seed)
    dataset = torch.utils.data.TensorDataset(
        torch.from_numpy(features),
        torch.from_numpy(targets),
        torch.from_numpy(target_lengths),
        torch.from_numpy(weights),
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
        weighted_loss_sum = 0.0
        weight_sum = 0.0
        for batch_features, batch_targets, batch_lengths, batch_weights in loader:
            batch_features = batch_features.to(device)
            batch_targets = batch_targets.to(device)
            batch_lengths = batch_lengths.to(device)
            batch_weights = batch_weights.to(device)
            optimizer.zero_grad(set_to_none=True)
            losses = training_losses(
                torch,
                model(batch_features),
                batch_targets,
                batch_lengths,
            )
            loss = (losses * batch_weights).sum() / batch_weights.sum()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            weighted_loss_sum += float(
                (losses.detach() * batch_weights).sum().cpu()
            )
            weight_sum += float(batch_weights.sum().cpu())
        scores = predict_margins(
            torch,
            model,
            development_features,
            device=device,
            batch_size=batch_size,
        )
        positive = scores[development_labels == 1]
        negative = scores[development_labels == 0]
        operating = zero_false_operating_point(positive, negative)
        auc = roc_auc(positive, negative)
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
            stale = 0
        else:
            stale += 1
        print(
            f"EPOCH|held={held_out_group}|{epoch}/{epochs}|recall={operating['positive_recall']:.6f}|auc={auc:.6f}",
            flush=True,
        )
        if stale >= patience:
            break
    if best_state is None or best_epoch is None:
        raise RuntimeError("mdtc_confusable_ctc_no_best_state")
    model.load_state_dict(best_state)
    model.eval()
    torch.save(best_state, output_path)
    return (
        {
            "held_out_speaker_group": held_out_group,
            "included_human_windows": int(np.count_nonzero(included)),
            "excluded_human_windows": int(np.count_nonzero(~included)),
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "receptive_field_frames": int(model.backbone.padding),
            "training_seconds": time.perf_counter() - started,
            "best_epoch": best_epoch,
            "epochs_completed": len(history),
            "history": history,
            "checkpoint": output_path.as_posix(),
            "checkpoint_sha256": sha256(output_path),
        },
        model,
    )


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
    confusable_weight: float,
    seed: int,
    device: str,
) -> dict[str, object]:
    if hard_negative_weight < 1 or human_weight < 1 or confusable_weight < 1:
        raise ValueError("mdtc_confusable_ctc_weight_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_confusable_ctc_output_exists:{output_directory}")
    feature_manifest = read_json(feature_manifest_path)
    if feature_manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_mdtc_confusable_ctc_feature_schema")
    if feature_manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_confusable_ctc_blind_boundary_invalid")
    base_features, base_labels, base_records = load_partition(
        feature_manifest, "base_train"
    )
    development_features, development_labels, development_records = load_partition(
        feature_manifest, "base_development"
    )
    human_features, human_labels, human_records = load_partition(
        feature_manifest, "human_development"
    )
    base_targets, base_target_lengths = target_arrays(base_records, base_labels)
    development_targets, development_target_lengths = target_arrays(
        development_records, development_labels
    )
    human_targets, human_target_lengths = target_arrays(human_records, human_labels)
    human_groups = np.asarray(
        [str(record.get("speaker_group")) for record in human_records]
    )
    groups = sorted(set(human_groups.tolist()))
    base_weights = np.asarray(
        [
            hard_negative_weight if "source_speaker_id" in record else 1.0
            for record in base_records
        ],
        dtype=np.float32,
    )
    base_weights[
        explicit_confusable_mask(base_targets, base_target_lengths)
    ] *= confusable_weight
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
            base_train_features=base_features,
            base_train_targets=base_targets,
            base_train_target_lengths=base_target_lengths,
            base_train_weights=base_weights,
            development_features=development_features,
            development_labels=development_labels,
            human_features=human_features,
            human_targets=human_targets,
            human_target_lengths=human_target_lengths,
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
            confusable_weight=confusable_weight,
            seed=seed,
            device=device,
        )
        development_scores = predict_margins(
            torch,
            model,
            development_features,
            device=device,
            batch_size=batch_size,
        )
        threshold = float(
            np.nextafter(development_scores[development_labels == 0].max(), math.inf)
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
        "schema": "baxy.mdtc-confusable-phonetic-ctc-group-cv.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_leave_one_speaker_group_out",
        "architecture": {
            "frontend": "80_bin_kaldi_fbank_25ms_10ms",
            "classifier": "causal_mdtc_ctc_target_minus_best_confusable",
            "vocabulary": VOCABULARY,
            "target_ids": TARGET_IDS,
            "confusable_ids": CONFUSABLE_IDS,
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
        "target_counts": {
            "base_train_exact_sequences": int(np.count_nonzero(base_target_lengths)),
            "base_development_exact_sequences": int(
                np.count_nonzero(development_target_lengths)
            ),
            "human_exact_sequences": int(np.count_nonzero(human_target_lengths)),
        },
        "training": {
            "epochs": epochs,
            "patience": patience,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "hard_negative_weight": hard_negative_weight,
            "human_weight": human_weight,
            "confusable_weight": confusable_weight,
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
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--hard-negative-weight", type=float, default=2.0)
    parser.add_argument("--human-weight", type=float, default=8.0)
    parser.add_argument("--confusable-weight", type=float, default=1.0)
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
        confusable_weight=args.confusable_weight,
        seed=args.seed,
        device=args.device,
    )
    print(json.dumps({"metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
