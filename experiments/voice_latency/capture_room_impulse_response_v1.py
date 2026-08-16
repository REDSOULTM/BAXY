"""Capture a non-speech room impulse response for wake-word augmentation.

The script emits an exponential sine sweep through one explicit speaker and
records one explicit microphone.  It writes only the derived impulse response
and a hashed development report; the raw room capture is never retained.  The
result is training evidence, not a product wake asset and not a promotion gate.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import wave
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_wakeword_physical_room_gate as room  # noqa: E402


REPORT_SCHEMA = "baxy.room-impulse-response-development.v1"
TARGET_SAMPLE_RATE = 16_000


def generate_exponential_sweep(
    *,
    sample_rate: int,
    duration_seconds: float,
    start_hz: float,
    end_hz: float,
    fade_seconds: float,
) -> np.ndarray:
    if (
        sample_rate < 8_000
        or not math.isfinite(duration_seconds)
        or duration_seconds < 1.0
        or not math.isfinite(start_hz)
        or not math.isfinite(end_hz)
        or not 20.0 <= start_hz < end_hz <= sample_rate * 0.48
        or not math.isfinite(fade_seconds)
        or not 0.005 <= fade_seconds <= duration_seconds / 4.0
    ):
        raise ValueError("room_sweep_contract_invalid")
    from scipy.signal import chirp

    samples = round(duration_seconds * sample_rate)
    timeline = np.arange(samples, dtype=np.float64) / sample_rate
    sweep = chirp(
        timeline,
        f0=start_hz,
        f1=end_hz,
        t1=duration_seconds,
        method="logarithmic",
        phi=-90.0,
    ).astype(np.float32)
    fade_samples = max(1, round(fade_seconds * sample_rate))
    phase = np.linspace(0.0, math.pi, fade_samples, endpoint=True)
    fade = (0.5 - 0.5 * np.cos(phase)).astype(np.float32)
    sweep[:fade_samples] *= fade
    sweep[-fade_samples:] *= fade[::-1]
    return np.ascontiguousarray(sweep)


def estimate_impulse_response(
    captured: np.ndarray,
    sweep: np.ndarray,
    *,
    sample_rate: int,
    start_hz: float,
    end_hz: float,
    duration_seconds: float,
    pre_peak_seconds: float,
    regularization: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    observed = np.asarray(captured, dtype=np.float64).reshape(-1)
    emitted = np.asarray(sweep, dtype=np.float64).reshape(-1)
    if (
        sample_rate < 8_000
        or emitted.size < sample_rate
        or observed.size < emitted.size
        or not np.isfinite(observed).all()
        or not np.isfinite(emitted).all()
        or float(np.max(np.abs(emitted))) <= 1e-9
        or not 20.0 <= start_hz < end_hz <= sample_rate * 0.48
        or not 0.1 <= duration_seconds <= 3.0
        or not 0.0 <= pre_peak_seconds <= min(0.05, duration_seconds / 4.0)
        or not 1e-10 <= regularization <= 1e-2
    ):
        raise ValueError("room_impulse_contract_invalid")

    fft_size = 1 << (observed.size + emitted.size - 2).bit_length()
    observed_spectrum = np.fft.rfft(observed, n=fft_size)
    emitted_spectrum = np.fft.rfft(emitted, n=fft_size)
    emitted_power = np.square(np.abs(emitted_spectrum))
    peak_power = float(np.max(emitted_power))
    transfer = observed_spectrum * np.conj(emitted_spectrum)
    transfer /= emitted_power + regularization * peak_power
    frequencies = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    passband = (frequencies >= start_hz * 0.8) & (
        frequencies <= min(sample_rate / 2.0, end_hz * 1.05)
    )
    transfer[~passband] = 0.0
    raw_impulse = np.fft.irfft(transfer, n=fft_size)[: observed.size]

    peak_index = int(np.argmax(np.abs(raw_impulse)))
    pre_peak_samples = round(pre_peak_seconds * sample_rate)
    output_samples = round(duration_seconds * sample_rate)
    crop_start = max(0, peak_index - pre_peak_samples)
    impulse = raw_impulse[crop_start : crop_start + output_samples]
    if impulse.size < output_samples:
        impulse = np.pad(impulse, (0, output_samples - impulse.size))
    peak_in_crop = peak_index - crop_start
    absolute_peak = float(np.max(np.abs(impulse)))
    if absolute_peak <= 1e-12:
        raise ValueError("room_impulse_silent")
    impulse /= absolute_peak
    noise_region = impulse[: max(1, peak_in_crop - max(1, sample_rate // 1000))]
    noise_rms = float(np.sqrt(np.mean(np.square(noise_region))))
    direct_to_pre_db = 20.0 * math.log10(1.0 / max(noise_rms, 1e-12))
    tail_start = min(output_samples, peak_in_crop + round(0.01 * sample_rate))
    tail_energy = float(np.sum(np.square(impulse[tail_start:])))
    total_energy = float(np.sum(np.square(impulse)))
    metrics: dict[str, float | int] = {
        "rawPeakIndex": peak_index,
        "cropStartIndex": crop_start,
        "directPeakIndex": peak_in_crop,
        "directPeakSeconds": peak_in_crop / sample_rate,
        "directToPreDeconvolutionDb": direct_to_pre_db,
        "tailEnergyFraction": tail_energy / max(total_energy, 1e-12),
    }
    return np.ascontiguousarray(impulse.astype(np.float32)), metrics


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_pcm16(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not values.size or not np.isfinite(values).all():
        raise ValueError("room_impulse_output_invalid")
    encoded = np.rint(np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(sample_rate)
        destination.writeframes(encoded.tobytes())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--input-device", type=room._device, required=True)
    parser.add_argument("--output-device", type=room._device, required=True)
    parser.add_argument("--rir-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--gain", type=room._finite_float, default=0.20)
    parser.add_argument("--sweep-seconds", type=room._finite_float, default=4.0)
    parser.add_argument("--pre-roll-seconds", type=room._finite_float, default=0.75)
    parser.add_argument("--post-roll-seconds", type=room._finite_float, default=1.5)
    parser.add_argument("--start-hz", type=room._finite_float, default=80.0)
    parser.add_argument("--end-hz", type=room._finite_float, default=7_600.0)
    parser.add_argument("--fade-seconds", type=room._finite_float, default=0.05)
    parser.add_argument("--rir-seconds", type=room._finite_float, default=1.0)
    parser.add_argument("--pre-peak-seconds", type=room._finite_float, default=0.005)
    parser.add_argument("--regularization", type=room._finite_float, default=1e-6)
    parser.add_argument("--minimum-correlation", type=room._finite_float, default=0.10)
    parser.add_argument("--minimum-snr-db", type=room._finite_float, default=8.0)
    parser.add_argument(
        "--minimum-direct-to-pre-db", type=room._finite_float, default=8.0
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.physical_output:
        raise SystemExit("Refusing acoustic playback without --physical-output.")
    if not 0.01 <= args.gain <= 0.5:
        raise SystemExit("--gain must be between 0.01 and 0.5.")
    if args.rir_output.resolve() == args.report_output.resolve():
        raise SystemExit("RIR and report outputs must differ.")
    for path in (args.rir_output.resolve(), args.report_output.resolve()):
        if path.exists():
            raise SystemExit(f"Output already exists: {path}")

    import sounddevice as sd

    hardware_rate = room._resolve_hardware_rate(
        sd,
        args.input_device,
        args.output_device,
    )
    end_hz = min(args.end_hz, hardware_rate * 0.48)
    sweep = generate_exponential_sweep(
        sample_rate=hardware_rate,
        duration_seconds=args.sweep_seconds,
        start_hz=args.start_hz,
        end_hz=end_hz,
        fade_seconds=args.fade_seconds,
    )
    pre_samples = round(args.pre_roll_seconds * hardware_rate)
    post_samples = round(args.post_roll_seconds * hardware_rate)
    playback = np.pad(sweep * args.gain, (pre_samples, post_samples)).astype(
        np.float32
    )
    input_info = sd.query_devices(args.input_device, "input")
    output_info = sd.query_devices(args.output_device, "output")
    started = time.perf_counter()
    captured = sd.playrec(
        playback.reshape(-1, 1),
        samplerate=hardware_rate,
        channels=1,
        dtype="float32",
        device=(args.input_device, args.output_device),
        blocking=True,
    )
    captured = np.asarray(captured, dtype=np.float32).reshape(-1)
    noise = captured[:pre_samples]
    observed = captured[pre_samples : pre_samples + sweep.size + post_samples]
    noise_rms = float(np.sqrt(np.mean(np.square(noise), dtype=np.float64)))
    observed_rms = float(np.sqrt(np.mean(np.square(observed), dtype=np.float64)))
    snr_db = 20.0 * math.log10(max(observed_rms, 1e-9) / max(noise_rms, 1e-9))
    correlation = room.normalized_delay_correlation(captured, sweep)
    impulse, impulse_metrics = estimate_impulse_response(
        captured,
        sweep,
        sample_rate=hardware_rate,
        start_hz=args.start_hz,
        end_hz=end_hz,
        duration_seconds=args.rir_seconds,
        pre_peak_seconds=args.pre_peak_seconds,
        regularization=args.regularization,
    )
    impulse_16k = room._resample(impulse, hardware_rate, TARGET_SAMPLE_RATE)
    impulse_16k /= max(float(np.max(np.abs(impulse_16k))), 1e-12)
    passed = (
        correlation >= args.minimum_correlation
        and snr_db >= args.minimum_snr_db
        and float(impulse_metrics["directToPreDeconvolutionDb"])
        >= args.minimum_direct_to_pre_db
    )

    rir_path = args.rir_output.resolve()
    report_path = args.report_output.resolve()
    rir_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_pcm16(rir_path, impulse_16k, TARGET_SAMPLE_RATE)
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "non_speech_speaker_room_microphone_impulse_response",
        "physicalPath": {
            "topology": "explicit speaker -> room -> explicit microphone",
            "inputDevice": str(input_info["name"]),
            "outputDevice": str(output_info["name"]),
            "hardwareSampleRate": hardware_rate,
            "playbackGain": args.gain,
        },
        "sweep": {
            "method": "exponential_sine",
            "durationSeconds": args.sweep_seconds,
            "startHz": args.start_hz,
            "endHz": end_hz,
            "fadeSeconds": args.fade_seconds,
            "speechContent": False,
        },
        "quality": {
            "passed": passed,
            "pathCorrelation": correlation,
            "capturedSnrDb": snr_db,
            "minimumCorrelation": args.minimum_correlation,
            "minimumSnrDb": args.minimum_snr_db,
            "minimumDirectToPreDeconvolutionDb": args.minimum_direct_to_pre_db,
            **impulse_metrics,
        },
        "rir": {
            "sampleRate": TARGET_SAMPLE_RATE,
            "samples": int(impulse_16k.size),
            "durationSeconds": impulse_16k.size / TARGET_SAMPLE_RATE,
            "sha256": _sha256(rir_path),
        },
        "elapsedWallSeconds": time.perf_counter() - started,
        "rawCaptureRetained": False,
        "containsSpeech": False,
        "effectsExecuted": 0,
        "developmentOnly": True,
        "promotable": False,
        "promotionBlockedBy": [
            "training_augmentation_only",
            "single_room_position",
            "wake_candidate_not_retrained",
            "blind_physical_holdout_not_run",
        ],
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "pathCorrelation": correlation,
                "capturedSnrDb": snr_db,
                "directToPreDb": impulse_metrics[
                    "directToPreDeconvolutionDb"
                ],
                "rirSha256": report["rir"]["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
