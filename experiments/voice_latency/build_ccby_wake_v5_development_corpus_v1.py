"""Build an expanded CC-BY development corpus from frozen ASR mining output."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_ccby_wake_holdout import (  # noqa: E402
    extract_clip,
    inspect_wav,
    probe_audio_duration,
    sha256,
)
from mine_ccby_wake_v5_development_faster_whisper_v1 import (  # noqa: E402
    ALLOWED_LICENSE,
    is_lexical_candidate,
    read_object,
)


CLIP_SECONDS = 3.0
POSITIVE_PRE_SECONDS = 1.0
NEGATIVES_PER_POSITIVE_SOURCE = 2
SOURCE_END_SAFETY_SECONDS = 0.1


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")


def target_words(record: dict[str, object]) -> list[dict[str, object]]:
    values = []
    for segment in record.get("lexical_candidates", []):
        if not isinstance(segment, dict):
            raise ValueError("wake_v5_corpus_candidate_segment_invalid")
        for word in segment.get("words", []):
            if isinstance(word, dict) and is_lexical_candidate(str(word.get("word", ""))):
                values.append(word)
    return values


def choose_negative_centers(
    record: dict[str, object], target_onsets: list[float], count: int
) -> list[float]:
    eligible = []
    for segment in record.get("segments", []):
        if not isinstance(segment, dict) or not str(segment.get("text", "")).strip():
            continue
        start = float(segment["start_seconds"])
        end = float(segment["end_seconds"])
        center = (start + end) / 2
        if end - start < 0.5 or any(abs(center - target) < 5.0 for target in target_onsets):
            continue
        if is_lexical_candidate(str(segment["text"])):
            continue
        eligible.append(center)
    if len(eligible) < count:
        raise ValueError(f"wake_v5_corpus_negative_context_insufficient:{record['source_id']}")
    if count == 1:
        return [eligible[len(eligible) // 2]]
    indexes = [round(index * (len(eligible) - 1) / (count - 1)) for index in range(count)]
    return [eligible[index] for index in indexes]


def clip_start(onset_seconds: float, source_duration_seconds: float) -> float:
    desired = max(0.0, onset_seconds - POSITIVE_PRE_SECONDS)
    return min(
        desired,
        max(
            0.0,
            source_duration_seconds - CLIP_SECONDS - SOURCE_END_SAFETY_SECONDS,
        ),
    )


def build(
    *,
    mining_report_path: Path,
    inventory_paths: dict[str, Path],
    ffmpeg_path: Path,
    output_root: Path,
) -> dict[str, object]:
    mining_report_path = mining_report_path.resolve(strict=True)
    inventory_paths = {
        name: path.resolve(strict=True) for name, path in inventory_paths.items()
    }
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    output_root = output_root.resolve()
    manifest_path = output_root / "corpus.manifest.v1.json"
    if output_root.exists() or manifest_path.exists():
        raise ValueError("wake_v5_corpus_output_exists")
    mining = read_object(mining_report_path)
    if (
        mining.get("schema")
        != "baxy.ccby-wake-v5-development-faster-whisper-mining.v1"
        or mining.get("scope") != "development_only_data_mining"
        or mining.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_v5_corpus_mining_boundary_invalid")
    expected_inventories = mining.get("sources", {}).get("inventory_sha256")
    if not isinstance(expected_inventories, dict):
        raise ValueError("wake_v5_corpus_inventory_hashes_missing")
    inventories = {name: read_object(path) for name, path in inventory_paths.items()}
    for name, path in inventory_paths.items():
        if sha256(path) != expected_inventories.get(name):
            raise ValueError(f"wake_v5_corpus_inventory_hash_mismatch:{name}")
    source_lookup: dict[str, tuple[str, dict[str, object]]] = {}
    for inventory_name, inventory in inventories.items():
        for source in inventory.get("sources", []):
            if isinstance(source, dict):
                source_lookup[str(source["id"])] = (inventory_name, source)

    records: list[dict[str, object]] = []
    positive_source_count = 0
    for mined in mining.get("records", []):
        if not isinstance(mined, dict):
            raise ValueError("wake_v5_corpus_mining_record_invalid")
        words = target_words(mined)
        if not words:
            continue
        source_id = str(mined["source_id"])
        inventory_name, source = source_lookup[source_id]
        if source.get("license") != ALLOWED_LICENSE:
            raise ValueError(f"wake_v5_corpus_license_invalid:{source_id}")
        source_path = inventory_paths[inventory_name].parent / str(source["audio_file"])
        if sha256(source_path) != source.get("audio_sha256"):
            raise ValueError(f"wake_v5_corpus_audio_hash_mismatch:{source_id}")
        source_duration = probe_audio_duration(ffmpeg_path, source_path)
        if abs(source_duration - float(source["audio_seconds"])) > 0.25:
            raise ValueError(f"wake_v5_corpus_audio_duration_mismatch:{source_id}")
        speaker_group = "uploader_" + safe_name(str(source["uploader"]).casefold())
        target_onsets = [float(word["start_seconds"]) for word in words]
        positive_source_count += 1
        for index, word in enumerate(words):
            onset = float(word["start_seconds"])
            start = clip_start(onset, source_duration)
            output_name = f"{safe_name(source_id)}_{index:02d}_positive.wav"
            output = output_root / "positive" / output_name
            extract_clip(
                ffmpeg_path,
                source_path,
                output,
                start_seconds=start,
                duration_seconds=CLIP_SECONDS,
            )
            records.append(
                {
                    "partition": "development",
                    "label": "positive",
                    "source_id": source_id,
                    "speaker_group": speaker_group,
                    "language": mined.get("language"),
                    "license": source["license"],
                    "webpage_url": source["webpage_url"],
                    "source_audio_sha256": source["audio_sha256"],
                    "source_target_onset_seconds": onset,
                    "source_clip_start_seconds": start,
                    "target_onset_in_clip_seconds": onset - start,
                    "asr_word": word["word"],
                    "asr_word_probability": word["probability"],
                    "output_relative_path": output.relative_to(output_root).as_posix(),
                    "wav": inspect_wav(output, CLIP_SECONDS),
                }
            )
        negative_centers = choose_negative_centers(
            mined, target_onsets, NEGATIVES_PER_POSITIVE_SOURCE
        )
        for index, center in enumerate(negative_centers):
            start = min(
                max(0.0, center - CLIP_SECONDS / 2),
                max(
                    0.0,
                    source_duration - CLIP_SECONDS - SOURCE_END_SAFETY_SECONDS,
                ),
            )
            output_name = f"{safe_name(source_id)}_{index:02d}_matched_negative.wav"
            output = output_root / "matched_negative" / output_name
            extract_clip(
                ffmpeg_path,
                source_path,
                output,
                start_seconds=start,
                duration_seconds=CLIP_SECONDS,
            )
            records.append(
                {
                    "partition": "development",
                    "label": "matched_negative",
                    "source_id": source_id,
                    "speaker_group": speaker_group,
                    "language": mined.get("language"),
                    "license": source["license"],
                    "webpage_url": source["webpage_url"],
                    "source_audio_sha256": source["audio_sha256"],
                    "source_clip_start_seconds": start,
                    "output_relative_path": output.relative_to(output_root).as_posix(),
                    "wav": inspect_wav(output, CLIP_SECONDS),
                }
            )
    if positive_source_count < 2:
        raise ValueError("wake_v5_corpus_positive_source_diversity_insufficient")
    counts = Counter(str(record["label"]) for record in records)
    manifest: dict[str, object] = {
        "schema": "baxy.ccby-wake-v5-development-corpus.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only",
        "sources": {
            "mining_report_sha256": sha256(mining_report_path),
            "inventory_sha256": {
                name: sha256(path) for name, path in inventory_paths.items()
            },
            "ffmpeg_sha256": sha256(ffmpeg_path),
        },
        "contract": {
            "clip_seconds": CLIP_SECONDS,
            "positive_pre_seconds": POSITIVE_PRE_SECONDS,
            "negative_exclusion_seconds": 5.0,
            "source_end_safety_seconds": SOURCE_END_SAFETY_SECONDS,
            "negatives_per_positive_source": NEGATIVES_PER_POSITIVE_SOURCE,
            "speaker_group": "source_uploader",
        },
        "counts": {
            "positive_sources": positive_source_count,
            "positive_clips": counts["positive"],
            "matched_negative_clips": counts["matched_negative"],
        },
        "records": records,
        "candidate_model_scores_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mining-report", type=Path, required=True)
    parser.add_argument("--round1-inventory", type=Path, required=True)
    parser.add_argument("--round2-inventory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    manifest = build(
        mining_report_path=arguments.mining_report,
        inventory_paths={
            "round1": arguments.round1_inventory,
            "round2": arguments.round2_inventory,
        },
        ffmpeg_path=arguments.ffmpeg,
        output_root=arguments.output_root,
    )
    print(json.dumps(manifest["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
