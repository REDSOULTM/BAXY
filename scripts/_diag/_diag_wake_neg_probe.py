"""Tiny SAFE probe: time the NEGATIVES sliding-window cost on 2 FLAC files.

This is the suspected bottleneck of the full eval. We only touch 2 files
with the throttle ON to project the full 5323-file cost WITHOUT hanging.
"""
from __future__ import annotations

import glob
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ort_throttle  # noqa: E402

_ort_throttle.apply(n_threads=2)

import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import soundfile as sf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MDIR = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
CLF = ROOT / "output" / "hey_carter" / "hey_carter.onnx"
NEG = ROOT / "data" / "wake_universal_eval" / "negatives"

EMB_WIN = 76
STRIDE = 8
MIN_EMB = 16
WIN = 32000
HOP = 8000  # 0.5s hop (matches eval PREDICT_HOP_SAMPLES)


def make_sess(p: Path):
    so = ort.SessionOptions()
    so.intra_op_num_threads = 2
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    try:
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")
    except Exception:
        pass
    return ort.InferenceSession(
        str(p), sess_options=so, providers=["CPUExecutionProvider"],
    )


mel = make_sess(MDIR / "melspectrogram.onnx")
mel_in = mel.get_inputs()[0].name
emb = make_sess(MDIR / "embedding_model.onnx")
emb_in = emb.get_inputs()[0].name
clf = make_sess(CLF)
clf_in = clf.get_inputs()[0].name


def score_window(win_f32: np.ndarray) -> float:
    out = mel.run(None, {mel_in: win_f32[np.newaxis, :]})[0]
    if out.ndim == 4:
        out = out[:, 0, :, :]
    m = out[0] / 10.0 + 2.0
    if m.shape[0] < EMB_WIN:
        return 0.0
    embs = []
    for s in range(0, m.shape[0] - EMB_WIN + 1, STRIDE):
        w = m[s:s + EMB_WIN]
        e = emb.run(
            None, {emb_in: w[np.newaxis, :, :, np.newaxis].astype(np.float32)},
        )[0]
        embs.append(e.squeeze())
    if len(embs) < MIN_EMB:
        return 0.0
    seq = np.stack(embs[-MIN_EMB:], axis=0)
    o = clf.run(None, {clf_in: seq[np.newaxis, :, :].astype(np.float32)})[0]
    return float(o[0, 0])


def main() -> int:
    files = sorted(glob.glob(str(NEG / "**" / "*.flac"), recursive=True))[:2]
    total_windows = 0
    t_all = time.time()
    for f in files:
        data, sr = sf.read(f, dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        nwin = max(0, (data.size - WIN) // HOP + 1)
        t = time.time()
        for i in range(nwin):
            win = data[i * HOP:i * HOP + WIN]
            if win.size < WIN:
                break
            score_window(win)
        total_windows += nwin
        print("%.1fs audio, %d windows, %.2fs (%.3fs/win)  %s"
              % (data.size / sr, nwin, time.time() - t,
                 (time.time() - t) / max(1, nwin), Path(f).name))
    dt = time.time() - t_all
    per_win = dt / max(1, total_windows)
    print("--- %d windows in %.2fs (%.4fs/win) ---" % (total_windows, dt, per_win))
    # Projection: 5323 files, avg ~10.8s -> ~18 windows/file
    proj_windows = 5323 * 18
    print("--- projected 5323 negs (~%d windows): %.0fs = %.1f min ---"
          % (proj_windows, proj_windows * per_win, proj_windows * per_win / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
