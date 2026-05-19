"""Build the openWakeWord training dataset for "hey gemma".

Reads Grabacion (2).wav + testaudio_v2_expected.json (operator
annotated 105 wakes) and produces:

  wake_dataset/
    positive/wake_001.wav .. wake_105.wav  (1.2s clips around each wake)
    positive_aug/wake_NNN_augM.wav         (4 augmentations per positive)
    negative_hard/neg_NNN.wav              (~139 clips from gaps in audio)
    manifest.json
  wake_dataset.zip                          (everything above, packed)

Usage:
  python scripts/build_wake_dataset.py
  python scripts/build_wake_dataset.py --no-augmentation
  python scripts/build_wake_dataset.py --out custom_dir/
  python scripts/build_wake_dataset.py --no-zip

The zip is the artifact the operator uploads to the Sprint R3
Colab notebook (scripts/notebooks/train_hey_gemma.ipynb).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import random
import sys
import wave
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import SAMPLE_RATE  # noqa: E402

VOICE_TESTS = ROOT / "gemma4_agent" / "voice" / "tests"
DEFAULT_WAV = VOICE_TESTS / "Grabación (2).wav"
DEFAULT_EXPECTED = VOICE_TESTS / "testaudio_v2_expected.json"

WIN_PRE_S = 0.3
WIN_POST_S = 0.9
CLIP_DURATION_S = WIN_PRE_S + WIN_POST_S      # 1.2s exact
CLIP_SAMPLES = int(CLIP_DURATION_S * SAMPLE_RATE)

# Negatives shorter than this RMS are discarded (silence-only does
# not help the model discriminate).
SILENCE_RMS_THRESHOLD = 50.0

logger = logging.getLogger("build_wake_dataset")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def _load_wav(path: Path) -> np.ndarray:
    """Load a mono 16kHz PCM 16-bit WAV into a 1-D int16 numpy array."""
    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE, (
            f"expected {SAMPLE_RATE} Hz, got {wf.getframerate()}"
        )
        assert wf.getnchannels() == 1, "expected mono"
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _write_wav(path: Path, audio: np.ndarray) -> None:
    """Write a 1-D int16 array to a mono 16kHz PCM 16-bit WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.astype(np.int16, copy=False).tobytes())


# --- Clip extraction ----------------------------------------------

def extract_positive_clip(
    audio: np.ndarray, wake_ts_s: float,
    win_pre_s: float = WIN_PRE_S, win_post_s: float = WIN_POST_S,
) -> np.ndarray:
    """Extract a 1.2s clip centered around `wake_ts_s` with the
    configured pre/post window. Pads with silence (zeros) at the
    head/tail if the window extends beyond the audio bounds.

    Returns an int16 array of exactly CLIP_SAMPLES samples.
    """
    target_samples = int((win_pre_s + win_post_s) * SAMPLE_RATE)
    wake_idx = int(wake_ts_s * SAMPLE_RATE)
    start_idx = wake_idx - int(win_pre_s * SAMPLE_RATE)
    end_idx = wake_idx + int(win_post_s * SAMPLE_RATE)

    # Head pad if start is before 0.
    head_pad = 0
    if start_idx < 0:
        head_pad = -start_idx
        start_idx = 0
    # Tail pad if end exceeds audio length.
    tail_pad = 0
    if end_idx > len(audio):
        tail_pad = end_idx - len(audio)
        end_idx = len(audio)

    clip = audio[start_idx:end_idx]
    if head_pad > 0:
        clip = np.concatenate([np.zeros(head_pad, dtype=np.int16), clip])
    if tail_pad > 0:
        clip = np.concatenate([clip, np.zeros(tail_pad, dtype=np.int16)])
    # Guard against off-by-one rounding -- snap exactly to target.
    if clip.size < target_samples:
        clip = np.concatenate([clip, np.zeros(target_samples - clip.size,
                                              dtype=np.int16)])
    elif clip.size > target_samples:
        clip = clip[:target_samples]
    return clip


def _rms(clip: np.ndarray) -> float:
    if clip.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(clip.astype(np.float32) ** 2)))


