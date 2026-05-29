"""Tests de verify_post_action (Fase 1 computer-use).

Cierra el "click/type ciego": tras una acción GUI, mide si el SO cambió por
frame-diff de ROI + foreground, SIN VLM. Best-effort: nunca rompe la acción.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.computer_use_pkg import gui_verify as gv



class GuiVerifyTest(unittest.TestCase):
    def setUp(self):
        os.environ["GEMMA4_GUI_VERIFY"] = "1"

    def tearDown(self):
        os.environ.pop("GEMMA4_GUI_VERIFY", None)

    def test_gate_off_returns_none(self):
        os.environ["GEMMA4_GUI_VERIFY"] = "0"
        b = gv.capture_before(10, 10)
        self.assertTrue(b.get("_off"))
        self.assertIsNone(gv.verify_after(b)["state_changed"])

    def test_changed_when_roi_hash_differs(self):
        # before con un hash; after captura otro -> changed True. Mockeamos _capture.
        before = {"roi": {"left": 0, "top": 0, "width": 10, "height": 10},
                  "hash": 0, "fg": 111, "x": 5, "y": 5}
        orig = gv._capture
        gv._capture = lambda roi: gv._Cap(hash=0xFFFFFFFFFFFFFFFF, fg_hwnd=111)  # 64 bits distintos
        try:
            v = gv.verify_after(before)
            self.assertIs(v["state_changed"], True)
            self.assertGreaterEqual(v["signals"]["roi_hamming"], gv._DHASH_HAMMING_MIN)
        finally:
            gv._capture = orig

    def test_not_changed_when_roi_identical_and_fg_same(self):
        before = {"roi": {"left": 0, "top": 0, "width": 10, "height": 10},
                  "hash": 12345, "fg": 222, "x": 5, "y": 5}
        orig = gv._capture
        gv._capture = lambda roi: gv._Cap(hash=12345, fg_hwnd=222)  # idéntico
        try:
            v = gv.verify_after(before)
            self.assertIs(v["state_changed"], False)  # pudimos medir y NO cambió
        finally:
            gv._capture = orig

    def test_foreground_change_alone_counts_as_changed(self):
        before = {"roi": {"left": 0, "top": 0, "width": 10, "height": 10},
                  "hash": 999, "fg": 100, "x": 5, "y": 5}
        orig = gv._capture
        gv._capture = lambda roi: gv._Cap(hash=999, fg_hwnd=200)  # ROI igual, FG cambió
        try:
            v = gv.verify_after(before)
            self.assertIs(v["state_changed"], True)
            self.assertTrue(v["signals"]["fg_changed"])
        finally:
            gv._capture = orig

    def test_none_when_unmeasurable(self):
        before = {"roi": None, "hash": None, "fg": None, "x": None, "y": None}
        orig = gv._capture
        gv._capture = lambda roi: gv._Cap(hash=None, fg_hwnd=None)
        try:
            self.assertIsNone(gv.verify_after(before)["state_changed"])
        finally:
            gv._capture = orig

    def test_capture_before_none_coords_does_not_crash(self):
        b = gv.capture_before(None, None)
        self.assertIsInstance(b, dict)

    def test_empty_before_token_safe(self):
        self.assertIsNone(gv.verify_after({})["state_changed"])
        self.assertIsNone(gv.verify_after(None)["state_changed"])


if __name__ == "__main__":
    unittest.main()
