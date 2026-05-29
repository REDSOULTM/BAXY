"""Tests del gate de visión de la cascada GUI (Fase 8)."""
from __future__ import annotations

import os
import unittest

from gemma4_agent.computer_use_pkg import gui_vision_gate as g



class VisionGateTest(unittest.TestCase):
    def setUp(self):
        for k in ("GEMMA4_GUI_VISION_GATE", "GEMMA4_GUI_VISION_BUDGET"):
            os.environ.pop(k, None)
        g.reset_budget()

    def test_budget_default_two(self):
        self.assertTrue(g.can_escalate()[0])
        g.note_escalation()
        self.assertTrue(g.can_escalate()[0])
        g.note_escalation()
        ok, why = g.can_escalate()
        self.assertFalse(ok)
        self.assertIn("budget_exhausted", why)

    def test_reset_restores(self):
        g.note_escalation(); g.note_escalation()
        self.assertFalse(g.can_escalate()[0])
        g.reset_budget()
        self.assertTrue(g.can_escalate()[0])

    def test_gate_off(self):
        os.environ["GEMMA4_GUI_VISION_GATE"] = "0"
        ok, why = g.can_escalate()
        self.assertFalse(ok)
        self.assertEqual(why, "vision_gate_off")

    def test_custom_budget(self):
        os.environ["GEMMA4_GUI_VISION_BUDGET"] = "1"
        self.assertTrue(g.can_escalate()[0])
        g.note_escalation()
        self.assertFalse(g.can_escalate()[0])

    def test_budget_state_shape(self):
        s = g.budget_state()
        self.assertEqual(set(s), {"used", "budget", "enabled"})

    def test_idle_reset(self):
        # forzar un last_use viejo -> al consultar, _maybe_idle_reset limpia
        import time
        g.note_escalation(); g.note_escalation()
        self.assertFalse(g.can_escalate()[0])
        g._last_use_ts = time.time() - (g._MISSION_IDLE_RESET_S + 10)
        self.assertTrue(g.can_escalate()[0])  # misión "nueva" por inactividad


if __name__ == "__main__":
    unittest.main()
