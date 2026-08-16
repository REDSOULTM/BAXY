"""Audit Parakeet lexical proposals on the CC-BY development partition.

This runner is deliberately incapable of reading the blind partition.  Its
output is proposal evidence only: a BAXY-like transcript never authorizes a
turn until the acoustic CTC verifier accepts the same span.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctc_wake_verifier import lexical_proposal_spans  # noqa: E402


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


def development_records(manifest: dict[str, object]) -> list[dict[str, object]]:
    if manifest.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("unsupported_ccby_corpus_schema")
    raw_records = manifest.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("ccby_corpus_records_missing")
    records = [
        record
        for record in raw_records
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if not records:
        raise ValueError("ccby_development_records_empty")
    if any(record.get("label") not in {"positive", "hard_negative"} for record in records):
        raise ValueError("ccby_development_label_invalid")
    return records


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"wav_contract_mismatch:{path}:{contract}")
        payload = source.readframes(source.getnframes())
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def audit(
    *,
    corpus_manifest_path: Path,
    stt_directory: Path,
    output_path: Path,
) -> dict[str, object]:
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    corpus = read_json(corpus_manifest_path)
    records = development_records(corpus)
    missing = [name for name in STT_FILES if not (stt_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"parakeet_bundle_incomplete:{missing[0]}")

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

    corpus_root = corpus_manifest_path.parent
    results: list[dict[str, object]] = []
    for record in records:
        relative_path = str(record["output_relative_path"])
        path = corpus_root / relative_path
        expected_hash = str(record.get("wav", {}).get("sha256", ""))
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise ValueError(f"ccby_wav_hash_mismatch:{relative_path}")
        stream = recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, read_wav(path))
        started = time.perf_counter()
        recognizer.decode_stream(stream)
        latency = time.perf_counter() - started
        decoded = stream.result
        tokens = [str(token) for token in (decoded.tokens or [])]
        timestamps = [float(value) for value in (decoded.timestamps or [])]
        proposals = lexical_proposal_spans(tokens, timestamps)
        results.append(
            {
                "source_id": record["source_id"],
                "speaker_group": record["speaker_group"],
                "label": record["label"],
                "output_relative_path": relative_path,
                "wav_sha256": actual_hash,
                "transcript": str(decoded.text or "").strip(),
                "tokens": tokens,
                "timestamps": [round(value, 6) for value in timestamps],
                "lexical_proposals": list(proposals),
                "has_lexical_proposal": bool(proposals),
                "decode_seconds": round(latency, 6),
            }
        )

    by_label = {
        label: {
            "clips": sum(record["label"] == label for record in results),
            "proposals": sum(
                record["label"] == label and bool(record["has_lexical_proposal"])
                for record in results
            ),
        }
        for label in ("positive", "hard_negative")
    }
    report: dict[str, object] = {
        "schema": "baxy.ccby-wake-parakeet-development-audit.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "purpose": "permissive_lexical_proposal_only",
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": sha256(corpus_manifest_path),
        "preregistration_sha256": corpus.get("preregistration_sha256"),
        "parakeet": {
            "directory": stt_directory.as_posix(),
            "files": {
                name: sha256(stt_directory / name) for name in STT_FILES
            },
            "decoding_method": "modified_beam_search",
            "max_active_paths": 8,
            "num_threads": 6,
            "load_and_warmup_seconds": round(load_seconds, 6),
        },
        "metrics": by_label,
        "records": results,
        "blind_human_partition_accessed": False,
        "candidate_model_scores_accessed": False,
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
    parser.add_argument("--stt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(
        corpus_manifest_path=args.corpus_manifest,
        stt_directory=args.stt_dir,
        output_path=args.output,
    )
    sys.stdout.buffer.write(
        (
            json.dumps(
                {"output": args.output.resolve().as_posix(), "metrics": report["metrics"]},
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

