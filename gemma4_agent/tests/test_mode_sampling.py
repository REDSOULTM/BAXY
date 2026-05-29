"""Tests del sampling por modo (investigación 0, T4).

Los defaults de Gemma (T=1.0/top_p=0.95/top_k=64) son para chat; en modos de
ACCIÓN/info breve con baja-T se estabiliza la salida sin empobrecerla. Greedy
(decisión de tool-call) GANA sobre el override de modo. Sin override = default.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llm_client import LLMClient
from gemma4_agent.support.modes import choose_mode


class ModeSamplingValuesTest(unittest.TestCase):
    def test_action_and_info_modes_lower_temperature(self):
        fi = choose_mode("x", "fast_info", 512)
        self.assertEqual(fi.temperature, 0.6)
        fa = choose_mode("x", "fast_action", 512)
        self.assertEqual(fa.temperature, 0.4)

    def test_reasoning_modes_keep_defaults(self):
        for m in ("research", "deep_action", "quick_action", "vision_action"):
            self.assertIsNone(choose_mode("x", m, 512).temperature, m)


class ChatBodySamplingTest(unittest.TestCase):
    def setUp(self):
        self.cfg = AgentConfig()
        self.c = LLMClient(self.cfg)
        self.cap: dict = {}
        self.c._post_chat_with_recovery = self._capture

    def _capture(self, body, timeout):
        self.cap.clear()
        self.cap.update(body)
        return {"choices": [{"message": {"content": "ok"}}]}

    def test_mode_override_applied(self):
        self.c.chat([{"role": "user", "content": "hola"}],
                    sampling={"temperature": 0.6, "top_p": 0.95, "top_k": 40})
        self.assertEqual(self.cap["temperature"], 0.6)
        self.assertEqual(self.cap["top_p"], 0.95)
        self.assertEqual(self.cap["top_k"], 40)

    def test_greedy_wins_over_mode_sampling(self):
        # la decisión de tool-call manda con temp=0 aunque el modo pida 0.6
        self.c.chat([{"role": "user", "content": "abre steam"}],
                    tools=[{"x": 1}], greedy=True,
                    sampling={"temperature": 0.6, "top_p": 0.95, "top_k": 40})
        self.assertEqual(self.cap["temperature"], 0.0)
        self.assertEqual(self.cap["top_k"], 1)

    def test_none_sampling_uses_config_default(self):
        self.c.chat([{"role": "user", "content": "x"}],
                    sampling={"temperature": None, "top_p": None, "top_k": None})
        self.assertEqual(self.cap["temperature"], self.cfg.temperature)

    def test_no_sampling_arg_uses_config_default(self):
        self.c.chat([{"role": "user", "content": "x"}])
        self.assertEqual(self.cap["temperature"], self.cfg.temperature)

    def test_gate_disables_mode_sampling(self):
        os.environ["GEMMA4_MODE_SAMPLING"] = "0"
        try:
            self.c.chat([{"role": "user", "content": "x"}],
                        sampling={"temperature": 0.4, "top_p": 0.9, "top_k": 20})
            self.assertEqual(self.cap["temperature"], self.cfg.temperature)  # ignorado
        finally:
            os.environ.pop("GEMMA4_MODE_SAMPLING", None)


if __name__ == "__main__":
    unittest.main()
