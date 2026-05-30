"""Compara greedy vs MBS(4) vs MBS(8) (todos + blank_penalty + corrector) sobre
la voz real del usuario, por ENTITY-RECALL. Decide el método de decoding."""
import gc
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import sherpa_onnx
import soundfile as sf

from gemma4_agent.voice.corrector import FuzzyCorrector
from gemma4_agent.voice.inventory import get_inventory

MD = Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
MIC = ROOT / "data" / "stt_eval" / "real_mic"
MAX_DUR = 6.0
corr = FuzzyCorrector(get_inventory())

_VERB = ("abre", "abri", "cierra", "cerr", "pon", "pone", "ponme", "reproduc", "toca",
         "play", "prende", "busca", "busc", "mira", "ver", "quiero", "escucha", "lanza",
         "ejecut", "inicia", "arranca", "mandale", "manda", "sube", "subi", "baja",
         "pausa", "silenci", "apaga", "recorda", "anda", "dale", "abrime")
_STOP = set("el la los las un una de en a y o con para del al me te se su mi tu lo es hoy plus video".split())


def norm(s):
    return " ".join("".join(c for c in s.lower() if c.isalnum() or c.isspace()).split())


def ents(ref):
    return [t for t in norm(ref).split() if t not in _STOP and not any(t.startswith(v) for v in _VERB)]


def erecall(ref, hyp):
    e = ents(ref)
    if not e:
        return 1.0
    h = set(norm(hyp).split())
    return sum(1 for x in e if x in h) / len(e)


def make(method, maxp):
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(MD / "encoder.int8.onnx"), decoder=str(MD / "decoder.int8.onnx"),
        joiner=str(MD / "joiner.int8.onnx"), tokens=str(MD / "tokens.txt"),
        num_threads=4, model_type="nemo_transducer", decoding_method=method,
        max_active_paths=maxp, blank_penalty=0.8)


def tx(rec, a):
    s = rec.create_stream()
    s.accept_waveform(16000, a.astype(np.float32) / 32768.0)
    rec.decode_stream(s)
    return s.result.text.strip()


clips = []
for ln in (MIC / "manifest.tsv").read_text(encoding="utf-8").splitlines()[1:]:
    f = ln.split("\t")
    if len(f) < 4:
        continue
    try:
        dur = float(f[3])
    except ValueError:
        continue
    if not f[1].strip() or dur > MAX_DUR:
        continue
    a, _ = sf.read(str(MIC / f[0]), dtype="int16")
    if a.ndim > 1:
        a = a[:, 0]
    clips.append((f[1], a))

n = len(clips)
print(f"[compare] {n} clips voz real | corrector + blank_penalty=0.8")
print("=" * 78)
print(f"{'metodo':10} {'ER crudo':>9} {'ER+corr':>9} {'nombre100%':>11} {'lat/clip':>9}")
for method, maxp, label in [("greedy_search", 4, "greedy"),
                            ("modified_beam_search", 4, "MBS(4)"),
                            ("modified_beam_search", 8, "MBS(8)")]:
    rec = make(method, maxp)
    er_raw = er_fin = full = 0.0
    t0 = time.monotonic()
    for ref, a in clips:
        raw = tx(rec, a)
        fin = corr.correct(corr.strip_wake_phrase(raw)).strip()
        er_raw += erecall(ref, raw)
        er_fin += erecall(ref, fin)
        full += (erecall(ref, fin) >= 0.999)
    lat = (time.monotonic() - t0) / n
    print(f"{label:10} {er_raw/n:>9.3f} {er_fin/n:>9.3f} {int(full):>8}/{n} {lat*1000:>7.0f}ms")
    del rec
    gc.collect()
print("=" * 78)
