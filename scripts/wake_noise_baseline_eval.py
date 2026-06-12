"""Recall del wake-word BAJO RUIDO DE FONDO — baseline medido.

Escenario de campo: el wake no dispara mientras suena una película/serie u
otras voces, y vuelve a funcionar en silencio. Hipótesis de causa raíz:
baxy.onnx se entrenó con data/backgrounds VACÍO (mix_with_background es no-op
silencioso si no hay wavs) → el modelo solo vio "frase + SILENCIO alrededor".

Metodología:
  - Positivos: held-out universal (data/wake_universal_eval/positives, 500
    clips TTS, 13 idiomas) — el MISMO set del gate original (recall 0.872).
  - Ruido: LibriSpeech held-out (negatives/) = voz de fondo real, el proxy
    del escenario reportado (diálogo de serie / otras voces). Nunca visto
    en training (training usó ACAV100M).
  - Condiciones: limpio (ventana con silencio, como el eval original) y
    SNR 10 / 5 / 0 dB con el ruido cubriendo la ventana COMPLETA de 2 s
    (como en la vida real: la peli suena antes, durante y después).
  - SNR se computa sobre la REGIÓN de la frase (no sobre el padding).
  - Además: simulación del gate de energía del pipeline (umbral=piso×1.6,
    piso=EMA del ambiente≈RMS del ruido) → % de wakes REALES que el gate
    rechazaría aunque el modelo disparara.
  - FP rápido: ventanas de SOLO ruido, % con score ≥ threshold.

Uso: python scripts/wake_noise_baseline_eval.py [--max-clips N]
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

import _ort_throttle  # noqa: F401,E402  SIEMPRE antes de cargar ONNX (CLAUDE.md)

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.livekit_runtime import LiveKitWakeRuntime  # noqa: E402
from gemma4_agent.voice.pipeline import peak_window_rms, _RMS_WINDOW_S  # noqa: E402
from gemma4_agent.voice.noise_calibration import threshold_from_floor  # noqa: E402

SR = 16000
WINDOW = 2 * SR
THRESHOLD = 0.25          # threshold de producción (wake.py)
SNRS_DB = (10.0, 5.0, 0.0)
SEED = 20260611

POS_DIR = ROOT / "data" / "wake_universal_eval" / "positives_baxy"
NEG_DIR = ROOT / "data" / "wake_universal_eval" / "negatives"
MUSIC_HELDOUT = ROOT / "data" / "wake_universal_eval" / "noise_heldout" / "music"
MODELS_DIR = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"


def load_clip(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data[:, 0]
    assert sr == SR, f"{path}: sr={sr}"
    return data


HOP = SR // 2  # hop 0.5s = harness oficial (wake_universal_eval_livekit.py)


def make_stream(clip: np.ndarray, noise: np.ndarray | None, snr_db: float | None,
                rng: random.Random) -> np.ndarray:
    """Stream de 1s + frase + 1s. Limpio: silencio alrededor (= eval original).
    Ruidoso: ruido cubriendo el stream COMPLETO, frase mezclada a `snr_db`
    (SNR medido sobre la región de la frase, como augment.py de LiveKit)."""
    lead = SR
    stream = np.zeros(lead + clip.size + SR, dtype=np.float32)
    stream[lead:lead + clip.size] = clip
    if noise is None or snr_db is None:
        return stream
    start = rng.randint(0, max(0, noise.size - stream.size))
    n = noise[start:start + stream.size].astype(np.float32)
    if n.size < stream.size:
        n = np.tile(n, stream.size // max(1, n.size) + 1)[:stream.size]
    p_sig = float(np.mean(clip ** 2)) + 1e-12
    p_noise = float(np.mean(n ** 2)) + 1e-12
    scale = np.sqrt(p_sig / (p_noise * 10 ** (snr_db / 10)))
    return stream + scale * n


def score_stream(rt: LiveKitWakeRuntime, stream: np.ndarray) -> float:
    """Sliding-window (hop 0.5s) + max, como el harness oficial y como el
    runtime real (ring rolling, predict cada 4 chunks)."""
    x = to_i16(stream)
    if x.size <= WINDOW:
        pad = np.zeros(WINDOW, dtype=np.int16)
        pad[-x.size:] = x
        return float(rt.predict(pad))
    best = 0.0
    for start in range(0, x.size - WINDOW + 1, HOP):
        s = float(rt.predict(x[start:start + WINDOW]))
        if s > best:
            best = s
    return best


def to_i16(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) + 1e-9
    if peak > 1.0:          # evitar clipping al convertir (como haría el mic/AGC)
        x = x / peak
    return (x * 32767).astype(np.int16)


def load_noise_pool(files: list[Path], rng: random.Random,
                    cap: int = 120) -> list[np.ndarray]:
    rng.shuffle(files)
    pool = []
    for p in files[:cap]:
        try:
            n = load_clip(p)
            if n.size >= WINDOW:
                pool.append(n)
        except Exception:
            continue
    return pool


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-clips", type=int, default=0)
    ap.add_argument("--models-dir", default=str(MODELS_DIR),
                    help="dir con melspectrogram/embedding/<stem>.onnx")
    ap.add_argument("--stem", default="baxy")
    args = ap.parse_args()

    rng = random.Random(SEED)
    rt = LiveKitWakeRuntime(Path(args.models_dir), args.stem)
    assert rt.load(), rt.last_error
    print(f"modelo: {Path(args.models_dir) / (args.stem + '.onnx')}")

    positives = sorted(POS_DIR.glob("*.wav"))
    if args.max_clips:
        positives = positives[:args.max_clips]
    noise_files = sorted(NEG_DIR.glob("**/*.flac"))
    assert positives and noise_files, "faltan datos de eval"
    print(f"positivos: {len(positives)} | pool voces: {len(noise_files)} flac")

    pools: dict[str, list[np.ndarray]] = {
        "voces": load_noise_pool(noise_files, rng),
    }
    music_files = sorted(MUSIC_HELDOUT.glob("*.wav"))
    if music_files:
        pools["musica"] = load_noise_pool(music_files, rng)
    print("ruidos cargados: " +
          ", ".join(f"{k}={len(v)}" for k, v in pools.items()))

    conds: list[tuple[str, str | None, float | None]] = \
        [("limpio", None, None)] + \
        [(f"voces_snr{int(s)}dB", "voces", s) for s in SNRS_DB]
    if "musica" in pools:
        conds += [(f"musica_snr{int(s)}dB", "musica", s) for s in (5.0, 0.0)]
    stats = {name: {"fired": 0, "total": 0, "gate_reject": 0,
                    "gate_reject_115": 0, "scores": [], "by_lang": {}}
             for name, _, _ in conds}

    t0 = time.time()
    for i, pos in enumerate(positives):
        clip = load_clip(pos)
        lang = pos.name.split("_")[0]
        for name, pool_key, snr in conds:
            pool = pools[pool_key] if pool_key else None
            noise = None if pool is None else pool[rng.randrange(len(pool))]
            stream = make_stream(clip, noise, snr, rng)
            score = score_stream(rt, stream)
            st = stats[name]
            st["total"] += 1
            st["scores"].append(score)
            lang_st = st["by_lang"].setdefault(lang, [0, 0])
            lang_st[1] += 1
            if score >= THRESHOLD:
                st["fired"] += 1
                lang_st[0] += 1
                # gate de energía: ¿lo habría rechazado el pipeline? El piso
                # EMA converge al RMS del ruido; el gate mira el pico 0.2s.
                if snr is not None:
                    si16 = to_i16(stream)
                    noise_rms = float(np.sqrt(np.mean(
                        si16[:SR].astype(np.float64) ** 2)))  # 1er seg = solo ruido
                    gate = threshold_from_floor(noise_rms)   # factor actual 1.6
                    peak = peak_window_rms(si16, int(_RMS_WINDOW_S * SR))
                    if peak < gate:
                        st["gate_reject"] += 1
                    if peak < noise_rms * 1.15:              # factor propuesto
                        st["gate_reject_115"] += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(positives)} ({time.time() - t0:.0f}s)")

    print(f"\n== RECALL @ threshold {THRESHOLD} (modelo solo) ==")
    for name, _, _ in conds:
        st = stats[name]
        rec = st["fired"] / max(1, st["total"])
        scores = np.asarray(st["scores"])
        gr, gr115 = st["gate_reject"], st["gate_reject_115"]
        extra = ""
        if st["fired"] and name != "limpio":
            extra = (f" | gate x1.6 rechazaria {gr}/{st['fired']}, "
                     f"x1.15 rechazaria {gr115}/{st['fired']}")
        print(f"{name:16} recall={rec:.3f} ({st['fired']}/{st['total']}) "
              f"score p50={np.median(scores):.3f} p90={np.percentile(scores, 90):.3f}"
              f"{extra}")

    print("\n== sweep de threshold (recall por condición) ==")
    sweep = (0.20, 0.25, 0.30, 0.40, 0.50)
    header = "cond".ljust(16) + "".join(f"  thr{t:.2f}" for t in sweep)
    print(header)
    for name, _, _ in conds:
        sc = np.asarray(stats[name]["scores"])
        row = name.ljust(16) + "".join(
            f"  {float(np.mean(sc >= t)):.3f}" for t in sweep)
        print(row)

    print("\n== por idioma (limpio vs voces_snr5dB) ==")
    for lang in sorted(stats["limpio"]["by_lang"]):
        c = stats["limpio"]["by_lang"][lang]
        n5 = stats["voces_snr5dB"]["by_lang"].get(lang, [0, 0])
        print(f"  {lang:3} limpio {c[0]}/{c[1]}  snr5 {n5[0]}/{n5[1]}")

    # FP rápido: solo-ruido (todas las fuentes)
    for pool_name, pool in pools.items():
        fp = 0
        n_fp = 300
        for _ in range(n_fp):
            noise = pool[rng.randrange(len(pool))]
            start = rng.randint(0, max(0, noise.size - WINDOW))
            w = noise[start:start + WINDOW]
            if w.size < WINDOW:
                w = np.tile(w, 2)[:WINDOW]
            if float(rt.predict(to_i16(w))) >= THRESHOLD:
                fp += 1
        print(f"\nFP solo-{pool_name}: {fp}/{n_fp} ventanas >= {THRESHOLD}")
    print(f"total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
