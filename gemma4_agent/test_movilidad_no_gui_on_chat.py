"""Bug medido (2026-05-27): en modo MOVILIDAD, "¿quién eres?" terminaba en
gui(screenshot)+gui(locate_text) — el modo inyectaba gui/computer_use/uia aunque
el router ABSTUVO (es charla/identidad). Guard: las preferred_tools del modo solo
se inyectan si el router YA eligió ≥1 tool de dominio (turno de acción), no en
charla. Mock-only: client.chat mockeado (no LLM); capturamos el tool_subset."""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.config import AgentConfig
from gemma4_agent import accessibility as a11y


_PHYS = {"gui", "computer_use", "uia"}


class MovilidadNoGuiOnChatTest(unittest.TestCase):
    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def _subset_for(self, query):
        """Corre 1 turno con el LLM mockeado (responde prosa, sin tool) y devuelve
        el subset de tools del evento tool_subset."""
        captured = {}
        orig = self.ag.trace.event
        def _ev(tid, kind, **f):
            if kind == "tool_subset":
                captured["tools"] = f.get("tools") or []
            return orig(tid, kind, **f)
        self.ag.trace.event = _ev
        fake = {"choices": [{"message": {"content": "Soy Gemma, tu asistente."}}]}
        with mock.patch.object(self.ag.client, "chat", return_value=fake):
            self.ag.run_content(query)
        return captured.get("tools", [])

    def test_chat_identity_in_movilidad_has_no_physical_tools(self):
        with mock.patch.object(a11y, "get_active_mode", return_value=a11y.get("movilidad")):
            tools = self._subset_for("Quien eres?")
        # el modo NO debe haber inyectado gui/computer_use/uia para una pregunta
        # de identidad (el router abstuvo -> subset de dominio vacío).
        self.assertEqual(_PHYS & set(tools), set(),
                         f"movilidad inyectó tools físicas en charla: {tools}")

    def test_action_in_movilidad_still_gets_physical_tools(self):
        # un comando GUI real ("hace click...") SÍ debe tener las tools del modo.
        with mock.patch.object(a11y, "get_active_mode", return_value=a11y.get("movilidad")):
            tools = self._subset_for("hace click en el boton rojo")
        self.assertTrue(_PHYS & set(tools),
                        f"movilidad NO ofreció tools físicas en un comando GUI: {tools}")


if __name__ == "__main__":
    unittest.main()
