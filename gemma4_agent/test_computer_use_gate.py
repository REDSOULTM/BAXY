"""Test del GATE de activación de _try_computer_use (agent.py), offline (sin LLM/GUI).

Cubre el fix 2026-05-25: nombres coloquiales de app ("wsp"/"wasap" -> WhatsApp) que
NO matchean ningún título de ventana por texto, pero el PLANIFICADOR normaliza el
nombre en focus_app y ESE sí matchea una ventana abierta -> la capa se activa.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.agent import Gemma4Agent


class ComputerUseGateTest(unittest.TestCase):
    def _agent(self):
        # instancia vacía sin __init__ (no levanta cliente/servidor).
        ag = Gemma4Agent.__new__(Gemma4Agent)
        ag.trace = MagicMock()
        ag.trace.new_turn_id.return_value = "t1"
        ag._last_turn_ts = 0
        ag._remember_executed_tools = lambda ev: None
        return ag

    def test_slang_app_activates_via_plan_focus_arg(self):
        # "escribile a migue en wsp hola": el texto NO matchea ventana ("wsp" no está
        # en "WhatsApp"), pero el plan focus_app="WhatsApp" SÍ -> debe activarse.
        ag = self._agent()
        plan = [{"op": "focus_app", "arg": "WhatsApp"}, {"op": "open_chat", "arg": "migue"},
                {"op": "type", "arg": "hola"}, {"op": "send", "arg": ""}]
        # _window_title_in_text: None para el texto crudo, "WhatsApp" para el arg.
        def wtit(s):
            return "WhatsApp" if s == "WhatsApp" else None
        with patch.object(Gemma4Agent, "_window_title_in_text", side_effect=wtit), \
             patch("gemma4_agent.computer_use.plan_for", return_value=plan), \
             patch("gemma4_agent.computer_use.PlanExecutor") as PE, \
             patch("gemma4_agent.computer_use.summarize_result", return_value="ok"):
            PE.return_value.execute.return_value = {"ok": True, "steps": plan, "focused_app": "WhatsApp"}
            r = ag._try_computer_use("escribile a migue en wsp hola", "t1")
        self.assertIsNotNone(r)  # se activó pese a que "wsp" no matchea por texto

    def test_no_open_app_does_not_activate(self):
        # ni el texto ni el arg de focus_app matchean una ventana abierta -> None.
        ag = self._agent()
        plan = [{"op": "focus_app", "arg": "Telegram"}, {"op": "open_chat", "arg": "x"}]
        with patch.object(Gemma4Agent, "_window_title_in_text", return_value=None), \
             patch("gemma4_agent.computer_use.plan_for", return_value=plan):
            r = ag._try_computer_use("mandale algo a x en telegram", "t1")
        self.assertIsNone(r)

    def test_disabled_by_env(self):
        import os
        ag = self._agent()
        os.environ["GEMMA4_COMPUTER_USE"] = "0"
        try:
            r = ag._try_computer_use("calculá 2+2 en la calculadora", "t1")
        finally:
            os.environ.pop("GEMMA4_COMPUTER_USE", None)
        self.assertIsNone(r)


if __name__ == "__main__":
    unittest.main()
