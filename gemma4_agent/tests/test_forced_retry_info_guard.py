"""The forced-tool-retry (arXiv:2504.19277 mitigation) re-calls the LLM with
tool_choice=required when a turn that EXPECTED an action emitted prose instead of
a tool call. E2E with a real LLM (sesión de validación) revealed it ALSO fired on
INFO turns the model correctly answered from knowledge ("¿cuál es la capital de
Francia?" → "París"), because the router offers optional retrieval tools
(web/knowledge/memory) on questions. That spurious retry burned a full second LLM
pass (measured 15s → 3.6s once removed) to return nothing.

EJE del norte rector: LATENCIA (elimina un pass de LLM desperdiciado en cada turno
informativo) sin tocar FIABILIDAD (la retry sigue para turnos de ACCIÓN). Pin:
info-only tools + respuesta en prosa → NO fuerza; tool de acción ofrecido → SÍ.
"""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra.config import AgentConfig


def _make_agent(tmp: Path) -> Gemma4Agent:
    cfg = dataclasses.replace(
        AgentConfig.from_env(),
        memory_path=tmp / "m.json", captures_dir=tmp / "cap",
        trace_path=tmp / "t.jsonl", state_path=tmp / "s.json",
        enable_tracing=False, enable_safety=False,
    )
    return Gemma4Agent(cfg)


class TestForcedRetryInfoGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_retry_"))
        self.agent = _make_agent(self.tmp)

        # The LLM always answers in prose, never calls a tool.
        def _chat(messages, **kw):
            return {"choices": [{
                "message": {"role": "assistant",
                            "content": "La capital de Francia es Paris.",
                            "tool_calls": []},
                "finish_reason": "stop",
            }]}
        self.agent.client.chat = _chat

        # Detect the forced retry via its TRACE EVENT, not raw chat count — a
        # background fact-extraction pass also calls chat and would confound a
        # naive counter.
        self._events: list[str] = []
        _orig = self.agent.trace.event
        self.agent.trace.event = lambda tid, kind, **kw: (
            self._events.append(kind) or _orig(tid, kind, **kw))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _forced(self, tool_names, text) -> bool:
        # Parchea AMBOS: el módulo origen (planner) Y la referencia local
        # importada en agent.py at-module-load. Algunas órdenes de suite
        # cargan agent.py antes que el test, dejando el ref local con la
        # función real; parchar solo planner no llega. Configuramos un
        # MagicMock con `_last_fallback_used` para que `getattr(fn,
        # '_last_fallback_used', False)` devuelva False (no rompe el
        # downstream que lee ese atributo).
        from unittest.mock import MagicMock
        fake = MagicMock(return_value=list(tool_names))
        fake._last_fallback_used = False
        with mock.patch("gemma4_agent.planner.select_tool_names", fake), \
             mock.patch("gemma4_agent.agent.select_tool_names", fake):
            self._events.clear()
            self.agent.run_content(text)
        return "forced_tool_retry" in self._events

    def test_info_only_tools_with_prose_answer_does_not_force_retry(self):
        # web/knowledge/memory are optional grounding; a prose answer is fine.
        # This is THE case the E2E found: an info question answered from knowledge.
        self.assertFalse(
            self._forced(["web", "knowledge", "memory", "source_manager"],
                         "cual es la capital de Francia?"),
            "info turn answered in prose must NOT trigger the forced retry")

    def test_action_tool_offered_still_forces_retry(self):
        # An ACTION tool (app/window) on an ACTION command + prose-without-call =
        # a skipped action -> the forced retry must still fire (unchanged behavior).
        # NOTA (2026-06-01): el input era "abre la calculadora", pero el
        # app_open_shortcircuit (det. 2026-05-31) ahora maneja "abrí/abre X" ANTES del
        # LLM -> nunca llegaba al forced-retry (test stale). Uso una acción de ventana
        # que NO short-circuita (minimizar) y sí ejerce el camino LLM->prosa->retry.
        self.assertTrue(
            self._forced(["app", "window"], "minimizá la ventana actual"),
            "action turn with prose-skip MUST still force a tool retry")

    def test_mixed_info_and_action_still_forces(self):
        # If ANY non-info tool is in the subset (on an action command), force.
        self.assertTrue(
            self._forced(["web", "app"], "abre spotify y buscame algo"),
            "a mixed subset with an action tool must force")


if __name__ == "__main__":
    unittest.main()
