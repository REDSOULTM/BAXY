# -*- coding: utf-8 -*-
"""A/B: VAD raw-onnxruntime (sin torch) vs silero_vad wrapper (torch). Paridad de speech_prob
por frame sobre una secuencia de chunks. Si matchea, la reimplementación es correcta."""
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SR = 16000
FRAME = 512

# --- referencia: wrapper torch ---
import torch  # noqa: E402
from silero_vad import load_silero_vad  # noqa: E402

wrapper = load_silero_vad(onnx=True)
# ubicar el .onnx que usa el wrapper
model_path = None
for attr in ("session", "_session", "model"):
    obj = getattr(wrapper, attr, None)
    mp = getattr(obj, "_model_path", None) or getattr(obj, "model_path", None)
    if mp:
        model_path = mp
        break
if model_path is None:
    # fallback: el op18_ifless es el default de v5
    import silero_vad as _sv
    cands = list(Path(_sv.__file__).parent.rglob("*op18_ifless*.onnx")) or \
        list(Path(_sv.__file__).parent.rglob("silero_vad.onnx"))
    model_path = str(cands[0])
print("modelo onnx del wrapper:", Path(model_path).name)

# --- raw onnxruntime (sin torch) ---
import onnxruntime as ort  # noqa: E402

so = ort.SessionOptions()
so.intra_op_num_threads = 1
so.inter_op_num_threads = 1
sess = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
in_names = {i.name for i in sess.get_inputs()}
CONTEXT = 64  # Silero v5 @16k prepende 64 samples de contexto (ver OnnxWrapper.__call__)
state = np.zeros((2, 1, 128), dtype=np.float32)
context = np.zeros((1, CONTEXT), dtype=np.float32)


def raw_prob(chunk_f32: np.ndarray) -> float:
    global state, context
    x = np.concatenate([context, chunk_f32.reshape(1, -1)], axis=1).astype(np.float32)  # (1, 576)
    feed = {"input": x, "state": state}
    if "sr" in in_names:
        feed["sr"] = np.array(SR, dtype=np.int64)
    out, new_state = sess.run(None, feed)
    state = new_state
    context = x[:, -CONTEXT:]  # último contexto = cola del input concatenado
    return float(np.asarray(out).reshape(-1)[0])


# secuencia de prueba: silencio, ruido, "voz" (seno modulado), silencio — estado evoluciona
rng = np.random.RandomState(0)
chunks = []
for _ in range(10):
    chunks.append(np.zeros(FRAME, dtype=np.int16))                       # silencio
for _ in range(15):
    t = np.arange(FRAME)
    sig = (0.3 * np.sin(2 * np.pi * 200 * t / SR) * 32767).astype(np.int16)  # tono grave
    chunks.append(sig + rng.randint(-2000, 2000, FRAME).astype(np.int16))
for _ in range(10):
    chunks.append((rng.randn(FRAME) * 3000).astype(np.int16))             # ruido
for _ in range(8):
    chunks.append(np.zeros(FRAME, dtype=np.int16))                        # silencio

diffs = []
for ch in chunks:
    af = ch.astype(np.float32) / 32768.0
    p_ref = float(wrapper(torch.from_numpy(af), SR).item())
    p_raw = raw_prob(af)
    diffs.append(abs(p_ref - p_raw))

diffs = np.array(diffs)
print(f"frames: {len(diffs)} | max abs-diff prob: {diffs.max():.6f} | mean: {diffs.mean():.6f}")
print(f"frames con diff>0.01: {(diffs > 0.01).sum()} | >0.05: {(diffs > 0.05).sum()}")
print("PARIDAD OK" if diffs.max() < 0.02 else "REVISAR (desvio)")
