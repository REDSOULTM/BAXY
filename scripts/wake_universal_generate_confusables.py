"""Held-out de CONFUSABLES para "baxy": palabras vecinas que NO deben disparar.

Complementa positives_baxy: mismas 25 voces Piper held-out (13 idiomas), pero
sintetizando vecinos fonéticos ("taxi", "basta", "galaxy"...). Mide el otro
eje del techo del wake: precisión ante palabras parecidas (cero fake-fires),
no solo recall bajo ruido. Lista = custom_negative_phrases de baxy.yaml +
vecinos extra que el config no cubre (galaxy/relax/boxeo/máximo).

Output: data/wake_universal_eval/confusables_baxy/<voice>__w<idx>__<k>.wav
Uso:   python scripts/wake_universal_generate_confusables.py   (python del
       sistema: tiene piper; ~2-4 min)
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

from wake_universal_voices import HELD_OUT_VOICES  # noqa: E402
from wake_universal_generate_positives import (  # noqa: E402
    synthesize, resample_int16, VOICES_DIR, TARGET_SR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("gen_confusables")

OUT_DIR = ROOT / "data" / "wake_universal_eval" / "confusables_baxy"

# custom_negative_phrases de data/livekit_train/configs/baxy.yaml + extras.
CONFUSABLES = [
    "taxi", "maxi", "waxy", "boxy", "baby", "bagsy", "backs", "bats",
    "back", "bag", "boxes", "taxis", "basi", "vasco", "basta", "pasa",
    # extras no cubiertos por el config (vecinos de /baksi/):
    "galaxy", "relax", "boxeo", "maximo", "sexy", "biscuit",
]
CLIPS_PER_WORD = 1  # 25 voces x 22 palabras x 1 = ~550 clips


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from piper import PiperVoice

    rng = random.Random(7)
    total = 0
    start = time.time()
    for spec in HELD_OUT_VOICES:
        onnx = VOICES_DIR / spec.filename
        cfg = VOICES_DIR / spec.config_filename
        if not (onnx.exists() and cfg.exists()):
            continue
        try:
            voice = PiperVoice.load(str(onnx))
        except Exception as e:
            log.warning("load %s failed: %s", spec.voice_name, e)
            continue
        per_voice = 0
        for w_idx, word in enumerate(CONFUSABLES):
            for k in range(CLIPS_PER_WORD):
                try:
                    audio, sr = synthesize(
                        voice, word,
                        rng.uniform(0.85, 1.15), rng.uniform(0.5, 0.9))
                except Exception:
                    continue
                if audio.size == 0:
                    continue
                audio16 = resample_int16(audio, sr, TARGET_SR)
                out = OUT_DIR / f"{spec.voice_name}__w{w_idx:02d}__{k}.wav"
                wavf.write(str(out), TARGET_SR, audio16)
                total += 1
                per_voice += 1
        log.info("%s: %d clips", spec.voice_name, per_voice)
    log.info("Done: %d confusable clips en %.1fs", total, time.time() - start)
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
