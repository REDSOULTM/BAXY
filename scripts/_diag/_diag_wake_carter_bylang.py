"""READ-ONLY: full per-language recall of the baseline hey_carter model.

No training. Reuses the exact scoring path from _diag_wake_heldout_validate.py
but prints recall grouped by LANGUAGE (locale prefix) and per voice, so we can
see precisely which languages a respelling could plausibly rescue vs which are
phonetically out of reach for an espeak en-US TTS.
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
EMB_WIN, STRIDE, MIN_EMB, WIN, THR = 76, 8, 16, 32000, 0.25


def make_sess(p: Path):
    so = ort.SessionOptions()
    so.intra_op_num_threads = 2
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    try:
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")
    except Exception:
        pass
    return ort.InferenceSession(str(p), sess_options=so,
                               providers=["CPUExecutionProvider"])


def build_scorer(clf_path: Path):
    mel = make_sess(MDIR / "melspectrogram.onnx"); mel_in = mel.get_inputs()[0].name
    emb = make_sess(MDIR / "embedding_model.onnx"); emb_in = emb.get_inputs()[0].name
    clf = make_sess(clf_path); clf_in = clf.get_inputs()[0].name

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
    return score


def main() -> int:
    clf = ROOT / "output" / "hey_carter" / "hey_carter.onnx"
    pos = ROOT / "data" / "wake_universal_eval" / "positives_carter"
    score = build_scorer(clf)
    files = sorted(glob.glob(str(pos / "*.wav")))
    by_lang = defaultdict(lambda: [0, 0])
    by_voice = defaultdict(lambda: [0, 0])
    for f in files:
        with wave.open(f, "rb") as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        hit = 1 if score(a) >= THR else 0
        voice = Path(f).stem.split("__")[0]
        lang = voice.split("-")[0]            # es_AR, fr_FR, ...
        short = lang.split("_")[0]            # es, fr, ...
        by_lang[short][0] += hit; by_lang[short][1] += 1
        by_voice[voice][0] += hit; by_voice[voice][1] += 1
    print(f"OVERALL {sum(v[0] for v in by_lang.values())}/{len(files)}")
    print("=== by LANGUAGE ===")
    for lang in sorted(by_lang, key=lambda k: by_lang[k][0] / max(1, by_lang[k][1])):
        fr, tot = by_lang[lang]
        print(f"  {lang:4s} {fr:3d}/{tot:3d} = {fr/max(1,tot):.3f}")
    print("=== by VOICE ===")
    for v in sorted(by_voice, key=lambda k: by_voice[k][0] / max(1, by_voice[k][1])):
        fr, tot = by_voice[v]
        print(f"  {v:28s} {fr:2d}/{tot:2d} = {fr/max(1,tot):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
