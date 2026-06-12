"""Fusión OR de dos clasificadores de wake — medición OFFLINE previa.

Motivación (2026-06-12): el modelo prod (entrenado limpio) tiene recall
0.820 en silencio pero 0.000 con voces de fondo y llueve fake-wakes con
música en uso real; el candidato v5 (entrenado con ruido) detecta bajo
ruido pero pierde limpio (0.632) y dispara más en habla continua (fp/hr
6.0 @ thr 0.25). El frontend (mel+embedding) es COMPARTIDO y los
clasificadores son diminutos → correr AMBOS y disparar si cualquiera
supera SU umbral cuesta ~0 CPU extra.

Este script puntúa cada clip de eval con LOS DOS modelos UNA vez, y barre
pares de umbrales (t_orig, t_noise) computando la fusión OR:
  - recall limpio / voces-snr5 / música-snr5 (held-out 500)
  - fake-fires de confusables (550)
  - fp/hr sobre ~3 h de LibriSpeech (ventana deslizante + cooldown 2 s)

Uso: python scripts/wake_dual_or_eval.py [--fp-hours 3]
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import _ort_throttle  # noqa: F401,E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.livekit_runtime import LiveKitWakeRuntime  # noqa: E402

SR = 16000
WINDOW = 2 * SR
HOP = SR // 2
SEED = 20260612
MODELS = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
POS = ROOT / "data" / "wake_universal_eval" / "positives_baxy"
NEG = ROOT / "data" / "wake_universal_eval" / "negatives"
CONF = ROOT / "data" / "wake_universal_eval" / "confusables_baxy"
MUSIC = ROOT / "data" / "wake_universal_eval" / "noise_heldout" / "music"

ORIG_THRS = (0.25, 0.35, 0.50, None)     # None = ese modelo apagado
NOISE_THRS = (0.30, 0.40, 0.50, 0.60, None)


def load_f32(p: Path) -> np.ndarray:
    d, sr = sf.read(str(p), dtype="float32")
    if d.ndim > 1:
        d = d[:, 0]
    return d


def to_i16(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) + 1e-9
    if peak > 1.0:
        x = x / peak
    return (x * 32767).astype(np.int16)


def score_stream(rt: LiveKitWakeRuntime, x: np.ndarray) -> float:
    if x.size <= WINDOW:
        pad = np.zeros(WINDOW, dtype=np.int16)
        pad[-x.size:] = x
        return float(rt.predict(pad))
    best = 0.0
    for s in range(0, x.size - WINDOW + 1, HOP):
        best = max(best, float(rt.predict(x[s:s + WINDOW])))
    return best


def make_stream(clip, noise, snr_db, rng):
    lead = SR
    stream = np.zeros(lead + clip.size + SR, dtype=np.float32)
    stream[lead:lead + clip.size] = clip
    if noise is None:
        return stream
    start = rng.randint(0, max(0, noise.size - stream.size))
    n = noise[start:start + stream.size]
    if n.size < stream.size:
        n = np.tile(n, stream.size // max(1, n.size) + 1)[:stream.size]
    p_s = float(np.mean(clip ** 2)) + 1e-12
    p_n = float(np.mean(n ** 2)) + 1e-12
    return stream + n * np.sqrt(p_s / (p_n * 10 ** (snr_db / 10)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp-hours", type=float, default=3.0)
    args = ap.parse_args()
    rng = random.Random(SEED)

    rt_o = LiveKitWakeRuntime(MODELS, "baxy")
    rt_n = LiveKitWakeRuntime(MODELS, "baxy_noise")
    assert rt_o.load() and rt_n.load()

    voces_files = sorted(NEG.glob("**/*.flac"))
    rng.shuffle(voces_files)
    voces_pool = [load_f32(p) for p in voces_files[:100]
                  if p.stat().st_size > 200_000][:80]
    music_pool = [load_f32(p) for p in sorted(MUSIC.glob("*.wav"))[:28]]

    positives = sorted(POS.glob("*.wav"))
    print(f"positivos {len(positives)} | confusables "
          f"{len(list(CONF.glob('*.wav')))} | fp {args.fp_hours}h")

    # --- 1. scores de positivos por condición y modelo ---
    t0 = time.time()
    conds = {"limpio": None, "voces_snr5": ("v", 5.0), "musica_snr5": ("m", 5.0)}
    scores: dict[str, dict[str, list[float]]] = \
        {c: {"o": [], "n": []} for c in conds}
    langs: list[str] = []
    for i, p in enumerate(positives):
        clip = load_f32(p)
        langs.append(p.name.split("_")[0])
        for cname, spec in conds.items():
            if spec is None:
                stream = make_stream(clip, None, 0, rng)
            else:
                pool = voces_pool if spec[0] == "v" else music_pool
                stream = make_stream(clip, pool[rng.randrange(len(pool))],
                                     spec[1], rng)
            x = to_i16(stream)
            scores[cname]["o"].append(score_stream(rt_o, x))
            scores[cname]["n"].append(score_stream(rt_n, x))
        if (i + 1) % 100 == 0:
            print(f"  pos {i + 1}/{len(positives)} ({time.time() - t0:.0f}s)")

    # --- 2. confusables ---
    conf_o, conf_n = [], []
    for p in sorted(CONF.glob("*.wav")):
        x = to_i16(load_f32(p))
        conf_o.append(score_stream(rt_o, x))
        conf_n.append(score_stream(rt_n, x))

    # --- 3. fp: trazas por ventana sobre LibriSpeech ---
    fp_o, fp_n = [], []
    total_s = 0.0
    for p in voces_files[100:]:
        if total_s >= args.fp_hours * 3600:
            break
        a = load_f32(p)
        total_s += a.size / SR
        x = to_i16(a)
        for s in range(0, max(1, x.size - WINDOW + 1), HOP):
            w = x[s:s + WINDOW]
            if w.size < WINDOW:
                break
            fp_o.append(float(rt_o.predict(w)))
            fp_n.append(float(rt_n.predict(w)))
    fp_o = np.asarray(fp_o)
    fp_n = np.asarray(fp_n)
    print(f"scores listos ({time.time() - t0:.0f}s, fp windows={fp_o.size}, "
          f"{total_s / 3600:.2f}h)")

    def fp_per_hour(t_o, t_n) -> float:
        fire = np.zeros(fp_o.size, dtype=bool)
        if t_o is not None:
            fire |= fp_o >= t_o
        if t_n is not None:
            fire |= fp_n >= t_n
        # cooldown 2 s = 4 ventanas (hop 0.5 s): un burst = 1 fire
        count, cool = 0, -1
        for idx in np.flatnonzero(fire):
            if idx >= cool:
                count += 1
                cool = idx + 4
        return count / max(0.01, total_s / 3600)

    def recall(cond, t_o, t_n) -> float:
        o = np.asarray(scores[cond]["o"])
        n = np.asarray(scores[cond]["n"])
        fired = np.zeros(o.size, dtype=bool)
        if t_o is not None:
            fired |= o >= t_o
        if t_n is not None:
            fired |= n >= t_n
        return float(np.mean(fired))

    def conf_rate(t_o, t_n) -> float:
        o = np.asarray(conf_o)
        n = np.asarray(conf_n)
        fired = np.zeros(o.size, dtype=bool)
        if t_o is not None:
            fired |= o >= t_o
        if t_n is not None:
            fired |= n >= t_n
        return float(np.mean(fired))

    print("\n t_orig t_noise | limpio voces5 musica5 | confus  fp/hr")
    print("-" * 62)
    rows = []
    for t_o in ORIG_THRS:
        for t_n in NOISE_THRS:
            if t_o is None and t_n is None:
                continue
            r_l = recall("limpio", t_o, t_n)
            r_v = recall("voces_snr5", t_o, t_n)
            r_m = recall("musica_snr5", t_o, t_n)
            cr = conf_rate(t_o, t_n)
            fph = fp_per_hour(t_o, t_n)
            rows.append((t_o, t_n, r_l, r_v, r_m, cr, fph))
            print(f" {t_o if t_o is not None else ' off '!s:>6} "
                  f"{t_n if t_n is not None else ' off '!s:>7} | "
                  f"{r_l:.3f}  {r_v:.3f}  {r_m:.3f}  | {cr:6.1%} {fph:6.2f}")

    # recomendación: fp/hr<=1.0, maximizar (voces5 + limpio), reportar confus
    ok = [r for r in rows if r[6] <= 1.0]
    if ok:
        best = max(ok, key=lambda r: r[3] + r[2])
        print(f"\nRECOMENDADO (fp/hr<=1.0, max voces+limpio): "
              f"t_orig={best[0]} t_noise={best[1]} -> limpio {best[2]:.3f} "
              f"voces5 {best[3]:.3f} musica5 {best[4]:.3f} "
              f"confus {best[5]:.1%} fp/hr {best[6]:.2f}")
    print(f"total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
