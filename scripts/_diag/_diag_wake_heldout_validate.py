"""One-shot validation: is carter's 0.28 held-out recall REAL or a test artifact?

Reuses the EXACT scoring path from _diag_wake_recall_probe.py (pad-at-start,
sliding max, threshold 0.5) and runs it on:
  - carter model vs positives_carter, broken down per phrase-id and per voice
  - gemma  model vs positives        (same path) as a fairness control

If gemma reproduces ~0.74 and carter ~0.28 with the SAME code on the SAME
voice set, the test is fair and 0.28 is real (overfit), not an artifact.
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

EMB_WIN = 76
STRIDE = 8
MIN_EMB = 16
WIN = 32000
THR = 0.25  # the brief's reported threshold for both numbers


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


def build_scorer(clf_path: Path):
    mel = make_sess(MDIR / "melspectrogram.onnx")
    mel_in = mel.get_inputs()[0].name
    emb = make_sess(MDIR / "embedding_model.onnx")
    emb_in = emb.get_inputs()[0].name
    clf = make_sess(clf_path)
    clf_in = clf.get_inputs()[0].name

    def score(audio_i16: np.ndarray) -> float:
        audio = audio_i16.astype(np.float32) / 32768.0
        padded = np.zeros(WIN, dtype=np.float32)
        clip = audio[-WIN:] if audio.size > WIN else audio
        padded[-clip.size:] = clip  # pad at START (wake at end)
        out = mel.run(None, {mel_in: padded[np.newaxis, :]})[0]
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

    return score


def run(clf_path: Path, pos_dir: Path, label: str, per_phrase: bool):
    score = build_scorer(clf_path)
    files = sorted(glob.glob(str(pos_dir / "*.wav")))
    fired = 0
    by_phrase = defaultdict(lambda: [0, 0])  # pid -> [fired, total]
    by_voice = defaultdict(lambda: [0, 0])
    for f in files:
        with wave.open(f, "rb") as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        sc = score(a)
        hit = 1 if sc >= THR else 0
        fired += hit
        stem = Path(f).stem
        voice = stem.split("__")[0]
        pid = stem.split("__")[1] if "__" in stem else "?"
        by_phrase[pid][0] += hit
        by_phrase[pid][1] += 1
        by_voice[voice][0] += hit
        by_voice[voice][1] += 1
    print(f"\n=== {label}: {clf_path.name} on {pos_dir.name} @thr{THR} ===")
    print(f"  OVERALL recall = {fired}/{len(files)} = {fired/max(1,len(files)):.3f}")
    if per_phrase:
        for pid in sorted(by_phrase):
            fr, tot = by_phrase[pid]
            print(f"    {pid}: {fr:3d}/{tot:3d} = {fr/max(1,tot):.3f}")
        # worst/best voices
        vr = sorted(by_voice.items(), key=lambda kv: kv[1][0] / max(1, kv[1][1]))
        print("  worst 5 voices:")
        for v, (fr, tot) in vr[:5]:
            print(f"    {v:28s} {fr:2d}/{tot:2d} = {fr/max(1,tot):.3f}")
        print("  best 5 voices:")
        for v, (fr, tot) in vr[-5:]:
            print(f"    {v:28s} {fr:2d}/{tot:2d} = {fr/max(1,tot):.3f}")
    return fired / max(1, len(files))


def main() -> int:
    carter_clf = ROOT / "output" / "hey_carter" / "hey_carter.onnx"
    gemma_clf = MDIR / "hey_gemma.onnx"
    pos_carter = ROOT / "data" / "wake_universal_eval" / "positives_carter"
    pos_gemma = ROOT / "data" / "wake_universal_eval" / "positives"

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = all

    if carter_clf.exists():
        run(carter_clf, pos_carter, "CARTER", per_phrase=True)
    else:
        print("carter clf missing:", carter_clf)
    # Fairness control on gemma (full or sample)
    if gemma_clf.exists():
        run(gemma_clf, pos_gemma, "GEMMA (control)", per_phrase=True)
    else:
        print("gemma clf missing:", gemma_clf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
