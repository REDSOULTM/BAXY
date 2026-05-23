"""SPIKE de viabilidad — sherpa-onnx + Parakeet-TDT-0.6B-v3 int8 con hotwords.

NO es producción. Mide las 3 incógnitas que la investigación dejó abiertas,
contra nuestras restricciones (eje VIABILIDAD del sprint):
  1. LATENCIA en comandos cortos (CPU) — ¿comparable a whisper-small o peor?
  2. RAM pico al cargar/inferir.
  3. ENTITY-RECALL de nombres propios: Parakeet sin hotwords vs con hotwords,
     y vs whisper-small (baseline). Sobre clips reales + held-out.

Decisión que habilita (paso 1 de la investigación): si Parakeet+hotwords sube
U-WER de nombres propios sin reventar latencia/RAM, justifica migrar; si no,
nos quedamos en whisper-small.

Uso:
    python scripts/spike_sherpa_parakeet.py
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODEL_DIR = ROOT / "data" / "stt_eval" / "sherpa" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
AUDIO_DIR = ROOT / "data" / "stt_eval" / "audio"
REAL_DIR = ROOT / "data" / "stt_eval" / "real_es"


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\sáéíóúüñ]", " ", s)
    return " ".join(s.split())


def _peak_ram_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        return -1.0


def build_recognizer(hotwords_file: str | None = None):
    import sherpa_onnx
    kw = dict(
        encoder=str(MODEL_DIR / "encoder.int8.onnx"),
        decoder=str(MODEL_DIR / "decoder.int8.onnx"),
        joiner=str(MODEL_DIR / "joiner.int8.onnx"),
        tokens=str(MODEL_DIR / "tokens.txt"),
        num_threads=4,
        model_type="nemo_transducer",
    )
    if hotwords_file:
        kw.update(
            decoding_method="modified_beam_search",
            hotwords_file=hotwords_file,
            hotwords_score=2.0,
        )
    else:
        kw["decoding_method"] = "greedy_search"
    return sherpa_onnx.OfflineRecognizer.from_transducer(**kw)


def transcribe(rec, audio_int16: np.ndarray) -> str:
    import sherpa_onnx
    s = rec.create_stream()
    s.accept_waveform(16000, audio_int16.astype(np.float32) / 32768.0)
    rec.decode_stream(s)
    return s.result.text.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="clips por bucket")
    args = ap.parse_args()

    if not MODEL_DIR.exists():
        print(f"FALTA el modelo en {MODEL_DIR} — esperá la descarga.")
        return 1

    import scipy.io.wavfile as wavf

    print(f"RAM antes de cargar: {_peak_ram_mb():.0f} MB")
    t0 = time.time()
    rec_greedy = build_recognizer(hotwords_file=None)
    print(f"Carga (greedy): {time.time()-t0:.1f}s | RAM: {_peak_ram_mb():.0f} MB")

    # hotwords = nombres propios (clase anglicismo) — para el spike, los de los
    # comandos sintéticos. En prod vendrían del inventario dinámico.
    hot = MODEL_DIR.parent / "spike_hotwords.txt"
    hot.write_text("\n".join([
        "Steam", "Chrome", "Spotify", "Discord", "Telegram", "WhatsApp",
        "Firefox", "YouTube", "Netflix", "Disney", "Daredevil",
        "Stranger Things", "Counter-Strike", "Bad Bunny", "Benson Boone",
    ]) + "\n", encoding="utf-8")
    t0 = time.time()
    rec_hot = build_recognizer(hotwords_file=str(hot))
    print(f"Carga (hotwords): {time.time()-t0:.1f}s | RAM: {_peak_ram_mb():.0f} MB")

    # Latencia: medir sobre clips sintéticos cortos
    syn = sorted(AUDIO_DIR.glob("*__c*.wav"))[: args.n]
    print(f"\n=== LATENCIA comando corto (n={len(syn)}, 4 threads) ===")
    for label, rec in (("greedy", rec_greedy), ("hotwords", rec_hot)):
        lats = []
        for f in syn:
            sr, a = wavf.read(str(f)); a = a[:, 0] if a.ndim > 1 else a
            t0 = time.time(); transcribe(rec, a); lats.append(time.time() - t0)
        lats.sort()
        dur_avg = np.mean([wavf.read(str(f))[1].shape[0] / 16000 for f in syn])
        print(f"  {label:10} p50={lats[len(lats)//2]*1000:.0f}ms "
              f"p95={lats[int(len(lats)*0.95)]*1000:.0f}ms "
              f"(audio medio {dur_avg:.1f}s) RAM={_peak_ram_mb():.0f}MB")

    # Calidad de transcripción cualitativa (anglicismos): greedy vs hotwords
    print("\n=== ANGLICISMOS: greedy vs hotwords (cualitativo) ===")
    for f in syn[:12]:
        sr, a = wavf.read(str(f)); a = a[:, 0] if a.ndim > 1 else a
        g = transcribe(rec_greedy, a); h = transcribe(rec_hot, a)
        mark = "" if _norm(g) == _norm(h) else "  <-- DIFF"
        print(f"  greedy : {g[:55]!r}")
        print(f"  hotword: {h[:55]!r}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
