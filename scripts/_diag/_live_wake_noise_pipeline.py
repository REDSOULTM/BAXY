"""Live-test del wake BAJO RUIDO por el pipeline REAL (sin mic físico).

Ejercita VoicePipeline entero — calibración de piso, ring de preroll, throttle
de predict, gate de energía y transición IDLE→CAPTURE — alimentando _on_chunk
con chunks de 32 ms como lo haría el AudioPump:

  A) ruido(voces) 3s + "baxy" mezclado a SNR 5 + ruido 1.5s  → DEBE despertar
  B) silencio + "baxy" limpio + silencio                     → DEBE despertar
  C) casi-silencio + _on_wake() forzado (FP del modelo)      → gate DEBE rechazar
  D) solo ruido 8s (sin frase)                               → NO debe despertar

Uso:  python scripts/_diag/_live_wake_noise_pipeline.py [--stem baxy]
El stem elige el clasificador (GEMMA4_LIVEKIT_MODEL_STEM) para probar el
candidato reentrenado antes de pisar el de producción.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import _ort_throttle  # noqa: F401,E402

ap = argparse.ArgumentParser()
ap.add_argument("--stem", default="baxy")
ap.add_argument("--snr", type=float, default=5.0)
args = ap.parse_args()
os.environ["GEMMA4_LIVEKIT_MODEL_STEM"] = args.stem
os.environ.pop("GEMMA4_VOICE_MIN_CAPTURE_RMS", None)  # auto-cal activa

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.pipeline import (  # noqa: E402
    VoicePipeline, State, CHUNK_SAMPLES, SAMPLE_RATE,
)

SEED = 20260611
rng = random.Random(SEED)

POS = sorted((ROOT / "data" / "wake_universal_eval" / "positives_baxy").glob("es_*.wav"))
NOISE = sorted((ROOT / "data" / "wake_universal_eval" / "negatives").glob("**/*.flac"))


def load(path: Path) -> np.ndarray:
    d, sr = sf.read(str(path), dtype="float32")
    if d.ndim > 1:
        d = d[:, 0]
    assert sr == SAMPLE_RATE
    return d


def noise_seg(seconds: float) -> np.ndarray:
    while True:
        n = load(NOISE[rng.randrange(min(len(NOISE), 300))])
        need = int(seconds * SAMPLE_RATE)
        if n.size >= need:
            start = rng.randint(0, n.size - need)
            return n[start:start + need]


def to_i16(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) + 1e-9
    if peak > 1.0:
        x = x / peak
    return (x * 32767).astype(np.int16)


def feed(pipe: VoicePipeline, audio_i16: np.ndarray) -> None:
    for i in range(0, audio_i16.size - CHUNK_SAMPLES + 1, CHUNK_SAMPLES):
        pipe._on_chunk(audio_i16[i:i + CHUNK_SAMPLES])


def new_pipe() -> tuple[VoicePipeline, dict]:
    events: dict = {"wakes": 0, "states": []}

    def on_command(text: str, secs: float, raw: str) -> None:
        events.setdefault("commands", []).append(text)

    pipe = VoicePipeline(on_command=on_command,
                         on_state=lambda s: events["states"].append(s),
                         on_wake_event=lambda: events.__setitem__(
                             "wakes", events["wakes"] + 1))
    assert pipe.load(), pipe.last_error
    return pipe, events


def scenario_a() -> bool:
    """ruido continuo (un solo segmento) + baxy mezclado a SNR → debe despertar."""
    pipe, ev = new_pipe()
    clip = load(POS[0])
    total_s = 3.0 + clip.size / SAMPLE_RATE + 1.5
    noise = noise_seg(total_s)
    p_s = float(np.mean(clip ** 2)) + 1e-12
    p_n = float(np.mean(noise ** 2)) + 1e-12
    n_scale = np.sqrt(p_s / (p_n * 10 ** (args.snr / 10)))
    stream = noise * n_scale
    lead = int(3.0 * SAMPLE_RATE)
    stream[lead:lead + clip.size] += clip
    feed(pipe, to_i16(stream))
    ok = ev["wakes"] >= 1
    print(f"A ruido+baxy@snr{args.snr:.0f}: wakes={ev['wakes']} states={ev['states'][:3]} "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def scenario_b() -> bool:
    pipe, ev = new_pipe()
    clip = load(POS[1])
    sil = np.zeros(int(2.0 * SAMPLE_RATE), dtype=np.float32) + 0.0005 * np.random.randn(
        int(2.0 * SAMPLE_RATE)).astype(np.float32)
    stream = to_i16(np.concatenate([sil, clip, sil[:SAMPLE_RATE]]))
    feed(pipe, stream)
    ok = ev["wakes"] >= 1
    print(f"B limpio: wakes={ev['wakes']} {'PASS' if ok else 'FAIL'}")
    return ok


def scenario_c() -> bool:
    """FP del modelo EN SILENCIO (forzado) → el gate de energía debe rechazar."""
    pipe, ev = new_pipe()
    sil = (0.0005 * np.random.randn(int(3.0 * SAMPLE_RATE))).astype(np.float32)
    feed(pipe, to_i16(sil))                       # calibra piso en casi-silencio
    pipe._on_wake("baxy", 0.99)                   # FP sintético del modelo
    ok = pipe.state == State.IDLE and ev["wakes"] == 0
    print(f"C FP-en-silencio: state={pipe.state.value} wakes={ev['wakes']} "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def scenario_d() -> bool:
    pipe, ev = new_pipe()
    feed(pipe, to_i16(noise_seg(8.0)))
    ok = ev["wakes"] == 0
    print(f"D solo-ruido 8s: wakes={ev['wakes']} {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    print(f"modelo stem={args.stem} snr={args.snr}")
    results = [scenario_a(), scenario_b(), scenario_c(), scenario_d()]
    print("RESULTADO:", "PASS 4/4" if all(results) else
          f"FAIL ({sum(results)}/4)")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
