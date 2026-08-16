"""Build a hash-bound OpenSLR LibriSpeech negative-corpus manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


OPENSLR_PAGE = "https://www.openslr.org/12"
DEV_CLEAN_URL = "https://openslr.trmal.net/resources/12/dev-clean.tar.gz"
DEV_CLEAN_MD5 = "42e2234ba48799c1f50f24a7926300a1"
DEV_CLEAN_SHA256 = (
    "76f87d090650617fca0cac8f88b9416e0ebf80350acb97b343a85fa903728ab3"
)
SUBSET = "dev-clean"
SUBSETS: dict[str, dict[str, object]] = {
    "dev-clean": {
        "archive": "dev-clean.tar.gz",
        "url": DEV_CLEAN_URL,
        "md5": DEV_CLEAN_MD5,
        "sha256": DEV_CLEAN_SHA256,
        "schema": "baxy.openslr-librispeech-negative-development.v1",
        "scope": "independent_raw_negative_architecture_development",
        "candidate_development_use": True,
    },
    "train-clean-100": {
        "archive": "train-clean-100.tar.gz",
        "url": "https://www.openslr.org/resources/12/train-clean-100.tar.gz",
        "md5": "2a93770f6d5c6c964bc36631d331a522",
        "sha256": (
            "d4ddd1d5a6ab303066f14971d768ee43278a5f2a0aa43dc716b0e64ecbbbf6e2"
        ),
        "schema": "baxy.openslr-librispeech-negative-holdout.v1",
        "scope": "frozen_raw_negative_product_calibration_holdout",
        "candidate_development_use": False,
    },
}


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_transcripts(subset_root: Path) -> dict[str, str]:
    transcripts: dict[str, str] = {}
    for path in sorted(subset_root.rglob("*.trans.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                utterance_id, text = line.split(" ", 1)
            except ValueError as error:
                raise ValueError(f"librispeech_transcript_line_invalid:{path}") from error
            if utterance_id in transcripts:
                raise ValueError(f"librispeech_duplicate_utterance:{utterance_id}")
            transcripts[utterance_id] = text
    if not transcripts:
        raise ValueError("librispeech_transcripts_empty")
    return transcripts


def build_manifest(
    *,
    archive_path: Path,
    corpus_root: Path,
    output_path: Path,
    subset: str = SUBSET,
) -> dict[str, object]:
    try:
        profile = SUBSETS[subset]
    except KeyError as error:
        raise ValueError(f"librispeech_subset_unsupported:{subset}") from error
    archive_path = archive_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    archive_md5 = file_digest(archive_path, "md5")
    archive_sha256 = file_digest(archive_path, "sha256")
    expected_md5 = str(profile["md5"])
    if archive_md5 != expected_md5:
        raise ValueError(
            f"openslr_archive_md5_mismatch:{archive_md5}:{expected_md5}"
        )
    expected_sha256 = profile["sha256"]
    if expected_sha256 is not None and archive_sha256 != expected_sha256:
        raise ValueError(
            "openslr_archive_sha256_mismatch:"
            f"{archive_sha256}:{expected_sha256}"
        )
    subset_root = corpus_root / "LibriSpeech" / subset
    if not subset_root.is_dir():
        raise FileNotFoundError(f"librispeech_subset_missing:{subset_root}")
    transcripts = read_transcripts(subset_root)

    import soundfile as sf

    records: list[dict[str, object]] = []
    total_frames = 0
    for path in sorted(subset_root.rglob("*.flac")):
        relative = path.relative_to(corpus_root).as_posix()
        utterance_id = path.stem
        if utterance_id not in transcripts:
            raise ValueError(f"librispeech_transcript_missing:{utterance_id}")
        parts = utterance_id.split("-")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError(f"librispeech_utterance_id_invalid:{utterance_id}")
        info = sf.info(str(path))
        if info.samplerate != 16_000 or info.channels != 1 or info.frames <= 0:
            raise ValueError(f"librispeech_audio_contract_invalid:{relative}")
        total_frames += int(info.frames)
        records.append(
            {
                "utterance_id": utterance_id,
                "speaker_id": int(parts[0]),
                "chapter_id": int(parts[1]),
                "relative_path": relative,
                "sha256": file_digest(path, "sha256"),
                "sample_rate_hz": int(info.samplerate),
                "channels": int(info.channels),
                "frames": int(info.frames),
                "duration_seconds": round(info.frames / info.samplerate, 6),
                "transcript": transcripts[utterance_id],
            }
        )
    if len(records) != len(transcripts):
        raise ValueError(
            f"librispeech_audio_transcript_count_mismatch:{len(records)}:{len(transcripts)}"
        )
    speakers = {int(record["speaker_id"]) for record in records}
    report: dict[str, object] = {
        "schema": profile["schema"],
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": profile["scope"],
        "source": {
            "openslr_page": OPENSLR_PAGE,
            "download_url": profile["url"],
            "subset": subset,
            "license": "CC BY 4.0",
            "archive": archive_path.as_posix(),
            "archive_bytes": archive_path.stat().st_size,
            "archive_md5": archive_md5,
            "archive_sha256": archive_sha256,
        },
        "corpus_root": corpus_root.as_posix(),
        "metrics": {
            "utterances": len(records),
            "speakers": len(speakers),
            "audio_seconds": round(total_frames / 16_000, 6),
            "audio_hours": total_frames / 16_000 / 3600,
        },
        "records": records,
        "candidate_development_use": profile["candidate_development_use"],
        "product_far_claim_supported": False,
        "candidate_scored": False,
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
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subset", choices=sorted(SUBSETS), default=SUBSET)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_manifest(
        archive_path=args.archive,
        corpus_root=args.corpus_root,
        output_path=args.output,
        subset=args.subset,
    )
    print(json.dumps({"output": args.output.resolve().as_posix(), "metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
