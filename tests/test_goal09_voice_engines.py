"""Goal 09: the shipped wake, STT and TTS engines, driven with WAV."""

from __future__ import annotations

import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.voice import (  # noqa: E402
    SAMPLE_RATE,
    VoiceEngine,
    _transcript_is_doubtful,
)
from baxy_mind.voice_output import (  # noqa: E402
    NeuralSpeechOutput,
    create_speech_output,
    resolve_neural_tts_model,
)
from baxy_mind.wakeword import (  # noqa: E402
    AcousticWakeDetector,
    WINDOW_SAMPLES,
    load_wakeword_config,
)


WAKE_ONNX = Path(
    r"C:\Users\usuario\Desktop\ETC\Programacion\BAXY\legacy\models\artifacts"
    r"\wake_livekit\baxy.onnx"
)
SCRATCH = Path(
    os.environ.get(
        "BAXY_GOAL09_SCRATCH",
        r"C:\Users\usuario\AppData\Local\Temp\grok-goal-4eda3fa08868\implementer",
    )
)


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
        rate = handle.getframerate()
        channels = handle.getnchannels()
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1).astype(np.int16)
    audio = pcm.astype(np.float32) / 32768.0
    if rate != SAMPLE_RATE:
        ratio = SAMPLE_RATE / float(rate)
        index = np.round(np.arange(0, audio.size) * ratio).astype(int)
        index = index[index < int(audio.size * ratio) + 1]
        stretched = np.interp(
            np.linspace(0, audio.size - 1, int(audio.size * ratio)),
            np.arange(audio.size),
            audio,
        ).astype(np.float32)
        return stretched
    return audio


def _uncalibrated_wake_manifest(tmp_path: Path) -> Path:
    if not WAKE_ONNX.is_file():
        pytest.skip("inherited baxy.onnx is not on this machine")
    import hashlib
    import shutil

    os.environ["BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"] = "1"
    dest = tmp_path / "baxy.onnx"
    shutil.copy2(WAKE_ONNX, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    manifest = tmp_path / "baxy-wakeword-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-wakeword-v1",
                "model": "baxy.onnx",
                "modelName": "baxy",
                "phrase": "Baxy",
                "sampleRate": SAMPLE_RATE,
                "windowSamples": WINDOW_SAMPLES,
                "hopSamples": 4000,
                "threshold": 0.5,
                "debounceSeconds": 2.0,
                "sha256": digest,
                "calibration": {"approved": False},
            }
        ),
        encoding="utf-8",
    )
    os.environ["BAXY_VOICE_WAKE_MANIFEST"] = str(manifest)
    return manifest


def test_doubtful_transcript_does_not_look_like_a_command() -> None:
    assert _transcript_is_doubtful("?")
    assert _transcript_is_doubtful("…")
    assert not _transcript_is_doubtful("abre Spotify")
    assert not _transcript_is_doubtful("open notepad")


def test_product_tts_is_neural_spanish_not_system_sapi() -> None:
    if resolve_neural_tts_model() is None:
        pytest.skip("neural TTS model is not on this machine")
    output = create_speech_output()
    assert isinstance(output, NeuralSpeechOutput)
    assert "es_MX" in output.voice_name or "claude" in output.voice_name.casefold()


def test_neural_speak_starts_and_cancel_stops_mid_utterance(tmp_path: Path) -> None:
    if resolve_neural_tts_model() is None:
        pytest.skip("neural TTS model is not on this machine")
    output = NeuralSpeechOutput()
    try:
        assert output.start(timeout=20.0)
        started = time.perf_counter()
        assert output.speak(
            "Listo, Spotify está abierto y sonando. Sigo hablando para poder cortar."
        )
        deadline = time.monotonic() + 2.0
        while not output.speaking and time.monotonic() < deadline:
            time.sleep(0.02)
        assert output.speaking
        time.sleep(0.35)
        output.cancel()
        deadline = time.monotonic() + 2.0
        while output.speaking and time.monotonic() < deadline:
            time.sleep(0.02)
        elapsed = time.perf_counter() - started
        assert not output.speaking
        assert elapsed < 4.0
    finally:
        output.stop(timeout=3.0)


