"""Universal wake-word evaluation harness.

Measures the wake detector's behavior on:

  POSITIVES — synthetic 'hey gemma' clips from 25 held-out Piper voices
              across 13 languages. None of these voices were in v9
              training.  Each clip is short (~1 s). Recall = fraction
              of clips that fired at least one wake within the clip.

  NEGATIVES — LibriSpeech test-clean + dev-clean (~10 h English read
              speech, 80 speakers). None say 'hey gemma'. FP rate
              measured as fires per hour of negative audio.

The harness feeds audio through the same WakeDetector used in
production (gemma4_agent.voice.wake.WakeDetector), with the model under
test (default: hey_gemma.onnx). No VAD gate — matches pipeline.py
_handle_idle after the Sprint 5 fix.

Outputs JSON to bench_results_v2/wake_universal_<tag>.json with:
  - overall_recall, overall_precision-proxy, fp_per_hour
  - per_language recall + per-voice recall (where positives came from)
  - per-speaker FP counts on negatives (to spot biased false-fires)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import wave
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Force the runtime threshold/cooldown to known values for the eval so
# results are reproducible regardless of operator env vars.
os.environ.setdefault("GEMMA4_OWW_THRESHOLD", "0.3")
os.environ.setdefault("GEMMA4_OWW_PARTIAL", "0.15")

from gemma4_agent.voice.audio_io import CHUNK_SAMPLES, SAMPLE_RATE
from gemma4_agent.voice.wake import WakeDetector

POSITIVES_DIR = ROOT / "data" / "wake_universal_eval" / "positives"
NEGATIVES_DIR = ROOT / "data" / "wake_universal_eval" / "negatives"
OUT_DIR = ROOT / "bench_results_v2"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("wake_eval")


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
            "positives": {
                "total": self.positives_total,
                "fired": self.positives_fired,
                "overall_recall": round(
                    self.positives_fired / pos_total, 4,
                ),
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
    """Read int16 PCM from .wav (synth output) or .flac (LibriSpeech)."""
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
    elif suffix == ".flac":
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
    """Map 'en_US-amy-medium__p2__01' → (voice='en_US-amy-medium', lang='en')."""
    voice = stem.split("__")[0]
    lang = voice.split("_")[0]
    return voice, lang


def _speaker_from_path(p: Path) -> str:
    """LibriSpeech layout: .../<speaker>/<chapter>/<utt>.flac"""
    return p.parent.parent.name if p.parent.parent.name.isdigit() else "unknown"


def evaluate(
    model_path: Path | None,
    positives_dir: Path,
    negatives_dir: Path,
    max_negatives: int = -1,
    max_positives: int = -1,
) -> EvalResult:
    res = EvalResult()
    t0 = time.time()

    # ---- Load wake detector with the model under test ---------------
    # We have to patch CUSTOM_MODEL_PATH temporarily if the eval target
    # is a different file. For now we just rely on whatever
    # gemma4_agent/voice/models/oww/hey_gemma.onnx is.
    if model_path is not None:
        # Override the module-level constant before loading.
        import gemma4_agent.voice.wake as wake_mod
        wake_mod.CUSTOM_MODEL_PATH = Path(model_path)
        log.info("Using model: %s", model_path)

    fires_per_file: list[int] = []
    fires_per_file_idx = [0]

    def on_wake(phrase: str, score: float) -> None:
        fires_per_file_idx[0] += 1

    det = WakeDetector(on_wake=on_wake)
    if not det.load():
        log.error("WakeDetector failed to load: %s", det.last_error)
        return res
    log.info(
        "Wake loaded: model=%s, threshold=%.2f, partial=%.2f",
        "custom" if det.using_custom_model else "stock",
        float(os.environ["GEMMA4_OWW_THRESHOLD"]),
        float(os.environ["GEMMA4_OWW_PARTIAL"]),
    )

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
        # Reset between clips so a fire from clip N can't carry residue
        # into clip N+1 via the wake detector's rolling buffer.
        det.reset()
        fires_per_file_idx[0] = 0
        # Feed in pipeline chunks (512 samples).
        for j in range(0, audio.size, CHUNK_SAMPLES):
            chunk = audio[j:j + CHUNK_SAMPLES]
            if chunk.size < CHUNK_SAMPLES:
                # Pad final partial chunk with zeros.
                pad = np.zeros(CHUNK_SAMPLES - chunk.size, dtype=np.int16)
                chunk = np.concatenate([chunk, pad])
            det.feed(chunk)
        fired = 1 if fires_per_file_idx[0] > 0 else 0
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
                "  pos %d/%d (cumulative recall=%.3f)",
                i + 1, len(pos_files),
                res.positives_fired / max(1, res.positives_total),
            )

    log.info(
        "Positives done: %d/%d fired (overall recall=%.3f)",
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
        det.reset()
        fires_per_file_idx[0] = 0
        for j in range(0, audio.size, CHUNK_SAMPLES):
            chunk = audio[j:j + CHUNK_SAMPLES]
            if chunk.size < CHUNK_SAMPLES:
                pad = np.zeros(CHUNK_SAMPLES - chunk.size, dtype=np.int16)
                chunk = np.concatenate([chunk, pad])
            det.feed(chunk)
        fires = fires_per_file_idx[0]
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
        "--model", type=Path, default=None,
        help="Path to .onnx wake model. Defaults to "
             "gemma4_agent/voice/models/oww/hey_gemma.onnx",
    )
    parser.add_argument(
        "--positives-dir", type=Path, default=POSITIVES_DIR,
    )
    parser.add_argument(
        "--negatives-dir", type=Path, default=NEGATIVES_DIR,
    )
    parser.add_argument(
        "--max-negatives", type=int, default=-1,
        help="Cap on negative files (debug only)",
    )
    parser.add_argument(
        "--max-positives", type=int, default=-1,
        help="Cap on positive files (debug only)",
    )
    parser.add_argument(
        "--tag", type=str, default="default",
        help="Suffix for output JSON",
    )
    args = parser.parse_args()

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
    print("Universal wake eval — summary")
    print("=" * 60)
    print(f"  positives        {out['positives']['fired']}/"
          f"{out['positives']['total']} "
          f"recall={out['positives']['overall_recall']:.3f}")
    print(f"  fp_per_hour      {out['negatives']['fp_per_hour']:.3f} "
          f"({out['negatives']['fires']} fires in "
          f"{out['negatives']['total_hours']:.2f}h)")
    print(f"  elapsed_s        {out['elapsed_seconds']:.1f}")
    print(f"  wrote            {out_path}")
    print()
    print("  per-language recall:")
    for lang, lv in out["positives"]["per_language"].items():
        print(f"    {lang:6s} {lv['fired']:3d}/{lv['total']:3d} "
              f"recall={lv['recall']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
