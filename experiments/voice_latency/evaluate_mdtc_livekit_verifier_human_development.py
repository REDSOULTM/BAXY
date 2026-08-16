"""Evaluate the tiny LiveKit-embedding verifier on human development audio."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scan_openslr_librispeech_livekit_development import (  # noqa: E402
    BatchedLiveKitPredictor,
    SAMPLE_RATE,
    STEP_SECONDS,
    WINDOW_SECONDS,
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


def development_records(corpus: dict[str, object]) -> list[dict[str, object]]:
    if corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("unsupported_ccby_corpus_schema")
    records = corpus.get("records")
    if not isinstance(records, list):
        raise ValueError("ccby_corpus_records_missing")
    selected = [
        record
        for record in records
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    labels = {str(record.get("label")) for record in selected}
    if not selected or labels != {"positive", "hard_negative"}:
        raise ValueError("ccby_development_labels_invalid")
    return selected


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"ccby_wav_contract_mismatch:{path}:{contract}")
        payload = source.readframes(source.getnframes())
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def product_windows(audio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    window_samples = round(WINDOW_SECONDS * SAMPLE_RATE)
    step_samples = round(STEP_SECONDS * SAMPLE_RATE)
    padded = np.concatenate(
        (
            np.zeros(window_samples, np.float32),
            np.asarray(audio, dtype=np.float32).reshape(-1),
            np.zeros(window_samples, np.float32),
        )
    )
    ends = np.arange(window_samples, len(padded) + 1, step_samples)
    windows = np.stack([padded[end - window_samples : end] for end in ends])
    end_seconds = (ends - window_samples) / SAMPLE_RATE
    return windows, end_seconds


def human_zero_false_point(records: list[dict[str, object]]) -> dict[str, object]:
    positive = [
        float(record["maximum_student_score"])
        for record in records
        if record["label"] == "positive" and record["maximum_student_score"] is not None
    ]
    negative = [
        float(record["maximum_student_score"])
        for record in records
        if record["label"] == "hard_negative" and record["maximum_student_score"] is not None
    ]
    positive_total = sum(record["label"] == "positive" for record in records)
    if len(positive) != positive_total or not negative:
        return {"possible": False, "reason": "stage1_did_not_cover_every_positive"}
    maximum_negative = max(negative)
    threshold = float(np.nextafter(maximum_negative, math.inf))
    accepted = sum(score >= threshold for score in positive)
    return {
        "possible": accepted == positive_total,
        "threshold": threshold,
        "maximum_negative_score": maximum_negative,
        "minimum_positive_score": min(positive),
        "positive_accepted": accepted,
        "positive_total": positive_total,
        "recall": accepted / positive_total,
        "hard_negative_false_accepts": sum(score >= threshold for score in negative),
        "score_separation": min(positive) - maximum_negative,
    }


def evaluate(
    *,
    corpus_manifest_path: Path,
    livekit_model_path: Path,
    student_report_path: Path,
    livekit_proposal_threshold: float,
    output_path: Path,
) -> dict[str, object]:
    if not 0.0 < livekit_proposal_threshold < 1.0:
        raise ValueError("mdtc_human_livekit_threshold_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    livekit_model_path = livekit_model_path.resolve(strict=True)
    student_report_path = student_report_path.resolve(strict=True)
    corpus = read_json(corpus_manifest_path)
    records = development_records(corpus)
    student_report = read_json(student_report_path)
    if student_report.get("schema") != "baxy.mdtc-livekit-verifier-student-development.v1":
        raise ValueError("unsupported_mdtc_student_schema")
    if student_report.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_human_student_blind_boundary_invalid")
    artifacts = student_report.get("artifacts")
    training = student_report.get("training")
    if not isinstance(artifacts, dict) or not isinstance(training, dict):
        raise ValueError("mdtc_human_student_evidence_missing")
    student_path = Path(str(artifacts["onnx"])).resolve(strict=True)
    if sha256(student_path) != artifacts.get("onnx_sha256"):
        raise ValueError("mdtc_human_student_hash_mismatch")
    best_epoch = training.get("best_epoch")
    if not isinstance(best_epoch, dict):
        raise ValueError("mdtc_human_student_operating_point_missing")
    operating = best_epoch.get("zero_false_operating_point")
    if not isinstance(operating, dict):
        raise ValueError("mdtc_human_student_operating_point_missing")
    student_threshold = float(operating["threshold"])
    predictor = BatchedLiveKitPredictor(livekit_model_path, batch_size=64)
    import onnxruntime as ort

    session = ort.InferenceSession(
        str(student_path), providers=["CPUExecutionProvider"]
    )
    input_name = session.get_inputs()[0].name
    corpus_root = corpus_manifest_path.parent
    evaluated: list[dict[str, object]] = []
    for record in records:
        relative_path = str(record["output_relative_path"])
        path = corpus_root / relative_path
        wav_contract = record.get("wav")
        if not isinstance(wav_contract, dict) or sha256(path) != wav_contract.get(
            "sha256"
        ):
            raise ValueError(f"mdtc_human_audio_hash_mismatch:{relative_path}")
        windows, end_seconds = product_windows(read_wav(path))
        features = predictor.extract_features(windows)
        livekit_scores = predictor.predict_features(features)
        logits = np.asarray(
            session.run(None, {input_name: features})[0]
        ).reshape(-1)
        student_scores = 1.0 / (1.0 + np.exp(-logits))
        candidate_indices = np.flatnonzero(
            livekit_scores >= livekit_proposal_threshold
        )
        candidates = [
            {
                "window_end_seconds": float(end_seconds[index]),
                "livekit_score": float(livekit_scores[index]),
                "student_score": float(student_scores[index]),
            }
            for index in candidate_indices
        ]
        best = max(candidates, key=lambda item: item["student_score"]) if candidates else None
        maximum_student = float(best["student_score"]) if best else None
        detected = bool(
            maximum_student is not None and maximum_student >= student_threshold
        )
        evaluated.append(
            {
                "source_id": record["source_id"],
                "speaker_group": record["speaker_group"],
                "label": record["label"],
                "output_relative_path": relative_path,
                "candidate_windows": candidates,
                "best_candidate": best,
                "maximum_student_score": maximum_student,
                "detected_at_training_threshold": detected,
                "correct_at_training_threshold": detected if record["label"] == "positive" else not detected,
            }
        )
    positive = [record for record in evaluated if record["label"] == "positive"]
    negative = [record for record in evaluated if record["label"] == "hard_negative"]
    true_positive = sum(record["detected_at_training_threshold"] for record in positive)
    false_positive = sum(record["detected_at_training_threshold"] for record in negative)
    human_point = human_zero_false_point(evaluated)
    report: dict[str, object] = {
        "schema": "baxy.mdtc-livekit-verifier-human-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": sha256(corpus_manifest_path),
        "livekit": {
            "model": livekit_model_path.as_posix(),
            "model_sha256": sha256(livekit_model_path),
            "proposal_threshold": livekit_proposal_threshold,
        },
        "student": {
            "report": student_report_path.as_posix(),
            "report_sha256": sha256(student_report_path),
            "onnx": student_path.as_posix(),
            "onnx_sha256": sha256(student_path),
            "training_development_threshold": student_threshold,
        },
        "metrics_at_training_development_threshold": {
            "positive_clips": len(positive),
            "hard_negative_clips": len(negative),
            "stage1_positive_proposals": sum(record["maximum_student_score"] is not None for record in positive),
            "true_positive": true_positive,
            "false_negative": len(positive) - true_positive,
            "recall": true_positive / len(positive),
            "false_positive": false_positive,
            "hard_negative_rejection": 1.0 - false_positive / len(negative),
            "gate_passed": true_positive == len(positive) and false_positive == 0,
        },
        "human_development_zero_false_point": human_point,
        "records": evaluated,
        "candidate_frozen": False,
        "product_operating_point": False,
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
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--livekit-model", type=Path, required=True)
    parser.add_argument("--student-report", type=Path, required=True)
    parser.add_argument("--livekit-proposal-threshold", type=float, default=0.02)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        corpus_manifest_path=args.corpus_manifest,
        livekit_model_path=args.livekit_model,
        student_report_path=args.student_report,
        livekit_proposal_threshold=args.livekit_proposal_threshold,
        output_path=args.output,
    )
    print(json.dumps({"metrics": report["metrics_at_training_development_threshold"], "human_point": report["human_development_zero_false_point"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
