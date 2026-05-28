"""Bug medido (2026-05-27): en modo MOVILIDAD/NO_VIDENTE, una pregunta META
("¿qué podés hacer?", "¿quién eres?") terminaba en gui(screenshot). Causa: el
nudge "ejecutá vos el siguiente paso" (a11y_continue) se disparaba porque la
respuesta que DESCRIBE capacidades ("...controlar tu sistema, gestionar apps...")
matcheaba reply_delegates_task, y el re-prompt empujaba al 4B a capturar la
pantalla para "continuar" — pero NO había tarea: el router abstuvo (subset sin
tools de dominio) y no corrió ninguna acción. 5/5 reproducido en vivo.

FIX: el nudge SOLO se dispara en un turno de ACCIÓN (_cont_actionable): se ofreció
≥1 tool de dominio O se ejecutó una acción de dominio. Una pregunta meta/charla no
es una tarea delegada.

Mock-only: client.chat y reply_delegates_task mockeados (sin LLM, sin GUI)."""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.config import AgentConfig
from gemma4_agent import accessibility as a11y
from gemma4_agent import reply_validator as rv


def _prose(text="Puedo controlar tu sistema y gestionar aplicaciones."):
    return {"choices": [{"message": {"content": text}}]}


class A11yContinueMetaGuardTest(unittest.TestCase):
    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def _run_capture(self, query, *, subset_override=None):
        """Corre 1 turno en movilidad con el LLM devolviendo prosa que DELEGA
        (reply_delegates_task -> True). Devuelve (nudge_fired, executed_tools)."""
        seen = {"nudge": False}
        orig = self.ag.trace.event

        def _ev(tid, kind, **f):
            if kind == "a11y_continue_nudge":
                seen["nudge"] = True
            return orig(tid, kind, **f)

        self.ag.trace.event = _ev
        with mock.patch.object(a11y, "get_active_mode", return_value=a11y.get("movilidad")), \
             mock.patch.object(rv, "reply_delegates_task", return_value=True), \
             mock.patch.object(self.ag.client, "chat", return_value=_prose()):
            r = self.ag.run_content(query)
        return seen["nudge"], [e.name for e in (r.tool_events or [])]

    def test_meta_question_does_not_nudge_or_screenshot(self):
        # subset abstiene (sin dominio) y no corre acción -> aunque la prosa
        # "delegue", el nudge NO debe dispararse y NO debe ejecutar gui.
        nudge, executed = self._run_capture("que podes hacer")
        self.assertFalse(nudge, "nudge se disparó en una pregunta meta")
        self.assertNotIn("gui", executed, f"meta-pregunta sacó screenshot: {executed}")

    def test_identity_question_does_not_nudge(self):
        nudge, executed = self._run_capture("Quien eres?")
        self.assertFalse(nudge, "nudge se disparó en pregunta de identidad")
        self.assertNotIn("gui", executed)

    def test_action_turn_that_delegates_STILL_nudges(self):
        # Anti-regresión: el gate _cont_actionable NO debe matar el caso legítimo.
        # Un turno de ACCIÓN (corre una tool de dominio) cuya respuesta DELEGA
        # ("revisá los resultados") SÍ debe disparar el nudge para que el agente
        # siga actuando él mismo. Mockeamos: 1ª pasada -> tool_call web.search;
        # 2ª -> prosa que delega; 3ª -> cierre. web_search stubeado (sin red).
        self.ag.tools.web_search = lambda *a, **k: [
            {"title": "A", "url": "http://a"}, {"title": "B", "url": "http://b"}]
        calls = {"n": 0}

        def fake_chat(msgs, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"choices": [{"message": {"content": "", "tool_calls": [
                    {"id": "c1", "type": "function", "function": {
                        "name": "web",
                        "arguments": '{"action":"search","query":"teclados"}'}}]}}]}
            if calls["n"] == 2:
                return _prose("Revisá los resultados y elegí cuál abrir.")
            return _prose("Listo, abrí el primero.")

        seen = {"nudge": False}
        orig = self.ag.trace.event

        def _ev(tid, kind, **f):
            if kind == "a11y_continue_nudge":
                seen["nudge"] = True
            return orig(tid, kind, **f)

        self.ag.trace.event = _ev
        with mock.patch.object(a11y, "get_active_mode", return_value=a11y.get("movilidad")), \
             mock.patch.object(rv, "reply_delegates_task",
                               side_effect=lambda t: "evisá" in t), \
             mock.patch.object(self.ag.client, "chat", side_effect=fake_chat):
            self.ag.run_content("busca teclados y abri el mejor")
        self.assertTrue(seen["nudge"],
                        "el nudge NO se disparó en un turno de acción que delega")


if __name__ == "__main__":
    unittest.main()
