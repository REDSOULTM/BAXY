"""Tests de computer_use como TOOL del registry (rediseño 2026-05-25).

Antes computer-use era un short-circuit pre-LLM (_try_computer_use) con un gate que
secuestraba turnos — eso se ELIMINÓ (causaba: "abre steam"->enfoca/minimiza, WhatsApp
->caja equivocada, "router no ofrece tools"). Ahora `computer_use(goal=...)` es UNA
tool más: el router la ofrece y el LLM la llama. Estos tests cubren el impl de la tool
(t_computer_use) y que el router la rankee para operar-en-app.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.tools_pkg.tools import ToolRegistry


class ComputerUseToolTest(unittest.TestCase):
    def _reg(self):
        reg = ToolRegistry.__new__(ToolRegistry)
        reg.parent_agent = MagicMock()  # el executor reusa helpers del agente
        return reg

    def test_requires_goal(self):
        reg = self._reg()
        r = reg.t_computer_use({})
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("status"), "needs_user")

    def test_runs_plan_executor_and_returns_ok(self):
        reg = self._reg()
        plan = [{"op": "focus_app", "arg": "discord"}, {"op": "open_chat", "arg": "juan"},
                {"op": "type", "arg": "hola"}, {"op": "send", "arg": ""}]
        with patch("gemma4_agent.computer_use.plan_for", return_value=plan), \
             patch("gemma4_agent.computer_use.PlanExecutor") as PE, \
             patch("gemma4_agent.computer_use.summarize_result", return_value="Listo, le escribí hola a juan."):
            PE.return_value.execute.return_value = {"ok": True, "steps": plan, "focused_app": "Discord"}
            r = reg.t_computer_use({"goal": "escribile a juan en discord hola"})
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        self.assertEqual(r["completion_status"], "done")
        self.assertIn("juan", r["reply"])

    def test_unverified_plan_reports_attempted_not_done(self):
        reg = self._reg()
        plan = [{"op": "focus_app", "arg": "discord"},
                {"op": "discord_control", "arg": "deafen"}]
        with patch("gemma4_agent.computer_use.plan_for", return_value=plan), \
             patch("gemma4_agent.computer_use.PlanExecutor") as PE, \
             patch("gemma4_agent.computer_use.summarize_result", return_value="Intentado."):
            PE.return_value.execute.return_value = {
                "ok": True, "verified": False, "steps": plan, "focused_app": "Discord",
            }
            r = reg.t_computer_use({"goal": "ensordeceme en discord"})
        self.assertTrue(r["ok"])
        self.assertFalse(r["verified"])
        self.assertEqual(r["completion_status"], "attempted")

    def test_no_plan_is_honest_failure(self):
        reg = self._reg()
        with patch("gemma4_agent.computer_use.plan_for", return_value=None):
            r = reg.t_computer_use({"goal": "algo raro que no se planifica"})
        self.assertFalse(r["ok"])

    def test_registered_in_schemas(self):
        from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS
        names = [s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS]
        self.assertIn("computer_use", names)


class GuiCompatibilityTest(unittest.TestCase):
    """Recovery for common LLM-shaped GUI calls. These tests mock the actual
    app/click layers, so they never emit input to Windows."""

    def _reg(self):
        return ToolRegistry.__new__(ToolRegistry)

    def test_gui_open_routes_to_app_open(self):
        reg = self._reg()
        reg.t_app = MagicMock(return_value={"ok": True, "status": "done"})
        r = reg.t_gui({"action": "open", "target": "Opera GX"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["routed_to"], "app.open")
        reg.t_app.assert_called_once_with({
            "action": "open",
            "name": "Opera GX",
            "refresh": False,
        })

    def test_gui_click_target_routes_to_click_button(self):
        reg = self._reg()
        reg.gui_click_button = MagicMock(return_value={"ok": True, "method": "uia"})
        with patch("gemma4_agent.gui_safety.check_action_budget", return_value=None), \
             patch("gemma4_agent.gui_safety.check_user_activity", return_value=None), \
             patch("gemma4_agent.gui_safety.note_action"):
            r = reg.t_gui({"action": "click", "target": "favorite-site"})
        self.assertTrue(r["ok"])
        reg.gui_click_button.assert_called_once()
        self.assertEqual(reg.gui_click_button.call_args.args[0]["label"], "favorite-site")


class RouterOffersComputerUseTest(unittest.TestCase):
    """El router debe RANKEAR computer_use para comandos de operar-dentro-de-app."""

    @classmethod
    def setUpClass(cls):
        from gemma4_agent.routing.semantic_router import suggest_tools_scored
        # ¿hay encoder? si no, skip (CI sin sentence-transformers)
        cls.available = bool(suggest_tools_scored("test"))

    def _top(self, q):
        from gemma4_agent.routing.semantic_router import suggest_tools_scored
        return [t for t, _ in suggest_tools_scored(q)]

    def test_inapp_message_ranks_computer_use(self):
        if not self.available:
            self.skipTest("encoder no disponible")
        # computer_use debe estar entre las tools ofrecidas (subset router <=16);
        # medido #1 en estos casos, exigimos top-6 para robustez ante re-orderings.
        for q in ("mandale hola a pedro en discord",
                  "andá al canal general en discord",
                  "en opera entra a python.org"):
            self.assertIn("computer_use", self._top(q)[:6], msg=q)


if __name__ == "__main__":
    unittest.main()