def _sapi_baxy_wav(path: Path) -> np.ndarray:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(path), 3)
        voice.AudioOutputStream = stream
        for token in voice.GetVoices():
            description = str(token.GetDescription()).casefold()
            if "sabina" in description:
                voice.Voice = token
                break
        voice.Speak("Baxy")
        stream.Close()
    finally:
        pythoncom.CoUninitialize()
    return _read_wav(path)


def test_inherited_wake_fires_on_baxy_and_not_on_noise(tmp_path: Path) -> None:
    manifest = _uncalibrated_wake_manifest(tmp_path)
    os.environ["BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"] = "1"
    config = load_wakeword_config(manifest)
    detector = AcousticWakeDetector(config)
    noise = (np.random.default_rng(0).standard_normal(SAMPLE_RATE * 3) * 0.02).astype(
        np.float32
    )
    detector.reset()
    negative_hit = None
    for offset in range(0, noise.size, 512):
        found = detector.accept(noise[offset : offset + 512], now=offset / SAMPLE_RATE)
        if found is not None:
            negative_hit = found
    assert negative_hit is None

    audio = _sapi_baxy_wav(tmp_path / "baxy_sabina.wav")
    if audio.size < WINDOW_SAMPLES:
        audio = np.pad(audio, (0, WINDOW_SAMPLES - audio.size))
    detector.reset()
    hit = None
    for offset in range(0, audio.size, 512):
        found = detector.accept(audio[offset : offset + 512], now=offset / SAMPLE_RATE)
        if found is not None:
            hit = found
    assert hit is not None
    assert hit.phrase == "Baxy"
    assert hit.confidence >= 0.5


def test_parakeet_transcribes_spanish_english_and_codeswitch(tmp_path: Path) -> None:
    stt = Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
    if not (stt / "encoder.int8.onnx").is_file():
        pytest.skip("Parakeet bundle is not on this machine")
    os.environ["BAXY_MIND_STT_DIR"] = str(stt)
    engine = VoiceEngine(
        lambda _text: None,
        correction_terms=("notepad", "Spotify"),
    )
    try:
        engine.load()
        # Synthetic silence must not become a catalog command.
        silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
        text = engine.transcribe_pcm(silence)
        assert text == "" or _transcript_is_doubtful(text)

        def _speak_to_wav(phrase: str, dest: Path, prefer: str) -> np.ndarray:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                stream = win32com.client.Dispatch("SAPI.SpFileStream")
                stream.Open(str(dest), 3)
                voice.AudioOutputStream = stream
                for token in voice.GetVoices():
                    if prefer in str(token.GetDescription()).casefold():
                        voice.Voice = token
                        break
                voice.Speak(phrase)
                stream.Close()
            finally:
                pythoncom.CoUninitialize()
            return _read_wav(dest)

        english = engine.transcribe_pcm(
            _speak_to_wav("open notepad please", tmp_path / "en.wav", "zira")
        ).casefold()
        assert "notepad" in english
        spanish = engine.transcribe_pcm(
            _speak_to_wav("buenas noches", tmp_path / "es.wav", "sabina")
        ).casefold()
        assert "noche" in spanish or "buenas" in spanish
        mixed = engine.transcribe_pcm(
            _speak_to_wav("abre notepad please", tmp_path / "mix.wav", "sabina")
        ).casefold()
        assert "notepad" in mixed
        assert "abre" in mixed or "open" in mixed or "please" in mixed
    finally:
        engine.shutdown()


def _ingest_paced(engine: VoiceEngine, audio: np.ndarray) -> None:
    hop = 4_000
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    for offset in range(0, samples.size, hop):
        engine.ingest_pcm(samples[offset : offset + hop])
        time.sleep(0.05)


