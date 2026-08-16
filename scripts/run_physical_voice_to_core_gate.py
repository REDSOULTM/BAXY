"""Prove speaker -> room -> mic -> wake -> STT -> Mind -> verified Core.

The gate plays only two synthetic, preregistered read-only requests.  It keeps
neither captured audio nor transcript text and grants no confirmation token.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
VOICE_EXPERIMENTS = ROOT / "experiments" / "voice_latency"
for path in (ROOT, ROOT / "src", ROOT / "scripts", VOICE_EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import capture_controlled_physical_wake_corpus_v1 as capture  # noqa: E402
import evaluate_baxy_wake_cascade_runtime_raw_v1 as cascade_gate  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from scripts import test_mind_voice as voice_gate  # noqa: E402
from baxy_mind.voice import VoiceEngine, WakePhraseMatcher  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    HyperspotterCascadeDetector,
    has_strict_leading_alias,
    load_wake_cascade_config,
)


SCHEMA = "baxy.physical-voice-to-verified-core.v1"
SAMPLE_RATE = 16_000
DEFAULT_OUTPUT = ROOT / "artifacts" / "product" / "physical_voice_to_core_gate.json"
CASES = (
    {
        "id": "english_system_status",
        "voice": "409",
        "text": "Baxy, how much disk space do I have left",
        "expectedOperation": "system.status",
    },
    {
        "id": "spanglish_audio_status",
        "voice": "80A",
        "text": "Baxy, check el volumen de la compu",
        "expectedOperation": "audio.status",
    },
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _transcribe(engine: VoiceEngine, audio: np.ndarray) -> str:
    recognizer = engine._recognizer  # noqa: SLF001 - physical product gate
    if recognizer is None:
        raise RuntimeError("physical_voice_stt_not_loaded")
    stream = recognizer.create_stream()
    stream.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
    recognizer.decode_stream(stream)
    return str(stream.result.text or "").strip()


def _wake_detection(
    detector: HyperspotterCascadeDetector, audio: np.ndarray
) -> Any | None:
    detector.reset()
    for start in range(0, len(audio), 512):
        hit = detector.accept(audio[start : start + 512], now=10.0)
        if hit is not None:
            return hit
    return None


def _run_verified_core(text: str, expected: str, output: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["BAXY_LLM_GATE_PHYSICAL_VOICE_TEXT"] = text
    environment["BAXY_LLM_GATE_PHYSICAL_VOICE_EXPECTED"] = expected
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(ROOT / "scripts" / "run_llm_plan_execution_gate.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0 or not output.is_file():
        raise RuntimeError(
            "physical_voice_core_gate_failed:"
            + completed.stderr[-500:].replace("\n", " ")
        )
    report = json.loads(output.read_text(encoding="utf-8"))
    results = report.get("cases")
    if (
        report.get("summary", {}).get("status")
        not in {"passed", "passed_with_environment_blocks"}
        or not isinstance(results, list)
        or len(results) != 1
        or results[0].get("status") != "passed"
        or results[0].get("operations") != [expected]
    ):
        raise RuntimeError("physical_voice_core_result_not_verified")
    return {
        "reportSha256": _sha(output),
        "status": results[0]["status"],
        "operations": results[0]["operations"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--raw-capture-helper", type=Path, required=True)
    parser.add_argument("--input-device", type=room._device, required=True)
    parser.add_argument("--output-device", type=room._device, required=True)
    parser.add_argument("--gain", type=room._finite_float, default=0.65)
    parser.add_argument("--maximum-capture-attempts", type=int, default=6)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.physical_output:
        raise SystemExit("Refusing acoustic playback without --physical-output.")
    if not 0.01 <= args.gain <= 0.95 or args.maximum_capture_attempts < 1:
        raise SystemExit("Physical voice capture parameters are invalid.")
    output = args.output.resolve()
    cascade_manifest = args.cascade_manifest.resolve(strict=True)
    raw_helper = args.raw_capture_helper.resolve(strict=True)
    os.environ["BAXY_VOICE_WAKE_CASCADE_MANIFEST"] = str(cascade_manifest)
    config = load_wake_cascade_config(cascade_manifest)
    detector = HyperspotterCascadeDetector(config)
    engine = VoiceEngine(lambda _text: None)
    engine.load()
    matcher = WakePhraseMatcher()
    import sounddevice as sd

    hardware_rate = room._resolve_hardware_rate(
        sd, args.input_device, args.output_device
    )
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="baxy-physical-voice-core-") as temp:
            temporary = Path(temp)
            for case in CASES:
                source = voice_gate.synthesize(str(case["voice"]), str(case["text"]))
                played = room._resample(source, SAMPLE_RATE, hardware_rate)
                peak = float(np.max(np.abs(played))) if played.size else 0.0
                if peak <= 1e-7:
                    raise RuntimeError("physical_voice_source_silent")
                played = np.clip(played * (args.gain / peak), -0.98, 0.98)
                pre_samples = round(0.25 * hardware_rate)
                playback = np.pad(
                    played, (pre_samples, round(0.5 * hardware_rate))
                ).astype(np.float32)
                aligned, correlation, snr_db, _delay, attempts = (
                    capture.capture_validated_playback(
                        sd,
                        playback,
                        played,
                        sample_rate=hardware_rate,
                        input_device=args.input_device,
                        output_device=args.output_device,
                        pre_samples=pre_samples,
                        minimum_correlation=0.10,
                        minimum_snr_db=3.0,
                        maximum_attempts=args.maximum_capture_attempts,
                        raw_capture_helper=raw_helper,
                    )
                )
                microphone = room._resample(aligned, hardware_rate, SAMPLE_RATE)
                transcript = _transcribe(engine, microphone)
                hit = _wake_detection(detector, cascade_gate.stream_audio(microphone))
                lexical_ok = bool(
                    hit is not None
                    and (
                        not hit.lexical_rescue_required
                        or has_strict_leading_alias(transcript, config.lexical_aliases)
                    )
                )
                wake_prefix, command = matcher.strip(transcript)
                if not lexical_ok or not wake_prefix or not command:
                    raise RuntimeError("physical_voice_wake_or_transcript_failed")
                if engine._corrector is not None:  # noqa: SLF001
                    command = engine._corrector.correct(command)  # noqa: SLF001
                core = _run_verified_core(
                    command,
                    str(case["expectedOperation"]),
                    temporary / f"{case['id']}.json",
                )
                records.append(
                    {
                        "id": case["id"],
                        "sourceTextSha256": hashlib.sha256(
                            str(case["text"]).encode("utf-8")
                        ).hexdigest(),
                        "transcriptSha256": hashlib.sha256(
                            transcript.encode("utf-8")
                        ).hexdigest(),
                        "commandSha256": hashlib.sha256(
                            command.encode("utf-8")
                        ).hexdigest(),
                        "pathCorrelation": correlation,
                        "capturedSnrDb": snr_db,
                        "captureAttempts": attempts,
                        "wakeAccepted": lexical_ok,
                        "wakeMethod": hit.method if hit is not None else None,
                        "wakePrefixRecovered": wake_prefix,
                        "expectedOperation": case["expectedOperation"],
                        "verifiedCore": core,
                    }
                )
    finally:
        engine.shutdown()
    passed = len(records) == len(CASES) and all(
        record["verifiedCore"]["status"] == "passed" for record in records
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "scope": "physical_room_voice_exact_wake_stt_real_mind_verified_core",
        "cascadeManifestSha256": _sha(cascade_manifest),
        "rawCaptureHelperSha256": _sha(raw_helper),
        "hardwareSampleRate": hardware_rate,
        "playbackGain": args.gain,
        "cases": records,
        "metrics": {
            "cases": len(records),
            "wakeAccepted": sum(record["wakeAccepted"] for record in records),
            "verifiedCoreOperations": sum(
                len(record["verifiedCore"]["operations"]) for record in records
            ),
            "elapsedWallSeconds": time.perf_counter() - started,
        },
        "capturedAudioRetained": False,
        "transcriptTextRetained": False,
        "writeOrExternalEffectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
