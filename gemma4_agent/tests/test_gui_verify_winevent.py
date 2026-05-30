"""ITEM 2 (perfection roadmap 2026-05-29): 3ª señal de verify GUI vía
SetWinEventHook. Fusión 2-de-3, gated OFF, observación pura (no SendInput).

Foco: la LÓGICA de fusión (un evento UI rescata el false-PASS del frame-diff) y
el gating. El hook Win32 real necesita una app + ventana (verificación en vivo);
acá mockeamos stop_and_check para ejercer la fusión sin GUI.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from gemma4_agent.computer_use_pkg import gui_verify_winevent as WEV
from gemma4_agent.computer_use_pkg import gui_verify as GV


class WinEventGateTest(unittest.TestCase):
    def test_default_off(self):
        prev = os.environ.pop("GEMMA4_GUI_VERIFY_WINEVENT", None)
        try:
            self.assertFalse(WEV.winevent_enabled())
            self.assertIsNone(WEV.start_recording())  # off -> no recorder
        finally:
            if prev is not None:
                os.environ["GEMMA4_GUI_VERIFY_WINEVENT"] = prev

    def test_stop_check_none_handle_is_none(self):
        self.assertIsNone(WEV.stop_and_check(None, 12345))


class FusionTest(unittest.TestCase):
    """La 3ª señal entra a la fusión 2-de-3 sin romper la honestidad."""

    def _verify_after(self, *, hash_before, hash_after, fg_before, fg_after, winevent):
        before = {"roi": (0, 0, 10, 10), "hash": hash_before,
                  "fg": fg_before, "_winevent": "h"}
        # Mock _capture para devolver el 'after' deseado.
        cap = mock.MagicMock(); cap.hash = hash_after; cap.fg_hwnd = fg_after
        with mock.patch.object(GV, "_capture", return_value=cap), \
             mock.patch.object(GV, "_SETTLE_S", 0), \
             mock.patch("gemma4_agent.computer_use_pkg.gui_verify_winevent.stop_and_check",
                        return_value=winevent):
            return GV.verify_after(before)

    def test_winevent_rescues_pixel_false(self):
        # El toggle invisible: el ROI NO cambió (mismo hash) pero hubo evento UI.
        # Antes daría state_changed=False (false-PASS); ahora True.
        r = self._verify_after(hash_before=100, hash_after=100,
                               fg_before=1, fg_after=1, winevent=True)
        self.assertIs(r["state_changed"], True)
        self.assertIs(r["signals"]["winevent_fired"], True)

    def test_pixel_false_no_event_stays_false(self):
        # ROI no cambió Y no hubo evento -> False (honesto, no inventa cambio).
        r = self._verify_after(hash_before=100, hash_after=100,
                               fg_before=1, fg_after=1, winevent=False)
        self.assertIs(r["state_changed"], False)

    def test_pixel_true_unaffected(self):
        # ROI cambió (hamming alto) -> True sin importar el evento.
        r = self._verify_after(hash_before=0, hash_after=0xFFFFFFFFFFFFFFFF,
                               fg_before=1, fg_after=1, winevent=None)
        self.assertIs(r["state_changed"], True)

    def test_nothing_measurable_is_none(self):
        # Sin pixel medible y sin evento -> None (honesto: no sabemos).
        r = self._verify_after(hash_before=None, hash_after=None,
                               fg_before=1, fg_after=1, winevent=None)
        self.assertIsNone(r["state_changed"])

    def test_winevent_none_keeps_two_signal_behavior(self):
        # Con winevent=None (gated off / no disponible), la fusión es como antes.
        r = self._verify_after(hash_before=100, hash_after=100,
                               fg_before=1, fg_after=1, winevent=None)
        self.assertIs(r["state_changed"], False)  # pixel false, sin 3ª señal


if __name__ == "__main__":
    unittest.main()
