"""Build speaker-disjoint 2-second MDTC hard negatives from a LiveKit scan."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_openslr_librispeech_retained_parakeet import decode_flac  # noqa: E402


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 2 * SAMPLE_RATE


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


def development_speakers(
    speaker_ids: set[str], *, salt: str, count: int
) -> tuple[str, ...]:
    if not speaker_ids or not 0 < count < len(speaker_ids):
        raise ValueError("mdtc_hard_negative_speaker_split_invalid")
    ranked = sorted(
        speaker_ids,
        key=lambda speaker: hashlib.sha256(
            f"{salt}|{speaker}".encode("utf-8")
        ).hexdigest(),
    )
    return tuple(sorted(ranked[:count]))


def extract_window(audio: np.ndarray, end_seconds: float) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all() or end_seconds < 0.0:
        raise ValueError("mdtc_hard_negative_audio_invalid")
    end = round(end_seconds * SAMPLE_RATE)
    start = end - WINDOW_SAMPLES
    output = np.zeros(WINDOW_SAMPLES, np.float32)
    source_start = max(0, start)
    source_end = min(len(values), end)
    if source_end > source_start:
        destination_start = source_start - start
        output[
            destination_start : destination_start + source_end - source_start
        ] = values[source_start:source_end]
    return output


def write_pcm16(path: Path, audio: np.ndarray) -> None:
    pcm = np.rint(np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(SAMPLE_RATE)
        destination.writeframes(pcm.tobytes())


def build(
    *,
    corpus_manifest_path: Path,
    livekit_scan_path: Path,
    ffmpeg_path: Path,
    output_directory: Path,
    split_salt: str,
    development_speaker_count: int,
) -> dict[str, object]:
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    livekit_scan_path = livekit_scan_path.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_hard_negative_output_exists:{output_directory}")
    corpus_hash = sha256(corpus_manifest_path)
    scan_hash = sha256(livekit_scan_path)
    corpus = read_json(corpus_manifest_path)
    scan = read_json(livekit_scan_path)
    if corpus.get("schema") != "baxy.openslr-librispeech-negative-development.v1":
        raise ValueError("unsupported_openslr_corpus_schema")
    if scan.get("schema") != "baxy.openslr-librispeech-livekit-development-scan.v1":
        raise ValueError("unsupported_openslr_livekit_scan_schema")
    if scan.get("corpus_manifest_sha256") != corpus_hash:
        raise ValueError("mdtc_hard_negative_corpus_hash_mismatch")
    if scan.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_hard_negative_blind_boundary_is_not_clean")
    corpus_records = corpus.get("records")
    scan_records = scan.get("records")
    if not isinstance(corpus_records, list) or not isinstance(scan_records, list):
        raise ValueError("mdtc_hard_negative_records_missing")
    if len(corpus_records) != len(scan_records):
        raise ValueError("mdtc_hard_negative_record_count_mismatch")
    corpus_by_id = {
        str(record.get("utterance_id")): record
        for record in corpus_records
        if isinstance(record, dict)
    }
    retained_scan = [
        record
        for record in scan_records
        if isinstance(record, dict) and bool(record.get("retained_windows"))
    ]
    speakers = {
        str(corpus_by_id[str(record["utterance_id"])]["speaker_id"])
        for record in retained_scan
    }
    development = set(
        development_speakers(
            speakers, salt=split_salt, count=development_speaker_count
        )
    )
    train_directory = output_directory / "train"
    development_directory = output_directory / "development"
    train_directory.mkdir(parents=True)
    development_directory.mkdir()
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)
    records: list[dict[str, object]] = []
    for scan_record in retained_scan:
        utterance_id = str(scan_record["utterance_id"])
        source = corpus_by_id.get(utterance_id)
        if source is None or (
            source.get("relative_path") != scan_record.get("relative_path")
            or source.get("sha256") != scan_record.get("wav_sha256")
        ):
            raise ValueError("mdtc_hard_negative_identity_mismatch")
        source_path = corpus_root / str(source["relative_path"])
        if sha256(source_path) != source.get("sha256"):
            raise ValueError(f"mdtc_hard_negative_audio_hash_mismatch:{source_path}")
        audio = decode_flac(ffmpeg_path, source_path)
        split = "development" if str(source["speaker_id"]) in development else "train"
        directory = development_directory if split == "development" else train_directory
        retained_windows = scan_record["retained_windows"]
        if not isinstance(retained_windows, list):
            raise ValueError("mdtc_hard_negative_windows_invalid")
        for window_index, window in enumerate(retained_windows):
            if not isinstance(window, dict):
                raise ValueError("mdtc_hard_negative_window_invalid")
            end_seconds = float(window["window_end_seconds"])
            score = float(window["score"])
            output_name = f"{utterance_id}_w{window_index:03d}.wav"
            output_path = directory / output_name
            write_pcm16(output_path, extract_window(audio, end_seconds))
            records.append(
                {
                    "split": split,
                    "output_relative_path": output_path.relative_to(output_directory).as_posix(),
                    "output_sha256": sha256(output_path),
                    "source_utterance_id": utterance_id,
                    "source_speaker_id": source["speaker_id"],
                    "source_relative_path": source["relative_path"],
                    "source_sha256": source["sha256"],
                    "window_end_seconds": end_seconds,
                    "livekit_score": score,
                    "label": "hard_negative",
                }
            )
    report: dict[str, object] = {
        "schema": "baxy.mdtc-hard-negative-windows.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "candidate_development_hard_negative_mining",
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": corpus_hash,
        "livekit_scan": livekit_scan_path.as_posix(),
        "livekit_scan_sha256": scan_hash,
        "livekit_retention_threshold": scan["retention_threshold"],
        "output_directory": output_directory.as_posix(),
        "split": {
            "salt": split_salt,
            "development_speaker_count": len(development),
            "development_speakers": sorted(development),
            "speaker_overlap": 0,
        },
        "decoder": {"path": ffmpeg_path.as_posix(), "sha256": sha256(ffmpeg_path)},
        "metrics": {
            "source_utterances": len(retained_scan),
            "windows": len(records),
            "train_windows": sum(record["split"] == "train" for record in records),
            "development_windows": sum(record["split"] == "development" for record in records),
            "audio_hours": len(records) * 2.0 / 3600.0,
        },
        "records": records,
        "candidate_development_use": True,
        "product_far_claim_supported": False,
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
    parser.add_argument("--livekit-scan", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split-salt", default="baxy-mdtc-hard-negative-v1")
    parser.add_argument("--development-speaker-count", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        corpus_manifest_path=args.corpus_manifest,
        livekit_scan_path=args.livekit_scan,
        ffmpeg_path=args.ffmpeg,
        output_directory=args.output_dir,
        split_salt=args.split_salt,
        development_speaker_count=args.development_speaker_count,
    )
    print(json.dumps({"metrics": report["metrics"], "output": report["output_directory"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
