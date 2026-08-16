"""Audit Whisper lexical evidence on the human development wake partition."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.wake_verifier import has_exact_lexical_target  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_development_records(corpus: dict[str, object]) -> list[dict[str, object]]:
    if (
        corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1"
        or corpus.get("blind_partition_was_not_scored") is not True
    ):
        raise ValueError("whisper_wake_development_boundary_invalid")
    records = [
        record
        for record in corpus.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if len(records) != 18:
        raise ValueError("whisper_wake_development_records_invalid")
    return records


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    positives = [record for record in records if record["label"] == "positive"]
    negatives = [
        record for record in records if record["label"] == "hard_negative"
    ]
    accepted = sum(bool(record["exact_lexical_target"]) for record in positives)
    false = sum(bool(record["exact_lexical_target"]) for record in negatives)
    return {
        "positive_exact_lexical": accepted,
        "positive_total": len(positives),
        "positive_exact_lexical_rate": accepted / len(positives),
        "hard_negative_exact_lexical_false": false,
        "hard_negative_total": len(negatives),
        "diagnostic_zero_false": false == 0,
    }


def audit(
    *,
    corpus_manifest_path: Path,
    model_path: Path,
    ffmpeg_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("whisper_wake_output_exists")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    if ffmpeg_path.name.lower() != "ffmpeg.exe":
        raise ValueError("whisper_wake_ffmpeg_invalid")
    output_path = output_path.resolve()
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(corpus, dict):
        raise ValueError("whisper_wake_corpus_invalid")
    source_records = select_development_records(corpus)

    os.environ["PATH"] = str(ffmpeg_path.parent) + os.pathsep + os.environ.get(
        "PATH", ""
    )
    import whisper

    model = whisper.load_model(str(model_path), device="cpu")
    corpus_root = corpus_manifest_path.parent
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for source in source_records:
        path = corpus_root / str(source["output_relative_path"])
        wav = source.get("wav")
        if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
            raise ValueError(f"whisper_wake_audio_hash_mismatch:{path}")
        result = model.transcribe(
            str(path),
            fp16=False,
            temperature=0.0,
            condition_on_previous_text=False,
            verbose=False,
        )
        transcript = str(result.get("text", "")).strip()
        records.append(
            {
                "relative_path": source["output_relative_path"],
                "speaker_group": source["speaker_group"],
                "label": source["label"],
                "language": result.get("language"),
                "transcript": transcript,
                "exact_lexical_target": has_exact_lexical_target(transcript),
            }
        )
    report: dict[str, object] = {
        "schema": "baxy.ccby-wake-development-whisper-audit.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_diagnostic",
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "model_sha256": sha256(model_path),
            "ffmpeg_sha256": sha256(ffmpeg_path),
        },
        "metrics": summarize(records),
        "records": records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
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
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        corpus_manifest_path=arguments.corpus_manifest,
        model_path=arguments.model,
        ffmpeg_path=arguments.ffmpeg,
        output_path=arguments.output,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
