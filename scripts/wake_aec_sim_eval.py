"""Validación OFFLINE del AEC: ¿recupera el wake con la "peli" MÁS FUERTE
que la voz? Simula el lazo acústico completo y mide ANTES/DESPUÉS.

Simulación (por caso): referencia = música/voces held-out (lo que el PC
"reproduce"); eco en el mic = referencia con delay (5-60 ms) + filtro de
sala (RIR sintética simple: taps decrecientes) + ganancia; mic = eco +
"baxy" (held-out) a SIR {0, -5, -10} dB + ruido de piso. Métricas:
  - ERLE (atenuación del eco, dB) tras converger
  - recall del wake (modelo PROD) sobre la señal cruda vs la cancelada
La promesa Alexa es: a SIR negativo el wake crudo MUERE y el cancelado vive.

Uso: python scripts/wake_aec_sim_eval.py [--n 120]
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import _ort_throttle  # noqa: F401,E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.aec import EchoCanceller, CHUNK  # noqa: E402
from gemma4_agent.voice.livekit_runtime import LiveKitWakeRuntime  # noqa: E402

SR = 16000
WINDOW = 2 * SR
HOP = SR // 2
SEED = 20260612
POS = ROOT / "data" / "wake_universal_eval" / "positives_baxy"
MUSIC = ROOT / "data" / "wake_universal_eval" / "noise_heldout" / "music"
MODELS = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"


def load(p: Path) -> np.ndarray:
    d, _ = sf.read(str(p), dtype="float32")
    return d[:, 0] if d.ndim > 1 else d


def room_echo(ref: np.ndarray, delay: int, rng: np.random.RandomState
              ) -> np.ndarray:
    """Eco simple: delay + filtro de sala de 12 taps decrecientes."""
    taps = rng.uniform(0.2, 1.0, 12) * np.exp(-np.arange(12) / 3.0)
    taps /= np.sum(taps)
    echo = np.convolve(ref, taps)[:ref.size]
    return np.concatenate([np.zeros(delay, dtype=np.float32),
                           echo[:-delay] if delay else echo]).astype(np.float32)


def score_stream(rt, x16: np.ndarray) -> float:
    best = 0.0
    for s in range(0, max(1, x16.size - WINDOW + 1), HOP):
        w = x16[s:s + WINDOW]
        if w.size < WINDOW:
            break
        best = max(best, float(rt.predict(w)))
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    args = ap.parse_args()
    rng = np.random.RandomState(SEED)
    pyrng = random.Random(SEED)

    rt = LiveKitWakeRuntime(MODELS, "baxy")
    assert rt.load()
    music = [load(p) for p in sorted(MUSIC.glob("*.wav"))[:20]]
    positives = sorted(POS.glob("*.wav"))
    pyrng.shuffle(positives)
    positives = positives[:args.n]
    print(f"casos: {len(positives)} | thr 0.25 | filtro NLMS 256ms")

    t0 = time.time()
    for sir_db in (0.0, -5.0, -10.0):
        fired_raw = fired_aec = 0
        erles = []
        for pos in positives:
            clip = load(pos)
            m = music[pyrng.randrange(len(music))]
            start = pyrng.randint(0, max(1, m.size - (clip.size + 5 * SR)))
            ref = m[start:start + clip.size + 5 * SR]   # 3s converge + frase + cola
            delay = int(rng.uniform(0.005, 0.060) * SR)
            echo = room_echo(ref, delay, rng)
            # escala: eco a SIR dB sobre la frase (negativo = eco MÁS fuerte)
            lead = 3 * SR
            p_clip = float(np.mean(clip ** 2)) + 1e-12
            p_echo = float(np.mean(echo ** 2)) + 1e-12
            g = np.sqrt(p_clip / (p_echo * 10 ** (sir_db / 10)))
            echo = echo * g
            mic = echo.copy()
            mic[lead:lead + clip.size] += clip
            mic += rng.normal(0, 3e-4, mic.size).astype(np.float32)

            mic16 = np.clip(mic * 32767, -32768, 32767).astype(np.int16)
            ref16 = np.clip(ref * 32767, -32768, 32767).astype(np.int16)

            aec = EchoCanceller()
            out = np.empty_like(mic16)
            for i in range(0, mic16.size - CHUNK + 1, CHUNK):
                out[i:i + CHUNK] = aec.process(mic16[i:i + CHUNK],
                                               ref16[i:i + CHUNK])
            # ERLE sobre la cola (post-frase, solo eco, ya convergido)
            tail = slice(lead + clip.size + SR // 2, mic16.size - CHUNK)
            p_in = float(np.mean(mic16[tail].astype(np.float64) ** 2)) + 1e-9
            p_out = float(np.mean(out[tail].astype(np.float64) ** 2)) + 1e-9
            erles.append(10 * np.log10(p_in / p_out))

            if score_stream(rt, mic16) >= 0.25:
                fired_raw += 1
            if score_stream(rt, out) >= 0.25:
                fired_aec += 1
        n = len(positives)
        print(f"SIR {sir_db:+.0f} dB: recall crudo {fired_raw / n:.3f} -> "
              f"con AEC {fired_aec / n:.3f} | ERLE p50 "
              f"{np.median(erles):.1f} dB ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
