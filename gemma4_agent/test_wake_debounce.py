"""Wake detector debounce calibration (hotfix M.2 2026-05-18).

The testaudio analysis from Sprint M.1 surfaced that the operator
fired 6 raw wakes in a 5-minute recording, but only 3 reached
the callback — the other 3 were swallowed by a 2.0s debounce.
The fix lowers WAKE_DEBOUNCE_S to 0.8s to recover rapid-fire
wakes without re-introducing TTS-echo or wake-tail false fires.

This test pins the constant value range so a future drift is
visible in the diff.
"""
from __future__ import annotations

import unittest


class WakeDebounceConstantTest(unittest.TestCase):
    def test_debounce_in_calibrated_range(self) -> None:
        # Anything below 0.5s risks wake-word tail re-fires (Vosk
        # emits partials that span the wake phrase). Anything
        # above 1.5s risks dropping legitimate rapid follow-ups.
        # The empirical sweet spot is in [0.6, 1.2].
        from gemma4_agent.voice.wake import WAKE_DEBOUNCE_S
        self.assertGreaterEqual(WAKE_DEBOUNCE_S, 0.5)
        self.assertLessEqual(WAKE_DEBOUNCE_S, 1.5)

    def test_debounce_below_typical_tts_duration(self) -> None:
        # Default Piper TTS utterances are 1+ seconds; if the
        # debounce is ABOVE that, a user can't interrupt with a
        # new wake right after Gemma finishes speaking. We want
        # debounce < typical TTS duration.
        from gemma4_agent.voice.wake import WAKE_DEBOUNCE_S
        self.assertLess(WAKE_DEBOUNCE_S, 1.0)


if __name__ == "__main__":
    unittest.main()
