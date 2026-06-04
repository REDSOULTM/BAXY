"""Diagnostic: score distribution + per-language recall for hey_carter held-out.

Stratified across all 25 voices/13 langs. Prints histogram of raw scores and
recall at several thresholds. SAFE: pure onnxruntime + throttle, CPU only.
"""
from __future__ import annotations

import glob
import sys
import wave
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ort_throttle  # noqa: E402

_ort_throttle.apply(n_threads=2)

import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MDIR = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
CLF = ROOT / "gemma4_agent" / "voice" / "models" / "livekit" / "hey_gemma.onnx"
POS = ROOT / "data" / "wake_universal_eval" / "positives"

EMB_WIN = 76
STRIDE = 8
MIN_EMB = 16
WIN = 32000


def make_sess(p: Path):
    so = ort.SessionOptions()
    so.intra_op_num_threads = 2
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    try:
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")
    except Exception:
        pass
    return ort.InferenceSession(str(p), sess_options=so, providers=["CPUExecutionProvider"])


def main() -> int:
    mel = make_sess(MDIR / "melspectrogram.onnx")
    mel_in = mel.get_inputs()[0].name
    emb = make_sess(MDIR / "embedding_model.onnx")
    emb_in = emb.get_inputs()[0].name
    clf = make_sess(CLF)
    clf_in = clf.get_inputs()[0].name

    def score(audio_i16: np.ndarray) -> float:
        audio = audio_i16.astype(np.float32) / 32768.0
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
            w = m[s:s + EMB_WIN]
            e = emb.run(None, {emb_in: w[np.newaxis, :, :, np.newaxis].astype(np.float32)})[0]
            embs.append(e.squeeze())
        if len(embs) < MIN_EMB:
            return 0.0
        seq = np.stack(embs[-MIN_EMB:], axis=0)
        o = clf.run(None, {clf_in: seq[np.newaxis, :, :].astype(np.float32)})[0]
        return float(o[0, 0])

    files = sorted(glob.glob(str(POS / "*.wav")))
    # stratified: take every Nth to cover all voices but keep it fast (~120 clips)
    step = max(1, len(files) // 120)
    sample = files[::step]
    scores = []
    by_lang = defaultdict(list)
    for f in sample:
        with wave.open(f, "rb") as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        sc = score(a)
        scores.append(sc)
        lang = Path(f).name.split("_")[0]
        by_lang[lang].append(sc)
    scores = np.array(scores)
    print(f"N={len(scores)} clips (stratified from {len(files)})")
    print(f"score min={scores.min():.3f} p25={np.percentile(scores,25):.3f} "
          f"median={np.median(scores):.3f} p75={np.percentile(scores,75):.3f} max={scores.max():.3f}")
    print("histogram (bin width 0.1):")
    hist, edges = np.histogram(scores, bins=np.arange(0, 1.01, 0.1))
    for h, lo in zip(hist, edges[:-1]):
        print(f"  [{lo:.1f}-{lo+0.1:.1f}) {'#'*h} {h}")
    print("recall at thresholds:")
    for t in (0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5):
        print(f"  thr {t:.2f}: recall {np.mean(scores >= t):.3f}")
    print("per-lang recall @0.25 (mean score):")
    for lang in sorted(by_lang):
        arr = np.array(by_lang[lang])
        print(f"  {lang}: n={len(arr)} recall@.25={np.mean(arr>=0.25):.2f} meanscore={arr.mean():.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
