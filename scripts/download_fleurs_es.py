"""Re-descarga FLEURS es_419 (voz humana real, CC-BY) para el held-out anti-overfit.

Los WAV de data/stt_eval/real_es/fleurs_*.wav estaban CORRUPTOS (silencio: int16
max=1, bytes a cero) — descarga fallida previa. Este script los regenera desde
HuggingFace (google/fleurs, split test, es_419), reproducible (CLAUDE.md #2).

Escribe fleurs_es_NNNN.wav (16k mono int16) + reescribe manifest.tsv (file\ttext).
NO toca los chilean_*.wav (esos sí tienen audio).

Uso:
    python scripts/download_fleurs_es.py --n 120
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "stt_eval" / "real_es"
SR = 16000


def _resample(a: np.ndarray, sr_in: int) -> np.ndarray:
    if sr_in == SR:
        return a
    from math import gcd
    import scipy.signal
    g = gcd(int(sr_in), SR)
    return scipy.signal.resample_poly(a, SR // g, int(sr_in) // g)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    args = ap.parse_args()

    import io
    import scipy.io.wavfile as wavf
    import soundfile as sf
    from datasets import load_dataset, Audio

    OUT.mkdir(parents=True, exist_ok=True)
    print("Descargando google/fleurs es_419 (test split, streaming)...", flush=True)
    # streaming=True evita bajar el dataset entero; tomamos los primeros n con audio.
    # decode=False -> NO usar el decoder de `datasets` (requiere torchcodec y es
    # frágil); recibimos los bytes crudos y los decodificamos con soundfile.
    ds = load_dataset("google/fleurs", "es_419", split="test", streaming=True)
    ds = ds.cast_column("audio", Audio(decode=False))

    rows = []
    n = 0
    for ex in ds:
        if n >= args.n:
            break
        audio = ex["audio"]
        # con decode=False: {'bytes': ..., 'path': ...}. Si bytes es None, abrir path.
        raw = audio.get("bytes")
        if raw:
            arr, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        else:
            arr, sr = sf.read(audio["path"], dtype="float32", always_2d=False)
        if getattr(arr, "ndim", 1) > 1:
            arr = arr[:, 0]
        arr = np.asarray(arr, dtype=np.float32)
        arr = _resample(arr, int(sr))
        peak = float(np.max(np.abs(arr))) if arr.size else 0.0
        if peak < 0.01 or arr.size < int(0.3 * SR):
            continue  # saltar clips vacíos/cortísimos
        i16 = np.clip(arr / max(peak, 1e-6) * 0.95 * 32767, -32768, 32767).astype(np.int16)
        fn = f"fleurs_es_{n:04d}.wav"
        wavf.write(str(OUT / fn), SR, i16)
        text = re.sub(r"\s+", " ", ex.get("transcription") or ex.get("raw_transcription") or "").strip()
        rows.append((fn, text))
        n += 1
        if n % 20 == 0:
            print(f"  {n}/{args.n}", flush=True)

    # reescribir manifest.tsv (solo FLEURS; el manifest_cl.tsv de chilenos queda intacto)
    mf = OUT / "manifest.tsv"
    with open(mf, "w", encoding="utf-8") as f:
        f.write("file\ttext\n")
        for fn, text in rows:
            f.write(f"{fn}\t{text}\n")
    print(f"OK: {n} clips FLEURS con audio -> {mf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
