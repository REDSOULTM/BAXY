"""Build the preregistered human CC-BY wake-word corpus without scoring it.

The source specification deliberately contains acoustic target locations but no
candidate-model output.  This keeps extraction reproducible while preserving
the blind boundary until a model artifact and threshold have been frozen.
"""

from __future__ import annotations

import argparse
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave


SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2


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


def validate_entries(entries: list[dict[str, object]]) -> None:
    output_names: set[str] = set()
    source_partitions: dict[str, set[str]] = defaultdict(set)
    speaker_partitions: dict[str, set[str]] = defaultdict(set)
    allowed_partitions = {"development", "blind"}
    allowed_labels = {"positive", "hard_negative"}
    for entry in entries:
        partition = str(entry.get("partition", ""))
        label = str(entry.get("label", ""))
        source_id = str(entry.get("source_id", ""))
        speaker_group = str(entry.get("speaker_group", ""))
        output_name = str(entry.get("output_name", ""))
        source_relative_path = str(entry.get("source_relative_path", ""))
        if partition not in allowed_partitions:
            raise ValueError(f"invalid_partition:{partition}")
        if label not in allowed_labels:
            raise ValueError(f"invalid_label:{label}")
        if not source_id or not speaker_group or not source_relative_path:
            raise ValueError("entry_identity_is_incomplete")
        if not output_name.endswith(".wav") or Path(output_name).name != output_name:
            raise ValueError(f"invalid_output_name:{output_name}")
        if output_name in output_names:
            raise ValueError(f"duplicate_output_name:{output_name}")
        output_names.add(output_name)
        source_partitions[source_id].add(partition)
        speaker_partitions[speaker_group].add(partition)
        onset = float(entry.get("target_onset_seconds", -1.0))
        duration = float(entry.get("duration_seconds", 3.0))
        pre = float(entry.get("pre_seconds", 1.0))
        if onset < 0.0 or duration <= 0.0 or pre < 0.0:
            raise ValueError(f"invalid_timing:{output_name}")
    for source_id, partitions in source_partitions.items():
        if len(partitions) != 1:
            raise ValueError(f"source_crosses_partitions:{source_id}")
    for speaker_group, partitions in speaker_partitions.items():
        if len(partitions) != 1:
            raise ValueError(f"speaker_crosses_partitions:{speaker_group}")


def _preregistered_source_ids(
    preregistration: dict[str, object], partition: str, label: str
) -> set[str]:
    partition_value = preregistration.get(partition)
    if not isinstance(partition_value, dict):
        raise ValueError(f"preregistration_partition_missing:{partition}")
    field = "positive_sources" if label == "positive" else "hard_negative_sources"
    sources = partition_value.get(field)
    if not isinstance(sources, list):
        raise ValueError(f"preregistration_field_missing:{partition}:{field}")
    return {
        str(source.get("id"))
        for source in sources
        if isinstance(source, dict) and source.get("id")
    }


def validate_preregistration(
    spec: dict[str, object],
    preregistration_path: Path,
    entries: list[dict[str, object]],
) -> tuple[dict[str, object], str]:
    actual_hash = sha256(preregistration_path)
    expected_hash = str(spec.get("preregistration_sha256", "")).lower()
    if actual_hash != expected_hash:
        raise ValueError(
            f"preregistration_hash_mismatch:expected={expected_hash}:actual={actual_hash}"
        )
    preregistration = read_json(preregistration_path)
    if preregistration.get("candidate_model_scores_accessed") is not False:
        raise ValueError("blind_boundary_is_not_clean")
    if preregistration.get("split_frozen_before_candidate_scoring") is not True:
        raise ValueError("split_was_not_frozen_before_scoring")
    for entry in entries:
        partition = str(entry["partition"])
        label = str(entry["label"])
        source_id = str(entry["source_id"])
        allowed = _preregistered_source_ids(preregistration, partition, label)
        if source_id not in allowed:
            raise ValueError(
                f"source_not_preregistered:{partition}:{label}:{source_id}"
            )
    return preregistration, actual_hash


