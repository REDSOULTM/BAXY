"""Robustez de STT a ruido de fondo — mezcla comandos de RED con música a SNR.

Idea de RED: mezclar voz con música (sus propios masters) para medir qué tan
robusto es Parakeet+corrector a micrófonos difíciles / ambiente ruidoso. Mide
Entity-Recall de comandos a varios SNR. También verifica que la música PURA no
alucine comandos (false-trigger guard).

NO es producción. Reproducible (CLAUDE.md #2). La música es solo ruido de
prueba; NO se usa como ground-truth de transcripción.

Uso:
    python scripts/stt_noise_robustness.py
    python scripts/stt_noise_robustness.py --music "C:/ruta/a/canciones"
"""
from __future__ import annotations

import argparse
import sys
from math import gcd
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from stt_real_voice_eval import (  # noqa: E402
    load_red, _read_wav_16k, _strip_wake, _norm, _wilson,
)

SR = 16000
DEFAULT_MUSIC = Path("C:/Users/usuario/Desktop/ETC/Musica/2026/Masters")


def _load_music(music_dir: Path) -> np.ndarray:
    """Concatena unas canciones como ruido de fondo (float32 16k mono)."""
    import scipy.io.wavfile as wavf
    import scipy.signal
    chunks = []
    for s in sorted(music_dir.glob("*.wav"))[:3]:
        sr, a = wavf.read(str(s))
        if a.ndim > 1:
            a = a[:, 0]
        a = a.astype(np.float32)
        if np.abs(a).max() > 1.5:
            a = a / 32768.0
        if sr != SR:
            g = gcd(int(sr), SR)
            a = scipy.signal.resample_poly(a, SR // g, int(sr) // g).astype(np.float32)
        chunks.append(a)
    return np.concatenate(chunks) if chunks else np.zeros(SR, dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", type=str, default=str(DEFAULT_MUSIC))
    ap.add_argument("--snrs", type=str, default="20,10,5")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    from gemma4_agent.voice.parakeet_stt import ParakeetSTT
    from gemma4_agent.voice.corrector import FuzzyCorrector
    from gemma4_agent.voice.inventory import get_inventory
    from gemma4_agent.voice.vad import SileroVAD

    music_dir = Path(args.music)
    if not music_dir.exists():
        print(f"No hay carpeta de música en {music_dir}")
        return 1
    music = _load_music(music_dir)
    print(f"Música de fondo: {music.size / SR:.0f}s de {music_dir.name}")

    inv = get_inventory(include_discovery=True)
    stt = ParakeetSTT(); stt.load()
    corr = FuzzyCorrector(inv)
    vad = SileroVAD(); vad.load()

    def trim(a):
        vad.reset()
        i16 = np.clip(a * 32768, -32768, 32767).astype(np.int16)
        t = vad.trim_silence(i16)
        return t.astype(np.float32) / 32768.0 if (t is not None and t.size >= 1280) else a

    red = [r for r in load_red() if r[2]][:args.limit]

    # 1) limpio (referencia)
    def measure(scale):
        hit = tot = 0
        for wav, exp, ent in red:
            tot += 1
            a = _read_wav_16k(wav)
            if scale > 0:
                m = (music[:len(a)] if len(music) >= len(a)
                     else np.tile(music, len(a) // len(music) + 1)[:len(a)])
                s_rms = np.sqrt(np.mean(a ** 2)) + 1e-9
                m_rms = np.sqrt(np.mean(m ** 2)) + 1e-9
                a = np.clip(a + m * (s_rms / m_rms) * scale, -1, 1)
            at = trim(a)
            raw = _strip_wake(stt.transcribe(
                np.clip(at * 32768, -32768, 32767).astype(np.int16)))
            if ent in _norm(corr.correct(raw)):
                hit += 1
        return hit, tot

    print(f"\nEntity-Recall comandos (n={len(red)}) vs SNR:")
    h, t = measure(0)
    p, lo, hi = _wilson(h, t)
    print(f"  limpio       {h}/{t} = {p:.0%} [{lo:.0%},{hi:.0%}]")
    for snr in [int(x) for x in args.snrs.split(",")]:
        h, t = measure(10 ** (-snr / 20))
        p, lo, hi = _wilson(h, t)
        print(f"  SNR {snr:2}dB     {h}/{t} = {p:.0%} [{lo:.0%},{hi:.0%}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
