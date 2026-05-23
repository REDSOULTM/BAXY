"""Sampling dual para tool-calling (investigación 1, 2026-05-23).

En el turno de ACCIÓN (decidir/emitir el tool-call) usamos greedy (temp=0,
top_k=1) para bajar la entropía del primer token y curar el 2/6 sin reasoning.
En conversación, los defaults de Gemma (temp=1.0). Gate GEMMA4_GREEDY_TOOLCALL.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.config import AgentConfig
from gemma4_agent.llm_client import LLMClient


class GreedyToolCallTest(unittest.TestCase):
    def setUp(self):
        self.c = LLMClient(AgentConfig.from_env())
        self.bodies = []
        # interceptar el POST sin tocar el server real
        self.c._post_chat_with_recovery = lambda body, timeout: (
            self.bodies.append(body) or {"choices": [{"message": {"content": "x"}}]})
        os.environ.pop("GEMMA4_GREEDY_TOOLCALL", None)

    def _last(self):
        return self.bodies[-1]

    def test_action_turn_is_greedy(self):
        self.c.chat([{"role": "user", "content": "abre steam"}],
                    tools=[{"type": "function", "function": {"name": "app"}}],
                    greedy=True)
        b = self._last()
        self.assertEqual(b["temperature"], 0.0)
        self.assertEqual(b["top_k"], 1)
        self.assertEqual(b["top_p"], 1.0)
        self.assertNotIn("min_p", b)  # min_p se omite en greedy

    def test_conversation_uses_defaults(self):
        self.c.chat([{"role": "user", "content": "hola"}], greedy=False)
        b = self._last()
        self.assertEqual(b["temperature"], self.c.config.temperature)
        self.assertEqual(b["top_k"], self.c.config.top_k)

    def test_gate_off_disables_greedy(self):
        os.environ["GEMMA4_GREEDY_TOOLCALL"] = "0"
        try:
            self.c.chat([{"role": "user", "content": "abre steam"}],
                        tools=[{"type": "function", "function": {"name": "app"}}],
                        greedy=True)
            b = self._last()
            self.assertEqual(b["temperature"], self.c.config.temperature)
            self.assertEqual(b["top_k"], self.c.config.top_k)
        finally:
            os.environ.pop("GEMMA4_GREEDY_TOOLCALL", None)

    def test_repeat_penalty_never_raised(self):
        # Gemma 4: repeat_penalty > 1.0 causa <unused49> (issue #21338). Nunca subir.
        self.c.chat([{"role": "user", "content": "abre steam"}],
                    tools=[{"type": "function", "function": {"name": "app"}}],
                    greedy=True)
        self.assertLessEqual(self._last()["repeat_penalty"], 1.0)


if __name__ == "__main__":
    unittest.main()
