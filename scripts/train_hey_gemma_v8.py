"""Sprint 4 — train hey_gemma.onnx for production.

Per the research report recommendation:
  - Synthetic positive dataset via Piper voices (ES + EN multi-speaker)
  - Negative pool: ACAV100M pre-computed features (17 GB, already in WSL)
  - Augmentation: MIT RIRs + AudioSet background noise (already in WSL)
  - openWakeWord trainer with frozen Google speech-embedding backbone

This is DIFFERENT from the failed v1-v7 attempts:
  v1-v7: 105 operator clips, overfit single voice.
  v8: ~thousands of synthetic clips across MANY voices (4 Spanish Piper
      voices + LibriTTS multi-speaker English). Targets generalization
      not personalization.

Runs in WSL2 Ubuntu via the same venv used in v5 (preserved at
~/wake_training/venv). Output is a .onnx that drops into
gemma4_agent/voice/models/oww/hey_gemma.onnx.

This script is NOT run from Windows — it's the body of a bash command
executed via wsl. Documented here so the same approach can be re-run
in the future from a fresh WSL setup.
"""
# See scripts/train_hey_gemma_v8.sh for the actual entry point.
# This Python module is loaded inside that script via the WSL venv.
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train_v8")

WORKSPACE = Path.home() / "wake_training"
POSITIVES_DIR = WORKSPACE / "positive_clips_v8"
NEGATIVES_FEATURES = WORKSPACE / "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
OUTPUT_DIR = WORKSPACE / "hey_gemma_v8_output"
FINAL_ONNX = OUTPUT_DIR / "hey_gemma.onnx"

# Voices to use for synthetic positive generation. ES first to match
# operator's primary language; English to cover code-switching cases
# where 'hey gemma' is spoken with English pronunciation.
PIPER_VOICES = [
    WORKSPACE / "voices" / "es_AR-daniela-high.onnx",
    WORKSPACE / "voices" / "es_ES-davefx-medium.onnx",
    WORKSPACE / "voices" / "es_ES-carlfm-x_low.onnx",
    WORKSPACE / "voices" / "es_MX-claude-high.onnx",
]

# Phrase variations to bias robustness. The model only learns 'hey gemma'
# as the trigger, but generating variations exposes the head to natural
# prosody differences.
PHRASE_VARIATIONS = [
    "hey gemma",
    "hey gemma.",
    "hey gemma,",
    "Hey Gemma",
    "ey gemma",       # informal Spanish dropping of 'h'
    "hey gema",       # Spanish phonetic spelling variant
    "hey, gemma",
    "hey gemma!",
]

POSITIVES_PER_VOICE_PER_PHRASE = 50  # 4 voices × 8 phrases × 50 = 1600 clips
TARGET_TOTAL_POSITIVES = len(PIPER_VOICES) * len(PHRASE_VARIATIONS) * POSITIVES_PER_VOICE_PER_PHRASE


def generate_positives() -> int:
    """Generate synthetic positive 'hey gemma' clips via Piper.

    Each (voice × phrase variation) combination produces N clips with
    varied length_scale to introduce prosody diversity.
    """
    POSITIVES_DIR.mkdir(parents=True, exist_ok=True)
    from piper import PiperVoice

    count = 0
    rng = np.random.RandomState(42)
    start = time.time()
    for voice_path in PIPER_VOICES:
        if not voice_path.exists():
            log.warning("skip missing voice: %s", voice_path)
            continue
        voice_name = voice_path.stem
        try:
            voice = PiperVoice.load(str(voice_path))
        except Exception as exc:
            log.warning("failed to load %s: %s", voice_name, exc)
            continue
        sr = int(voice.config.sample_rate)
        for phrase in PHRASE_VARIATIONS:
            for i in range(POSITIVES_PER_VOICE_PER_PHRASE):
                # Vary prosody. Piper API varies between versions; we
                # try the most common interface (synthesize -> WAV bytes
                # or numpy). Adapt to whichever is available.
                length_scale = float(rng.uniform(0.85, 1.15))
                noise_scale = float(rng.uniform(0.5, 0.9))
                try:
                    audio_bytes = _synthesize_with_piper(
                        voice, phrase,
                        length_scale=length_scale,
                        noise_scale=noise_scale,
                    )
                except Exception as exc:
                    log.warning("synth failed (%s, %r): %s", voice_name, phrase, exc)
                    continue
                # Convert to int16 if needed.
                if isinstance(audio_bytes, np.ndarray):
                    audio = audio_bytes
                else:
                    audio = np.frombuffer(audio_bytes, dtype=np.int16)
                # Resample to 16 kHz if voice is at 22050 Hz.
                if sr != 16000:
                    import librosa
                    audio_f32 = audio.astype(np.float32) / 32768.0
                    audio_f32 = librosa.resample(
                        audio_f32, orig_sr=sr, target_sr=16000,
                    )
                    audio = (audio_f32 * 32767).astype(np.int16)
                out_path = POSITIVES_DIR / f"{voice_name}_{count:05d}.wav"
                wavf.write(str(out_path), 16000, audio)
                count += 1
                if count % 100 == 0:
                    elapsed = time.time() - start
                    log.info(
                        "  generated %d/%d (%.1f/s)",
                        count, TARGET_TOTAL_POSITIVES,
                        count / max(0.001, elapsed),
                    )
    log.info(
        "Positives: %d clips in %.1fs",
        count, time.time() - start,
    )
    return count


def _synthesize_with_piper(voice, text, length_scale=1.0, noise_scale=0.667):
    """Synthesize via piper-tts 1.x.

    API: voice.synthesize(text, syn_config=SynthesisConfig(...)) yields
    AudioChunk objects with .audio_int16_bytes.

    Returns bytes (PCM int16, voice's native sample rate).
    """
    try:
        from piper.config import SynthesisConfig
    except ImportError:
        SynthesisConfig = None

    chunks: list[bytes] = []
    if SynthesisConfig is not None:
        cfg = SynthesisConfig(
            length_scale=length_scale,
            noise_scale=noise_scale,
        )
        iterator = voice.synthesize(text, syn_config=cfg)
    else:
        iterator = voice.synthesize(text)
    for chunk in iterator:
        if hasattr(chunk, "audio_int16_bytes"):
            chunks.append(chunk.audio_int16_bytes)
        elif hasattr(chunk, "raw"):
            chunks.append(chunk.raw)
        elif isinstance(chunk, bytes):
            chunks.append(chunk)
        else:
            chunks.append(bytes(chunk))
    return b"".join(chunks)


if __name__ == "__main__":
    if "--positives" in sys.argv:
        n = generate_positives()
        sys.exit(0 if n > 0 else 1)
    else:
        print("Usage: python train_hey_gemma_v8.py --positives")
