"""Measure the MDTC student on speaker-disjoint raw negative development."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np


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


def summarize_activations(
    records: list[dict[str, object]],
    scores: np.ndarray,
    *,
    threshold: float,
    exposure_hours: float,
) -> dict[str, object]:
    values = np.asarray(scores, dtype=np.float64).reshape(-1)
    if len(records) != len(values) or not records:
        raise ValueError("mdtc_raw_negative_score_count_mismatch")
    if not 0.0 < threshold < 1.0 or exposure_hours <= 0.0:
        raise ValueError("mdtc_raw_negative_operating_point_invalid")
    by_utterance: dict[str, float] = {}
    for record, score in zip(records, values, strict=True):
        utterance = str(record["source_utterance_id"])
        by_utterance[utterance] = max(by_utterance.get(utterance, -math.inf), float(score))
    activated = {
        utterance: score
        for utterance, score in by_utterance.items()
        if score >= threshold
    }
    count = len(activated)
    return {
        "candidate_windows": len(records),
        "candidate_utterances": len(by_utterance),
        "false_activations": count,
        "point_false_activations_per_hour": count / exposure_hours,
        "zero_event_upper_95_fpph": -math.log(0.05) / exposure_hours if count == 0 else None,
        "maximum_score": max(by_utterance.values()),
        "activated_utterances": activated,
    }


def evaluate(
    *,
    hard_window_manifest_path: Path,
    hard_feature_manifest_path: Path,
    student_report_path: Path,
    output_path: Path,
    threshold_override: float | None,
) -> dict[str, object]:
    hard_window_manifest_path = hard_window_manifest_path.resolve(strict=True)
    hard_feature_manifest_path = hard_feature_manifest_path.resolve(strict=True)
    student_report_path = student_report_path.resolve(strict=True)
    windows = read_json(hard_window_manifest_path)
    features = read_json(hard_feature_manifest_path)
    student = read_json(student_report_path)
    if windows.get("schema") != "baxy.mdtc-hard-negative-windows.v1":
        raise ValueError("unsupported_mdtc_hard_negative_schema")
    if features.get("schema") != "baxy.mdtc-hard-negative-livekit-features.v1":
        raise ValueError("unsupported_mdtc_hard_feature_schema")
    if student.get("schema") != "baxy.mdtc-livekit-verifier-student-development.v1":
        raise ValueError("unsupported_mdtc_student_schema")
    if any(
        value.get("blind_human_partition_accessed") is not False
        for value in (windows, features, student)
    ):
        raise ValueError("mdtc_raw_negative_blind_boundary_invalid")
    if features.get("hard_negative_manifest_sha256") != sha256(hard_window_manifest_path):
        raise ValueError("mdtc_raw_negative_window_manifest_hash_mismatch")
    outputs = features.get("outputs")
    artifacts = student.get("artifacts")
    training = student.get("training")
    if not isinstance(outputs, dict) or not isinstance(artifacts, dict) or not isinstance(training, dict):
        raise ValueError("mdtc_raw_negative_evidence_missing")
    development_output = outputs.get("development")
    if not isinstance(development_output, dict):
        raise ValueError("mdtc_raw_negative_development_features_missing")
    feature_path = Path(str(development_output["path"])).resolve(strict=True)
    if sha256(feature_path) != development_output.get("sha256"):
        raise ValueError("mdtc_raw_negative_feature_hash_mismatch")
    feature_values = np.load(feature_path, allow_pickle=False).astype(np.float32)
    window_records = windows.get("records")
    if not isinstance(window_records, list):
        raise ValueError("mdtc_raw_negative_window_records_missing")
    development_records = [
        record
        for record in window_records
        if isinstance(record, dict) and record.get("split") == "development"
    ]
    expected_ids = [str(record["output_relative_path"]) for record in development_records]
    if development_output.get("record_ids") != expected_ids:
        raise ValueError("mdtc_raw_negative_feature_order_mismatch")
    student_path = Path(str(artifacts["onnx"])).resolve(strict=True)
    if sha256(student_path) != artifacts.get("onnx_sha256"):
        raise ValueError("mdtc_raw_negative_student_hash_mismatch")
    best_epoch = training.get("best_epoch")
    if not isinstance(best_epoch, dict) or not isinstance(best_epoch.get("zero_false_operating_point"), dict):
        raise ValueError("mdtc_raw_negative_student_threshold_missing")
    report_threshold = float(best_epoch["zero_false_operating_point"]["threshold"])
    threshold = report_threshold if threshold_override is None else threshold_override
    if not 0.0 < threshold < 1.0:
        raise ValueError("mdtc_raw_negative_threshold_invalid")
    import onnxruntime as ort

    session = ort.InferenceSession(str(student_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    logits = []
    for start in range(0, len(feature_values), 512):
        logits.append(
            np.asarray(
                session.run(None, {input_name: feature_values[start : start + 512]})[0]
            ).reshape(-1)
        )
    raw_logits = np.concatenate(logits)
    scores = 1.0 / (1.0 + np.exp(-raw_logits))
    corpus_manifest_path = Path(str(windows["corpus_manifest"])).resolve(strict=True)
    if sha256(corpus_manifest_path) != windows.get("corpus_manifest_sha256"):
        raise ValueError("mdtc_raw_negative_corpus_hash_mismatch")
    corpus = read_json(corpus_manifest_path)
    corpus_records = corpus.get("records")
    split = windows.get("split")
    if not isinstance(corpus_records, list) or not isinstance(split, dict):
        raise ValueError("mdtc_raw_negative_corpus_evidence_missing")
    development_speakers = {str(value) for value in split["development_speakers"]}
    exposure_records = [
        record
        for record in corpus_records
        if isinstance(record, dict) and str(record.get("speaker_id")) in development_speakers
    ]
    exposure_seconds = sum(float(record["duration_seconds"]) for record in exposure_records)
    exposure_hours = exposure_seconds / 3600.0
    metrics = summarize_activations(
        development_records,
        scores,
        threshold=threshold,
        exposure_hours=exposure_hours,
    )
    scored_records = [
        {
            **record,
            "student_score": float(score),
            "activated": bool(score >= threshold),
        }
        for record, score in zip(development_records, scores, strict=True)
    ]
    report: dict[str, object] = {
        "schema": "baxy.mdtc-student-raw-negative-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "speaker_disjoint_raw_negative_model_selection_development",
        "independent_holdout": False,
        "product_far_claim_supported": False,
        "reason_product_far_claim_not_supported": "development_speakers_used_for_epoch_and_threshold_selection_and_exposure_below_30_hours",
        "hard_window_manifest": hard_window_manifest_path.as_posix(),
        "hard_window_manifest_sha256": sha256(hard_window_manifest_path),
        "hard_feature_manifest": hard_feature_manifest_path.as_posix(),
        "hard_feature_manifest_sha256": sha256(hard_feature_manifest_path),
        "student_report": student_report_path.as_posix(),
        "student_report_sha256": sha256(student_report_path),
        "student_onnx": student_path.as_posix(),
        "student_onnx_sha256": sha256(student_path),
        "threshold": threshold,
        "threshold_source": "override" if threshold_override is not None else "student_training_development",
        "student_report_threshold": report_threshold,
        "exposure": {
            "speakers": sorted(development_speakers),
            "utterances": len(exposure_records),
            "seconds": exposure_seconds,
            "hours": exposure_hours,
        },
        "metrics": metrics,
        "records": scored_records,
        "candidate_frozen": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hard-window-manifest", type=Path, required=True)
    parser.add_argument("--hard-feature-manifest", type=Path, required=True)
    parser.add_argument("--student-report", type=Path, required=True)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        hard_window_manifest_path=args.hard_window_manifest,
        hard_feature_manifest_path=args.hard_feature_manifest,
        student_report_path=args.student_report,
        output_path=args.output,
        threshold_override=args.threshold,
    )
    print(json.dumps({"exposure": report["exposure"], "metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