def extract_clip(
    ffmpeg: Path,
    source: Path,
    output: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.stem}.partial.wav")
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            # Output seeking is intentionally placed after -i.  WebM input
            # seeking snaps to keyframes and previously shifted target times.
            "-ss",
            f"{start_seconds:.6f}",
            "-t",
            f"{duration_seconds:.6f}",
            "-map",
            "0:a:0",
            "-ac",
            str(CHANNELS),
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(temporary),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        temporary.unlink(missing_ok=True)
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg_failed:{source}:{detail}")
    temporary.replace(output)


def probe_audio_duration(ffmpeg: Path, source: Path) -> float:
    if source.suffix.casefold() == ".wav":
        with wave.open(str(source), "rb") as audio:
            return audio.getnframes() / audio.getframerate()
    ffprobe = ffmpeg.with_name(
        "ffprobe.exe" if ffmpeg.suffix.casefold() == ".exe" else "ffprobe"
    )
    if not ffprobe.is_file():
        raise FileNotFoundError(f"ffprobe_not_found:{ffprobe}")
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffprobe_failed:{source}:{detail}")
    try:
        duration = float(completed.stdout.decode("ascii").strip())
    except ValueError as error:
        raise ValueError(f"ffprobe_duration_invalid:{source}") from error
    if duration <= 0.0:
        raise ValueError(f"source_duration_invalid:{source}:{duration}")
    return duration


def choose_clip_start(
    *, target_onset_seconds: float, pre_seconds: float, duration_seconds: float,
    source_duration_seconds: float
) -> float:
    if source_duration_seconds + 1e-6 < duration_seconds:
        raise ValueError(
            "source_shorter_than_clip:"
            f"source={source_duration_seconds}:clip={duration_seconds}"
        )
    if target_onset_seconds > source_duration_seconds:
        raise ValueError(
            "target_after_source_end:"
            f"target={target_onset_seconds}:source={source_duration_seconds}"
        )
    desired = max(0.0, target_onset_seconds - pre_seconds)
    latest = max(0.0, source_duration_seconds - duration_seconds)
    start = min(desired, latest)
    if not start <= target_onset_seconds <= start + duration_seconds:
        raise ValueError(
            "target_outside_clip:"
            f"target={target_onset_seconds}:start={start}:duration={duration_seconds}"
        )
    return start


def inspect_wav(path: Path, expected_duration_seconds: float) -> dict[str, object]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.getnframes()
        payload = source.readframes(frames)
    if (channels, sample_width, sample_rate) != (
        CHANNELS,
        SAMPLE_WIDTH_BYTES,
        SAMPLE_RATE,
    ):
        raise ValueError(
            f"wav_contract_mismatch:{path}:{channels}:{sample_width}:{sample_rate}"
        )
    expected_frames = round(expected_duration_seconds * SAMPLE_RATE)
    if abs(frames - expected_frames) > 1:
        raise ValueError(
            f"wav_duration_mismatch:{path}:expected={expected_frames}:actual={frames}"
        )
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError(f"wav_is_empty:{path}")
    square_sum = sum(value * value for value in samples)
    peak = max(abs(value) for value in samples)
    rms = (square_sum / len(samples)) ** 0.5 / 32768.0
    if peak == 0:
        raise ValueError(f"wav_is_silent:{path}")
    return {
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frames": frames,
        "duration_seconds": round(frames / sample_rate, 6),
        "rms": round(rms, 9),
        "peak": round(peak / 32768.0, 9),
    }


