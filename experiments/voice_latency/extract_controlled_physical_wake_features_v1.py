"""Extract frozen LiveKit features from a controlled physical-room corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


CORPUS_SCHEMA = "baxy.controlled-physical-wake-corpus.v1"
FEATURE_SCHEMA = "baxy.controlled-physical-wake-livekit-features.v1"
OPENED_LOCALIZATION_SCHEMA = "baxy.opened-human-wake-parakeet-localization.v1"
FEATURE_SHAPE = (16, 96)
SAMPLE_RATE = 16_000
WINDOW_SECONDS = 2.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def development_record(record: dict[str, object], salt: str) -> bool:
    source_hash = record.get("sourceSha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("controlled_physical_feature_source_identity_invalid")
    digest = hashlib.sha256(f"{salt}:{source_hash}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 5 == 0


def split_records(
    records: list[dict[str, object]], salt: str
) -> dict[str, list[dict[str, object]]]:
    result = {
        "positive_train": [],
        "positive_development": [],
        "negative_train": [],
        "negative_development": [],
    }
    for record in records:
        record_id = record.get("recordId")
        if not isinstance(record_id, str) or "/" not in record_id:
            raise ValueError("controlled_physical_feature_record_id_invalid")
        label = record_id.split("/", 1)[0]
        if label not in {"positive", "negative"}:
            raise ValueError("controlled_physical_feature_label_invalid")
        partition = "development" if development_record(record, salt) else "train"
        result[f"{label}_{partition}"].append(record)
    if any(not values for values in result.values()):
        raise ValueError("controlled_physical_feature_split_empty")
    return result


def load_teacher_target_spans(
    corpus_manifest_path: Path,
    teacher_report_path: Path,
) -> dict[str, tuple[float, float]]:
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    teacher_report_path = teacher_report_path.resolve(strict=True)
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8-sig"))
    teacher = json.loads(teacher_report_path.read_text(encoding="utf-8-sig"))
    if corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("controlled_physical_feature_teacher_corpus_schema_invalid")
    if teacher.get("schema") != "baxy.ccby-wake-ctc-cascade-development.v1":
        raise ValueError("controlled_physical_feature_teacher_schema_invalid")
    if teacher.get("partition") != "development" or teacher.get(
        "blind_human_partition_accessed"
    ) is not False:
        raise ValueError("controlled_physical_feature_teacher_boundary_invalid")
    if teacher.get("corpus_manifest_sha256") != sha256(corpus_manifest_path):
        raise ValueError("controlled_physical_feature_teacher_corpus_digest_mismatch")
    corpus_records = corpus.get("records")
    teacher_records = teacher.get("records")
    if not isinstance(corpus_records, list) or not isinstance(teacher_records, list):
        raise ValueError("controlled_physical_feature_teacher_records_invalid")
    teacher_by_path = {
        str(record.get("output_relative_path")): record
        for record in teacher_records
        if isinstance(record, dict) and record.get("label") == "positive"
    }
    result: dict[str, tuple[float, float]] = {}
    for record in corpus_records:
        if not isinstance(record, dict) or record.get("partition") != "development":
            continue
        if record.get("label") != "positive":
            continue
        wav = record.get("wav")
        relative = record.get("output_relative_path")
        teacher_record = teacher_by_path.get(str(relative))
        if not isinstance(wav, dict) or not isinstance(teacher_record, dict):
            raise ValueError("controlled_physical_feature_teacher_binding_missing")
        source_hash = wav.get("sha256")
        best = teacher_record.get("best_verifier")
        if not isinstance(source_hash, str) or not isinstance(best, dict):
            raise ValueError("controlled_physical_feature_teacher_span_missing")
        span = (
            float(best["locator_start_seconds"]),
            float(best["locator_end_seconds"]),
        )
        if not (0.0 <= span[0] < span[1]):
            raise ValueError("controlled_physical_feature_teacher_span_invalid")
        result[source_hash] = span
    if not result:
        raise ValueError("controlled_physical_feature_teacher_spans_empty")
    return result


def load_opened_target_spans(report_path: Path) -> dict[str, tuple[float, float]]:
    report_path = report_path.resolve(strict=True)
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    if report.get("schema") != OPENED_LOCALIZATION_SCHEMA:
        raise ValueError("controlled_physical_feature_opened_teacher_schema_invalid")
    if report.get("blindHumanPartitionAccessed") is not False:
        raise ValueError("controlled_physical_feature_opened_teacher_boundary_invalid")
    records = report.get("records")
    if not isinstance(records, list):
        raise ValueError("controlled_physical_feature_opened_teacher_records_invalid")
    result: dict[str, tuple[float, float]] = {}
    for record in records:
        if not isinstance(record, dict) or record.get("targetSpanSeconds") is None:
            continue
        source_hash = record.get("sourceSha256")
        span = record.get("targetSpanSeconds")
        if not isinstance(source_hash, str) or not isinstance(span, dict):
            raise ValueError("controlled_physical_feature_opened_teacher_span_invalid")
        values = (float(span["start"]), float(span["end"]))
        if not 0.0 <= values[0] < values[1]:
            raise ValueError("controlled_physical_feature_opened_teacher_span_invalid")
        result[source_hash] = values
    if not result:
        raise ValueError("controlled_physical_feature_opened_teacher_spans_empty")
    return result


def retain_localized_positives(
    split: dict[str, list[dict[str, object]]],
    target_spans: dict[str, tuple[float, float]],
) -> dict[str, list[dict[str, object]]]:
    filtered = {name: list(records) for name, records in split.items()}
    for name in ("positive_train", "positive_development"):
        filtered[name] = [
            record
            for record in filtered[name]
            if record.get("sourceSha256") in target_spans
        ]
        if not filtered[name]:
            raise ValueError("controlled_physical_feature_localized_split_empty")
    return filtered


def target_aligned_window(
    audio: np.ndarray,
    target_span: tuple[float, float],
) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    target_start, target_end = target_span
    duration = values.size / SAMPLE_RATE
    if not (0.0 <= target_start < target_end <= duration + 1e-3):
        raise ValueError("controlled_physical_feature_target_span_outside_audio")
    window_samples = round(WINDOW_SECONDS * SAMPLE_RATE)
    center = (target_start + target_end) / 2.0
    start_seconds = min(
        max(0.0, center - WINDOW_SECONDS / 2.0),
        max(0.0, duration - WINDOW_SECONDS),
    )
    start = round(start_seconds * SAMPLE_RATE)
    result = values[start : start + window_samples]
    if result.size < window_samples:
        result = np.pad(result, (0, window_samples - result.size))
    return result.astype(np.float32)


def extract_record_features(
    *,
    records: list[dict[str, object]],
    corpus_root: Path,
    mel_frontend: object,
    speech_embedding: object,
    teacher_spans_by_source_sha: dict[str, tuple[float, float]] | None = None,
) -> np.ndarray:
    import soundfile as sf
    from livekit.wakeword.data.features import _pad_or_truncate

    output: list[np.ndarray] = []
    for record in records:
        relative = record.get("output")
        expected_hash = record.get("outputSha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ValueError("controlled_physical_feature_output_identity_invalid")
        path = (corpus_root / relative).resolve(strict=True)
        if corpus_root not in path.parents or sha256(path) != expected_hash:
            raise ValueError("controlled_physical_feature_output_digest_mismatch")
        audio, sample_rate = sf.read(str(path), dtype="float32")
        if sample_rate != SAMPLE_RATE or audio.ndim != 1:
            raise ValueError("controlled_physical_feature_audio_contract_invalid")
        record_id = str(record.get("recordId", ""))
        if teacher_spans_by_source_sha is not None and record_id.startswith(
            "positive/"
        ):
            source_hash = str(record.get("sourceSha256", ""))
            span = teacher_spans_by_source_sha.get(source_hash)
            if span is None:
                raise ValueError("controlled_physical_feature_teacher_source_unmatched")
            audio = target_aligned_window(audio, span)
        mel = mel_frontend(audio)
        embeddings = speech_embedding.extract_embeddings(mel)
        output.append(_pad_or_truncate(embeddings[0]))
    return np.stack(output).astype(np.float32)


def training_repeat_weight(
    partition_name: str,
    *,
    default_repeats: int,
    positive_repeats: int | None,
    negative_repeats: int | None,
) -> int:
    if not partition_name.endswith("_train"):
        return 1
    if partition_name.startswith("positive_"):
        return positive_repeats or default_repeats
    if partition_name.startswith("negative_"):
        return negative_repeats or default_repeats
    raise ValueError("controlled_physical_feature_partition_invalid")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split-salt", default="baxy-physical-room-features-v1")
    parser.add_argument("--train-repeats", type=int, default=16)
    parser.add_argument("--positive-train-repeats", type=int)
    parser.add_argument("--negative-train-repeats", type=int)
    parser.add_argument("--teacher-corpus-manifest", type=Path)
    parser.add_argument("--teacher-report", type=Path)
    parser.add_argument("--opened-localization-report", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    repeat_values = {
        "--train-repeats": args.train_repeats,
        "--positive-train-repeats": args.positive_train_repeats,
        "--negative-train-repeats": args.negative_train_repeats,
    }
    for argument, value in repeat_values.items():
        if value is not None and not 1 <= value <= 128:
            raise SystemExit(f"{argument} must be between 1 and 128.")
    if (args.teacher_corpus_manifest is None) != (args.teacher_report is None):
        raise SystemExit(
            "--teacher-corpus-manifest and --teacher-report must be supplied together."
        )
    if args.opened_localization_report is not None and args.teacher_report is not None:
        raise SystemExit("Opened and CTC teacher reports are mutually exclusive.")
    manifest_path = args.corpus_manifest.resolve(strict=True)
    corpus_root = manifest_path.parent
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source.get("schema") != CORPUS_SCHEMA:
        raise ValueError("controlled_physical_feature_corpus_schema_invalid")
    if source.get("blindHumanPartitionAccessed") is not False:
        raise ValueError("controlled_physical_feature_blind_boundary_invalid")
    records = source.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("controlled_physical_feature_records_invalid")
    split = split_records(records, args.split_salt)
    if args.opened_localization_report is not None:
        teacher_spans = load_opened_target_spans(args.opened_localization_report)
        teacher_method = "opened_development_parakeet_token_timestamp_span"
        teacher_inputs = [args.opened_localization_report.resolve()]
    elif args.teacher_corpus_manifest is not None:
        teacher_spans = load_teacher_target_spans(
            args.teacher_corpus_manifest, args.teacher_report
        )
        teacher_method = "opened_development_ctc_exact_target_span"
        teacher_inputs = [
            args.teacher_corpus_manifest.resolve(),
            args.teacher_report.resolve(),
        ]
    else:
        teacher_spans = None
        teacher_method = None
        teacher_inputs = []
    if teacher_spans is not None:
        split = retain_localized_positives(split, teacher_spans)
    output_directory = args.output_dir.resolve()
    if output_directory.exists():
        raise SystemExit("Output directory already exists.")
    output_directory.mkdir(parents=True, exist_ok=False)

    from livekit.wakeword.models.feature_extractor import (
        MelSpectrogramFrontend,
        SpeechEmbedding,
    )
    from livekit.wakeword.resources import (
        get_embedding_model_path,
        get_mel_model_path,
    )

    mel_path = Path(get_mel_model_path()).resolve(strict=True)
    embedding_path = Path(get_embedding_model_path()).resolve(strict=True)
    mel_frontend = MelSpectrogramFrontend(onnx_path=mel_path)
    speech_embedding = SpeechEmbedding(onnx_path=embedding_path)
    started = time.perf_counter()
    outputs: dict[str, dict[str, object]] = {}
    for name, partition_records in split.items():
        features = extract_record_features(
            records=partition_records,
            corpus_root=corpus_root,
            mel_frontend=mel_frontend,
            speech_embedding=speech_embedding,
            teacher_spans_by_source_sha=teacher_spans,
        )
        source_records = int(features.shape[0])
        repeats = training_repeat_weight(
            name,
            default_repeats=args.train_repeats,
            positive_repeats=args.positive_train_repeats,
            negative_repeats=args.negative_train_repeats,
        )
        if repeats > 1:
            features = np.repeat(features, repeats, axis=0)
        output_path = output_directory / f"{name}.npy"
        np.save(output_path, features)
        outputs[name] = {
            "path": output_path.as_posix(),
            "sha256": sha256(output_path),
            "shape": list(features.shape),
            "sourceRecords": source_records,
            "repeatWeight": repeats,
        }
    report = {
        "schema": FEATURE_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "controlled_physical_room_livekit_feature_extension",
        "corpusManifest": manifest_path.as_posix(),
        "corpusManifestSha256": sha256(manifest_path),
        "splitSalt": args.split_salt,
        "trainRepeats": args.train_repeats,
        "positiveTrainRepeats": args.positive_train_repeats or args.train_repeats,
        "negativeTrainRepeats": args.negative_train_repeats or args.train_repeats,
        "teacherAlignment": (
            {
                "method": teacher_method,
                "inputs": [
                    {"path": path.as_posix(), "sha256": sha256(path)}
                    for path in teacher_inputs
                ],
                "boundPositiveSourceCount": len(teacher_spans or {}),
            }
            if teacher_spans is not None
            else None
        ),
        "frontend": {
            "melModelSha256": sha256(mel_path),
            "embeddingModelSha256": sha256(embedding_path),
            "featureShape": list(FEATURE_SHAPE),
        },
        "outputs": outputs,
        "elapsedSeconds": time.perf_counter() - started,
        "blind_human_partition_accessed": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    report_path = output_directory / "livekit_features.manifest.v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({name: value["shape"] for name, value in outputs.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
