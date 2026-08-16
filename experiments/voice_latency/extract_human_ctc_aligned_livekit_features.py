"""Extract teacher-aligned LiveKit windows from human wake development audio."""

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


def contains_target(
    window_end_seconds: float,
    *,
    target_start_seconds: float,
    target_end_seconds: float,
) -> bool:
    if not (
        math.isfinite(window_end_seconds)
        and math.isfinite(target_start_seconds)
        and math.isfinite(target_end_seconds)
        and target_end_seconds > target_start_seconds
    ):
        raise ValueError("human_feature_alignment_invalid")
    window_start_seconds = window_end_seconds - WINDOW_SECONDS
    return (
        window_start_seconds <= target_start_seconds
        and target_end_seconds <= window_end_seconds
    )


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"human_feature_wav_contract_mismatch:{path}:{contract}")
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
    return (
        np.stack([padded[end - window_samples : end] for end in ends]),
        (ends - window_samples) / SAMPLE_RATE,
    )


def extract(
    *,
    corpus_manifest_path: Path,
    teacher_report_path: Path,
    livekit_model_path: Path,
    output_directory: Path,
) -> dict[str, object]:
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    teacher_report_path = teacher_report_path.resolve(strict=True)
    livekit_model_path = livekit_model_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"human_feature_output_exists:{output_directory}")
    corpus = read_json(corpus_manifest_path)
    teacher = read_json(teacher_report_path)
    if corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("unsupported_ccby_corpus_schema")
    if teacher.get("schema") != "baxy.ccby-wake-ctc-cascade-development.v1":
        raise ValueError("unsupported_human_teacher_schema")
    if teacher.get("partition") != "development":
        raise ValueError("human_feature_teacher_partition_invalid")
    if teacher.get("corpus_manifest_sha256") != sha256(corpus_manifest_path):
        raise ValueError("human_feature_teacher_corpus_hash_mismatch")
    if teacher.get("blind_human_partition_accessed") is not False:
        raise ValueError("human_feature_blind_boundary_invalid")
    corpus_records = corpus.get("records")
    teacher_records = teacher.get("records")
    if not isinstance(corpus_records, list) or not isinstance(teacher_records, list):
        raise ValueError("human_feature_records_missing")
    development = [
        record
        for record in corpus_records
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    teacher_by_path = {
        str(record.get("output_relative_path")): record
        for record in teacher_records
        if isinstance(record, dict)
    }
    if set(teacher_by_path) != {
        str(record["output_relative_path"]) for record in development
    }:
        raise ValueError("human_feature_teacher_record_set_mismatch")
    predictor = BatchedLiveKitPredictor(livekit_model_path, batch_size=64)
    root = corpus_manifest_path.parent
    feature_chunks: list[np.ndarray] = []
    labels: list[int] = []
    metadata: list[dict[str, object]] = []
    for record in development:
        relative_path = str(record["output_relative_path"])
        path = root / relative_path
        wav_contract = record.get("wav")
        if not isinstance(wav_contract, dict) or sha256(path) != wav_contract.get(
            "sha256"
        ):
            raise ValueError(f"human_feature_audio_hash_mismatch:{relative_path}")
        windows, end_seconds = product_windows(read_wav(path))
        features = predictor.extract_features(windows)
        livekit_scores = predictor.predict_features(features)
        teacher_record = teacher_by_path[relative_path]
        target_span: tuple[float, float] | None = None
        if record["label"] == "positive":
            best = teacher_record.get("best_verifier")
            if not isinstance(best, dict):
                raise ValueError(f"human_feature_positive_teacher_span_missing:{relative_path}")
            target_span = (
                float(best["locator_start_seconds"]),
                float(best["locator_end_seconds"]),
            )
        for index, end in enumerate(end_seconds):
            label = int(
                target_span is not None
                and contains_target(
                    float(end),
                    target_start_seconds=target_span[0],
                    target_end_seconds=target_span[1],
                )
            )
            labels.append(label)
            metadata.append(
                {
                    "source_id": record["source_id"],
                    "speaker_group": record["speaker_group"],
                    "clip_label": record["label"],
                    "output_relative_path": relative_path,
                    "window_end_seconds": float(end),
                    "livekit_score": float(livekit_scores[index]),
                    "teacher_aligned_label": label,
                }
            )
        feature_chunks.append(features)
    feature_values = np.concatenate(feature_chunks).astype(np.float32)
    label_values = np.asarray(labels, dtype=np.uint8)
    if len(feature_values) != len(label_values) or len(metadata) != len(labels):
        raise ValueError("human_feature_output_count_mismatch")
    if not np.any(label_values == 1) or not np.any(label_values == 0):
        raise ValueError("human_feature_output_labels_invalid")
    output_directory.mkdir(parents=True)
    feature_path = output_directory / "features.npy"
    label_path = output_directory / "labels.npy"
    np.save(feature_path, feature_values, allow_pickle=False)
    np.save(label_path, label_values, allow_pickle=False)
    report: dict[str, object] = {
        "schema": "baxy.human-ctc-aligned-livekit-features.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "human_development_teacher_student_distillation",
        "partition": "development",
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": sha256(corpus_manifest_path),
        "teacher_report": teacher_report_path.as_posix(),
        "teacher_report_sha256": sha256(teacher_report_path),
        "livekit_model": livekit_model_path.as_posix(),
        "livekit_model_sha256": sha256(livekit_model_path),
        "frontend": {
            "mel_model": predictor.mel_path.as_posix(),
            "mel_model_sha256": sha256(predictor.mel_path),
            "embedding_model": predictor.embedding_path.as_posix(),
            "embedding_model_sha256": sha256(predictor.embedding_path),
        },
        "outputs": {
            "features": feature_path.as_posix(),
            "features_sha256": sha256(feature_path),
            "features_shape": list(feature_values.shape),
            "labels": label_path.as_posix(),
            "labels_sha256": sha256(label_path),
            "labels_shape": list(label_values.shape),
        },
        "metrics": {
            "clips": len(development),
            "speaker_groups": len({record["speaker_group"] for record in development}),
            "windows": len(labels),
            "positive_windows": int(label_values.sum()),
            "negative_windows": int(len(label_values) - label_values.sum()),
        },
        "records": metadata,
        "candidate_development_use": True,
        "candidate_frozen": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    manifest_path = output_directory / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--teacher-report", type=Path, required=True)
    parser.add_argument("--livekit-model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract(
        corpus_manifest_path=args.corpus_manifest,
        teacher_report_path=args.teacher_report,
        livekit_model_path=args.livekit_model,
        output_directory=args.output_dir,
    )
    print(json.dumps({"output": args.output_dir.resolve().as_posix(), "metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
