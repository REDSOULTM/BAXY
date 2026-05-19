"""Generate multi-voice, multi-language synthetic 'hey gemma' positives.

For each downloaded Piper voice, synthesise N variants of the wake
phrase with varied prosody. Goal: ~500 positive clips across ≥25 voices
and ≥7 languages. None of these voices were in v9 training.

Phrase variations include:
  - Canonical 'hey gemma'
  - Common phonetic alternatives in different languages (ay/ey/hey)
  - With and without sentence punctuation (changes prosody in Piper)
  - Mixed-case variants

Output: data/wake_universal_eval/positives/<voice>_<phrase_id>_<idx>.wav
Each clip is 16 kHz mono int16 PCM.
"""
from __future__ import annotations

import logging
import random
import sys
import time
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from wake_universal_voices import HELD_OUT_VOICES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("gen_positives")

VOICES_DIR = ROOT / "data" / "wake_universal_eval" / "voices"
OUT_DIR = ROOT / "data" / "wake_universal_eval" / "positives"
TARGET_SR = 16000

# Phrase variations. Keep the count modest so we hit ~500 total across
# 25 voices: 25 × 5 × 4 = 500. The phrases cover anglo + latin
# pronunciations of "hey gemma" since the wake must work for both.
PHRASE_VARIATIONS = [
    "hey gemma",
    "hey gemma.",
    "Hey Gemma!",
    "ey gemma",        # Hispanic informal h-drop
    "hey gema",        # Spanish phonetic
]
CLIPS_PER_PHRASE = 4  # 4 prosody variants per (voice, phrase)


def synthesize(voice, text: str, length_scale: float, noise_scale: float):
    """Returns (int16 audio, sample_rate)."""
    from piper.config import SynthesisConfig
    cfg = SynthesisConfig(length_scale=length_scale, noise_scale=noise_scale)
    chunks: list[bytes] = []
    for chunk in voice.synthesize(text, syn_config=cfg):
        if hasattr(chunk, "audio_int16_bytes"):
            chunks.append(chunk.audio_int16_bytes)
        elif isinstance(chunk, bytes):
            chunks.append(chunk)
    audio = np.frombuffer(b"".join(chunks), dtype=np.int16)
    sr = int(voice.config.sample_rate)
    return audio, sr


def resample_int16(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    # scipy.signal.resample_poly is faster than librosa for this size.
    from math import gcd
    g = gcd(sr_in, sr_out)
    up, down = sr_out // g, sr_in // g
    import scipy.signal
    a = audio.astype(np.float32)
    out = scipy.signal.resample_poly(a, up, down)
    out = np.clip(out, -32768, 32767).astype(np.int16)
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from piper import PiperVoice

    rng = random.Random(42)
    total = 0
    skipped_voices = 0
    start = time.time()

    for spec in HELD_OUT_VOICES:
        onnx = VOICES_DIR / spec.filename
        cfg = VOICES_DIR / spec.config_filename
        if not (onnx.exists() and cfg.exists()):
            log.warning("skip %s — voice files missing", spec.voice_name)
            skipped_voices += 1
            continue
        try:
            voice = PiperVoice.load(str(onnx))
        except Exception as e:
            log.warning("load %s failed: %s", spec.voice_name, e)
            skipped_voices += 1
            continue
        sr_native = int(voice.config.sample_rate)
        log.info("=== %s (lang=%s, sr=%d) ===", spec.voice_name, spec.lang, sr_native)
        per_voice = 0
        for phrase_id, phrase in enumerate(PHRASE_VARIATIONS):
            for k in range(CLIPS_PER_PHRASE):
                ls = rng.uniform(0.80, 1.20)
                ns = rng.uniform(0.45, 0.95)
                try:
                    audio, sr = synthesize(voice, phrase, ls, ns)
                except Exception as e:
                    log.debug("synth fail %s %r: %s", spec.voice_name, phrase, e)
                    continue
                if audio.size == 0:
                    continue
                audio16 = resample_int16(audio, sr, TARGET_SR)
                out = OUT_DIR / f"{spec.voice_name}__p{phrase_id}__{k:02d}.wav"
                wavf.write(str(out), TARGET_SR, audio16)
                total += 1
                per_voice += 1
        log.info("  %d clips for %s", per_voice, spec.voice_name)

    el = time.time() - start
    log.info(
        "Done: %d positive clips across %d voices in %.1fs (skipped %d voices)",
        total, len(HELD_OUT_VOICES) - skipped_voices, el, skipped_voices,
    )
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
