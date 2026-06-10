"""Few-shot dinámico de acción (2026-06-10): sesga el primer token del turno de
acción hacia disparar la tool (ataca el first-token misalignment, residual ~75%).
"""
from __future__ import annotations

import json
import os
import unittest

from gemma4_agent.routing.action_fewshot import build_action_fewshot


class TestActionFewshot(unittest.TestCase):
    def test_builds_pair_for_offered_tool(self):
        msgs = build_action_fewshot(["reminder", "session"])
        self.assertEqual(len(msgs), 2)  # 1 par user->assistant
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")
        tc = msgs[1]["tool_calls"][0]["function"]
        self.assertEqual(tc["name"], "reminder")
        # arguments es JSON string válido (formato OpenAI que el template renderiza)
        json.loads(tc["arguments"])

    def test_caps_at_two_shots(self):
        # 5 tools con ejemplo -> máximo 2 pares (la curva se aplana tras 2).
        msgs = build_action_fewshot(["audio", "app", "window", "browser", "reminder"])
        assistants = [m for m in msgs if m["role"] == "assistant"]
        self.assertLessEqual(len(assistants), 2)

    def test_preserves_router_order(self):
        # la primera tool del subset (más probable) va primero.
        msgs = build_action_fewshot(["device_settings", "audio"])
        first = msgs[1]["tool_calls"][0]["function"]["name"]
        self.assertEqual(first, "device_settings")

    def test_skips_non_action_tools(self):
        # session/safety/state/verify/knowledge NO generan ejemplo.
        for t in ("session", "safety", "state", "verify", "knowledge"):
            self.assertEqual(build_action_fewshot([t]), [])

    def test_empty_when_no_tools(self):
        self.assertEqual(build_action_fewshot([]), [])
        self.assertEqual(build_action_fewshot(None), [])

    def test_gate_off_disables(self):
        os.environ["GEMMA4_ACTION_FEWSHOT"] = "0"
        try:
            self.assertEqual(build_action_fewshot(["reminder", "session"]), [])
        finally:
            os.environ.pop("GEMMA4_ACTION_FEWSHOT", None)

    def test_unknown_tool_no_example(self):
        # una tool sin ejemplo canónico no rompe ni inventa.
        self.assertEqual(build_action_fewshot(["some_unknown_tool"]), [])


if __name__ == "__main__":
    unittest.main()
