"""Fast, SAFE per-language recall probe for the Carter wake-word.

Scores the held-out positives with PURE onnxruntime + _ort_throttle (no spinning,
2 threads, affinity-capped) so it does NOT freeze the PC like the official eval
(which loads 3 ONNX with no SessionOptions + 5.3k negatives = ~2h). 500 clips in
~12s here.

WHAT IT MEASURES (and why per-language matters): global recall HIDES the failure.
The diagnosed root cause of Carter's 0.28 held-out is CROSS-LANGUAGE PHONETICS —
en_US recall ~1.00 but it/fr/es/pl/ar ~0.00, because the en-US-only TTS teaches
only the anglo /r/. A global number averages that into a single misleading figure.
This probe joins each clip to its language via HELD_OUT_VOICES and prints recall
PER LANGUAGE. That per-language table IS the anti-regression gate: universal use
(CLAUDE.md) requires no strong subgroup collapsing.

This probe measures RECALL only (positives). False-positive rate / fp-per-hour is
a separate axis — acotá los negativos en el eval oficial con --max-negatives; NO
lo corras acá (cuelga). Gate del proyecto: recall >= 0.60 ∧ fp/hr <= 1.0 @ thr 0.25.

Usage:
    python scripts/_diag_wake_recall_probe.py [N] [--threshold 0.5] [--model PATH]
        N         clips to score (default: all in positives_carter)
        --threshold  fire threshold (default 0.5; project gate calibrates at 0.25)
        --model      override classifier ONNX (default output/hey_carter/hey_carter.onnx)
"""
from __future__ import annotations

import argparse
import glob
import sys
import time
import wave
from collections import defaultdict
from pathlib import Path

# Throttle BEFORE importing onnxruntime — the whole point of this diagnosis.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ort_throttle  # noqa: E402

_ort_throttle.apply(n_threads=2)

import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402

# Map every held-out voice_name -> language tag for the per-language breakdown.
from wake_universal_voices import HELD_OUT_VOICES  # noqa: E402

_VOICE_LANG = {spec.voice_name: spec.lang for spec in HELD_OUT_VOICES}

ROOT = Path(__file__).resolve().parent.parent
MDIR = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
DEFAULT_CLF = ROOT / "output" / "hey_carter" / "hey_carter.onnx"
POS = ROOT / "data" / "wake_universal_eval" / "positives_carter"

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
    return ort.InferenceSession(
        str(p), sess_options=so, providers=["CPUExecutionProvider"],
    )


def _lang_of(filename: str) -> str:
    """Filenames are '<voice_name>__p<phrase>__<idx>.wav' (see generator)."""
    stem = Path(filename).name
    voice = stem.split("__", 1)[0]
    return _VOICE_LANG.get(voice, "??")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", type=int, default=0,
                    help="clips to score (0 = all)")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--model", type=str, default=str(DEFAULT_CLF))
    args = ap.parse_args()

    clf_path = Path(args.model)
    if not clf_path.exists():
        print(f"ERROR: classifier not found: {clf_path}")
        return 2
    if not POS.exists():
        print(f"ERROR: positives dir not found: {POS}\n"
              "Generate it: set GEMMA4_EVAL_WAKE=carter && "
              "python scripts/wake_universal_generate_positives.py")
        return 2

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
        padded[-clip.size:] = clip  # pad at START (wake at end) — Sprint 7.5 gotcha
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

    files = sorted(glob.glob(str(POS / "*.wav")))
    if args.n and args.n > 0:
        files = files[:args.n]
    if not files:
        print(f"ERROR: no clips in {POS}")
        return 2

    thr = args.threshold
    # per-language tallies: lang -> [fired, total]
    by_lang: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    fired_total = 0
    t_all = time.time()
    for f in files:
        with wave.open(f, "rb") as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        sc = score(a)
        hit = 1 if sc >= thr else 0
        fired_total += hit
        lang = _lang_of(f)
        by_lang[lang][0] += hit
        by_lang[lang][1] += 1
    total_t = time.time() - t_all

    n = len(files)
    print(f"\nmodel: {clf_path}")
    print(f"clips: {n}   threshold: {thr:.2f}   time: {total_t:.1f}s "
          f"({total_t / n:.3f}s/clip)")
    print(f"GLOBAL recall: {fired_total}/{n} = {fired_total / n:.3f}\n")

    print("per-language recall (THE anti-regression gate — universal use):")
    print(f"  {'lang':<6}{'recall':>8}   fired/total")
    worst = 1.0
    for lang in sorted(by_lang):
        fired, tot = by_lang[lang]
        r = fired / tot if tot else 0.0
        worst = min(worst, r)
        flag = "  <-- COLLAPSE" if r < 0.30 else ""
        print(f"  {lang:<6}{r:>8.3f}   {fired}/{tot}{flag}")
    print(f"\n  worst-language recall: {worst:.3f}")
    print("  (universal gate intent: NO language should collapse; the en-only-TTS "
          "failure shows as non-en langs near 0.0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
