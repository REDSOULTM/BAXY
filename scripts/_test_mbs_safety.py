"""GATE de seguridad antes de habilitar hotwords: ¿modified_beam_search (MBS)
es seguro en la sherpa-onnx instalada, o sufre el bug #3267 (~33% "Yeah."/vacío
sobre audio claro)? Compara greedy vs MBS(4) vs MBS(8) sobre la voz real del
usuario. Decide si vale la pena el camino de hotwords. Sin hotwords todavía
(MBS puro no necesita bpe.vocab)."""
import gc
import sys
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

MD = Path.home() / ".gemma4" / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
MIC = ROOT / "data" / "stt_eval" / "real_mic"
MAX_DUR = 6.0
# garbage canónico del #3267 + degeneraciones
GARBAGE = {"", "yeah", "yeah.", "you", "thank you", "."}


def make(method, maxp=4):
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(MD / "encoder.int8.onnx"), decoder=str(MD / "decoder.int8.onnx"),
        joiner=str(MD / "joiner.int8.onnx"), tokens=str(MD / "tokens.txt"),
        num_threads=4, model_type="nemo_transducer",
        decoding_method=method, max_active_paths=maxp, blank_penalty=0.8,
    )


def tx(rec, audio):
    s = rec.create_stream()
    s.accept_waveform(16000, (audio.astype(np.float32) / 32768.0))
    rec.decode_stream(s)
    return s.result.text.strip()


def norm(s):
    return " ".join("".join(c for c in s.lower() if c.isalnum() or c.isspace()).split())


rows = []
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
    rows.append((f[0], f[1]))

clips = []
for name, ref in rows:
    a, sr = sf.read(str(MIC / name), dtype="int16")
    if a.ndim > 1:
        a = a[:, 0]
    clips.append((name, ref, a))
print(f"[mbs-safety] {len(clips)} clips de voz real | sherpa-onnx {sherpa_onnx.__version__ if hasattr(sherpa_onnx,'__version__') else '?'}")


def run(method, maxp, label):
    rec = make(method, maxp)
    out = [(ref, tx(rec, a)) for _, ref, a in clips]
    del rec
    gc.collect()
    garbage = sum(1 for _, h in out if norm(h) in GARBAGE)
    return label, out, garbage


print("=" * 80)
results = {}
for method, maxp, label in [("greedy_search", 4, "greedy"),
                            ("modified_beam_search", 4, "MBS(4)"),
                            ("modified_beam_search", 8, "MBS(8)")]:
    label, out, garbage = run(method, maxp, label)
    results[label] = out
    print(f"[{label:8}] garbage/vacio (#3267): {garbage}/{len(out)}  ({100*garbage/len(out):.0f}%)")
print("=" * 80)
# agreement MBS(4) vs greedy + casos donde difieren
g = {norm(r): h for r, h in results["greedy"]} if False else results["greedy"]
diff = 0
print("Casos donde MBS(4) DIFIERE de greedy (primeros 20):")
for (ref, hg), (_, hm) in zip(results["greedy"], results["MBS(4)"]):
    if norm(hg) != norm(hm):
        diff += 1
        if diff <= 20:
            print(f"  ref={ref!r}")
            print(f"     greedy={hg!r}   MBS={hm!r}")
print("=" * 80)
print(f"[VEREDICTO] MBS(4) difiere de greedy en {diff}/{len(clips)} clips.")
print("  Si garbage MBS ~0% y las diferencias son MEJORAS de nombres -> MBS seguro, vale hotwords.")
print("  Si garbage MBS alto (~33%, #3267) -> NO usar MBS en esta version; quedarse en greedy.")
