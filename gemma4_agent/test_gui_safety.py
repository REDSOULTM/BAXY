"""Tests de las guardas de seguridad GUI (Fase 5 computer-use)."""
from __future__ import annotations

import os
import unittest

from gemma4_agent import gui_safety


class UserActivityGuardTest(unittest.TestCase):
    def setUp(self):
        # estado limpio por test
        gui_safety._last_agent_input_ts = 0.0
        for k in ("GEMMA4_GUI_USER_ACTIVITY_GUARD", "GEMMA4_GUI_USER_IDLE_MIN_MS"):
            os.environ.pop(k, None)

    def test_idle_ms_is_int_or_none(self):
        v = gui_safety.user_idle_ms()
        self.assertTrue(v is None or isinstance(v, int))

    def test_gate_off_never_blocks(self):
        os.environ["GEMMA4_GUI_USER_ACTIVITY_GUARD"] = "0"
        os.environ["GEMMA4_GUI_USER_IDLE_MIN_MS"] = "999999999"  # todo sería activo
        self.assertFalse(gui_safety.user_is_active())
        self.assertIsNone(gui_safety.check_user_activity())

    def test_high_threshold_blocks_when_recent_activity(self):
        # umbral altísimo -> cualquier input reciente cuenta como activo. Como el
        # harness/SO siempre tiene algún input dentro de minutos, idle < umbral.
        os.environ["GEMMA4_GUI_USER_IDLE_MIN_MS"] = "999999999"
        gui_safety._last_agent_input_ts = 0.0  # sin input del agente
        idle = gui_safety.user_idle_ms()
        if idle is None:
            self.skipTest("GetLastInputInfo no disponible")
        blk = gui_safety.check_user_activity()
        self.assertIsNotNone(blk)
        self.assertEqual(blk["blocked"], "user_active")
        self.assertFalse(blk["ok"])

    def test_agent_own_input_not_counted(self):
        # umbral altísimo (todo sería activo) PERO el agente acaba de teclear ->
        # la actividad reciente es del agente, NO del usuario -> no bloquea.
        os.environ["GEMMA4_GUI_USER_IDLE_MIN_MS"] = "999999999"
        idle = gui_safety.user_idle_ms()
        if idle is None:
            self.skipTest("GetLastInputInfo no disponible")
        gui_safety.note_agent_input()  # el agente acaba de actuar
        self.assertFalse(gui_safety.user_is_active())
        self.assertIsNone(gui_safety.check_user_activity())


class PasswordGuardTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("GEMMA4_GUI_PASSWORD_GUARD", None)

    def test_gate_off_returns_none(self):
        os.environ["GEMMA4_GUI_PASSWORD_GUARD"] = "0"
        self.assertIsNone(gui_safety.focused_is_password())
        self.assertIsNone(gui_safety.check_password_field())

    def test_focused_is_password_is_tri_state(self):
        # True / False / None — nunca lanza.
        v = gui_safety.focused_is_password()
        self.assertIn(v, (True, False, None))

    def test_check_password_returns_block_or_none(self):
        r = gui_safety.check_password_field()
        if r is not None:
            self.assertEqual(r["blocked"], "password_field")
            self.assertFalse(r["ok"])
            self.assertEqual(r["completion_status"], "secret_handoff")


class ActionBudgetTest(unittest.TestCase):
    """R8: cap de acciones físicas por turno (anti pop-up/visual injection)."""

    def setUp(self):
        for k in ("GEMMA4_GUI_ACTION_BUDGET", "GEMMA4_GUI_ACTION_BUDGET_GUARD"):
            os.environ.pop(k, None)
        gui_safety.reset_action_budget()

    def test_under_budget_ok(self):
        os.environ["GEMMA4_GUI_ACTION_BUDGET"] = "3"
        self.assertIsNone(gui_safety.check_action_budget())
        gui_safety.note_action()
        gui_safety.note_action()
        self.assertIsNone(gui_safety.check_action_budget())  # 2 < 3

    def test_over_budget_blocks(self):
        os.environ["GEMMA4_GUI_ACTION_BUDGET"] = "3"
        for _ in range(3):
            self.assertIsNone(gui_safety.check_action_budget())
            gui_safety.note_action()
        blk = gui_safety.check_action_budget()
        self.assertIsNotNone(blk)
        self.assertEqual(blk["blocked"], "action_budget_exhausted")
        self.assertFalse(blk["ok"])

    def test_reset_restores(self):
        os.environ["GEMMA4_GUI_ACTION_BUDGET"] = "1"
        gui_safety.note_action()
        self.assertIsNotNone(gui_safety.check_action_budget())
        gui_safety.reset_action_budget()
        self.assertIsNone(gui_safety.check_action_budget())

    def test_gate_off(self):
        os.environ["GEMMA4_GUI_ACTION_BUDGET"] = "1"
        os.environ["GEMMA4_GUI_ACTION_BUDGET_GUARD"] = "0"
        gui_safety.note_action()
        gui_safety.note_action()
        self.assertIsNone(gui_safety.check_action_budget())  # guard off -> nunca bloquea

    def test_default_budget_allows_multistep(self):
        # default 6 debe permitir holgado una misión de 2-3 pasos
        for _ in range(4):
            self.assertIsNone(gui_safety.check_action_budget())
            gui_safety.note_action()


if __name__ == "__main__":
    unittest.main()
