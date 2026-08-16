"""Decode LiveKit's augmented negative development split with Parakeet.

The output supplies lexical proposal and word-boundary evidence to the CTC
cascade.  This split participated in candidate development, so the report is
diagnostic and can never substantiate a final false-activation claim.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctc_wake_verifier import (  # noqa: E402
    lexical_proposal_spans,
    lexical_word_spans,
)


SAMPLE_RATE = 16_000
_AUGMENTED_NAME = re.compile(r"^clip_\d{6}_r\d+\.wav$")
STT_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def augmented_wavs(directory: Path) -> list[Path]:
    paths = sorted(
        path
        for path in directory.glob("*.wav")
        if path.is_file() and _AUGMENTED_NAME.fullmatch(path.name)
    )
    if not paths:
        raise ValueError("livekit_negative_augmented_wavs_empty")
    return paths


def wav_set_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def read_wav(path: Path) -> tuple[np.ndarray, float]:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"wav_contract_mismatch:{path}:{contract}")
        frames = source.getnframes()
        payload = source.readframes(frames)
    return (
        np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0,
        frames / SAMPLE_RATE,
    )


def load_checkpoint(
    path: Path,
    *,
    feature_sha256: str,
    ordered_wav_set_sha256: str,
    paths: list[Path],
) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(value, dict)
        or value.get("schema")
        != "baxy.livekit-negative-parakeet-checkpoint.v1"
    ):
        raise ValueError("unsupported_negative_parakeet_checkpoint_schema")
    if value.get("feature_sha256") != feature_sha256:
        raise ValueError("negative_parakeet_checkpoint_feature_mismatch")
    if value.get("ordered_wav_set_sha256") != ordered_wav_set_sha256:
        raise ValueError("negative_parakeet_checkpoint_wav_set_mismatch")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > len(paths):
        raise ValueError("negative_parakeet_checkpoint_records_invalid")
    for index, record in enumerate(records):
        if not isinstance(record, dict) or record.get("file") != paths[index].name:
            raise ValueError("negative_parakeet_checkpoint_order_mismatch")
    return records


def write_checkpoint(
    path: Path,
    *,
    feature_sha256: str,
    ordered_wav_set_sha256: str,
    records: list[dict[str, object]],
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "baxy.livekit-negative-parakeet-checkpoint.v1",
                "feature_sha256": feature_sha256,
                "ordered_wav_set_sha256": ordered_wav_set_sha256,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def audit(
    *,
    wav_directory: Path,
    feature_path: Path,
    stt_directory: Path,
    output_path: Path,
    batch_size: int,
) -> dict[str, object]:
    if batch_size <= 0:
        raise ValueError("negative_parakeet_batch_size_invalid")
    wav_directory = wav_directory.resolve(strict=True)
    feature_path = feature_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    paths = augmented_wavs(wav_directory)
    features = np.load(feature_path, mmap_mode="r")
    if features.ndim != 3 or features.shape[1:] != (16, 96):
        raise ValueError(f"negative_feature_shape_invalid:{features.shape}")
    if len(features) != len(paths):
        raise ValueError(
            f"negative_feature_wav_count_mismatch:{len(features)}:{len(paths)}"
        )
    missing = [name for name in STT_FILES if not (stt_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"parakeet_bundle_incomplete:{missing[0]}")
    feature_hash = sha256(feature_path)
    wav_digest = wav_set_digest(paths)
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    records = load_checkpoint(
        checkpoint_path,
        feature_sha256=feature_hash,
        ordered_wav_set_sha256=wav_digest,
        paths=paths,
    )

    import sherpa_onnx

    load_started = time.perf_counter()
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=6,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
    )
    warmup = recognizer.create_stream()
    warmup.accept_waveform(SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, np.float32))
    recognizer.decode_stream(warmup)
    load_seconds = time.perf_counter() - load_started
    decode_started = time.perf_counter()
    for start in range(len(records), len(paths), batch_size):
        batch_paths = paths[start : start + batch_size]
        streams = []
        durations = []
        for path in batch_paths:
            audio, duration = read_wav(path)
            stream = recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, audio)
            streams.append(stream)
            durations.append(duration)
        batch_started = time.perf_counter()
        recognizer.decode_streams(streams)
        batch_seconds = time.perf_counter() - batch_started
        per_clip_seconds = batch_seconds / len(streams)
        for path, stream, duration in zip(
            batch_paths, streams, durations, strict=True
        ):
            decoded = stream.result
            tokens = [str(token) for token in (decoded.tokens or [])]
            timestamps = [float(value) for value in (decoded.timestamps or [])]
            words = lexical_word_spans(tokens, timestamps)
            proposals = lexical_proposal_spans(tokens, timestamps)
            records.append(
                {
                    "file": path.name,
                    "wav_sha256": sha256(path),
                    "duration_seconds": round(duration, 6),
                    "transcript": str(decoded.text or "").strip(),
                    "tokens": tokens,
                    "timestamps": [round(value, 6) for value in timestamps],
                    "lexical_words": list(words),
                    "lexical_proposals": list(proposals),
                    "has_lexical_proposal": bool(proposals),
                    "decode_seconds_amortized": round(per_clip_seconds, 6),
                }
            )
        write_checkpoint(
            checkpoint_path,
            feature_sha256=feature_hash,
            ordered_wav_set_sha256=wav_digest,
            records=records,
        )
        print(f"PROGRESS|{len(records)}/{len(paths)}", flush=True)
    decode_seconds = time.perf_counter() - decode_started

    report: dict[str, object] = {
        "schema": "baxy.livekit-negative-parakeet-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "candidate_development_negative_split",
        "wav_directory": wav_directory.as_posix(),
        "ordered_wav_set_sha256": wav_digest,
        "feature_file": feature_path.as_posix(),
        "feature_sha256": feature_hash,
        "clips": len(paths),
        "audio_seconds": round(
            sum(float(record["duration_seconds"]) for record in records), 6
        ),
        "lexical_proposals": sum(
            bool(record["has_lexical_proposal"]) for record in records
        ),
        "parakeet": {
            "directory": stt_directory.as_posix(),
            "files": {
                name: sha256(stt_directory / name) for name in STT_FILES
            },
            "load_and_warmup_seconds": round(load_seconds, 6),
            "decode_seconds": round(decode_seconds, 6),
            "batch_size": batch_size,
        },
        "records": records,
        "independent_holdout": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav-dir", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--stt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(
        wav_directory=args.wav_dir,
        feature_path=args.features,
        stt_directory=args.stt_dir,
        output_path=args.output,
        batch_size=args.batch_size,
    )
    print(
        json.dumps(
            {
                "output": args.output.resolve().as_posix(),
                "clips": report["clips"],
                "lexical_proposals": report["lexical_proposals"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