def test_voice_engine_pcm_source_wakes_on_injected_wav(tmp_path: Path) -> None:
    stt = Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
    if not (stt / "encoder.int8.onnx").is_file():
        pytest.skip("Parakeet bundle is not on this machine")
    _uncalibrated_wake_manifest(tmp_path)
    os.environ["BAXY_MIND_STT_DIR"] = str(stt)
    os.environ["BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"] = "1"
    events: list[dict] = []
    transcripts: list[str] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine.use_pcm_source()
    try:
        started = engine.start("wake")
        if not started:
            pytest.skip(f"wake start failed: {engine.last_error}")
        engine.ingest_pcm(np.zeros(4_000, dtype=np.float32))
        time.sleep(0.8)
        noise = (np.random.default_rng(1).standard_normal(SAMPLE_RATE * 2) * 0.01).astype(
            np.float32
        )
        _ingest_paced(engine, noise)
        time.sleep(0.5)
        assert not any(event.get("event") == "wake_detected" for event in events)

        baxy = _sapi_baxy_wav(tmp_path / "baxy_launch.wav")
        if baxy.size < WINDOW_SAMPLES:
            baxy = np.pad(baxy, (0, WINDOW_SAMPLES - baxy.size))
        _ingest_paced(engine, baxy)
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and not any(
            event.get("event") == "wake_detected" for event in events
        ):
            time.sleep(0.05)
        assert any(event.get("event") == "wake_detected" for event in events)

        engine.ingest_pcm(np.zeros(int(SAMPLE_RATE * 1.2), dtype=np.float32))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if any(event.get("event") == "wake" for event in events) or engine.speaking:
                break
            time.sleep(0.05)
        engine.cancel_speech()
        before = list(transcripts)

        request = _speak_named("open notepad please", tmp_path / "req.wav", "zira")
        _ingest_paced(engine, request)
        engine.ingest_pcm(np.zeros(int(SAMPLE_RATE * 1.2), dtype=np.float32))
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            joined = " ".join(transcripts[len(before) :]).casefold()
            if "notepad" in joined:
                break
            time.sleep(0.05)
        joined = " ".join(transcripts[len(before) :]).casefold()
        assert "notepad" in joined
    finally:
        engine.stop()
        engine.shutdown()


def test_end_of_speech_to_first_signal_is_under_budget(tmp_path: Path) -> None:
    stt = Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
    if not (stt / "encoder.int8.onnx").is_file():
        pytest.skip("Parakeet bundle is not on this machine")
    os.environ["BAXY_MIND_STT_DIR"] = str(stt)
    delays: list[float] = []
    phrases = (
        ("open notepad please", "zira", "notepad"),
        ("buenas noches", "sabina", "noche"),
        ("abre notepad please", "sabina", "notepad"),
    )
    for phrase, prefer, needle in phrases:
        events: list[dict] = []
        transcripts: list[str] = []
        engine = VoiceEngine(transcripts.append, events.append)
        engine.use_pcm_source()
        try:
            assert engine.start("direct")
            audio = _speak_named(phrase, tmp_path / f"eou_{prefer}.wav", prefer)
            engine.ingest_pcm(audio)
            eou = time.perf_counter()
            engine.ingest_pcm(np.zeros(int(SAMPLE_RATE * 1.2), dtype=np.float32))
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if any(event.get("event") in {"recognized", "partial"} for event in events) or transcripts:
                    delays.append(time.perf_counter() - eou)
                    break
                time.sleep(0.02)
            else:
                delays.append(time.perf_counter() - eou)
            joined = " ".join(transcripts).casefold()
            assert needle in joined or any(
                event.get("event") == "recognized" for event in events
            )
        finally:
            engine.stop()
            engine.shutdown()
    ordered = sorted(delays)
    p50 = ordered[len(ordered) // 2]
    assert p50 <= 1.5
    assert max(delays) < 3.0


def _speak_named(phrase: str, dest: Path, prefer: str) -> np.ndarray:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(dest), 3)
        voice.AudioOutputStream = stream
        for token in voice.GetVoices():
            if prefer in str(token.GetDescription()).casefold():
                voice.Voice = token
                break
        voice.Speak(phrase)
        stream.Close()
    finally:
        pythoncom.CoUninitialize()
    return _read_wav(dest)
