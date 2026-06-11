"""Footprint RAM real de Whisper-small int8 (carga, inferencia, descarga)."""
import gc
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np  # noqa: E402
import psutil  # noqa: E402

from gemma4_agent.voice.stt import STT  # noqa: E402

p = psutil.Process()
rss0 = p.memory_info().rss / 1e6
t0 = time.time()
w = STT()
ok = w.load()
t_load = time.time() - t0
rss1 = p.memory_info().rss / 1e6
audio = np.zeros(16000, dtype=np.int16)
w.transcribe(audio, language="es")
rss2 = p.memory_info().rss / 1e6
w._model = None
del w
gc.collect()
time.sleep(0.5)
rss3 = p.memory_info().rss / 1e6
print(f"load={t_load:.1f}s ok={ok}")
print(f"RSS base={rss0:.0f}MB  +carga={rss1 - rss0:.0f}MB  +infer={rss2 - rss1:.0f}MB")
print(f"unload libera={rss2 - rss3:.0f}MB (residuo +{rss3 - rss0:.0f}MB sobre base)")