def extract_hard_negatives(
    audio: np.ndarray, wake_timestamps_s: list[float],
    win_pre_s: float = WIN_PRE_S, win_post_s: float = WIN_POST_S,
    silence_rms_threshold: float = SILENCE_RMS_THRESHOLD,
) -> tuple[list[np.ndarray], int]:
    """Cut 1.2s windows from the audio that do NOT overlap any
    positive window. Apply RMS filter to discard silence-only.

    Returns (kept_clips, n_skipped_silence).
    """
    target_samples = int((win_pre_s + win_post_s) * SAMPLE_RATE)
    pre_samples = int(win_pre_s * SAMPLE_RATE)
    post_samples = int(win_post_s * SAMPLE_RATE)

    # Forbidden intervals (in sample indices) covered by positives.
    forbidden: list[tuple[int, int]] = []
    for ts in wake_timestamps_s:
        idx = int(ts * SAMPLE_RATE)
        forbidden.append((idx - pre_samples, idx + post_samples))
    forbidden.sort()

    def overlaps_forbidden(start: int, end: int) -> bool:
        for a, b in forbidden:
            if start < b and end > a:
                return True
        return False

    kept: list[np.ndarray] = []
    skipped_silence = 0
    step = target_samples  # non-overlapping windows
    for start in range(0, len(audio) - target_samples + 1, step):
        end = start + target_samples
        if overlaps_forbidden(start, end):
            continue
        clip = audio[start:end].copy()
        if _rms(clip) < silence_rms_threshold:
            skipped_silence += 1
            continue
        kept.append(clip)
    return kept, skipped_silence


# --- Augmentation ------------------------------------------------

