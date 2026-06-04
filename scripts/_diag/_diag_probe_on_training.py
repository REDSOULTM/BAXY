"""Corre el MISMO scoring del probe sobre clips de TRAINING (positive_test).

Si el trainer reportó recall ~0.84 sobre estos y el probe da ~0.84 -> probe OK
(el modelo sobreajusta, held-out 0.28 es real). Si el probe da ~0.28 sobre los
MISMOS clips -> el PROBE está roto (padding/normalización), el 0.28 es falso.
"""
from __future__ import annotations
import glob
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ort_throttle  # noqa: E402
_ort_throttle.apply(n_threads=2)

import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MDIR = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
CLF = ROOT / "output" / "hey_carter" / "hey_carter.onnx"
TRAIN_CLIPS = ROOT / "output" / "hey_carter" / "positive_test"
EMB_WIN, STRIDE, MIN_EMB, WIN = 76, 8, 16, 32000


def make_sess(p):
    so = ort.SessionOptions()
    so.intra_op_num_threads = 2
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    try:
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")
    except Exception:
        pass
    return ort.InferenceSession(str(p), sess_options=so, providers=["CPUExecutionProvider"])


mel = make_sess(MDIR / "melspectrogram.onnx"); mel_in = mel.get_inputs()[0].name
emb = make_sess(MDIR / "embedding_model.onnx"); emb_in = emb.get_inputs()[0].name
clf = make_sess(CLF); clf_in = clf.get_inputs()[0].name


def score(a):
    audio = a.astype(np.float32) / 32768.0
    padded = np.zeros(WIN, dtype=np.float32)
    clip = audio[-WIN:] if audio.size > WIN else audio
    padded[-clip.size:] = clip
    out = mel.run(None, {mel_in: padded[np.newaxis, :]})[0]
    if out.ndim == 4:
        out = out[:, 0, :, :]
    m = out[0] / 10.0 + 2.0
    if m.shape[0] < EMB_WIN:
        return 0.0
    embs = []
    for s in range(0, m.shape[0] - EMB_WIN + 1, STRIDE):
        e = emb.run(None, {emb_in: m[s:s + EMB_WIN][np.newaxis, :, :, np.newaxis].astype(np.float32)})[0]
        embs.append(e.squeeze())
    if len(embs) < MIN_EMB:
        return 0.0
    seq = np.stack(embs[-MIN_EMB:], axis=0)
    return float(clf.run(None, {clf_in: seq[np.newaxis, :, :].astype(np.float32)})[0][0, 0])


files = sorted(glob.glob(str(TRAIN_CLIPS / "*.wav")))[:300]
scores = []
for f in files:
    with wave.open(f, "rb") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    scores.append(score(a))
n = len(scores)
import statistics
print(f"probe sobre {n} clips de TRAINING (positive_test):")
for thr in [0.5, 0.25]:
    print(f"  recall@{thr} = {sum(1 for s in scores if s >= thr)/n:.3f}")
print(f"  score medio {statistics.mean(scores):.3f}, mediana {statistics.median(scores):.3f}, max {max(scores):.3f}")
print("  -> si ~0.84 PROBE OK (modelo sobreajusta); si ~0.28 PROBE ROTO")
