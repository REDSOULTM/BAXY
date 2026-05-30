"""Triage: ¿Parakeet (motor actual) transcribe BIEN voz real, o garabatea?
Corre los primeros N clips reales (data/stt_eval/real_es) por el Parakeet ACTUAL
y muestra crudo (motor) vs final (post-corrector) vs ground-truth. Decide si la
regresión es del MOTOR o ambiental (tu mic/voz)."""
import csv
import sys
import wave
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from gemma4_agent.voice.parakeet_stt import ParakeetSTT
from gemma4_agent.voice.corrector import FuzzyCorrector
from gemma4_agent.voice.inventory import get_inventory

N = 8
REAL = ROOT / "data" / "stt_eval" / "real_es"

pk = ParakeetSTT()
assert pk.load(), f"Parakeet no cargó: {pk.last_error}"
corr = FuzzyCorrector(get_inventory())


def load_wav(path):
    with wave.open(str(path), "rb") as wf:
        sr, ch, n = wf.getframerate(), wf.getnchannels(), wf.getnframes()
        audio = np.frombuffer(wf.readframes(n), dtype=np.int16)
    if ch > 1:
        audio = audio[::ch]
    return audio, sr


def wer(ref, hyp):
    r, hy = ref.lower().split(), hyp.lower().split()
    # Levenshtein de palabras
    d = [[0] * (len(hy) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(hy) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(hy) + 1):
            c = 0 if r[i - 1] == hy[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
    return d[len(r)][len(hy)] / max(1, len(r))


rows = list(csv.DictReader(open(REAL / "manifest_cl.tsv", encoding="utf-8"), delimiter="\t"))[:N]
print(f"[Parakeet] modelo: {getattr(pk, '_model_dir', '?')}")
print("=" * 78)
tot = 0.0
for r in rows:
    audio, sr = load_wav(REAL / r["file"])
    gt = r["transcription"].strip()
    raw = pk.transcribe(audio).strip()
    final = corr.correct(corr.strip_wake_phrase(raw)).strip()
    w = wer(gt, raw)
    tot += w
    print(f"[{r['file']}]  sr={sr}  WER_crudo={w:.2f}")
    print(f"  GT:    {gt}")
    print(f"  crudo: {raw}")
    if final != raw:
        print(f"  final: {final}   (corrector cambió)")
    print("-" * 78)
print("=" * 78)
print(f"[RESUMEN] WER crudo promedio sobre {len(rows)} clips reales: {tot / max(1, len(rows)):.3f}")
print("  (Parakeet RED reportó WER ~0.26 sobre comandos; >0.5 aquí = motor/ audio MAL)")
