"""Decode only acoustically retained LibriSpeech development utterances."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctc_wake_verifier import (  # noqa: E402
    lexical_proposal_spans,
    lexical_word_spans,
)


SAMPLE_RATE = 16_000
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


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def decode_flac(ffmpeg_path: Path, audio_path: Path) -> np.ndarray:
    """Decode a corpus FLAC deterministically without changing the Mind runtime."""
    completed = subprocess.run(
        [
            str(ffmpeg_path),
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    audio = np.frombuffer(completed.stdout, dtype="<f4").copy()
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError(f"openslr_audio_decode_invalid:{audio_path}")
    return audio


def selected_records(
    corpus: dict[str, object],
    scan: dict[str, object],
    *,
    corpus_manifest_sha256: str,
) -> list[dict[str, object]]:
    if corpus.get("schema") != "baxy.openslr-librispeech-negative-development.v1":
        raise ValueError("unsupported_openslr_corpus_schema")
    if scan.get("schema") != "baxy.openslr-librispeech-livekit-development-scan.v1":
        raise ValueError("unsupported_openslr_livekit_scan_schema")
    if scan.get("corpus_manifest_sha256") != corpus_manifest_sha256:
        raise ValueError("openslr_parakeet_corpus_hash_mismatch")
    if scan.get("blind_human_partition_accessed") is not False:
        raise ValueError("openslr_parakeet_blind_boundary_is_not_clean")
    threshold = float(scan["retention_threshold"])
    corpus_records = corpus.get("records")
    scan_records = scan.get("records")
    if not isinstance(corpus_records, list) or not isinstance(scan_records, list):
        raise ValueError("openslr_parakeet_source_records_missing")
    corpus_by_id = {
        str(record.get("utterance_id")): record
        for record in corpus_records
        if isinstance(record, dict)
    }
    selected = []
    for record in scan_records:
        if not isinstance(record, dict) or float(record["max_score"]) < threshold:
            continue
        utterance_id = str(record["utterance_id"])
        source = corpus_by_id.get(utterance_id)
        if source is None or source.get("relative_path") != record.get("relative_path"):
            raise ValueError("openslr_parakeet_record_identity_mismatch")
        selected.append({"source": source, "scan": record})
    if not selected:
        raise ValueError("openslr_parakeet_selected_records_empty")
    return selected


def load_checkpoint(
    path: Path,
    *,
    corpus_manifest_sha256: str,
    livekit_scan_sha256: str,
    selected: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    value = read_json(path)
    if value.get("schema") != "baxy.openslr-parakeet-checkpoint.v1":
        raise ValueError("unsupported_openslr_parakeet_checkpoint_schema")
    if value.get("corpus_manifest_sha256") != corpus_manifest_sha256:
        raise ValueError("openslr_parakeet_checkpoint_corpus_mismatch")
    if value.get("livekit_scan_sha256") != livekit_scan_sha256:
        raise ValueError("openslr_parakeet_checkpoint_scan_mismatch")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > len(selected):
        raise ValueError("openslr_parakeet_checkpoint_records_invalid")
    for index, record in enumerate(records):
        source = selected[index]["source"]
        if (
            not isinstance(record, dict)
            or record.get("utterance_id") != source.get("utterance_id")
        ):
            raise ValueError("openslr_parakeet_checkpoint_order_mismatch")
    return records


def write_checkpoint(
    path: Path,
    *,
    corpus_manifest_sha256: str,
    livekit_scan_sha256: str,
    records: list[dict[str, object]],
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "baxy.openslr-parakeet-checkpoint.v1",
                "corpus_manifest_sha256": corpus_manifest_sha256,
                "livekit_scan_sha256": livekit_scan_sha256,
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
    corpus_manifest_path: Path,
    livekit_scan_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    output_path: Path,
    batch_size: int,
) -> dict[str, object]:
    if batch_size <= 0:
        raise ValueError("openslr_parakeet_batch_size_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    livekit_scan_path = livekit_scan_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    if not ffmpeg_path.is_file():
        raise FileNotFoundError(f"ffmpeg_is_not_a_file:{ffmpeg_path}")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_hash = sha256(corpus_manifest_path)
    scan_hash = sha256(livekit_scan_path)
    corpus = read_json(corpus_manifest_path)
    scan = read_json(livekit_scan_path)
    selected = selected_records(
        corpus, scan, corpus_manifest_sha256=corpus_hash
    )
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)
    missing = [name for name in STT_FILES if not (stt_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"parakeet_bundle_incomplete:{missing[0]}")
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    records = load_checkpoint(
        checkpoint_path,
        corpus_manifest_sha256=corpus_hash,
        livekit_scan_sha256=scan_hash,
        selected=selected,
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
    for start in range(len(records), len(selected), batch_size):
        batch = selected[start : start + batch_size]
        streams = []
        for item in batch:
            source = item["source"]
            path = corpus_root / str(source["relative_path"])
            if sha256(path) != source.get("sha256"):
                raise ValueError(f"openslr_audio_hash_mismatch:{path}")
            audio = decode_flac(ffmpeg_path, path)
            stream = recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, audio)
            streams.append(stream)
        batch_started = time.perf_counter()
        recognizer.decode_streams(streams)
        per_clip_seconds = (time.perf_counter() - batch_started) / len(streams)
        for item, stream in zip(batch, streams, strict=True):
            source = item["source"]
            scan_record = item["scan"]
            decoded = stream.result
            tokens = [str(token) for token in (decoded.tokens or [])]
            timestamps = [float(value) for value in (decoded.timestamps or [])]
            words = lexical_word_spans(tokens, timestamps)
            proposals = lexical_proposal_spans(tokens, timestamps)
            records.append(
                {
                    "utterance_id": source["utterance_id"],
                    "relative_path": source["relative_path"],
                    "wav_sha256": source["sha256"],
                    "duration_seconds": source["duration_seconds"],
                    "reference_transcript": source["transcript"],
                    "livekit_max_score": scan_record["max_score"],
                    "livekit_proposal": scan_record["proposal"],
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
            corpus_manifest_sha256=corpus_hash,
            livekit_scan_sha256=scan_hash,
            records=records,
        )
        print(f"PROGRESS|{len(records)}/{len(selected)}", flush=True)
    decode_seconds = time.perf_counter() - decode_started
    selected_audio_seconds = sum(
        float(record["duration_seconds"]) for record in records
    )
    report: dict[str, object] = {
        "schema": "baxy.openslr-librispeech-parakeet-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "independent_raw_negative_architecture_development",
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": corpus_hash,
        "livekit_scan": livekit_scan_path.as_posix(),
        "livekit_scan_sha256": scan_hash,
        "selection_threshold": scan["retention_threshold"],
        "metrics": {
            "selected_utterances": len(records),
            "selected_audio_seconds": selected_audio_seconds,
            "selected_audio_hours": selected_audio_seconds / 3600.0,
            "lexical_proposals": sum(
                bool(record["has_lexical_proposal"]) for record in records
            ),
        },
        "parakeet": {
            "directory": stt_directory.as_posix(),
            "files": {
                name: sha256(stt_directory / name) for name in STT_FILES
            },
            "load_and_warmup_seconds": round(load_seconds, 6),
            "decode_seconds": round(decode_seconds, 6),
            "audio_realtime_factor": decode_seconds / selected_audio_seconds,
            "batch_size": batch_size,
        },
        "decoder": {
            "path": ffmpeg_path.as_posix(),
            "sha256": sha256(ffmpeg_path),
            "output_contract": "mono_f32le_16000_hz",
        },
        "records": records,
        "candidate_development_use": True,
        "product_far_claim_supported": False,
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
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--livekit-scan", type=Path, required=True)
    parser.add_argument("--stt-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(
        corpus_manifest_path=args.corpus_manifest,
        livekit_scan_path=args.livekit_scan,
        stt_directory=args.stt_dir,
        ffmpeg_path=args.ffmpeg,
        output_path=args.output,
        batch_size=args.batch_size,
    )
    print(json.dumps({"output": args.output.resolve().as_posix(), "metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
