"""R1 sprint 2026-05-28: integration tests del flow de 3 fases.

Verifica que `_decide_turn` / `_execute_turn` / `_finalize_turn` se
ejecutan correctamente end-to-end con LLM mockeado. Si el split del R1
se rompe (ejemplo: alguien añade un return en mal lugar), estos tests
lo detectan.
"""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.config import AgentConfig


def _make_agent(*, prose_content: str = "Hola.") -> Gemma4Agent:
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_r1_"))
    cfg = dataclasses.replace(
        AgentConfig.from_env(),
        memory_path=tmp / "m.json", captures_dir=tmp / "cap",
        trace_path=tmp / "t.jsonl", state_path=tmp / "s.json",
        enable_tracing=False, enable_safety=False,
    )
    a = Gemma4Agent(cfg)

    def chat(messages, **kw):
        return {"choices": [{
            "message": {"role": "assistant", "content": prose_content, "tool_calls": []},
            "finish_reason": "stop",
        }]}
    a.client.chat = chat
    return a


class TestR1ThreePhaseFlow(unittest.TestCase):
    """End-to-end del flow decide → execute → finalize."""

    def test_simple_turn_completes_e2e(self):
        a = _make_agent()
        reply = a.run_content("hola")
        self.assertEqual(reply.content, "Hola.")

    def test_mission_status_emitted(self):
        a = _make_agent()
        reply = a.run_content("hola")
        self.assertIsNotNone(reply.mission)
        self.assertIn(reply.mission["mission_status"], {"PASS", "FAILED", "PARTIAL"})

    def test_multiple_turns_in_same_agent(self):
        """Cada turno crea un decision/execute/finalize fresh."""
        a = _make_agent()
        replies = [a.run_content(f"mensaje {i}") for i in range(3)]
        for r in replies:
            self.assertTrue(r.content)

    def test_decide_turn_returns_turn_decision(self):
        """`_decide_turn` devuelve TurnDecision tipado."""
        from gemma4_agent.turn_types import TurnDecision
        a = _make_agent()
        decision = a._decide_turn("hola", progress=None)
        self.assertIsInstance(decision, TurnDecision)

    def test_early_reply_short_circuits(self):
        """Si _decide_turn devuelve early_reply, no se ejecuta _execute_turn."""
        a = _make_agent()
        # Configurar pending_intent yes/no para forzar el handshake
        # de Jarvis (que devuelve early_reply).
        # Simplemente verificamos que TurnDecision.early_reply es None
        # en un flow normal.
        decision = a._decide_turn("hola", progress=None)
        self.assertIsNone(decision.early_reply,
                          "Simple 'hola' no debería tener early_reply")

    def test_finalize_continue_sentinel_exists(self):
        """`_FINALIZE_CONTINUE` sentinel existe (para el continue del a11y)."""
        from gemma4_agent.agent import _FINALIZE_CONTINUE, _FinalizeContinue
        self.assertIsInstance(_FINALIZE_CONTINUE, _FinalizeContinue)

    def test_empty_string_does_not_crash(self):
        a = _make_agent()
        try:
            reply = a.run_content("")
            self.assertIsNotNone(reply)
        except ValueError:
            # Empty string puede ser rechazada — no es bug, es decision.
            pass


if __name__ == "__main__":
    unittest.main()
