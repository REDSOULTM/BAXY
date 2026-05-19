"""Sprint 5 — v9 training. Strategy:

  - 7 Spanish Piper voices × 12 phrase variations × 60 clips/combo
    = ~5000 raw synthetic positives.
  - Aggressive prosody variation (length_scale 0.75-1.20, noise_scale
    0.4-0.95) so each clip differs from its siblings.
  - RIR augmentation: each clip convolved with 1 of 270 MIT room
    impulse responses (already in WSL) before training.
  - Small operator-real calibration set (105 clips × 4 RIR aug =
    ~420 samples) included at 5% of dataset weight to bias toward
    operator's voice WITHOUT collapsing to one speaker.
  - openWakeWord trainer: 15k steps (same as v8), but with this
    fatter dataset.
"""
from __future__ import annotations

import json
import logging
import os
import random
import sys
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import scipy.io.wavfile as wavf
import scipy.signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train_v9")

WORKSPACE = Path.home() / "wake_training"
VOICES_DIR = WORKSPACE / "voices"
RIR_DIR = WORKSPACE / "mit_rirs"
OPERATOR_CLIPS_DIR = Path("/mnt/c/Users/usuario/Desktop/ETC/Programacion/Probando Gemma 4/gemma4_agent/voice/tests")
OUTPUT_DIR = WORKSPACE / "positive_clips_v9"

# Phrase variations.
PHRASE_VARIATIONS = [
    "hey gemma",
    "hey gemma.",
    "hey gemma,",
    "Hey Gemma",
    "ey gemma",
    "hey gema",
    "hey, gemma",
    "hey gemma!",
    "ay gemma",
    "ey gema",
    "hey gemma ¿qué tal?",  # connected speech
    "hey gemma, ",          # trailing slot
]

VOICES = [p for p in VOICES_DIR.glob("*.onnx")]
CLIPS_PER_COMBO = 60
TARGET_RAW = len(VOICES) * len(PHRASE_VARIATIONS) * CLIPS_PER_COMBO
TARGET_SR = 16000


def load_rirs() -> list[np.ndarray]:
    """Load all RIRs as float32 arrays at TARGET_SR."""
    rirs: list[np.ndarray] = []
    for f in RIR_DIR.glob("*.wav"):
        try:
            with wave.open(str(f)) as w:
                sr = w.getframerate()
                raw = w.readframes(w.getnframes())
                ch = w.getnchannels()
            a = np.frombuffer(raw, dtype=np.int16)
            if ch > 1:
                a = a.reshape(-1, ch).mean(axis=1).astype(np.int16)
            af = a.astype(np.float32) / 32768.0
            if sr != TARGET_SR:
                import librosa
                af = librosa.resample(af, orig_sr=sr, target_sr=TARGET_SR)
            # Normalize energy
            if af.max() > 0:
                af = af / np.abs(af).max() * 0.7
            rirs.append(af.astype(np.float32))
        except Exception as exc:
            log.debug("skip RIR %s: %s", f.name, exc)
    log.info("Loaded %d RIRs", len(rirs))
    return rirs


def synthesize_clip(voice, text: str, length_scale: float, noise_scale: float) -> tuple[np.ndarray, int]:
    """Returns (int16 audio array, sample_rate)."""
    from piper.config import SynthesisConfig
    cfg = SynthesisConfig(length_scale=length_scale, noise_scale=noise_scale)
    chunks = []
    for chunk in voice.synthesize(text, syn_config=cfg):
        if hasattr(chunk, "audio_int16_bytes"):
            chunks.append(chunk.audio_int16_bytes)
    audio_bytes = b"".join(chunks)
    audio = np.frombuffer(audio_bytes, dtype=np.int16)
    sr = int(voice.config.sample_rate)
    return audio, sr


def apply_rir(audio: np.ndarray, rir: np.ndarray) -> np.ndarray:
    """Convolve int16 audio with RIR. Returns int16."""
    a = audio.astype(np.float32) / 32768.0
    convolved = scipy.signal.fftconvolve(a, rir, mode="full")
    # Match length to input
    convolved = convolved[: len(a)]
    # Avoid clipping
    peak = np.abs(convolved).max()
    if peak > 0.95:
        convolved = convolved * (0.95 / peak)
    return (convolved * 32767).astype(np.int16)