def build_corpus(
    *,
    spec_path: Path,
    preregistration_path: Path,
    source_root: Path,
    output_root: Path,
    ffmpeg: Path,
    measured_at_utc: str | None = None,
) -> dict[str, object]:
    spec = read_json(spec_path)
    if spec.get("schema") != "baxy.ccby-wake-holdout-spec.v1":
        raise ValueError("unsupported_spec_schema")
    raw_entries = spec.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("spec_entries_are_missing")
    entries = [entry for entry in raw_entries if isinstance(entry, dict)]
    if len(entries) != len(raw_entries):
        raise ValueError("spec_entry_is_not_object")
    validate_entries(entries)
    _, preregistration_hash = validate_preregistration(
        spec, preregistration_path, entries
    )
    if not ffmpeg.is_file():
        raise FileNotFoundError(f"ffmpeg_not_found:{ffmpeg}")

    records: list[dict[str, object]] = []
    for entry in entries:
        source = source_root / str(entry["source_relative_path"])
        if not source.is_file():
            raise FileNotFoundError(f"source_not_found:{source}")
        onset = float(entry["target_onset_seconds"])
        pre = float(entry.get("pre_seconds", 1.0))
        duration = float(entry.get("duration_seconds", 3.0))
        source_duration = probe_audio_duration(ffmpeg, source)
        start = choose_clip_start(
            target_onset_seconds=onset,
            pre_seconds=pre,
            duration_seconds=duration,
            source_duration_seconds=source_duration,
        )
        output = (
            output_root
            / str(entry["partition"])
            / str(entry["label"])
            / str(entry["output_name"])
        )
        extract_clip(
            ffmpeg,
            source,
            output,
            start_seconds=start,
            duration_seconds=duration,
        )
        wav = inspect_wav(output, duration)
        records.append(
            {
                "partition": entry["partition"],
                "label": entry["label"],
                "source_id": entry["source_id"],
                "speaker_group": entry["speaker_group"],
                "language": entry.get("language"),
                "acoustic_label": entry.get("acoustic_label"),
                "source_relative_path": entry["source_relative_path"],
                "source_sha256": sha256(source),
                "source_duration_seconds": round(source_duration, 6),
                "source_target_onset_seconds": onset,
                "source_clip_start_seconds": round(start, 6),
                "target_onset_in_clip_seconds": round(onset - start, 6),
                "output_relative_path": output.relative_to(output_root).as_posix(),
                "wav": wav,
            }
        )

    count_by_partition_and_label = Counter(
        (str(record["partition"]), str(record["label"])) for record in records
    )
    groups_by_partition_and_label: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in records:
        key = (str(record["partition"]), str(record["label"]))
        groups_by_partition_and_label[key].add(str(record["speaker_group"]))
    counts = {
        f"{partition}_{label}_clips": count
        for (partition, label), count in sorted(count_by_partition_and_label.items())
    }
    counts.update(
        {
            f"{partition}_{label}_speaker_groups": len(groups)
            for (partition, label), groups in sorted(
                groups_by_partition_and_label.items()
            )
        }
    )
    manifest: dict[str, object] = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "measured_at_utc": measured_at_utc
        or datetime.now(timezone.utc).isoformat(),
        "spec_sha256": sha256(spec_path),
        "preregistration_sha256": preregistration_hash,
        "candidate_model_scores_accessed": False,
        "blind_partition_was_not_scored": True,
        "extraction": {
            "ffmpeg_sha256": sha256(ffmpeg),
            "seek_policy": "accurate output seek after input decode",
            "sample_rate_hz": SAMPLE_RATE,
            "channels": CHANNELS,
            "sample_width_bytes": SAMPLE_WIDTH_BYTES,
        },
        "preregistration_amendments": spec.get(
            "preregistration_amendments", []
        ),
        "counts": counts,
        "records": records,
        "effects_executed": 0,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "corpus.manifest.v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--measured-at-utc")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_corpus(
        spec_path=args.spec,
        preregistration_path=args.preregistration,
        source_root=args.source_root,
        output_root=args.output_root,
        ffmpeg=args.ffmpeg,
        measured_at_utc=args.measured_at_utc,
    )
    counts = manifest["counts"]
    print(f"CORPUS|{args.output_root}")
    print(f"COUNTS|{json.dumps(counts, sort_keys=True)}")
    print(f"BLIND_SCORED|{str(False).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
