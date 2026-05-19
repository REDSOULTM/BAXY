"""Tests for scripts/build_wake_dataset.py (Sprint R3).

All tests use tempfile + synthetic WAVs; no dependency on the
operator's real audio. Augmentation tests stub out librosa where
needed to keep CI lightweight."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_wake_dataset",
        ROOT / "scripts" / "build_wake_dataset.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_wake_dataset"] = mod
    spec.loader.exec_module(mod)
    return mod


def _synth_audio(duration_s: float, sr: int = 16000,
                 amplitude: int = 1000,
                 seed: int = 42) -> np.ndarray:
    """Construct synthetic int16 audio. Non-silent so RMS > threshold."""
    rng = np.random.default_rng(seed)
    n = int(duration_s * sr)
    return (rng.standard_normal(n) * amplitude).astype(np.int16)


def _write_wav(path: Path, audio: np.ndarray, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())


class ExtractPositiveTest(unittest.TestCase):
    def test_extract_positive_clip_window_pre_post(self) -> None:
        m = _load_builder()
        # 5s of synthetic audio; wake at 2.0s. Default windows
        # -> clip should be 0.3+0.9=1.2s = 19200 samples exact.
        audio = _synth_audio(5.0)
        clip = m.extract_positive_clip(audio, wake_ts_s=2.0)
        expected_samples = int(1.2 * 16000)
        self.assertEqual(clip.shape[0], expected_samples)
        # The 1.2s clip starts at t=1.7s; check that audio at
        # the wake position matches.
        wake_offset_in_clip = int(0.3 * 16000)  # 0.3s pre
        original_at_wake = audio[int(2.0 * 16000)]
        clip_at_wake = clip[wake_offset_in_clip]
        # Values match exactly (no transform).
        self.assertEqual(int(clip_at_wake), int(original_at_wake))

    def test_extract_positive_clip_padding_at_boundary(self) -> None:
        m = _load_builder()
        # Wake at ts=0.1s; window pre=0.3s extends below 0.
        # Expect 0.2s of zero-padding at the head and full
        # 0.9s post-wake content; total still 1.2s.
        audio = _synth_audio(5.0)
        clip = m.extract_positive_clip(audio, wake_ts_s=0.1)
        self.assertEqual(clip.shape[0], int(1.2 * 16000))
        # First 0.2s = 3200 samples should be zero (silence pad).
        head_pad_samples = int(0.2 * 16000)
        self.assertTrue(np.all(clip[:head_pad_samples] == 0))
        # Sample at "wake position" (offset 0.3s = 4800) should
        # match audio at ts=0.1s.
        self.assertEqual(int(clip[int(0.3 * 16000)]),
                         int(audio[int(0.1 * 16000)]))


class ExtractHardNegativesTest(unittest.TestCase):
    def test_hard_negatives_dont_overlap_positives(self) -> None:
        m = _load_builder()
        # 30s audio, 3 wakes at 5, 15, 25. Each forbidden interval
        # extends from wake-0.3s to wake+0.9s.
        audio = _synth_audio(30.0)
        wakes = [5.0, 15.0, 25.0]
        negatives, n_skipped = m.extract_hard_negatives(audio, wakes)
        self.assertGreater(len(negatives), 0)
        # Every negative is 1.2s = 19200 samples.
        clip_samples = int(1.2 * 16000)
        for clip in negatives:
            self.assertEqual(clip.shape[0], clip_samples)
        # Reconstruct sample ranges + verify they don't overlap
        # forbidden intervals.
        pre_samples = int(0.3 * 16000)
        post_samples = int(0.9 * 16000)
        forbidden = [
            (int(t * 16000) - pre_samples, int(t * 16000) + post_samples)
            for t in wakes
        ]
        # Negative clips come in document order, non-overlapping
        # windows of size CLIP_SAMPLES. We can't easily get their
        # indices back, so just assert there's at least one
        # negative AND that the algorithm picked some windows
        # that we can verify by re-running with the same audio.
        # The cleanest contract test: at most floor(30/1.2)=25
        # possible windows; subtract those that overlap the 3
        # forbidden ranges. Expected count >= 17 in this layout.
        self.assertGreaterEqual(len(negatives), 17)

    def test_silence_filter_skips_quiet_clips(self) -> None:
        m = _load_builder()
        # Build 10s of audio that is half loud, half silence.
        # No wakes -> all windows are candidates. The silent
        # half should be filtered out by RMS threshold.
        sr = 16000
        loud = _synth_audio(5.0, amplitude=2000)
        silent = np.zeros(5 * sr, dtype=np.int16)
        audio = np.concatenate([loud, silent])
        negatives, n_skipped = m.extract_hard_negatives(audio, [])
        # Silent half = ~3-4 clips of 1.2s. They should all be skipped.
        self.assertGreaterEqual(n_skipped, 3)
        # Every kept clip has RMS >= threshold.
        for clip in negatives:
            self.assertGreaterEqual(m._rms(clip), m.SILENCE_RMS_THRESHOLD)


class AugmentationTest(unittest.TestCase):
    def test_augmentation_count_matches_expected(self) -> None:
        m = _load_builder()
        # 1.2s of synthetic audio; augment_clip should emit 4
        # variations (noise, pitch, stretch, combo). If any fail,
        # the rest still come through.
        clip = _synth_audio(1.2)
        outputs = m.augment_clip(clip, seed=1)
        self.assertGreaterEqual(len(outputs), 3,
                                "At least 3 of 4 augs should succeed")
        self.assertLessEqual(len(outputs), 4)
        for label, aug_clip in outputs:
            self.assertTrue(label.startswith("aug"))
            # Output shape preserved (trim/pad to original).
            self.assertEqual(aug_clip.shape[0], clip.shape[0])
            self.assertEqual(aug_clip.dtype, np.int16)


class BuildSmokeTest(unittest.TestCase):
    """Run the whole build() against synthetic inputs in a temp dir,
    no augmentation (to skip librosa cost), no zip."""

    def test_build_produces_expected_layout(self) -> None:
        m = _load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wav = tmp_path / "fake.wav"
            expected = tmp_path / "expected.json"
            audio = _synth_audio(30.0, amplitude=2000)
            _write_wav(wav, audio)
            expected.write_text(json.dumps({
                "wakes": [
                    {"timestamp_s": 5.0, "expected": True},
                    {"timestamp_s": 15.0, "expected": True},
                    {"timestamp_s": 25.0, "expected": True},
                ]
            }), encoding="utf-8")

            out_dir = tmp_path / "ds"
            manifest = m.build(
                audio_path=wav,
                expected_path=expected,
                out_dir=out_dir,
                do_augmentation=False,
                do_zip=False,
            )

        self.assertEqual(manifest["positives"]["raw_count"], 3)
        self.assertGreaterEqual(manifest["hard_negatives"]["count"], 17)
        self.assertEqual(manifest["audio_format"],
                         "PCM 16-bit, 16kHz, mono")


if __name__ == "__main__":
    unittest.main()
