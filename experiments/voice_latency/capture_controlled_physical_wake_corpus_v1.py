"""Capture a controlled speaker -> room -> microphone training corpus.

Only known source WAVs are played.  The saved clip is aligned to that known
playback and excludes the fixed pre/post room recording, so incidental room
audio outside the playback interval is not retained.  This is an external,
opened-development corpus; it never touches blind human partitions.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_wakeword_physical_room_gate as room  # noqa: E402


SCHEMA = "baxy.controlled-physical-wake-corpus.v1"
SAMPLE_RATE = 16_000
_CLEAN_CLIP = re.compile(r"^clip_\d{6}\.wav$")


def select_sources(
    directory: Path,
    limit: int,
    seed: int,
    *,
    clean_clip_names_only: bool = True,
    maximum_source_seconds: float | None = None,
) -> list[Path]:
    candidates: list[Path] = []
    for path in sorted(directory.rglob("*.wav")):
        if not path.is_file() or (
            clean_clip_names_only and not _CLEAN_CLIP.fullmatch(path.name)
        ):
            continue
        if maximum_source_seconds is not None:
            with wave.open(str(path), "rb") as source:
                duration_seconds = source.getnframes() / source.getframerate()
            if duration_seconds > maximum_source_seconds:
                continue
        candidates.append(path)
    unique: list[Path] = []
    seen_hashes: set[str] = set()
    for path in candidates:
        digest = room._sha256(path)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        unique.append(path)
    if len(unique) < limit:
        raise ValueError("controlled_physical_source_population_insufficient")
    generator = random.Random(seed)
    return sorted(generator.sample(unique, limit))


def align_known_playback(
    captured: np.ndarray,
    played: np.ndarray,
) -> tuple[np.ndarray, float, int]:
    """Return the captured interval aligned to a known, controlled source."""

    from scipy.signal import correlate

    microphone = np.asarray(captured, dtype=np.float64).reshape(-1)
    reference = np.asarray(played, dtype=np.float64).reshape(-1)
    if reference.size < 1 or microphone.size < reference.size:
        raise ValueError("controlled_physical_alignment_length_invalid")
    microphone -= microphone.mean()
    reference -= reference.mean()
    numerator = correlate(microphone, reference, mode="valid", method="fft")
    start = int(np.argmax(np.abs(numerator)))
    segment = microphone[start : start + reference.size]
    denominator = float(np.linalg.norm(segment) * np.linalg.norm(reference))
    correlation = (
        abs(float(np.dot(segment, reference))) / denominator
        if denominator > 1e-12
        else 0.0
    )
    return segment.astype(np.float32), correlation, start


def normalize_training_capture(audio: np.ndarray) -> tuple[np.ndarray, float]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    values -= float(np.mean(values, dtype=np.float64))
    robust_peak = float(np.percentile(np.abs(values), 99.5)) if values.size else 0.0
    if robust_peak <= 1e-7:
        raise ValueError("controlled_physical_capture_silent")
    gain = min(30.0, 0.65 / robust_peak)
    return np.clip(values * gain, -0.98, 0.98).astype(np.float32), gain


def requires_split_stream(
    sounddevice: Any,
    input_device: int | str,
    output_device: int | str,
) -> bool:
    input_info = sounddevice.query_devices(input_device, "input")
    output_info = sounddevice.query_devices(output_device, "output")
    input_api = sounddevice.query_hostapis(int(input_info["hostapi"]))["name"]
    output_api = sounddevice.query_hostapis(int(output_info["hostapi"]))["name"]
    return input_api == output_api and "WDM-KS" in str(input_api).upper()


def play_and_record(
    sounddevice: Any,
    playback: np.ndarray,
    *,
    sample_rate: int,
    input_device: int | str,
    output_device: int | str,
    raw_capture_helper: Path | None = None,
) -> np.ndarray:
    values = np.asarray(playback, dtype=np.float32).reshape(-1, 1)
    if raw_capture_helper is not None:
        with tempfile.TemporaryDirectory(prefix="baxy-raw-capture-") as temp:
            output_path = Path(temp) / "capture.wav"
            duration_seconds = len(values) / sample_rate + 1.0
            process = subprocess.Popen(
                [
                    str(raw_capture_helper),
                    "capture",
                    str(output_path),
                    f"{duration_seconds:.6f}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=os.environ.copy(),
            )
            assert process.stdout is not None
            ready: list[str] = []
            reader = threading.Thread(
                target=lambda: ready.append(process.stdout.readline()),
                name="baxy-raw-capture-ready",
                daemon=True,
            )
            reader.start()
            reader.join(timeout=10.0)
            if reader.is_alive() or not ready or ready[0].strip() != "READY":
                process.kill()
                _, stderr = process.communicate(timeout=5.0)
                raise RuntimeError(
                    "controlled_physical_raw_capture_not_ready:" + stderr[-500:]
                )
            try:
                sounddevice.play(
                    values,
                    samplerate=sample_rate,
                    device=output_device,
                    blocking=True,
                )
                _, stderr = process.communicate(timeout=duration_seconds + 10.0)
            except BaseException:
                process.kill()
                process.communicate(timeout=5.0)
                raise
            if process.returncode != 0 or not output_path.is_file():
                raise RuntimeError(
                    "controlled_physical_raw_capture_failed:" + stderr[-500:]
                )
            captured, captured_rate = room._read_pcm16(output_path)
            return room._resample(captured, captured_rate, sample_rate).astype(np.float32)
    if not requires_split_stream(sounddevice, input_device, output_device):
        return np.asarray(
            sounddevice.playrec(
                values,
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                device=(input_device, output_device),
                blocking=True,
            ),
            dtype=np.float32,
        ).reshape(-1)
    # PortAudio's WDM-KS backend deliberately rejects its blocking API.  The
    # callback API is supported and also lets the two raw endpoints run as
    # independent streams when the driver cannot expose a duplex device.
    chunks: list[np.ndarray] = []
    statuses: list[str] = []
    input_done = threading.Event()
    output_done = threading.Event()
    captured_samples = 0
    played_samples = 0

    def record_input(indata: np.ndarray, frames: int, _time: Any, status: Any) -> None:
        nonlocal captured_samples
        if status:
            statuses.append(f"input:{status}")
        take = min(frames, len(values) - captured_samples)
        if take:
            chunks.append(np.asarray(indata[:take, 0], dtype=np.float32).copy())
            captured_samples += take
        if captured_samples >= len(values):
            raise sounddevice.CallbackStop

    def write_output(outdata: np.ndarray, frames: int, _time: Any, status: Any) -> None:
        nonlocal played_samples
        if status:
            statuses.append(f"output:{status}")
        outdata.fill(0)
        take = min(frames, len(values) - played_samples)
        if take:
            outdata[:take, 0] = values[played_samples : played_samples + take, 0]
            played_samples += take
        if played_samples >= len(values):
            raise sounddevice.CallbackStop

    input_stream = sounddevice.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=input_device,
        callback=record_input,
        finished_callback=input_done.set,
    )
    output_stream = sounddevice.OutputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=output_device,
        callback=write_output,
        finished_callback=output_done.set,
    )
    timeout_seconds = max(10.0, len(values) / sample_rate + 5.0)
    try:
        input_stream.start()
        output_stream.start()
        if not output_done.wait(timeout_seconds):
            raise RuntimeError("controlled_physical_split_output_timeout")
        if not input_done.wait(timeout_seconds):
            raise RuntimeError("controlled_physical_split_input_timeout")
    finally:
        output_stream.close()
        input_stream.close()
    if statuses:
        raise RuntimeError(
            "controlled_physical_split_stream_status:" + "|".join(statuses)
        )
    if captured_samples != len(values) or played_samples != len(values):
        raise RuntimeError("controlled_physical_split_stream_length_mismatch")
    return np.concatenate(chunks).astype(np.float32)


def _write_pcm16(path: Path, audio: np.ndarray) -> None:
    pcm = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    payload = np.round(pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(SAMPLE_RATE)
        sink.writeframes(payload.tobytes())


def _load_progress(path: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    if not path.exists():
        return records
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError
            record_id = value.get("recordId")
            if not isinstance(record_id, str) or record_id in records:
                raise ValueError
            records[record_id] = value
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError("controlled_physical_progress_invalid") from error
    return records


def _append_progress(path: Path, record: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()
        os.fsync(sink.fileno())


def capture_validated_playback(
    sounddevice: Any,
    playback: np.ndarray,
    played: np.ndarray,
    *,
    sample_rate: int,
    input_device: int | str,
    output_device: int | str,
    pre_samples: int,
    minimum_correlation: float,
    minimum_snr_db: float,
    maximum_attempts: int,
    raw_capture_helper: Path | None,
) -> tuple[np.ndarray, float, float, int, int]:
    """Capture one source, retrying transient physical-path failures."""

    last_failure = "controlled_physical_capture_quality_unknown"
    for attempt in range(1, maximum_attempts + 1):
        captured = play_and_record(
            sounddevice,
            playback,
            sample_rate=sample_rate,
            input_device=input_device,
            output_device=output_device,
            raw_capture_helper=raw_capture_helper,
        )
        captured = np.asarray(captured, dtype=np.float32).reshape(-1)
        noise = captured[:pre_samples]
        noise_rms = float(np.sqrt(np.mean(np.square(noise), dtype=np.float64)))
        full_rms = float(np.sqrt(np.mean(np.square(captured), dtype=np.float64)))
        snr_db = 20.0 * math.log10(
            max(full_rms, 1e-9) / max(noise_rms, 1e-9)
        )
        aligned, correlation, delay_samples = align_known_playback(captured, played)
        if correlation < minimum_correlation:
            last_failure = "controlled_physical_path_correlation_below_floor"
        elif snr_db < minimum_snr_db:
            last_failure = "controlled_physical_snr_below_floor"
        else:
            return aligned, correlation, snr_db, delay_samples, attempt
    raise ValueError(last_failure)


def _capture_group(
    *,
    label: str,
    sources: list[Path],
    output_directory: Path,
    sounddevice: Any,
    input_device: int | str,
    output_device: int | str,
    hardware_rate: int,
    playback_gain: float,
    pre_roll_seconds: float,
    post_roll_seconds: float,
    minimum_correlation: float,
    minimum_snr_db: float,
    maximum_attempts: int,
    raw_capture_helper: Path | None,
    progress_path: Path,
    existing_records: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    destination = output_directory / label
    destination.mkdir(parents=True, exist_ok=True)
    pre_samples = round(pre_roll_seconds * hardware_rate)
    post_samples = round(post_roll_seconds * hardware_rate)
    records: list[dict[str, object]] = []
    for index, source_path in enumerate(sources):
        record_id = f"{label}/{index:06d}"
        source_hash = room._sha256(source_path)
        existing = existing_records.get(record_id)
        if existing is not None:
            relative_output = existing.get("output")
            if not isinstance(relative_output, str):
                raise ValueError("controlled_physical_progress_invalid")
            output_path = (output_directory / relative_output).resolve(strict=True)
            output_path.relative_to(output_directory)
            if (
                existing.get("sourceSha256") != source_hash
                or existing.get("outputSha256") != room._sha256(output_path)
            ):
                raise ValueError("controlled_physical_progress_mismatch")
            records.append(existing)
            continue
        source, source_rate = room._read_pcm16(source_path)
        played = room._resample(source, source_rate, hardware_rate)
        peak = float(np.max(np.abs(played))) if played.size else 0.0
        if peak <= 1e-7:
            raise ValueError("controlled_physical_source_silent")
        played = np.clip(played * (playback_gain / peak), -0.98, 0.98)
        playback = np.pad(played, (pre_samples, post_samples)).astype(np.float32)
        aligned, correlation, snr_db, delay_samples, capture_attempts = (
            capture_validated_playback(
            sounddevice,
            playback,
            played,
            sample_rate=hardware_rate,
            input_device=input_device,
            output_device=output_device,
            pre_samples=pre_samples,
            minimum_correlation=minimum_correlation,
            minimum_snr_db=minimum_snr_db,
            maximum_attempts=maximum_attempts,
            raw_capture_helper=raw_capture_helper,
        )
        )
        aligned_16k = room._resample(aligned, hardware_rate, SAMPLE_RATE)
        conditioned, conditioning_gain = normalize_training_capture(aligned_16k)
        output_path = destination / f"clip_{index:06d}_r0.wav"
        _write_pcm16(output_path, conditioned)
        record = {
            "recordId": record_id,
            "sourceSha256": source_hash,
            "output": output_path.relative_to(output_directory).as_posix(),
            "outputSha256": room._sha256(output_path),
            "sourceSeconds": source.size / source_rate,
            "pathCorrelation": correlation,
            "capturedSnrDb": snr_db,
            "delaySeconds": delay_samples / hardware_rate,
            "conditioningGain": conditioning_gain,
            "captureAttempts": capture_attempts,
        }
        _append_progress(progress_path, record)
        records.append(record)
        if (index + 1) % 20 == 0 or index + 1 == len(sources):
            print(f"{label}:{index + 1}/{len(sources)}", flush=True)
    return records


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--positive-limit", type=room._positive_int, required=True)
    parser.add_argument("--negative-limit", type=room._positive_int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-device", type=room._device, required=True)
    parser.add_argument("--output-device", type=room._device, required=True)
    parser.add_argument(
        "--raw-capture-helper",
        type=Path,
        help="Use an attested IAudioClient2 RAW capture helper instead of PortAudio input.",
    )
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument(
        "--include-all-wavs",
        action="store_true",
        help="Allow non-LiveKit names while still deduplicating content hashes.",
    )
    parser.add_argument("--gain", type=room._finite_float, default=0.25)
    parser.add_argument(
        "--maximum-source-seconds",
        type=room._finite_float,
        default=20.0,
        help="Reject unexpectedly long playback sources before sampling.",
    )
    parser.add_argument("--pre-roll-seconds", type=room._finite_float, default=0.25)
    parser.add_argument("--post-roll-seconds", type=room._finite_float, default=0.5)
    parser.add_argument(
        "--minimum-path-correlation", type=room._finite_float, default=0.10
    )
    parser.add_argument(
        "--minimum-captured-snr-db", type=room._finite_float, default=3.0
    )
    parser.add_argument("--maximum-capture-attempts", type=room._positive_int, default=3)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue an interrupted capture after verifying every saved hash.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.physical_output:
        raise SystemExit("Refusing acoustic playback without --physical-output.")
    if not 0.01 <= args.gain <= 0.95:
        raise SystemExit("--gain must be between 0.01 and 0.95.")
    if args.maximum_source_seconds <= 0:
        raise SystemExit("--maximum-source-seconds must be positive.")
    output_directory = args.output_dir.resolve()
    if output_directory.exists() and not args.resume:
        raise SystemExit("Output directory already exists.")
    positive_root = args.positive.resolve(strict=True)
    negative_root = args.negative.resolve(strict=True)
    raw_capture_helper = (
        args.raw_capture_helper.resolve(strict=True)
        if args.raw_capture_helper is not None
        else None
    )
    clean_only = not args.include_all_wavs
    positives = select_sources(
        positive_root,
        args.positive_limit,
        args.seed,
        clean_clip_names_only=clean_only,
        maximum_source_seconds=args.maximum_source_seconds,
    )
    negatives = select_sources(
        negative_root,
        args.negative_limit,
        args.seed + 1,
        clean_clip_names_only=clean_only,
        maximum_source_seconds=args.maximum_source_seconds,
    )
    output_directory.mkdir(parents=True, exist_ok=args.resume)
    progress_path = output_directory / "progress.v1.jsonl"
    existing_records = _load_progress(progress_path) if args.resume else {}
    import sounddevice as sd

    hardware_rate = room._resolve_hardware_rate(
        sd, args.input_device, args.output_device
    )
    input_info = sd.query_devices(args.input_device, "input")
    output_info = sd.query_devices(args.output_device, "output")
    started = time.perf_counter()
    common = {
        "output_directory": output_directory,
        "sounddevice": sd,
        "input_device": args.input_device,
        "output_device": args.output_device,
        "hardware_rate": hardware_rate,
        "playback_gain": args.gain,
        "pre_roll_seconds": args.pre_roll_seconds,
        "post_roll_seconds": args.post_roll_seconds,
        "minimum_correlation": args.minimum_path_correlation,
        "minimum_snr_db": args.minimum_captured_snr_db,
        "maximum_attempts": args.maximum_capture_attempts,
        "raw_capture_helper": raw_capture_helper,
        "progress_path": progress_path,
        "existing_records": existing_records,
    }
    positive_records = _capture_group(label="positive", sources=positives, **common)
    negative_records = _capture_group(label="negative", sources=negatives, **common)
    manifest = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "controlled_opened_known_playback_physical_room_training",
        "seed": args.seed,
        "physicalPath": {
            "inputDevice": str(input_info["name"]),
            "outputDevice": str(output_info["name"]),
            "hardwareSampleRate": hardware_rate,
            "playbackGain": args.gain,
            "preRollSecondsNotRetained": args.pre_roll_seconds,
            "postRollSecondsNotRetained": args.post_roll_seconds,
            "maximumSourceSeconds": args.maximum_source_seconds,
            "maximumCaptureAttempts": args.maximum_capture_attempts,
            "minimumPathCorrelation": args.minimum_path_correlation,
            "minimumCapturedSnrDb": args.minimum_captured_snr_db,
            "captureTransport": (
                "wasapi_raw_iaudioclient2"
                if raw_capture_helper is not None
                else "portaudio"
            ),
            "rawCaptureHelperSha256": (
                room._sha256(raw_capture_helper)
                if raw_capture_helper is not None
                else None
            ),
        },
        "sources": {
            "positiveRootSha256": room._corpus_sha256(positives, positive_root),
            "negativeRootSha256": room._corpus_sha256(negatives, negative_root),
            "filenamesOrTranscriptsRetained": False,
        },
        "counts": {
            "positive": len(positive_records),
            "negative": len(negative_records),
        },
        "records": [*positive_records, *negative_records],
        "elapsedWallSeconds": time.perf_counter() - started,
        "capturedPreOrPostRoomAudioRetained": False,
        "blindHumanPartitionAccessed": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    manifest_path = output_directory / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
