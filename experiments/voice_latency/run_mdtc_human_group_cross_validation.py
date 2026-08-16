"""Run leave-one-speaker-group-out development validation for the MDTC student."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_mdtc_livekit_verifier_student import (  # noqa: E402
    load_feature,
    read_json,
    roc_auc,
    sha256,
    train,
    zero_false_operating_point,
)


def sigmoid(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    return 1.0 / (1.0 + np.exp(-values))


def clip_scores(
    records: list[dict[str, object]], scores: np.ndarray
) -> list[dict[str, object]]:
    values = np.asarray(scores, dtype=np.float64).reshape(-1)
    if len(records) != len(values) or not np.isfinite(values).all():
        raise ValueError("mdtc_human_cv_score_shape_invalid")
    paths = sorted({str(record.get("output_relative_path")) for record in records})
    output = []
    for path in paths:
        indexes = [
            index
            for index, record in enumerate(records)
            if str(record.get("output_relative_path")) == path
        ]
        labels = {str(records[index].get("clip_label")) for index in indexes}
        groups = {str(records[index].get("speaker_group")) for index in indexes}
        if len(labels) != 1 or len(groups) != 1:
            raise ValueError("mdtc_human_cv_clip_contract_invalid")
        aligned = [
            index
            for index in indexes
            if int(records[index].get("teacher_aligned_label", 0)) == 1
        ]
        output.append(
            {
                "output_relative_path": path,
                "speaker_group": next(iter(groups)),
                "clip_label": next(iter(labels)),
                "score": float(values[indexes].max()),
                "teacher_aligned_max_score": None
                if not aligned
                else float(values[aligned].max()),
                "windows": len(indexes),
            }
        )
    return output


def run(
    *,
    synthetic_directory: Path,
    hard_feature_manifest_path: Path,
    human_feature_manifest_path: Path,
    wekws_directory: Path,
    output_directory: Path,
    hidden_dimension: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    hard_negative_weight: float,
    human_weight: float,
    seed: int,
    device: str,
) -> dict[str, object]:
    import onnxruntime as ort

    human_feature_manifest_path = human_feature_manifest_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_human_cv_output_exists:{output_directory}")
    human = read_json(human_feature_manifest_path)
    if human.get("schema") != "baxy.human-ctc-aligned-livekit-features.v2":
        raise ValueError("unsupported_mdtc_human_cv_feature_schema")
    if human.get("partition") != "development":
        raise ValueError("mdtc_human_cv_partition_invalid")
    if human.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_human_cv_blind_boundary_invalid")
    outputs = human.get("outputs")
    records_value = human.get("records")
    if not isinstance(outputs, dict) or not isinstance(records_value, list):
        raise ValueError("mdtc_human_cv_inputs_missing")
    records = []
    for record in records_value:
        if not isinstance(record, dict):
            raise ValueError("mdtc_human_cv_record_invalid")
        records.append(record)
    feature_path = Path(str(outputs.get("features"))).resolve(strict=True)
    label_path = Path(str(outputs.get("labels"))).resolve(strict=True)
    if sha256(feature_path) != outputs.get("features_sha256"):
        raise ValueError("mdtc_human_cv_feature_hash_mismatch")
    if sha256(label_path) != outputs.get("labels_sha256"):
        raise ValueError("mdtc_human_cv_label_hash_mismatch")
    features = load_feature(feature_path)
    labels = np.load(label_path, allow_pickle=False)
    if len(features) != len(labels) or len(records) != len(labels):
        raise ValueError("mdtc_human_cv_input_shape_invalid")
    groups = sorted({str(record.get("speaker_group")) for record in records})
    if len(groups) < 2:
        raise ValueError("mdtc_human_cv_groups_insufficient")
    output_directory.mkdir(parents=True)
    fold_reports = []
    out_of_fold_clips: list[dict[str, object]] = []
    for fold_index, group in enumerate(groups):
        print(
            f"FOLD|{fold_index + 1}/{len(groups)}|held_out={group}", flush=True
        )
        fold_directory = output_directory / f"fold_{fold_index + 1:02d}_{group}"
        training_report = train(
            synthetic_directory=synthetic_directory,
            hard_feature_manifest_path=hard_feature_manifest_path,
            wekws_directory=wekws_directory,
            output_directory=fold_directory,
            hidden_dimension=hidden_dimension,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            hard_negative_weight=hard_negative_weight,
            human_feature_manifest_path=human_feature_manifest_path,
            excluded_human_speaker_group=group,
            human_weight=human_weight,
            seed=seed,
            device=device,
        )
        artifact = training_report.get("artifacts")
        if not isinstance(artifact, dict):
            raise ValueError("mdtc_human_cv_training_artifact_missing")
        onnx_path = Path(str(artifact.get("onnx"))).resolve(strict=True)
        if sha256(onnx_path) != artifact.get("onnx_sha256"):
            raise ValueError("mdtc_human_cv_onnx_hash_mismatch")
        indexes = np.asarray(
            [
                index
                for index, record in enumerate(records)
                if str(record.get("speaker_group")) == group
            ],
            dtype=np.int64,
        )
        session = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        held_logits = np.asarray(
            session.run(None, {"features": features[indexes]})[0]
        ).reshape(-1)
        held_scores = sigmoid(held_logits)
        held_records = [records[index] for index in indexes]
        held_clips = clip_scores(held_records, held_scores)
        out_of_fold_clips.extend(held_clips)
        fold_reports.append(
            {
                "held_out_speaker_group": group,
                "held_out_windows": int(len(indexes)),
                "held_out_positive_windows": int(np.asarray(labels[indexes]).sum()),
                "training_report": (
                    fold_directory / "development_report.v2.json"
                ).as_posix(),
                "training_report_sha256": sha256(
                    fold_directory / "development_report.v2.json"
                ),
                "onnx_sha256": sha256(onnx_path),
                "clips": held_clips,
            }
        )
    positive_scores = np.asarray(
        [record["score"] for record in out_of_fold_clips if record["clip_label"] == "positive"],
        dtype=np.float64,
    )
    negative_scores = np.asarray(
        [record["score"] for record in out_of_fold_clips if record["clip_label"] == "hard_negative"],
        dtype=np.float64,
    )
    operating = zero_false_operating_point(positive_scores, negative_scores)
    report: dict[str, object] = {
        "schema": "baxy.mdtc-human-speaker-group-cross-validation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_leave_one_speaker_group_out",
        "sources": {
            "synthetic_directory": synthetic_directory.resolve(strict=True).as_posix(),
            "hard_feature_manifest": hard_feature_manifest_path.resolve(strict=True).as_posix(),
            "hard_feature_manifest_sha256": sha256(hard_feature_manifest_path.resolve(strict=True)),
            "human_feature_manifest": human_feature_manifest_path.as_posix(),
            "human_feature_manifest_sha256": sha256(human_feature_manifest_path),
            "wekws_directory": wekws_directory.resolve(strict=True).as_posix(),
        },
        "training": {
            "hidden_dimension": hidden_dimension,
            "epochs": epochs,
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
            "clip_auc": roc_auc(positive_scores, negative_scores),
            "zero_false_operating_point": operating,
        },
        "folds": fold_reports,
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
    parser.add_argument("--synthetic-dir", type=Path, required=True)
    parser.add_argument("--hard-feature-manifest", type=Path, required=True)
    parser.add_argument("--human-feature-manifest", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hidden-dimension", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--hard-negative-weight", type=float, default=2.0)
    parser.add_argument("--human-weight", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        synthetic_directory=args.synthetic_dir,
        hard_feature_manifest_path=args.hard_feature_manifest,
        human_feature_manifest_path=args.human_feature_manifest,
        wekws_directory=args.wekws_dir,
        output_directory=args.output_dir,
        hidden_dimension=args.hidden_dimension,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        hard_negative_weight=args.hard_negative_weight,
        human_weight=args.human_weight,
        seed=args.seed,
        device=args.device,
    )
    print(json.dumps({"metrics": report["metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
