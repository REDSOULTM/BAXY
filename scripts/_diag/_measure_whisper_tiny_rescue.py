"""¿whisper-TINY alcanza como rescatador? Footprint + carga + WER vs small
sobre los 84 comandos cortos REALES (la zona exacta del rescate), language=es."""
import gc
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import psutil  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.stt import STT, SAMPLE_RATE  # noqa: E402

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
    return " ".join("".join(c for c in t.lower() if c.isalnum() or c.isspace()).split())


mic = ROOT / "data" / "stt_eval" / "real_mic"
rows = []
for line in (mic / "manifest.tsv").read_text(encoding="utf-8").splitlines():
    p = line.split("\t")
    if len(p) >= 6 and p[5] in TANDAS and (mic / p[0]).exists():
        rows.append((p[0], p[1]))
print(f"clips: {len(rows)}")

proc = psutil.Process()
for size in ("tiny", "small"):
    gc.collect()
    rss0 = proc.memory_info().rss / 1e6
    t0 = time.time()
    w = STT(model_size=size)
    assert w.load(), w.last_error
    t_load = time.time() - t0
    rss1 = proc.memory_info().rss / 1e6
    total_wer, lats = 0.0, []
    for fname, expected in rows:
        data, _ = sf.read(str(mic / fname), dtype="int16")
        if data.ndim > 1:
            data = data[:, 0]
        t1 = time.time()
        text = w.transcribe(data, language="es")
        lats.append(time.time() - t1)
        total_wer += wer(norm(expected), norm(text or ""))
    p50 = sorted(lats)[len(lats) // 2]
    print(f"{size:5} load={t_load:.1f}s +RAM={rss1 - rss0:.0f}MB "
          f"WER={total_wer / len(rows):.4f} p50={p50 * 1000:.0f}ms")
    w._model = None
    del w
    gc.collect()
