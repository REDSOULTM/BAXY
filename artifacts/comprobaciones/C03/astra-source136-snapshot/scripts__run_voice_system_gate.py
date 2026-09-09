"""Gate integral de voz: licencias, runtime, hardware y efectos acústicos.

No persiste audio ni transcripciones. El micrófono se abre físicamente y solo
se guardan capacidades/estados booleanos. ``--physical-output`` hace hablar a
SAPI y verifica que la cancelación corte su ciclo; se usa en la validación del
equipo, no en CI silencioso.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import re
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from baxy_mind.corrector import catalog_correction_terms  # noqa: E402
from baxy_mind.voice import (  # noqa: E402
    SAMPLE_RATE,
    VoiceEngine,
    WakePhraseMatcher,
)
from baxy_mind.voice_aec import AudioDucker, _com_apartment  # noqa: E402
from baxy_mind.speex_aec import EchoCanceller, FRAME_SAMPLES, REFERENCE_SAMPLES  # noqa: E402
from baxy_mind.voice_output import SapiSpeechOutput  # noqa: E402

OUT = REPO / "artifacts" / "product" / "voice_system_gate.json"

# Fixture contract for the historical Spotify clip below. Production obtains
# this same closed value from the authenticated hello catalog; the gate keeps
# the dependency explicit instead of relying on a product phrase inventory.
_HISTORICAL_CLIP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "streaming.play",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["spotify"],
                    }
                },
                "additionalProperties": False,
            },
        },
    }
]

EXPECTED_DISTRIBUTIONS = {
    "sherpa-onnx": ("1.13.4", "Apache-2.0"),
    "livekit-wakeword": ("0.2.1", "Apache-2.0"),
    "silero-vad": ("6.2.1", "MIT"),
    "sounddevice": ("0.5.5", "MIT"),
    "pywin32": ("311", "PSF"),
    "PyAudioWPatch": ("0.2.12.8", "Apache-2.0"),
    "pycaw": ("20251023", "MIT"),
}


def _apply_registered_stt_directory() -> None:
    if os.environ.get("BAXY_MIND_STT_DIR"):
        return
    local_data = os.environ.get("LOCALAPPDATA")
    if not local_data:
        return
    manifest = Path(local_data) / "BAXYRuntime" / "mind-runtime-v1.json"
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
        stt_dir = Path(str(value.get("stt_dir") or ""))
    except (OSError, TypeError, ValueError):
        return
    required = (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    )
    if value.get("schema") == "baxy-mind-runtime-v1" and all(
        (stt_dir / name).is_file() for name in required
    ):
        os.environ["BAXY_MIND_STT_DIR"] = str(stt_dir.resolve())


def _distribution_gate() -> tuple[bool, list[dict[str, str]]]:
    rows = []
    passed = True
    for name, (expected, license_name) in EXPECTED_DISTRIBUTIONS.items():
        try:
            actual = importlib.metadata.version(name)
            ok = actual == expected
        except importlib.metadata.PackageNotFoundError:
            actual = "missing"
            ok = False
        rows.append(
            {
                "distribution": name,
                "expected": expected,
                "actual": actual,
                "license": license_name,
                "ok": ok,
            }
        )
        passed = passed and ok
    return passed, rows


def _forbidden_product_imports() -> list[str]:
    findings = []
    pattern = re.compile(
        r"^\s*(?:from\s+(?:piper|openwakeword)\b|import\s+(?:piper|openwakeword)\b)",
        re.MULTILINE,
    )
    for source in (REPO / "src" / "baxy_mind").glob("*.py"):
        text = source.read_text(encoding="utf-8").casefold()
        if pattern.search(text):
            findings.append(source.name)
    return findings


def _aec_gate() -> dict[str, float | bool]:
    rng = np.random.default_rng(20260716)
    reference = rng.normal(0, 900, 16_000).astype(np.int16)
    microphone = np.zeros_like(reference)
    microphone[96:] = (reference[:-96].astype(np.float64) * 0.58).astype(np.int16)
    padded_size = math.ceil(microphone.size / FRAME_SAMPLES) * FRAME_SAMPLES
    mic = np.pad(microphone, (0, padded_size - microphone.size))
    ref = np.pad(reference, (REFERENCE_SAMPLES - FRAME_SAMPLES, padded_size - reference.size))
    frames = []
    canceller = EchoCanceller()
    try:
        for offset in range(0, padded_size, FRAME_SAMPLES):
            clean_frame, _, _ = canceller.process(
                mic[offset : offset + FRAME_SAMPLES].astype(np.float32) / 32768.0,
                ref[offset : offset + REFERENCE_SAMPLES],
            )
            frames.append(clean_frame)
    finally:
        canceller.close()
    clean = np.concatenate(frames)[: microphone.size]
    start = 8_000
    before = float(np.sqrt(np.mean(microphone[start:].astype(np.float64) ** 2)))
    after = float(np.sqrt(np.mean((clean[start:] * 32_768.0) ** 2)))
    erle = 20.0 * math.log10(max(before, 1e-9) / max(after, 1e-9))
    return {
        "erle_db": round(erle, 2),
        "passed": erle >= 6.0,
    }


def _lexical_fallback_gate() -> dict[str, object]:
    """Test only prefix cleanup, never claim it is acoustic detection."""

    matcher = WakePhraseMatcher()
    cases = [
        ("Baxy, abre Spotify", True, "abre Spotify"),
        ("oye baxi dime la hora", True, "dime la hora"),
        ("mañana abre Baxy", False, "mañana abre Baxy"),
        ("bastante ruido", False, "bastante ruido"),
    ]
    results = []
    for text, expected_match, expected_command in cases:
        matched, command = matcher.strip(text)
        results.append(
            {
                "matched": matched,
                "expected_match": expected_match,
                "command_ok": command == expected_command,
            }
        )
    return {
        "role": "explicit compatibility fallback / post-KWS prefix cleanup",
        "cases": results,
        "passed": all(
            row["matched"] == row["expected_match"] and row["command_ok"]
            for row in results
        ),
    }


def _ducking_gate() -> dict[str, object]:
    ducker = None
    before = during = after = None
    try:
        from pycaw.pycaw import AudioUtilities

        with _com_apartment():
            before = float(
                AudioUtilities.GetSpeakers().EndpointVolume.GetMasterVolumeLevelScalar()
            )
        ducker = AudioDucker(target=max(0.0, before - 0.05))
        ducked = ducker.duck()
        with _com_apartment():
            during = float(
                AudioUtilities.GetSpeakers().EndpointVolume.GetMasterVolumeLevelScalar()
            )
        restored = ducker.restore()
        with _com_apartment():
            after = float(
                AudioUtilities.GetSpeakers().EndpointVolume.GetMasterVolumeLevelScalar()
            )
        passed = (
            ducked
            and restored
            and during <= before
            and abs(after - before) < 1e-6
        )
        return {
            "ducked": ducked,
            "restored": restored,
            "level_reduced": during <= before,
            "exact_restore": abs(after - before) < 1e-6,
            "passed": passed,
        }
    except Exception as error:  # noqa: BLE001 - gate reporta degradación
        if ducker is not None:
            ducker.restore()
        return {
            "ducked": False,
            "restored": False,
            "level_reduced": False,
            "exact_restore": before is not None and after == before,
            "error": type(error).__name__,
            "passed": False,
        }


def _hardware_gate() -> dict[str, object]:
    events: list[dict] = []
    transcripts_observed = 0

    def transcript(_text: str) -> None:
        nonlocal transcripts_observed
        transcripts_observed += 1

    engine = VoiceEngine(
        transcript,
        events.append,
        correction_terms=catalog_correction_terms(_HISTORICAL_CLIP_TOOLS),
    )
    started = time.perf_counter()
    # Hardware/STT gate exercises the direct path. A true wake gate requires a
    # separately calibrated BAXY ONNX model and must not fall back to ASR.
    engine.start("direct")
    load_seconds = time.perf_counter() - started
    time.sleep(2.0)
    status = engine.status()
    historical = _historical_user_clip_gate(engine)
    engine.shutdown()
    ready = any(event.get("event") == "ready" for event in events)
    return {
        "load_seconds": round(load_seconds, 3),
        "ready_event": ready,
        "input_opened": bool(status.get("inputDevice")),
        "loopback_active": status.get("loopbackActive") is True,
        "wake_backend": status.get("wakeBackend"),
        "wake_word_model": status.get("wakeWordModel"),
        "transcript_events_count_only": transcripts_observed,
        "last_error": status.get("lastError"),
        "historical_user_clip": historical,
        "passed": (
            ready
            and bool(status.get("inputDevice"))
            and status.get("loopbackActive") is True
            and status.get("lastError") is None
            and historical["passed"] is True
        ),
    }


def _historical_user_clip_gate(engine: VoiceEngine) -> dict[str, bool]:
    """Reusa una locución física preservada sin publicar su transcript."""

    path = REPO / "legacy" / "Experimentando" / "test_open_spotify.wav"
    if not path.is_file() or engine._recognizer is None:  # noqa: SLF001
        return {"available": False, "stt_nonempty": False, "entity_recovered": False, "passed": False}
    with wave.open(str(path), "rb") as source:
        source_rate = source.getframerate()
        channels = source.getnchannels()
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
    normalized = audio.astype(np.float32) / 32768.0
    if source_rate != SAMPLE_RATE:
        from scipy.signal import resample_poly

        normalized = resample_poly(normalized, SAMPLE_RATE, source_rate).astype(np.float32)
    stream = engine._recognizer.create_stream()  # noqa: SLF001
    stream.accept_waveform(SAMPLE_RATE, normalized)
    engine._recognizer.decode_stream(stream)  # noqa: SLF001
    raw = (stream.result.text or "").strip()
    corrected = engine._corrector.correct(raw) if engine._corrector is not None else raw  # noqa: SLF001
    recovered = "spotify" in corrected.casefold()
    return {
        "available": True,
        "stt_nonempty": bool(raw),
        "entity_recovered": recovered,
        "passed": bool(raw) and recovered,
    }


def _tts_gate(physical_output: bool) -> dict[str, object]:
    states: list[bool] = []
    output = SapiSpeechOutput(states.append)
    available = output.start()
    accepted = False
    observed_speaking = False
    cancelled = False
    if physical_output and available:
        accepted = output.speak("Hola. Soy BAXY y mi voz local está funcionando.")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not output.speaking:
            time.sleep(0.02)
        observed_speaking = output.speaking
        output.cancel()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and output.speaking:
            time.sleep(0.02)
        cancelled = not output.speaking
    stopped = output.stop()
    passed = available and stopped and (
        not physical_output or accepted and observed_speaking and cancelled
    )
    return {
        "physical_output": physical_output,
        "available": available,
        "accepted": accepted,
        "observed_speaking": observed_speaking,
        "cancelled": cancelled,
        "state_transitions": states,
        "stopped": stopped,
        "last_error": output.last_error,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument(
        "--streaming-preview",
        action="store_true",
        help="also load and validate the optional Nemotron ASR partial path",
    )
    args = parser.parse_args()
    if args.streaming_preview:
        os.environ["BAXY_VOICE_STREAMING_STT"] = "on"
    _apply_registered_stt_directory()

    versions_ok, distributions = _distribution_gate()
    forbidden = _forbidden_product_imports()
    probe = VoiceEngine.probe()
    lexical_fallback = _lexical_fallback_gate()
    aec = _aec_gate()
    ducking = _ducking_gate()
    hardware = _hardware_gate()
    tts = _tts_gate(args.physical_output)
    passed = all(
        (
            versions_ok,
            not forbidden,
            probe.get("available") is True,
            probe.get("wakeWord") is True,
            probe.get("wakeBackend") == "acoustic",
            not args.streaming_preview or probe.get("streamingStt") is True,
            lexical_fallback["passed"] is True,
            aec["passed"] is True,
            ducking["passed"] is True,
            hardware["passed"] is True,
            hardware.get("wake_backend") == "acoustic",
            tts["passed"] is True,
        )
    )
    report = {
        "schema": "baxy-voice-system-gate-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "architecture": {
            "wake": "Hyperspotter cascade + 2 s pre-roll; no ASR activation",
            "stt": "Parakeet TDT 0.6B v3 int8 final on capture-cleaned audio; Nemotron 3.5 Streaming only partial after an authorized turn",
            "streaming_preview_requested": args.streaming_preview,
            "vad": "Silero VAD 6.2.1 ONNX/CPU",
            "tts": "Windows SAPI installed voice",
            "aec": "SpeexDSP streaming capture AEC + residual echo suppression",
            "barge_in": "VAD onset + loopback echo correlation + SAPI purge",
        },
        "probe": probe,
        "distributions": distributions,
        "forbidden_product_imports": forbidden,
        "wake": {
            "backend": probe.get("wakeBackend"),
            "model": probe.get("wakeWordModel"),
            "phrase": probe.get("wakeWordPhrase"),
            "error": probe.get("wakeWordError"),
            "calibrated_model_required": True,
            "lexical_fallback": lexical_fallback,
        },
        "aec": aec,
        "ducking": ducking,
        "hardware": hardware,
        "tts": tts,
        "requires_user_voice": [
            "custom acoustic Baxy model evaluated for recall, false-reject rate and false activations in the user's room",
            "acoustic human barge-in over loudspeaker playback",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
