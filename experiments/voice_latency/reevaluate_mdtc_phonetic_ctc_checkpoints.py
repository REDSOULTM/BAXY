"""Correctly re-aggregate frozen MDTC CTC fold checkpoints by human clip."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

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
from train_mdtc_phonetic_ctc_group_cv import (  # noqa: E402
    build_model,
    load_partition,
    predict_margins,
)


def run(
    *,
    feature_manifest_path: Path,
    original_report_path: Path,
    wekws_directory: Path,
    output_path: Path,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    original_report_path = original_report_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"mdtc_phonetic_ctc_reevaluation_exists:{output_path}")
    features_manifest = read_json(feature_manifest_path)
    original = read_json(original_report_path)
    if features_manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_mdtc_phonetic_ctc_reevaluation_features")
    if original.get("schema") != "baxy.mdtc-phonetic-ctc-speaker-group-cross-validation.v1":
        raise ValueError("unsupported_mdtc_phonetic_ctc_reevaluation_report")
    if (
        features_manifest.get("blind_human_partition_accessed") is not False
        or original.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("mdtc_phonetic_ctc_reevaluation_blind_boundary_invalid")
    development_features, development_labels, _ = load_partition(
        features_manifest, "base_development"
    )
    human_features, _, human_records = load_partition(
        features_manifest, "human_development"
    )
    human_groups = np.asarray(
        [str(record.get("speaker_group")) for record in human_records]
    )
    architecture = original.get("architecture")
    folds_value = original.get("folds")
    if not isinstance(architecture, dict) or not isinstance(folds_value, list):
        raise ValueError("mdtc_phonetic_ctc_reevaluation_contract_missing")
    source_folds = {
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
        source_fold = source_folds.get(group)
        if not isinstance(source_fold, dict):
            raise ValueError(f"mdtc_phonetic_ctc_reevaluation_fold_missing:{group}")
        checkpoint_path = Path(str(source_fold.get("checkpoint"))).resolve(strict=True)
        if sha256(checkpoint_path) != source_fold.get("checkpoint_sha256"):
            raise ValueError(f"mdtc_phonetic_ctc_checkpoint_hash_mismatch:{group}")
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
        development_scores = predict_margins(
            torch,
            model,
            development_features,
            device=device,
            batch_size=batch_size,
        )
        threshold = float(
            np.nextafter(
                development_scores[development_labels == 0].max(), math.inf
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
        folds.append(
            {
                "held_out_speaker_group": group,
                "checkpoint": checkpoint_path.as_posix(),
                "checkpoint_sha256": sha256(checkpoint_path),
                "calibration_threshold": threshold,
                "clips": clips,
            }
        )
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
    report: dict[str, object] = {
        "schema": "baxy.mdtc-phonetic-ctc-checkpoint-reevaluation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "corrected_development_clip_aggregation_without_retraining",
        "correction": {
            "invalid_original_report": original_report_path.as_posix(),
            "invalid_original_report_sha256": sha256(original_report_path),
            "defect": (
                "human manifest stores relative_path; original aggregator expected "
                "output_relative_path and collapsed clips per speaker group"
            ),
            "training_repeated": False,
            "checkpoints_changed": False,
        },
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "wekws_directory": wekws_directory.as_posix(),
        },
        "architecture": architecture,
        "metrics": {
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
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--original-report", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        feature_manifest_path=args.feature_manifest,
        original_report_path=args.original_report,
        wekws_directory=args.wekws_dir,
        output_path=args.output,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps({"metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
