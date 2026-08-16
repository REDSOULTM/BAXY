"""Rebuild a LiveKit Piper positive split after a pronunciation audit.

The original scale campaign alternated ``["baxy", "baxi"]``.  Piper's
English phonemizer renders those as /beIksi/ and /baeksi/ respectively, while
the product wake pronunciation is /baksi/.  LiveKit cycles phrases by sample
index, so even indices are the rejected spelling and odd indices are the
accepted spelling.

This utility is deliberately reversible: it renames the complete original
split to an adjacent archive and creates a dense replacement from hard links
to the accepted odd-index files.  It never deletes or rewrites audio.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import wave
from datetime import datetime, timezone
from pathlib import Path

_CLIP_RE = re.compile(r"clip_(\d{6})\.wav")
_SAMPLE_RATE = 16_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_wav(path: Path) -> int:
    with wave.open(str(path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != _SAMPLE_RATE
            or source.getcomptype() != "NONE"
        ):
            raise ValueError(f"invalid_wav_format:{path.name}")
        frames = source.getnframes()
        payload = source.readframes(frames + 1)
    if frames <= 0 or len(payload) != frames * 2:
        raise ValueError(f"invalid_wav_payload:{path.name}")
    return frames


def _ordered_clips(directory: Path) -> list[Path]:
    clips = sorted(directory.glob("clip_*.wav"))
    indices: list[int] = []
    for path in clips:
        match = _CLIP_RE.fullmatch(path.name)
        if match is None:
            raise ValueError(f"invalid_clip_name:{path.name}")
        indices.append(int(match.group(1)))
    if indices != list(range(len(indices))):
        raise ValueError("source_split_is_not_dense")
    return clips


def _corpus_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        name = path.name.encode("ascii")
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def rebuild_split(split: Path, archive_name: str) -> dict[str, object]:
    """Archive *split* and densely hard-link its accepted odd-index clips."""

    split = split.resolve(strict=True)
    if split.name not in {"positive_train", "positive_test"}:
        raise ValueError("unsupported_positive_split")
    archive = split.parent / archive_name
    if archive.exists():
        raise FileExistsError(f"archive_already_exists:{archive}")

    source_clips = _ordered_clips(split)
    if not source_clips:
        raise ValueError("source_split_is_empty")
    for path in source_clips:
        _validate_wav(path)
    source_digest = _corpus_digest(source_clips)

    split.rename(archive)
    split.mkdir()
    accepted_sources = source_clips[1::2]
    try:
        for dense_index, old_path in enumerate(accepted_sources):
            archived_path = archive / old_path.name
            destination = split / f"clip_{dense_index:06d}.wav"
            os.link(archived_path, destination)
        replacement = _ordered_clips(split)
        for path in replacement:
            _validate_wav(path)
    except Exception:
        # Keep both directories for diagnosis.  Never erase evidence or try a
        # broad rollback whose target may have changed underneath us.
        raise

    return {
        "split": split.name,
        "source_count": len(source_clips),
        "accepted_count": len(replacement),
        "rejected_count": len(source_clips) - len(replacement),
        "source_archive": archive.name,
        "selection": "old sample index modulo 2 equals 1",
        "old_phrase_order": ["baxy", "baxi"],
        "accepted_phrase": "baxi",
        "source_sha256": source_digest,
        "replacement_sha256": _corpus_digest(replacement),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", choices=("positive_train", "positive_test"), required=True)
    parser.add_argument("--archive-name", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.apply:
        raise SystemExit("Refusing to mutate the corpus without --apply.")
    root = args.root.resolve(strict=True)
    split = root / args.split
    if split.parent != root or Path(args.archive_name).name != args.archive_name:
        raise SystemExit("Split/archive paths must remain directly under --root.")
    result = rebuild_split(split, args.archive_name)
    report = {
        "schema": "baxy.livekit-pronunciation-corpus-rebuild.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "reversible_archive_plus_hardlinks",
        "result": result,
        "effects_executed": 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
