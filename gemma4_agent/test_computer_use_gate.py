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

    def test_activates_via_plan_focus_arg_when_text_doesnt_match(self):
        # VÍA 2: el TEXTO no matchea ninguna ventana, pero el plan focus_app (que el
        # 4B normaliza) SÍ matchea una ventana abierta -> debe activarse. Uso Discord
        # (sin tool dedicada; WhatsApp deferiría a su tool). Simula un fraseo donde el
        # texto crudo no nombra "Discord" pero el plan lo resuelve.
        ag = self._agent()
        plan = [{"op": "focus_app", "arg": "Discord"}, {"op": "open_chat", "arg": "migue"},
                {"op": "type", "arg": "hola"}, {"op": "send", "arg": ""}]
        def wtit(s):
            return "@Ron - Discord" if s == "Discord" else None  # solo el arg matchea
        with patch.object(Gemma4Agent, "_window_title_in_text", side_effect=wtit), \
             patch("gemma4_agent.computer_use.plan_for", return_value=plan), \
             patch("gemma4_agent.computer_use.PlanExecutor") as PE, \
             patch("gemma4_agent.computer_use.summarize_result", return_value="ok"):
            PE.return_value.execute.return_value = {"ok": True, "steps": plan, "focused_app": "Discord"}
            r = ag._try_computer_use("mandale hola a migue", "t1")
        self.assertIsNotNone(r)  # se activó vía el focus_arg del plan

    def test_no_open_app_does_not_activate(self):
        # ni el texto ni el arg de focus_app matchean una ventana abierta -> None.
        ag = self._agent()
        plan = [{"op": "focus_app", "arg": "Telegram"}, {"op": "open_chat", "arg": "x"}]
        with patch.object(Gemma4Agent, "_window_title_in_text", return_value=None), \
             patch("gemma4_agent.computer_use.plan_for", return_value=plan):
            r = ag._try_computer_use("mandale algo a x en telegram", "t1")
        self.assertIsNone(r)

    def test_bare_focus_plan_does_NOT_hijack(self):
        # REGRESIÓN medida 2026-05-25: "abre steam"/"Cierra steam" con Steam YA
        # abierto -> plan = [focus_app(steam)] (sin op de operación-en-app) ->
        # computer_use NO debe tomar el turno (eso es del tool dedicado steam/window).
        # Antes secuestraba y "enfocaba/minimizaba Steam porque sí".
        ag = self._agent()
        plan = [{"op": "focus_app", "arg": "steam"}]
        with patch.object(Gemma4Agent, "_window_title_in_text", return_value="Steam"), \
             patch("gemma4_agent.computer_use.plan_for", return_value=plan):
            r = ag._try_computer_use("abre steam", "t1")
        self.assertIsNone(r)  # no secuestra -> el router/LLM usa el tool steam

    def test_inapp_op_plan_DOES_fire(self):
        # un plan con una primitiva de operación-en-app (type/send/click/open_chat/
        # open_url) SÍ activa computer_use.
        ag = self._agent()
        plan = [{"op": "focus_app", "arg": "discord"}, {"op": "open_chat", "arg": "juan"},
                {"op": "type", "arg": "hola"}, {"op": "send", "arg": ""}]
        with patch.object(Gemma4Agent, "_window_title_in_text", return_value="Discord"), \
             patch("gemma4_agent.computer_use.plan_for", return_value=plan), \
             patch("gemma4_agent.computer_use.PlanExecutor") as PE, \
             patch("gemma4_agent.computer_use.summarize_result", return_value="ok"):
            PE.return_value.execute.return_value = {"ok": True, "steps": plan, "focused_app": "Discord"}
            r = ag._try_computer_use("escribile a juan en discord hola", "t1")
        self.assertIsNotNone(r)

    def test_whatsapp_defers_to_dedicated_tool(self):
        # REGRESIÓN 2026-05-25: WhatsApp tiene tool DEDICADA (`whatsapp`). La capa
        # universal tecleaba por SendInput (no llega al WebView2) -> escribía en la 1ª
        # caja disponible / contacto equivocado. Debe DEFERIR: computer_use devuelve
        # None y el router/LLM usa la tool whatsapp. Discord (sin tool dedicada) NO.
        ag = self._agent()
        plan = [{"op": "focus_app", "arg": "whatsapp"}, {"op": "open_chat", "arg": "vicente"},
                {"op": "type", "arg": "gracias"}, {"op": "send", "arg": ""}]
        with patch.object(Gemma4Agent, "_window_title_in_text", return_value="WhatsApp"), \
             patch("gemma4_agent.computer_use.plan_for", return_value=plan):
            r = ag._try_computer_use("escribe a vicente en wsp gracias", "t1")
        self.assertIsNone(r)  # defiere a la tool whatsapp

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