def _add_gaussian_noise(clip: np.ndarray, snr_db: float = 20.0,
                        rng: np.random.Generator | None = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng()
    clip_f32 = clip.astype(np.float32)
    signal_power = float(np.mean(clip_f32 ** 2)) + 1e-12
    noise_power = signal_power / (10 ** (snr_db / 10))
    noise = rng.standard_normal(clip_f32.shape).astype(np.float32) * np.sqrt(noise_power)
    out = clip_f32 + noise
    return np.clip(out, -32768, 32767).astype(np.int16)


def _pitch_shift(clip: np.ndarray, n_steps: float) -> np.ndarray:
    """Pitch-shift via librosa. Lazy import (librosa is heavy)."""
    import librosa  # type: ignore
    clip_f32 = clip.astype(np.float32) / 32768.0
    shifted = librosa.effects.pitch_shift(
        y=clip_f32, sr=SAMPLE_RATE, n_steps=n_steps,
    )
    # librosa may return slightly different length; trim/pad to original.
    if shifted.shape[0] < clip.shape[0]:
        shifted = np.concatenate(
            [shifted, np.zeros(clip.shape[0] - shifted.shape[0],
                               dtype=np.float32)]
        )
    elif shifted.shape[0] > clip.shape[0]:
        shifted = shifted[:clip.shape[0]]
    return np.clip(shifted * 32768.0, -32768, 32767).astype(np.int16)


def _time_stretch(clip: np.ndarray, rate: float) -> np.ndarray:
    """Time-stretch via librosa. Output length differs by 1/rate;
    we trim/pad to original to keep window size constant."""
    import librosa  # type: ignore
    clip_f32 = clip.astype(np.float32) / 32768.0
    stretched = librosa.effects.time_stretch(y=clip_f32, rate=rate)
    if stretched.shape[0] < clip.shape[0]:
        stretched = np.concatenate(
            [stretched, np.zeros(clip.shape[0] - stretched.shape[0],
                                 dtype=np.float32)]
        )
    elif stretched.shape[0] > clip.shape[0]:
        stretched = stretched[:clip.shape[0]]
    return np.clip(stretched * 32768.0, -32768, 32767).astype(np.int16)


def augment_clip(
    clip: np.ndarray, seed: int,
) -> list[tuple[str, np.ndarray]]:
    """Produce 4 augmentations of `clip`. Returns (label, audio)
    pairs. If a specific augmentation raises (e.g. librosa edge
    case), it's skipped silently and the rest still run -- the
    caller reports the total."""
    rng = np.random.default_rng(seed)
    out: list[tuple[str, np.ndarray]] = []

    try:
        out.append(("aug1", _add_gaussian_noise(clip, snr_db=20.0, rng=rng)))
    except Exception as exc:
        logger.warning("noise aug failed: %s", exc)

    try:
        n_steps = 2.0 if rng.random() < 0.5 else -2.0
        out.append(("aug2", _pitch_shift(clip, n_steps=n_steps)))
    except Exception as exc:
        logger.warning("pitch aug failed: %s", exc)

    try:
        rate = 0.95 if rng.random() < 0.5 else 1.05
        out.append(("aug3", _time_stretch(clip, rate=rate)))
    except Exception as exc:
        logger.warning("stretch aug failed: %s", exc)

    # 4th = noise + pitch combined for extra diversity.
    try:
        noisy = _add_gaussian_noise(clip, snr_db=15.0, rng=rng)
        n_steps = 1.0 if rng.random() < 0.5 else -1.0
        out.append(("aug4", _pitch_shift(noisy, n_steps=n_steps)))
    except Exception as exc:
        logger.warning("combo aug failed: %s", exc)

    return out


# --- Main driver --------------------------------------------------

def build(
    audio_path: Path, expected_path: Path,
    out_dir: Path, do_augmentation: bool, do_zip: bool,
) -> dict:
    print(f"Reading {expected_path.name}...")
    with open(expected_path, encoding="utf-8") as fh:
        expected_data = json.load(fh)
    wakes = sorted(
        float(w["timestamp_s"])
        for w in expected_data.get("wakes", [])
        if w.get("expected", True)
    )
    print(f"Loaded {len(wakes)} wakes from operator annotations.")

    print(f"Loading audio from {audio_path.name}...")
    audio = _load_wav(audio_path)
    audio_duration_s = len(audio) / SAMPLE_RATE

    pos_dir = out_dir / "positive"
    aug_dir = out_dir / "positive_aug"
    neg_dir = out_dir / "negative_hard"
    for d in (pos_dir, aug_dir, neg_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"Extracting positive clips into {pos_dir}/...")
    for i, ts in enumerate(wakes, start=1):
        clip = extract_positive_clip(audio, ts)
        _write_wav(pos_dir / f"wake_{i:03d}.wav", clip)
    print(f"Wrote {len(wakes)} positives.")

    augmented_count = 0
    if do_augmentation:
        print(f"Generating augmentations (4 per clip) into {aug_dir}/...")
        for i, ts in enumerate(wakes, start=1):
            clip = extract_positive_clip(audio, ts)
            for label, aug_clip in augment_clip(clip, seed=i):
                _write_wav(aug_dir / f"wake_{i:03d}_{label}.wav", aug_clip)
                augmented_count += 1
        print(f"Wrote {augmented_count} augmented clips "
              f"({len(wakes) * 4} expected, may differ if some failed).")
    else:
        print("Skipping augmentation (--no-augmentation).")

    print("Extracting hard negatives (no-overlap windows)...")
    negatives, n_skipped = extract_hard_negatives(audio, wakes)
    for i, clip in enumerate(negatives, start=1):
        _write_wav(neg_dir / f"neg_{i:03d}.wav", clip)
    print(f"Wrote {len(negatives)} hard negatives "
          f"(skipped {n_skipped} silence-only candidates).")

    manifest = {
        "source_audio": audio_path.name,
        "source_duration_s": round(audio_duration_s, 2),
        "window_pre_s": WIN_PRE_S,
        "window_post_s": WIN_POST_S,
        "positives": {
            "raw_count": len(wakes),
            "augmented_count": augmented_count,
            "total": len(wakes) + augmented_count,
        },
        "hard_negatives": {
            "count": len(negatives),
            "rms_filter_threshold": SILENCE_RMS_THRESHOLD,
            "silence_skipped": n_skipped,
        },
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "audio_format": "PCM 16-bit, 16kHz, mono",
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {manifest_path.relative_to(ROOT) if manifest_path.is_absolute() and manifest_path.is_relative_to(ROOT) else manifest_path}")

    if do_zip:
        zip_path = ROOT / "wake_dataset.zip"
        print(f"Packing {out_dir.name}/ -> {zip_path.name} ...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(out_dir.rglob("*")):
                if p.is_file():
                    zf.write(p, arcname=p.relative_to(out_dir.parent))
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"Wrote {zip_path.name} ({size_mb:.1f} MB).")
        manifest["zip_path"] = str(zip_path.name)
        manifest["zip_size_mb"] = round(size_mb, 1)

    print("Done.")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the openWakeWord training dataset for 'hey gemma'."
    )
    parser.add_argument(
        "--audio", type=Path, default=DEFAULT_WAV,
        help=f"Source WAV (default: {DEFAULT_WAV})",
    )
    parser.add_argument(
        "--expected", type=Path, default=DEFAULT_EXPECTED,
        help=f"Annotated wake timestamps JSON (default: {DEFAULT_EXPECTED})",
    )
    parser.add_argument(
        "--out", type=Path, default=ROOT / "wake_dataset",
        help="Output directory (default: wake_dataset/)",
    )
    parser.add_argument(
        "--no-augmentation", action="store_true",
        help="Skip augmentation (faster, for debugging cuts)",
    )
    parser.add_argument(
        "--no-zip", action="store_true",
        help="Don't pack the output into a .zip",
    )
    args = parser.parse_args(argv)

    if not args.audio.exists():
        print(f"ERROR: audio not found: {args.audio}", file=sys.stderr)
        return 2
    if not args.expected.exists():
        print(f"ERROR: expected.json not found: {args.expected}", file=sys.stderr)
        return 2

    build(
        audio_path=args.audio,
        expected_path=args.expected,
        out_dir=args.out,
        do_augmentation=not args.no_augmentation,
        do_zip=not args.no_zip,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
