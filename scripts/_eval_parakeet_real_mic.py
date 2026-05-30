"""Mide el pipeline STT ACTUAL (Parakeet greedy + corrector) sobre la VOZ REAL
del usuario (data/stt_eval/real_mic, grabado 2026-05-23). Compara contra el
ground-truth del manifest. Muestra cuánto RESCATA el corrector y dónde sigue
fallando. Es la medición que importa (voz del usuario, no held-out)."""
import sys
import unicodedata
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import soundfile as sf

from gemma4_agent.voice.parakeet_stt import ParakeetSTT
from gemma4_agent.voice.corrector import FuzzyCorrector
from gemma4_agent.voice.inventory import get_inventory

MIC = ROOT / "data" / "stt_eval" / "real_mic"
MAX_DUR = 6.0  # solo comandos (descarta el monólogo de 82s y outliers largos)

pk = ParakeetSTT()
assert pk.load(), f"Parakeet no cargó: {pk.last_error}"
corr = FuzzyCorrector(get_inventory())


def norm(s: str) -> str:
    s = s.lower().strip()
    s = "".join(c for c in s if c.isalnum() or c.isspace())
    return " ".join(s.split())


_VERB_ROOTS = ("abre", "abri", "cierra", "cerr", "pon", "pone", "ponme", "reproduc",
               "toca", "play", "prende", "busca", "busc", "mira", "ver", "quiero",
               "escucha", "lanza", "ejecut", "inicia", "arranca", "mandale", "manda",
               "sube", "subi", "baja", "pausa", "silenci", "apaga", "recorda", "recordame",
               "pone", "andá", "anda", "ponme", "dale", "abrime")
_STOP_E = set("el la los las un una de en a y o con para del al me te se su mi tu lo "
              "es hoy un plus video al".split())


def _entity_tokens(ref: str) -> list[str]:
    """Tokens de contenido del ref (el nombre propio): saca verbos+stopwords."""
    out = []
    for t in norm(ref).split():
        if t in _STOP_E:
            continue
        if any(t.startswith(r) for r in _VERB_ROOTS):
            continue
        out.append(t)
    return out


def entity_recall(ref: str, hyp: str) -> float:
    ents = _entity_tokens(ref)
    if not ents:
        return 1.0
    h = set(norm(hyp).split())
    return sum(1 for e in ents if e in h) / len(ents)


def wer(ref: str, hyp: str) -> float:
    r, h = norm(ref).split(), norm(hyp).split()
    if not r:
        return 0.0 if not h else 1.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            c = 0 if r[i - 1] == h[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
    return d[len(r)][len(h)] / len(r)


rows = []
for ln in (MIC / "manifest.tsv").read_text(encoding="utf-8").splitlines()[1:]:
    f = ln.split("\t")
    if len(f) < 4:
        continue
    name, ref, rec_hyp, dur = f[0], f[1], f[2], f[3]
    try:
        dur = float(dur)
    except ValueError:
        continue
    if not ref.strip() or dur > MAX_DUR:
        continue
    rows.append((name, ref, rec_hyp))

print(f"[eval] {len(rows)} comandos de voz real del usuario | modelo: {pk._model_dir.name}")
print("=" * 92)
sum_raw = sum_fin = 0.0
er_raw = er_fin = 0.0
full_raw = full_fin = 0          # comandos con el nombre 100% recuperado
rescued = broke = exact_fin = 0
lost = []                        # entity NO recuperada tras corrector
for name, ref, rec in rows:
    audio, sr = sf.read(str(MIC / name), dtype="int16")
    if audio.ndim > 1:
        audio = audio[:, 0]
    raw = pk.transcribe(audio).strip()
    final = corr.correct(corr.strip_wake_phrase(raw)).strip()
    wr, wf = wer(ref, raw), wer(ref, final)
    err, erf = entity_recall(ref, raw), entity_recall(ref, final)
    sum_raw += wr; sum_fin += wf
    er_raw += err; er_fin += erf
    full_raw += (err >= 0.999); full_fin += (erf >= 0.999)
    exact_fin += norm(ref) == norm(final)
    if erf > err:
        rescued += 1
    elif erf < err:
        broke += 1
    if erf < 0.999:
        lost.append((erf, ref, raw, final))

n = len(rows)
print(f"                          WER     | entity-recall | nombre 100% recuperado")
print(f"Parakeet crudo:          {sum_raw / n:.3f}   |    {er_raw / n:.3f}      | {full_raw}/{n}")
print(f"+ corrector (ACTUAL):    {sum_fin / n:.3f}   |    {er_fin / n:.3f}      | {full_fin}/{n}")
print(f"corrector entity: rescató {rescued} | rompió {broke} | neto {rescued - broke:+d}  | exactos {exact_fin}/{n}")
print("=" * 92)
print(f"Comandos donde el NOMBRE se pierde tras corrector ({len(lost)}):")
for erf, ref, raw, final in sorted(lost)[:30]:
    print(f"  ER={erf:.2f}  ref={ref!r}")
    print(f"           crudo={raw!r}  ->  final={final!r}")
