"""D5: ¿modified_beam_search (+hotwords) mejora a greedy en Parakeet?

Sobre los 84 comandos reales RED: WER y latencia p50 de
  (a) greedy + blank_penalty 0.8       (prod actual)
  (b) modified_beam_search             (sin hotwords)
  (c) modified_beam_search + hotwords  (apps del inventario, si sherpa acepta)
"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.parakeet_stt import (  # noqa: E402
    DEFAULT_MODEL_DIR, _blank_penalty, _optimal_threads,
)

MIC = ROOT / "data" / "stt_eval" / "real_mic"
TANDAS = ("20260523_015719", "20260523_020155")


def wer(ref, hyp):
    r, h = ref.lower().split(), hyp.lower().split()
    if not r:
        return 0.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r)][len(h)] / len(r)


def norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").casefold())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() or c.isspace() else " "
                            for c in t).split())


def make_rec(method: str, hotwords_file: str | None = None,
             blank_penalty: float | None = None):
    import sherpa_onnx
    md = DEFAULT_MODEL_DIR
    kw = dict(
        encoder=str(md / "encoder.int8.onnx"),
        decoder=str(md / "decoder.int8.onnx"),
        joiner=str(md / "joiner.int8.onnx"),
        tokens=str(md / "tokens.txt"),
        num_threads=_optimal_threads(),
        model_type="nemo_transducer",
        decoding_method=method,
    )
    if blank_penalty is not None:
        kw["blank_penalty"] = blank_penalty
    elif method == "greedy_search":
        kw["blank_penalty"] = _blank_penalty()
    if hotwords_file:
        kw["hotwords_file"] = hotwords_file
        kw["hotwords_score"] = 1.5
    return sherpa_onnx.OfflineRecognizer.from_transducer(**kw)


def run(rec, rows):
    total_wer, lats = 0.0, []
    for fname, expected in rows:
        audio, sr = sf.read(str(MIC / fname), dtype="float32")
        if audio.ndim > 1:
            audio = audio[:, 0]
        t0 = time.time()
        s = rec.create_stream()
        s.accept_waveform(sr, audio)
        rec.decode_stream(s)
        lats.append(time.time() - t0)
        total_wer += wer(norm(expected), norm(s.result.text))
    return total_wer / len(rows), sorted(lats)[len(lats) // 2]


rows = []
for line in (MIC / "manifest.tsv").read_text(encoding="utf-8").splitlines():
    p = line.split("\t")
    if len(p) >= 6 and p[5] in TANDAS and (MIC / p[0]).exists():
        rows.append((p[0], p[1]))
print(f"clips: {len(rows)}")

w, lat = run(make_rec("greedy_search"), rows)
print(f"greedy+bp0.8         WER={w:.4f} p50={lat * 1000:.0f}ms")

try:
    w, lat = run(make_rec("modified_beam_search"), rows)
    print(f"modified_beam        WER={w:.4f} p50={lat * 1000:.0f}ms")
except Exception as exc:
    print(f"modified_beam        ERROR: {exc}")

for bp in (0.4, 0.8):
    try:
        w, lat = run(make_rec("modified_beam_search", blank_penalty=bp), rows)
        print(f"beam+bp{bp}          WER={w:.4f} p50={lat * 1000:.0f}ms")
    except Exception as exc:
        print(f"beam+bp{bp}          ERROR: {exc}")

# ANTI-REGRESIÓN dominio terceros (FLEURS+chileno, voz ajena): la mejora en
# comandos no puede costar degradación en habla de terceros (CLAUDE.md).
ter_dir = ROOT / "data" / "stt_eval" / "real_es"
ter_rows = []
man = ter_dir / "manifest.tsv"
if man.exists():
    for line in man.read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) >= 2 and (ter_dir / p[0]).exists():
            ter_rows.append((p[0], p[1]))
if ter_rows:
    globals()["MIC"] = ter_dir  # run() lee de MIC
    import importlib
    g_mod = sys.modules[__name__]
    g_mod.MIC = ter_dir
    w, lat = run(make_rec("greedy_search"), ter_rows)
    print(f"TERCEROS greedy      WER={w:.4f} p50={lat * 1000:.0f}ms (n={len(ter_rows)})")
    w, lat = run(make_rec("modified_beam_search"), ter_rows)
    print(f"TERCEROS beam        WER={w:.4f} p50={lat * 1000:.0f}ms")
else:
    print("TERCEROS: manifest no encontrado, salteado")

# hotwords: apps reales del inventario
try:
    from gemma4_agent.voice.inventory import get_inventory
    inv = get_inventory()
    hw_path = ROOT / "documentacion" / "_hotwords_tmp.txt"
    apps = [a for a in inv.get("apps", [])][:60]
    hw_path.write_text("\n".join(apps), encoding="utf-8")
    w, lat = run(make_rec("modified_beam_search", str(hw_path)), rows)
    print(f"beam+hotwords({len(apps)}) WER={w:.4f} p50={lat * 1000:.0f}ms")
    hw_path.unlink(missing_ok=True)
except Exception as exc:
    print(f"beam+hotwords        ERROR: {type(exc).__name__}: {exc}")