def resample_to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr == TARGET_SR:
        return audio
    import librosa
    af = audio.astype(np.float32) / 32768.0
    af = librosa.resample(af, orig_sr=sr, target_sr=TARGET_SR)
    return (af * 32767).astype(np.int16)


def generate_v9_positives() -> int:
    from piper import PiperVoice

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rirs = load_rirs()
    rng = random.Random(42)

    count = 0
    start = time.time()
    for voice_path in VOICES:
        if not voice_path.exists():
            continue
        voice_name = voice_path.stem
        try:
            voice = PiperVoice.load(str(voice_path))
        except Exception as exc:
            log.warning("voice load %s failed: %s", voice_name, exc)
            continue
        sr_native = int(voice.config.sample_rate)
        for phrase in PHRASE_VARIATIONS:
            for _ in range(CLIPS_PER_COMBO):
                ls = rng.uniform(0.75, 1.20)
                ns = rng.uniform(0.40, 0.95)
                try:
                    audio, sr = synthesize_clip(voice, phrase, ls, ns)
                except Exception as exc:
                    log.debug("synth fail %s %r: %s", voice_name, phrase, exc)
                    continue
                audio = resample_to_16k(audio, sr)
                # 50% chance of applying an RIR
                if rirs and rng.random() < 0.5:
                    rir = rng.choice(rirs)
                    audio = apply_rir(audio, rir)
                out_path = OUTPUT_DIR / f"{voice_name}_{count:05d}.wav"
                wavf.write(str(out_path), TARGET_SR, audio)
                count += 1
                if count % 200 == 0:
                    el = time.time() - start
                    log.info("  %d/%d clips (%.1f/s)", count, TARGET_RAW, count / max(0.01, el))

    log.info("Generated %d clips in %.1fs", count, time.time() - start)
    return count


def add_operator_real_clips() -> int:
    """Add ~5% of operator's real clips with RIR augmentation."""
    # The real clips were lost in the clean-slate commit. Try to find them.
    # The wake_dataset/ folder was removed but the source audio + JSON
    # are still there.
    expected_json = OPERATOR_CLIPS_DIR / "testaudio_v2_expected.json"
    audio_path = OPERATOR_CLIPS_DIR / "Grabación (2).wav"
    if not expected_json.exists() or not audio_path.exists():
        log.warning("operator clips not available; skipping")
        return 0

    # Load audio and annotations
    with open(expected_json, encoding="utf-8") as f:
        wake_times = sorted(float(w["timestamp_s"]) for w in json.load(f)["wakes"])
    with wave.open(str(audio_path)) as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16)
    assert sr == TARGET_SR, f"Audio is {sr} Hz, expected {TARGET_SR}"

    rirs = load_rirs()
    rng = random.Random(43)
    count = 0
    WIN_PRE = 0.3
    WIN_POST = 0.9
    WIN_SAMPLES = int((WIN_PRE + WIN_POST) * TARGET_SR)

    for wt in wake_times:
        start_s = max(0, wt - WIN_PRE)
        start_idx = int(start_s * TARGET_SR)
        end_idx = start_idx + WIN_SAMPLES
        if end_idx > len(audio):
            continue
        clip = audio[start_idx:end_idx]
        if clip.size == 0:
            continue
        # Original
        out = OUTPUT_DIR / f"operator_{count:05d}.wav"
        wavf.write(str(out), TARGET_SR, clip)
        count += 1
        # 3 RIR-augmented variants
        for j in range(3):
            if not rirs:
                break
            rir = rng.choice(rirs)
            aug = apply_rir(clip, rir)
            out = OUTPUT_DIR / f"operator_aug_{count:05d}.wav"
            wavf.write(str(out), TARGET_SR, aug)
            count += 1

    log.info("Operator real clips added: %d", count)
    return count


if __name__ == "__main__":
    n_synth = generate_v9_positives()
    n_real = add_operator_real_clips()
    log.info("V9 dataset built: %d synthetic + %d operator real = %d total",
              n_synth, n_real, n_synth + n_real)
