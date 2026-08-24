"""Measure inherited wake, Parakeet STT and neural TTS on this machine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from baxy_mind.voice import SAMPLE_RATE, VoiceEngine, _transcript_is_doubtful  # noqa: E402
from baxy_mind.voice_output import (  # noqa: E402
    NeuralSpeechOutput,
    resolve_neural_tts_model,
)
from baxy_mind.wakeword import (  # noqa: E402
    WINDOW_SAMPLES,
    AcousticWakeDetector,
    load_wakeword_config,
)
from scripts.evaluate_wake_corpus import (  # noqa: E402
    one_sided_poisson_upper_rate_per_hour,
)

WAKE_SOURCE = Path(
    r"C:\Users\usuario\Desktop\ETC\Programacion\BAXY\legacy\models\artifacts"
    r"\wake_livekit\baxy.onnx"
)
STT_DIR = Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
SCRATCH_DEFAULT = Path(
    os.environ.get(
        "BAXY_GOAL09_SCRATCH",
        r"C:\Users\usuario\AppData\Local\Temp\grok-goal-4eda3fa08868\implementer",
    )
)
THRESHOLD = 0.5  # goal 01 operating point; not retuned after opening holdout
HOP = 4000
DEBOUNCE = 2.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def install_wake_assets(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    model = destination / "baxy.onnx"
    if not model.is_file():
        shutil.copy2(WAKE_SOURCE, model)
    digest = _sha256(model)
    os.environ["BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"] = "1"
    manifest = destination / "baxy-wakeword-v1.json"
    payload = {
        "schema": "baxy-wakeword-v1",
        "model": "baxy.onnx",
        "modelName": "baxy",
        "phrase": "Baxy",
        "sampleRate": SAMPLE_RATE,
        "windowSamples": WINDOW_SAMPLES,
        "hopSamples": HOP,
        "threshold": THRESHOLD,
        "debounceSeconds": DEBOUNCE,
        "sha256": digest,
        "calibration": {"approved": False},
    }
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.environ["BAXY_VOICE_WAKE_MANIFEST"] = str(manifest)
    return manifest


def _resample(audio: np.ndarray, source_rate: int) -> np.ndarray:
    if source_rate == SAMPLE_RATE or audio.size == 0:
        return audio.astype(np.float32)
    target = max(1, int(audio.size * SAMPLE_RATE / source_rate))
    return np.interp(
        np.linspace(0, audio.size - 1, target),
        np.arange(audio.size),
        audio,
    ).astype(np.float32)


def _sapi_write(text: str, path: Path, token, rate: int) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(path), 3)
        voice.Voice = token
        voice.Rate = rate
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()
    finally:
        pythoncom.CoUninitialize()


def synthesize_holdout(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    tokens = list(voice.GetVoices())
    pythoncom.CoUninitialize()
    positives: list[Path] = []
    other: list[Path] = []
    positive_phrases = (
        "Baxy",
        "Baxy.",
        "Baxy, abre Spotify.",
        "Baxy open notepad.",
        "Okay Baxy",
        "Baxy, súbele al volumen.",
        "Hey Baxy",
        "Baxy what's the time?",
        "Baxy silencia",
        "Baxy mute",
        "Baxy, dime la hora",
        "Baxy please",
        "Baxy, para",
        "Baxy Baxy",
        "Escucha Baxy",
        "It's Baxy",
    )
    other_phrases = (
        "Abre Spotify.",
        "Open notepad please.",
        "Vas y me avisas.",
        "Maxi abre Steam.",
        "The movie is starting.",
        "Buenas noches.",
        "Play the next song.",
        "Que hora es?",
    )
    rates = (-6, -3, 0, 3, 6)
    folder = output_dir / "positive"
    folder.mkdir(parents=True, exist_ok=True)
    index = 0
    for token in tokens:
        for rate in rates:
            for phrase in positive_phrases:
                path = folder / f"{index:03d}.wav"
                _sapi_write(phrase, path, token, rate)
                positives.append(path)
                index += 1
    folder = output_dir / "other"
    folder.mkdir(parents=True, exist_ok=True)
    index = 0
    for token in tokens:
        for phrase in other_phrases:
            path = folder / f"{index:03d}.wav"
            _sapi_write(phrase, path, token, 0)
            other.append(path)
            index += 1
    from baxy_mind.voice_output import _PiperOnnxEngine

    model_path = resolve_neural_tts_model()
    if model_path is not None:
        engine = _PiperOnnxEngine(model_path)
        for phrase in ("Baxy", "Baxy, abre Spotify."):
            samples = _resample(engine.generate(phrase), engine.sample_rate)
            path = (output_dir / "positive") / f"piper_{phrase[:8].strip()}.wav"
            _write_wav(path, samples)
            positives.append(path)
    return {
        "positive": positives,
        "other": other,
        "voices": len(tokens),
        "count": len(positives),
    }


def score_wake(manifest: Path, clips: list[Path]) -> dict[str, object]:
    config = load_wakeword_config(manifest)
    detector = AcousticWakeDetector(config)
    matched = 0
    scores: list[float] = []
    latencies: list[float] = []
    for path in clips:
        with wave.open(str(path), "rb") as handle:
            pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
        audio = pcm.astype(np.float32) / 32768.0
        if audio.size < WINDOW_SAMPLES:
            audio = np.pad(audio, (0, WINDOW_SAMPLES - audio.size))
        detector.reset()
        hit = None
        started = time.perf_counter()
        for offset in range(0, audio.size, 512):
            found = detector.accept(
                audio[offset : offset + 512],
                now=offset / SAMPLE_RATE,
            )
            if found is not None and hit is None:
                hit = found
        latencies.append(time.perf_counter() - started)
        if detector.last_score is not None:
            scores.append(detector.last_score)
        if hit is not None:
            matched += 1
    return {
        "files": len(clips),
        "matched": matched,
        "max_score": max(scores) if scores else None,
        "min_score": min(scores) if scores else None,
        "p50_wall_s": sorted(latencies)[len(latencies) // 2] if latencies else None,
    }


def score_far_media(
    manifest: Path,
    media: list[Path],
    max_hours: float,
    checkpoint: Path | None = None,
) -> dict[str, object]:
    config = load_wakeword_config(manifest)
    detector = AcousticWakeDetector(config)
    activations = 0
    seconds = 0.0
    budget = max_hours * 3600.0
    last_checkpoint_hours = 0.0
    last_checkpoint_wall = time.monotonic()
    used: list[str] = []

    def snapshot() -> dict[str, object]:
        hours = seconds / 3600.0
        upper = one_sided_poisson_upper_rate_per_hour(activations, seconds, 0.95)
        return {
            "seconds": round(seconds, 3),
            "hours": round(hours, 4),
            "activations": activations,
            "far_per_hour": None if seconds <= 0 else activations * 3600.0 / seconds,
            "far_upper_per_hour": upper,
            "threshold": THRESHOLD,
            "threshold_locked_before_open": True,
            "files_used": len(used),
            "last_file": used[-1] if used else None,
        }

    def maybe_checkpoint() -> None:
        nonlocal last_checkpoint_hours, last_checkpoint_wall
        hours = seconds / 3600.0
        now = time.monotonic()
        if checkpoint is None:
            return
        if hours - last_checkpoint_hours < 0.1 and now - last_checkpoint_wall < 30.0:
            return
        last_checkpoint_hours = hours
        last_checkpoint_wall = now
        checkpoint.write_text(
            json.dumps(
                {
                    "measured_at": datetime.now(timezone.utc).isoformat(),
                    "partial": True,
                    "far": snapshot(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    for path in media:
        if seconds >= budget:
            break
        used.append(str(path))
        command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0?",
            "-vn",
            "-sn",
            "-dn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            "-t",
            str(max(1, int(budget - seconds))),
            "pipe:1",
        ]
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        assert process.stdout is not None
        leftover = b""
        frame_bytes = 512 * 2
        try:
            while seconds < budget:
                chunk = process.stdout.read(frame_bytes * 32)
                if not chunk:
                    break
                leftover += chunk
                while len(leftover) >= frame_bytes and seconds < budget:
                    frame = leftover[:frame_bytes]
                    leftover = leftover[frame_bytes:]
                    audio = (
                        np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0
                    )
                    hit = detector.accept(audio, now=seconds)
                    seconds += audio.size / SAMPLE_RATE
                    if hit is not None:
                        activations += 1
                    maybe_checkpoint()
        finally:
            process.kill()
            process.wait()
    result = snapshot()
    if checkpoint is not None:
        checkpoint.write_text(
            json.dumps(
                {
                    "measured_at": datetime.now(timezone.utc).isoformat(),
                    "partial": False,
                    "far": result,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return result


def measure_stt(clips: dict[str, list[Path]]) -> dict[str, object]:
    os.environ["BAXY_MIND_STT_DIR"] = str(STT_DIR)
    engine = VoiceEngine(lambda _text: None)
    rows: list[dict[str, object]] = []
    try:
        engine.load()
        expected = {
            "positive": [
                "baxy",
                "abre spotify",
                "open notepad",
                "volumen",
                "time",
            ]
        }
        for kind, paths in clips.items():
            if not isinstance(paths, list):
                continue
            selected = paths[:24] if kind == "other" else paths[:12]
            for path in selected:
                with wave.open(str(path), "rb") as handle:
                    pcm = np.frombuffer(
                        handle.readframes(handle.getnframes()), dtype=np.int16
                    )
                audio = pcm.astype(np.float32) / 32768.0
                started = time.perf_counter()
                text = engine.transcribe_pcm(audio)
                rows.append(
                    {
                        "file": path.name,
                        "kind": kind,
                        "text": text,
                        "doubtful": _transcript_is_doubtful(text) if text else True,
                        "seconds": round(time.perf_counter() - started, 3),
                    }
                )
    finally:
        engine.shutdown()
    return {"rows": rows, "expected_hints": expected}


def measure_tts() -> dict[str, object]:
    output = NeuralSpeechOutput()
    started_load = time.perf_counter()
    ready = output.start(timeout=30.0)
    load_s = time.perf_counter() - started_load
    if not ready:
        return {"available": False, "error": output.last_error}
    started = time.perf_counter()
    accepted = output.speak("Listo, Spotify está abierto y sonando")
    while not output.speaking and time.perf_counter() - started < 5.0:
        time.sleep(0.02)
    first_signal = time.perf_counter() - started
    time.sleep(0.4)
    output.cancel()
    while output.speaking and time.perf_counter() - started < 5.0:
        time.sleep(0.02)
    cancelled = not output.speaking
    output.stop(timeout=3.0)
    identity_model = resolve_neural_tts_model()
    return {
        "available": True,
        "accepted": accepted,
        "load_s": round(load_s, 3),
        "first_audio_s": round(first_signal, 3),
        "cancelled_mid_utterance": cancelled,
        "voice": identity_model.name if identity_model else None,
        "sha256": _sha256(identity_model) if identity_model else None,
    }


def list_media() -> list[Path]:
    roots = [
        Path(r"D:\Movies\Peliculas"),
        Path(r"D:\Movies\Series"),
    ]
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in {".mkv", ".mp4", ".avi", ".m4v", ".webm"}:
                files.append(path)
    files.sort(key=lambda item: item.stat().st_size)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, default=SCRATCH_DEFAULT)
    parser.add_argument("--far-hours", type=float, default=2.0)
    args = parser.parse_args()
    scratch = args.scratch
    scratch.mkdir(parents=True, exist_ok=True)
    wake_dir = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "assets" / "wake"
    manifest = install_wake_assets(wake_dir)
    holdout_dir = scratch / "holdout"
    if (holdout_dir / "positive").is_dir() and list((holdout_dir / "positive").glob("*.wav")):
        clips = {
            "positive": sorted((holdout_dir / "positive").glob("*.wav")),
            "other": sorted((holdout_dir / "other").glob("*.wav"))
            if (holdout_dir / "other").is_dir()
            else [],
        }
    else:
        clips = synthesize_holdout(holdout_dir)
    wake_pos = score_wake(manifest, clips["positive"])
    wake_neg_synth = score_wake(manifest, clips["other"])
    media = list_media()
    far = score_far_media(manifest, media, args.far_hours)
    stt = measure_stt(clips)
    tts = measure_tts()
    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "threshold": THRESHOLD,
        "threshold_source": "goal01_operating_point_0.5",
        "wake_manifest": str(manifest),
        "wake_model_sha256": _sha256(wake_dir / "baxy.onnx"),
        "wake_positive": wake_pos,
        "wake_negative_synth": wake_neg_synth,
        "wake_far": far,
        "stt": stt,
        "tts": tts,
    }
    out = scratch / "goal09_measure.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
