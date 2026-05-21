"""The mmproj-leak relaunch trigger (#21690) must keep firing if a recycle
fails. The prior `_image_counter == THRESHOLD` check fired exactly once: if the
recycle returned early or failed WITHOUT resetting the counter, 41 != 40 so the
callback never fired again and VRAM leaked unbounded. Now it re-fires every
`threshold` images until a successful reset re-arms it.

Pure counter logic — no GPU, no server."""
from __future__ import annotations

import threading
import unittest

from gemma4_agent import multimodal as mm


class TestVisionRelaunchCounter(unittest.TestCase):
    def setUp(self):
        self.fired: list[int] = []
        mm.set_vision_relaunch_callback(self.fired.append)
        mm.reset_image_counter()

    def tearDown(self):
        mm.set_vision_relaunch_callback(None)
        mm.reset_image_counter()

    def _bump(self, n: int):
        for _ in range(n):
            mm._bump_image_counter()

    def test_fires_at_threshold(self):
        self._bump(mm.IMAGE_RELAUNCH_THRESHOLD)
        self.assertEqual(self.fired, [mm.IMAGE_RELAUNCH_THRESHOLD])

    def test_does_not_fire_before_threshold(self):
        self._bump(mm.IMAGE_RELAUNCH_THRESHOLD - 1)
        self.assertEqual(self.fired, [])

    def test_refires_when_recycle_did_not_reset(self):
        # Simulate a failed/early recycle: callback fires but NO reset happens.
        T = mm.IMAGE_RELAUNCH_THRESHOLD
        self._bump(2 * T)
        self.assertEqual(self.fired, [T, 2 * T],
                         "must keep retrying when the counter isn't reset")

    def test_reset_rearms_for_next_band(self):
        T = mm.IMAGE_RELAUNCH_THRESHOLD
        self._bump(T)            # fires at T
        mm.reset_image_counter()  # successful recycle resets
        self.fired.clear()
        self._bump(T)            # counter restarts -> fires again at T
        self.assertEqual(self.fired, [T])

    def test_counter_is_thread_safe(self):
        # Concurrent bumps must total exactly N and fire the right number of times.
        T = mm.IMAGE_RELAUNCH_THRESHOLD
        total = 4 * T

        def worker():
            for _ in range(total // 4):
                mm._bump_image_counter()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(mm.get_image_counter(), total)
        # Fires at each multiple of T up to total -> T, 2T, 3T, 4T.
        self.assertEqual(sorted(self.fired), [T, 2 * T, 3 * T, 4 * T])


if __name__ == "__main__":
    unittest.main()
