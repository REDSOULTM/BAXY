"""Evaluate frozen confusable-CTC folds with presence plus rivalry gates."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate_livekit_embedding_separability import aggregate_clips  # noqa: E402
from train_mdtc_confusable_ctc_group_cv import (  # noqa: E402
    BLANK_ID,
    CONFUSABLE_IDS,
    TARGET_IDS,
    VOCABULARY,
    build_model,
    fixed_sequence_log_probability,
)
from train_mdtc_livekit_verifier_student import (  # noqa: E402
    read_json,
    roc_auc,
    sha256,
)
from train_mdtc_phonetic_ctc_group_cv import load_partition  # noqa: E402


def zero_false_rectangle(
    positive_pairs: np.ndarray, negative_pairs: np.ndarray
) -> dict[str, object]:
    positive = np.asarray(positive_pairs, dtype=np.float64)
    negative = np.asarray(negative_pairs, dtype=np.float64)
    if positive.ndim != 2 or negative.ndim != 2 or positive.shape[1:] != (2,) or negative.shape[1:] != (2,):
        raise ValueError("mdtc_confusable_dual_pair_shape_invalid")
    if len(positive) == 0 or len(negative) == 0:
        raise ValueError("mdtc_confusable_dual_partition_empty")
    if not np.isfinite(positive).all() or not np.isfinite(negative).all():
        raise ValueError("mdtc_confusable_dual_pair_values_invalid")
    presence_candidates = [
        float(np.nextafter(negative[:, 0].min(), -np.inf)),
        *[
            float(np.nextafter(value, np.inf))
            for value in np.unique(negative[:, 0])
        ],
    ]
    minimum_rivalry = float(
        np.nextafter(
            min(positive[:, 1].min(), negative[:, 1].min()), -np.inf
        )
    )
    best = None
    for presence_threshold in presence_candidates:
        active_negative = negative[:, 0] >= presence_threshold
        rivalry_threshold = (
            float(np.nextafter(negative[active_negative, 1].max(), np.inf))
            if np.any(active_negative)
            else minimum_rivalry
        )
        positive_accepted = (
            (positive[:, 0] >= presence_threshold)
            & (positive[:, 1] >= rivalry_threshold)
        )
        negative_accepted = (
            (negative[:, 0] >= presence_threshold)
            & (negative[:, 1] >= rivalry_threshold)
        )
        candidate = {
            "presence_threshold": presence_threshold,
            "rivalry_threshold": rivalry_threshold,
            "positive_accepted": int(np.count_nonzero(positive_accepted)),
            "positive_total": int(len(positive)),
            "positive_recall": float(np.mean(positive_accepted)),
            "negative_false_accepts": int(np.count_nonzero(negative_accepted)),
        }
        key = (
            candidate["positive_accepted"],
            -presence_threshold,
            -rivalry_threshold,
        )
        if best is None or key > best[0]:
            best = (key, candidate)
    if best is None or best[1]["negative_false_accepts"] != 0:
        raise RuntimeError("mdtc_confusable_dual_no_zero_false_rectangle")
    return best[1]


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


def combined_margins(pairs: np.ndarray, operating: dict[str, object]) -> np.ndarray:
    values = np.asarray(pairs, dtype=np.float64)
    return np.minimum(
        values[:, 0] - float(operating["presence_threshold"]),
        values[:, 1] - float(operating["rivalry_threshold"]),
    )


def run(
    *,
    feature_manifest_path: Path,
    training_report_path: Path,
    wekws_directory: Path,
    output_path: Path,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    training_report_path = training_report_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"mdtc_confusable_dual_output_exists:{output_path}")
    features_manifest = read_json(feature_manifest_path)
    training_report = read_json(training_report_path)
    if features_manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_mdtc_confusable_dual_features")
    if training_report.get("schema") != "baxy.mdtc-confusable-phonetic-ctc-group-cv.v1":
        raise ValueError("unsupported_mdtc_confusable_dual_training_report")
    if (
        features_manifest.get("blind_human_partition_accessed") is not False
        or training_report.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("mdtc_confusable_dual_blind_boundary_invalid")
    development_features, development_labels, _ = load_partition(
        features_manifest, "base_development"
    )
    human_features, _, human_records = load_partition(
        features_manifest, "human_development"
    )
    human_groups = np.asarray(
        [str(record.get("speaker_group")) for record in human_records]
    )
    architecture = training_report.get("architecture")
    folds_value = training_report.get("folds")
    if not isinstance(architecture, dict) or not isinstance(folds_value, list):
        raise ValueError("mdtc_confusable_dual_training_contract_missing")
    folds_by_group = {
        str(fold.get("held_out_speaker_group")): fold
        for fold in folds_value
        if isinstance(fold, dict)
    }
    sys.path.insert(0, str(wekws_directory))
    import torch
    from wekws.model.mdtc import MDTC

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    folds = []
    out_of_fold_clips = []
    for group in sorted(set(human_groups.tolist())):
        source_fold = folds_by_group.get(group)
        if not isinstance(source_fold, dict):
            raise ValueError(f"mdtc_confusable_dual_fold_missing:{group}")
        checkpoint_path = Path(str(source_fold.get("checkpoint"))).resolve(strict=True)
        if sha256(checkpoint_path) != source_fold.get("checkpoint_sha256"):
            raise ValueError(f"mdtc_confusable_dual_checkpoint_hash_mismatch:{group}")
        model = build_model(
            torch,
            MDTC,
            hidden_dimension=int(architecture["hidden_dimension"]),
            stack_count=int(architecture["stack_count"]),
            stack_size=int(architecture["stack_size"]),
            kernel_size=int(architecture["kernel_size"]),
        ).to(device)
        model.load_state_dict(
            torch.load(checkpoint_path, map_location=device, weights_only=True)
        )
        model.eval()
        development_pairs = predict_pairs(
            torch,
            model,
            development_features,
            device=device,
            batch_size=batch_size,
        )
        operating = zero_false_rectangle(
            development_pairs[development_labels == 1],
            development_pairs[development_labels == 0],
        )
        held_mask = human_groups == group
        held_pairs = predict_pairs(
            torch,
            model,
            human_features[held_mask],
            device=device,
            batch_size=batch_size,
        )
        margins = combined_margins(held_pairs, operating)
        held_records = [
            record for item, record in zip(held_mask, human_records, strict=True) if item
        ]
        clips = aggregate_clips(held_records, margins, calibration_threshold=0.0)
        folds.append(
            {
                "held_out_speaker_group": group,
                "checkpoint": checkpoint_path.as_posix(),
                "checkpoint_sha256": sha256(checkpoint_path),
                "development_operating_point": operating,
                "clips": clips,
            }
        )
        out_of_fold_clips.extend(clips)
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    positive = np.asarray(
        [clip["score"] for clip in out_of_fold_clips if clip["clip_label"] == "positive"]
    )
    negative = np.asarray(
        [clip["score"] for clip in out_of_fold_clips if clip["clip_label"] == "hard_negative"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mdtc-confusable-ctc-dual-gate-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_checkpoint_reevaluation_without_retraining",
        "mechanism": {
            "presence": "target_ctc_log_probability_minus_blank_path",
            "rivalry": "target_ctc_log_probability_minus_best_explicit_confusable",
            "acceptance": "both_thresholds_met_on_same_window",
            "operating_point": "maximum_positive_window_recall_with_zero_development_negative_windows",
        },
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "training_report": training_report_path.as_posix(),
            "training_report_sha256": sha256(training_report_path),
            "wekws_directory": wekws_directory.as_posix(),
        },
        "architecture": architecture,
        "metrics": {
            "positive_clips": int(len(positive)),
            "hard_negative_clips": int(len(negative)),
            "calibrated_combined_margin_auc": roc_auc(positive, negative),
            "positive_accepted": int(np.count_nonzero(positive >= 0)),
            "positive_total": int(len(positive)),
            "negative_false_accepts": int(np.count_nonzero(negative >= 0)),
            "negative_total": int(len(negative)),
        },
        "folds": folds,
        "candidate_development_use": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--training-report", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        feature_manifest_path=args.feature_manifest,
        training_report_path=args.training_report,
        wekws_directory=args.wekws_dir,
        output_path=args.output,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps({"metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
