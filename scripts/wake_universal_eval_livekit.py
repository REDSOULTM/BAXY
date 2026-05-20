"""Universal wake-word evaluation for LiveKit ONNX models.

Sprint 7 (2026-05-19): mirror of scripts/wake_universal_eval.py but
uses LiveKit's WakeWordModel runtime (Python 3.11, in .venv_livekit).
Run with:

    .venv_livekit/Scripts/python.exe scripts/wake_universal_eval_livekit.py \
        --model output/hey_gemma/hey_gemma.onnx \
        --tag sprint7

Acceptance gate: universal_recall >= 0.60 AND fp_per_hour <= 1.00.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

POSITIVES_DIR = ROOT / "data" / "wake_universal_eval" / "positives"
NEGATIVES_DIR = ROOT / "data" / "wake_universal_eval" / "negatives"
OUT_DIR = ROOT / "bench_results_v2"

# LiveKit predicts on ~2 s windows. We slide that window over the
# audio with this hop to score every ~80 ms (similar cadence to OWW).
SAMPLE_RATE = 16000
PREDICT_WINDOW_S = 2.0
PREDICT_HOP_S = 0.5  # 0.5s hop = 4 predictions/sec, balance speed vs miss-rate
PREDICT_WINDOW_SAMPLES = int(PREDICT_WINDOW_S * SAMPLE_RATE)
PREDICT_HOP_SAMPLES = int(PREDICT_HOP_S * SAMPLE_RATE)

# Fire threshold; LiveKit recommends ~0.5 default.
FIRE_THRESHOLD = 0.5

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("wake_eval_lk")


@dataclass
class EvalResult:
    positives_total: int = 0
    positives_fired: int = 0
    positives_per_lang: dict[str, dict[str, int]] = field(default_factory=dict)
    positives_per_voice: dict[str, dict[str, int]] = field(default_factory=dict)
    negative_seconds: float = 0.0
    negative_files: int = 0
    negative_fires: int = 0
    negative_fires_per_speaker: dict[str, int] = field(default_factory=dict)
    elapsed_s: float = 0.0
    threshold: float = FIRE_THRESHOLD

    def as_dict(self) -> dict:
        pos_total = max(1, self.positives_total)
        neg_hours = self.negative_seconds / 3600.0
        per_lang = {
            lang: {
                "total": v["total"],
                "fired": v["fired"],
                "recall": round(v["fired"] / max(1, v["total"]), 4),
            }
            for lang, v in sorted(self.positives_per_lang.items())
        }
        per_voice = {
            voice: {
                "total": v["total"],
                "fired": v["fired"],
                "recall": round(v["fired"] / max(1, v["total"]), 4),
            }
            for voice, v in sorted(self.positives_per_voice.items())
        }
        return {
            "threshold": self.threshold,
            "positives": {
                "total": self.positives_total,
                "fired": self.positives_fired,
                "overall_recall": round(self.positives_fired / pos_total, 4),
                "per_language": per_lang,
                "per_voice": per_voice,
            },
            "negatives": {
                "files": self.negative_files,
                "total_seconds": round(self.negative_seconds, 1),
                "total_hours": round(neg_hours, 2),
                "fires": self.negative_fires,
                "fp_per_hour": round(
                    self.negative_fires / max(0.001, neg_hours), 3,
                ),
                "top_fp_speakers": sorted(
                    self.negative_fires_per_speaker.items(),
                    key=lambda x: -x[1],
                )[:10],
            },
            "elapsed_seconds": round(self.elapsed_s, 1),
        }


def _load_wav_int16(path: Path) -> tuple[np.ndarray, int]:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        with wave.open(str(path), "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
            sampwidth = wf.getsampwidth()
        if sampwidth != 2:
            return np.zeros(0, dtype=np.int16), sr
        audio = np.frombuffer(raw, dtype=np.int16)
        if n_channels > 1:
            audio = audio.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
        return audio, sr
    if suffix == ".flac":
        import soundfile as sf
        data, sr = sf.read(str(path), dtype="int16", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1).astype(np.int16)
        return data, sr
    return np.zeros(0, dtype=np.int16), 0


def _resample_int16(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    from math import gcd
    g = gcd(sr_in, sr_out)
    up, down = sr_out // g, sr_in // g
    import scipy.signal
    out = scipy.signal.resample_poly(audio.astype(np.float32), up, down)
    return np.clip(out, -32768, 32767).astype(np.int16)


def _voice_lang_from_filename(stem: str) -> tuple[str, str]:
    voice = stem.split("__")[0]
    lang = voice.split("_")[0]
    return voice, lang


def _speaker_from_path(p: Path) -> str:
    return p.parent.parent.name if p.parent.parent.name.isdigit() else "unknown"


def _score_audio(model, score_key: str, audio: np.ndarray) -> float:
    """Run sliding-window prediction over the full clip and return max score.

    Sprint 7.5 fix (2026-05-19): the LiveKit model was trained with the
    wake phrase positioned at the END of the 2-second window (LiveKit's
    augmentation pads zeros at the start). Padding short clips at the
    end instead of the start collapses scores to ~0. We pad at the
    start (or roll the window so audio ends at sample 32000).
    """
    if audio.size == 0:
        return 0.0
    # For short clips (< 2 s), pad with zeros at the START (wake at end).
    if audio.size < PREDICT_WINDOW_SAMPLES:
        padded = np.zeros(PREDICT_WINDOW_SAMPLES, dtype=audio.dtype)
        padded[-audio.size:] = audio
        try:
            scores = model.predict(padded)
        except Exception as exc:
            log.warning("predict failed on short clip: %s", exc)
            return 0.0
        return float(scores.get(score_key, 0.0))

    # For longer clips, slide a 2-second window. The wake might be at
    # any offset, so we still need sliding.
    max_score = 0.0
    n_windows = max(1, (audio.size - PREDICT_WINDOW_SAMPLES) // PREDICT_HOP_SAMPLES + 1)
    for i in range(n_windows):
        start = i * PREDICT_HOP_SAMPLES
        end = start + PREDICT_WINDOW_SAMPLES
        if end > audio.size:
            break
        window = audio[start:end]
        try:
            scores = model.predict(window)
        except Exception as exc:
            log.warning("predict failed: %s", exc)
            continue
        s = float(scores.get(score_key, 0.0))
        if s > max_score:
            max_score = s
    return max_score


def _count_fires_streaming(
    model, score_key: str, audio: np.ndarray, threshold: float,
) -> int:
    """Sliding-window over a long audio. Counts non-overlapping fires
    (consecutive windows above threshold count as ONE fire)."""
    if audio.size < PREDICT_WINDOW_SAMPLES:
        return 0
    fires = 0
    in_fire = False
    n_windows = (audio.size - PREDICT_WINDOW_SAMPLES) // PREDICT_HOP_SAMPLES + 1
    for i in range(n_windows):
        start = i * PREDICT_HOP_SAMPLES
        end = start + PREDICT_WINDOW_SAMPLES
        if end > audio.size:
            break
        window = audio[start:end]
        try:
            scores = model.predict(window)
        except Exception:
            continue
        s = float(scores.get(score_key, 0.0))
        if s >= threshold:
            if not in_fire:
                fires += 1
                in_fire = True
        else:
            in_fire = False
    return fires


def evaluate(
    model_path: Path,
    positives_dir: Path,
    negatives_dir: Path,
    threshold: float,
    max_negatives: int = -1,
    max_positives: int = -1,
) -> EvalResult:
    res = EvalResult(threshold=threshold)
    t0 = time.time()

    from livekit.wakeword.inference import WakeWordModel
    log.info("Loading LiveKit WakeWordModel: %s", model_path)
    model = WakeWordModel(models=[str(model_path)])
    score_key = model_path.stem
    log.info("Model loaded; score_key=%s", score_key)

    # ---- POSITIVES ---------------------------------------------------
    pos_files = sorted(positives_dir.glob("*.wav"))
    if max_positives > 0:
        pos_files = pos_files[:max_positives]
    log.info("Positives: %d clips", len(pos_files))

    for i, p in enumerate(pos_files):
        audio, sr = _load_wav_int16(p)
        if audio.size == 0:
            continue
        if sr != SAMPLE_RATE:
            audio = _resample_int16(audio, sr, SAMPLE_RATE)
        voice, lang = _voice_lang_from_filename(p.stem)
        max_s = _score_audio(model, score_key, audio)
        fired = 1 if max_s >= threshold else 0
        res.positives_total += 1
        res.positives_fired += fired
        ld = res.positives_per_lang.setdefault(lang, {"total": 0, "fired": 0})
        ld["total"] += 1
        ld["fired"] += fired
        vd = res.positives_per_voice.setdefault(voice, {"total": 0, "fired": 0})
        vd["total"] += 1
        vd["fired"] += fired
        if (i + 1) % 50 == 0 or (i + 1) == len(pos_files):
            log.info(
                "  pos %d/%d (recall=%.3f)",
                i + 1, len(pos_files),
                res.positives_fired / max(1, res.positives_total),
            )

    log.info(
        "Positives done: %d/%d (recall=%.3f)",
        res.positives_fired, res.positives_total,
        res.positives_fired / max(1, res.positives_total),
    )

    # ---- NEGATIVES ---------------------------------------------------
    neg_files = sorted(negatives_dir.rglob("*.flac"))
    if max_negatives > 0:
        neg_files = neg_files[:max_negatives]
    log.info("Negatives: %d files", len(neg_files))

    for i, p in enumerate(neg_files):
        audio, sr = _load_wav_int16(p)
        if audio.size == 0:
            continue
        if sr != SAMPLE_RATE:
            audio = _resample_int16(audio, sr, SAMPLE_RATE)
        speaker = _speaker_from_path(p)
        fires = _count_fires_streaming(model, score_key, audio, threshold)
        res.negative_seconds += audio.size / SAMPLE_RATE
        res.negative_files += 1
        res.negative_fires += fires
        if fires > 0:
            res.negative_fires_per_speaker[speaker] = (
                res.negative_fires_per_speaker.get(speaker, 0) + fires
            )
        if (i + 1) % 500 == 0 or (i + 1) == len(neg_files):
            log.info(
                "  neg %d/%d (sec=%.0f fires=%d fp/hr=%.2f)",
                i + 1, len(neg_files),
                res.negative_seconds, res.negative_fires,
                res.negative_fires / max(0.001, res.negative_seconds / 3600),
            )

    res.elapsed_s = time.time() - t0
    return res


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", type=Path, required=True,
        help="Path to LiveKit-exported ONNX wake model.",
    )
    parser.add_argument("--positives-dir", type=Path, default=POSITIVES_DIR)
    parser.add_argument("--negatives-dir", type=Path, default=NEGATIVES_DIR)
    parser.add_argument("--threshold", type=float, default=FIRE_THRESHOLD)
    parser.add_argument("--max-negatives", type=int, default=-1)
    parser.add_argument("--max-positives", type=int, default=-1)
    parser.add_argument("--tag", type=str, default="livekit")
    args = parser.parse_args()

    if not args.model.exists():
        log.error("Model not found: %s", args.model)
        return 1
    if not args.positives_dir.exists():
        log.error("Positives missing: %s", args.positives_dir)
        return 1
    if not args.negatives_dir.exists():
        log.error("Negatives missing: %s", args.negatives_dir)
        return 1

    res = evaluate(
        model_path=args.model,
        positives_dir=args.positives_dir,
        negatives_dir=args.negatives_dir,
        threshold=args.threshold,
        max_negatives=args.max_negatives,
        max_positives=args.max_positives,
    )

    out = res.as_dict()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"wake_universal_{args.tag}.json"
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    print()
    print("=" * 60)
    print(f"Universal LiveKit eval — threshold={args.threshold}")
    print("=" * 60)
    print(f"  positives    {out['positives']['fired']}/"
          f"{out['positives']['total']} "
          f"recall={out['positives']['overall_recall']:.3f}")
    print(f"  fp_per_hour  {out['negatives']['fp_per_hour']:.3f} "
          f"({out['negatives']['fires']} fires in "
          f"{out['negatives']['total_hours']:.2f}h)")
    print(f"  elapsed_s    {out['elapsed_seconds']:.1f}")
    print(f"  wrote        {out_path}")
    print()
    print("  per-language recall:")
    for lang, lv in out["positives"]["per_language"].items():
        print(f"    {lang:6s} {lv['fired']:3d}/{lv['total']:3d} "
              f"recall={lv['recall']:.3f}")

    # ---- GATE -------------------------------------------------------
    recall = out["positives"]["overall_recall"]
    fp_hr = out["negatives"]["fp_per_hour"]
    print()
    print("Sprint 7 acceptance gate:")
    print(f"  recall >= 0.60   ... actual {recall:.3f}  "
          f"{'PASS' if recall >= 0.60 else 'FAIL'}")
    print(f"  fp_per_hour <= 1 ... actual {fp_hr:.3f}  "
          f"{'PASS' if fp_hr <= 1.0 else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
