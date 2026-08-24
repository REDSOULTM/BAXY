"""Drive the shipped voice engine the same way the App does: start/speak/cancel.

Feeds a real «BAXY» WAV then a request WAV through ``ingest_pcm``.
"""

from __future__ import annotations

import json
import os
import sys
import time
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

SCRATCH = Path(
    os.environ.get(
        "BAXY_GOAL09_SCRATCH",
        r"C:\Users\usuario\AppData\Local\Temp\grok-goal-4eda3fa08868\implementer",
    )
)
os.environ.setdefault(
    "BAXY_VOICE_WAKE_MANIFEST",
    str(
        Path(os.environ["LOCALAPPDATA"])
        / "BAXYRuntime"
        / "assets"
        / "wake"
        / "baxy-wakeword-v1.json"
    ),
)
os.environ.setdefault("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED", "1")
os.environ.setdefault(
    "BAXY_MIND_STT_DIR",
    str(Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"),
)

import numpy as np

from baxy_mind.voice import SAMPLE_RATE, VoiceEngine
from baxy_mind.wakeword import WINDOW_SAMPLES


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
        rate = handle.getframerate()
        channels = handle.getnchannels()
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1).astype(np.int16)
    audio = pcm.astype(np.float32) / 32768.0
    if rate != SAMPLE_RATE:
        target = max(1, int(audio.size * SAMPLE_RATE / rate))
        audio = np.interp(
            np.linspace(0, audio.size - 1, target), np.arange(audio.size), audio
        ).astype(np.float32)
    return audio


def _speak(phrase: str, dest: Path, prefer: str) -> np.ndarray:
    import pythoncom
    import win32com.client

    dest.parent.mkdir(parents=True, exist_ok=True)
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


def _ingest_paced(engine: VoiceEngine, audio: np.ndarray) -> None:
    """Feed PCM in hop-sized chunks so the KWS queue is not reset by a dump."""

    hop = 4_000
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    for offset in range(0, samples.size, hop):
        engine.ingest_pcm(samples[offset : offset + hop])
        time.sleep(0.05)


def _wait_wake(events: list[dict], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(event.get("event") == "wake_detected" for event in events):
            return True
        time.sleep(0.05)
    return any(event.get("event") == "wake_detected" for event in events)


def one_run(index: int, baxy: np.ndarray, request: np.ndarray) -> dict:
    events: list[dict] = []
    transcripts: list[str] = []
    log: list[str] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine.use_pcm_source()
    started = engine.start("wake")
    log.append(f"run={index} start={started} error={engine.last_error}")
    # First ONNX hop is slow; a 2 s dump here resets the KWS window.
    engine.ingest_pcm(np.zeros(4_000, dtype=np.float32))
    time.sleep(0.8)
    _ingest_paced(
        engine,
        (np.random.default_rng(index).standard_normal(SAMPLE_RATE * 2) * 0.01).astype(
            np.float32
        ),
    )
    time.sleep(0.3)
    noise_wake = any(event.get("event") == "wake_detected" for event in events)
    log.append(f"run={index} noise_wake={noise_wake}")
    _ingest_paced(engine, baxy)
    woke = _wait_wake(events, 4.0)
    if not woke:
        log.append(f"run={index} retry_baxy events={[e.get('event') for e in events]}")
        _ingest_paced(engine, baxy)
        woke = _wait_wake(events, 4.0)
    log.append(f"run={index} wake_detected={woke} events={[e.get('event') for e in events]}")
    # Close the name-only utterance so the request is the armed follow-up.
    engine.ingest_pcm(np.zeros(int(SAMPLE_RATE * 1.2), dtype=np.float32))
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if any(event.get("event") == "wake" for event in events) or engine.speaking:
            break
        time.sleep(0.05)
    engine.cancel_speech()
    before = len(transcripts)
    _ingest_paced(engine, request)
    eou = time.perf_counter()
    engine.ingest_pcm(np.zeros(int(SAMPLE_RATE * 1.2), dtype=np.float32))
    deadline = time.monotonic() + 5.0
    first_signal_s = None
    while time.monotonic() < deadline:
        command = transcripts[before:]
        if any("notepad" in text.casefold() for text in command):
            first_signal_s = time.perf_counter() - eou
            break
        time.sleep(0.02)
    spoke = engine.speak("Listo, te escucho.")
    deadline = time.monotonic() + 4.0
    while not engine.speaking and time.monotonic() < deadline:
        time.sleep(0.02)
    time.sleep(0.2)
    engine.cancel_speech()
    deadline = time.monotonic() + 2.0
    while engine.speaking and time.monotonic() < deadline:
        time.sleep(0.02)
    cancelled = not engine.speaking
    engine.stop()
    engine.shutdown()
    log.append(
        f"run={index} transcript={transcripts!r} first_signal_s={first_signal_s} "
        f"spoke={spoke} cancelled={cancelled}"
    )
    return {
        "run": index,
        "started": started,
        "noise_did_not_wake": not noise_wake,
        "wake_detected": woke,
        "transcripts": transcripts,
        "first_signal_s": first_signal_s,
        "spoke": spoke,
        "cancelled_mid_utterance": cancelled,
        "log": log,
        "last_error": engine.last_error,
    }


def main() -> int:
    scratch = SCRATCH
    scratch.mkdir(parents=True, exist_ok=True)
    baxy = _speak("Baxy", scratch / "launch_baxy.wav", "sabina")
    if baxy.size < WINDOW_SAMPLES:
        baxy = np.pad(baxy, (0, WINDOW_SAMPLES - baxy.size))
    request = _speak("open notepad please", scratch / "launch_request.wav", "zira")
    runs = [one_run(1, baxy, request), one_run(2, baxy, request)]
    lines: list[str] = []
    ok = True
    for run in runs:
        lines.extend(run["log"])
        if not (
            run["started"]
            and run["noise_did_not_wake"]
            and run["wake_detected"]
            and any("notepad" in text.casefold() for text in run["transcripts"])
            and run["spoke"]
            and run["cancelled_mid_utterance"]
        ):
            ok = False
    payload = {"ok": ok, "runs": runs}
    (scratch / "voice_launch.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    log_text = "\n".join(lines) + "\n" + json.dumps(payload, indent=2) + "\n"
    (scratch / "voice_launch.log").write_text(log_text, encoding="utf-8")
    print(log_text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
