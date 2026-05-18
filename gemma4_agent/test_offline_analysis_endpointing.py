"""P.1: scripts/testaudio_analysis._live_endpoint must close at
silence, not at fixed 15s. Sprint N analysis was unfairly
penalizing the pipeline because it gave Whisper 15s of audio
when the live pipeline gives only what's up to the first
VAD_SILENCE_MS gap."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _import_script():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "testaudio_analysis",
        ROOT / "scripts" / "testaudio_analysis.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class EndpointSimulationTest(unittest.TestCase):
    def setUp(self) -> None:
        from gemma4_agent.voice.audio_io import SAMPLE_RATE
        self.sr = SAMPLE_RATE
        self.mod = _import_script()

    def _build_audio(self, segments: list[tuple[float, bool]]) -> np.ndarray:
        """Build int16 audio from a list of (duration_s, is_speech).
        Speech = white noise at amplitude 5000; silence = zeros."""
        out = []
        rng = np.random.default_rng(seed=42)
        for dur, is_speech in segments:
            n = int(dur * self.sr)
            if is_speech:
                out.append((rng.standard_normal(n) * 5000).astype(np.int16))
            else:
                out.append(np.zeros(n, dtype=np.int16))
        return np.concatenate(out)

    def test_closes_at_silence_not_at_max(self) -> None:
        audio = self._build_audio([(2.0, True), (1.0, False), (5.0, True)])
        end_idx, reason = self.mod._live_endpoint(audio, 0, max_s=15.0)
        end_s = end_idx / self.sr
        self.assertLess(end_s, 4.0,
                        f"endpoint should close at silence, got {end_s:.2f}s")
        self.assertEqual(reason, "endpoint_silence")

    def test_max_window_when_no_silence(self) -> None:
        audio = self._build_audio([(20.0, True)])
        end_idx, reason = self.mod._live_endpoint(audio, 0, max_s=10.0)
        end_s = end_idx / self.sr
        self.assertAlmostEqual(end_s, 10.0, delta=0.5)
        self.assertEqual(reason, "max_window")

    def test_no_speech_returns_start(self) -> None:
        audio = self._build_audio([(5.0, False)])
        end_idx, reason = self.mod._live_endpoint(audio, 0, max_s=10.0)
        self.assertEqual(end_idx, 0)
        self.assertEqual(reason, "no_speech_detected")

    def test_rapid_fire_split_into_separate_calls(self) -> None:
        # "Gemma X. [800ms silence] Gemma Y." → 2 calls produce
        # 2 separate endpoints when called sequentially.
        audio = self._build_audio([
            (1.5, True),   # "Gemma abre Chrome"
            (0.8, False),  # pause > VAD_SILENCE_MS (500ms)
            (1.5, True),   # "Gemma cierra Steam"
        ])
        end1, _ = self.mod._live_endpoint(audio, 0, max_s=15.0)
        end1_s = end1 / self.sr
        self.assertLess(end1_s, 2.5,
                        f"first endpoint should close <2.5s, got {end1_s:.2f}s")
        end2, _ = self.mod._live_endpoint(audio, end1, max_s=15.0)
        end2_s = end2 / self.sr
        self.assertGreater(end2_s, end1_s + 1.0,
                           "second segment should contain the second utterance")


if __name__ == "__main__":
    unittest.main()
