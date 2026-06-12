"""GATE DE CONTENIDO para bloques de positivos del wake (la pieza que faltó).

Lección v6 (2026-06-12): el gate de duración no alcanza — los bloques de/zh
tenían duraciones sanas pero el CONTENIDO era mumble ("Yeah.", "shaman") y
envenenaron el train (es 1.00→0.05, val inestable). Este gate transcribe una
muestra del bloque con Parakeet y puntúa la similitud fonética dual ES/EN
contra las variantes de "baxy" (la misma maquinaria del corrector). Un bloque
entra al train SOLO si su score agregado supera el umbral CALIBRADO contra
los bloques conocidos-buenos (EN/pl/nl) y conocidos-malos (de-mumble/zh).

Uso CLI:  python scripts/wake_block_content_gate.py <start> <end> [n_sample]
Uso lib:  from wake_block_content_gate import block_score, clip_phon_score
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

from gemma4_agent.voice.corrector import (  # noqa: E402
    _normalise, _metaphone, _metaphone_es,
)

WAKES = ("baxy", "baxi", "backsy", "bakse")
# Umbral por clip (similitud fonética del MEJOR token del transcript) y
# fracción mínima del bloque que debe pasarlo. CALIBRADO 2026-06-12 contra
# bloques conocidos (ver _calibrate_content_gate en la doc del wake):
#   EN (bueno) ~0.62 · pl 0.78 · nl 0.85 · ru 0.60  vs  de-mumble 0.20 · zh 0.18
CLIP_THR = 65.0
BLOCK_MIN_FRACTION = 0.45


def clip_phon_score(text: str) -> float:
    """Mejor score fonético/textual de los tokens de `text` vs 'baxy'."""
    from rapidfuzz import fuzz
    norm = _normalise(text or "")
    if not norm:
        return -1.0   # vacío: no evidencia (no cuenta a favor ni en contra)
    best = 0.0
    for tok in norm.split():
        for w in WAKES:
            wn = _normalise(w)
            best = max(best, fuzz.ratio(tok, wn))
            en_t, en_w = _metaphone(tok), _metaphone(wn)
            if en_t and en_w:
                best = max(best, fuzz.ratio(en_t, en_w))
            es_t, es_w = _metaphone_es(tok), _metaphone_es(wn)
            if es_t and es_w:
                best = max(best, fuzz.ratio(es_t, es_w))
    return best


def block_score(stt, clip_paths: list[Path], n_sample: int = 40) -> dict:
    """Puntúa una muestra del bloque. Devuelve dict con fraction_ok, n, etc.
    `stt` = ParakeetSTT ya cargado (lo comparte el caller entre bloques)."""
    import soundfile as sf
    step = max(1, len(clip_paths) // n_sample)
    sampled = clip_paths[::step][:n_sample]
    scores = []
    for p in sampled:
        a, _sr = sf.read(str(p), dtype="int16")
        if a.ndim > 1:
            a = a[:, 0]
        scores.append(clip_phon_score(stt.transcribe(a)))
    arr = np.asarray([s for s in scores if s >= 0])
    n_empty = sum(1 for s in scores if s < 0)
    frac = float(np.mean(arr >= CLIP_THR)) if arr.size else 0.0
    return {
        "n": len(sampled), "n_empty": n_empty,
        "fraction_ok": frac,
        "p50": float(np.median(arr)) if arr.size else 0.0,
        "passes": frac >= BLOCK_MIN_FRACTION,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace",
                           line_buffering=True)
    import _ort_throttle  # noqa: F401
    from gemma4_agent.voice.parakeet_stt import ParakeetSTT
    start, end = int(sys.argv[1]), int(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    stt = ParakeetSTT()
    assert stt.load(), stt.last_error
    pos = ROOT / "output" / "baxy" / "positive_train"
    paths = [pos / f"clip_{i:06d}.wav" for i in range(start, end)
             if (pos / f"clip_{i:06d}.wav").exists()]
    r = block_score(stt, paths, n)
    print(f"bloque [{start}:{end}] -> fraction_ok={r['fraction_ok']:.2f} "
          f"p50={r['p50']:.0f} vacios={r['n_empty']}/{r['n']} "
          f"=> {'PASS' if r['passes'] else 'FAIL'}")
    return 0 if r["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
