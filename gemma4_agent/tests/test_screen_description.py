"""Lectura de pantalla para no-vidente (2026-05-27): vision describe_screen
DESCRIBE directo (visión limpia) y el agente surfacea esa descripción como reply
— el 4B débil no la relata fiable desde el tool-result (medido). Mock-only.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.agent_core.agent import Gemma4Agent, ToolEvent
from gemma4_agent.agent_core.turn_types import TurnDecision
from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.routing.planner import plan_mission
from gemma4_agent.support.modes import choose_mode


class ScreenDescriptionReplyTest(unittest.TestCase):
    """_screen_description_reply: toma la descripción del último evento vision."""

    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def test_returns_description_from_vision_event(self):
        evs = [ToolEvent(name="vision", args={"action": "describe_screen"},
                         result={"ok": True, "description": "Se ve el escritorio con el navegador abierto."})]
        self.assertEqual(self.ag._screen_description_reply(evs),
                         "Se ve el escritorio con el navegador abierto.")

    def test_none_when_no_vision_description(self):
        evs = [ToolEvent(name="app", args={}, result={"ok": True})]
        self.assertIsNone(self.ag._screen_description_reply(evs))

    def test_takes_last_vision_description(self):
        evs = [
            ToolEvent(name="vision", args={}, result={"description": "primera"}),
            ToolEvent(name="vision", args={}, result={"description": "segunda"}),
        ]
        self.assertEqual(self.ag._screen_description_reply(evs), "segunda")

    def test_empty_events(self):
        self.assertIsNone(self.ag._screen_description_reply([]))


class DescribeImageDirectlyTest(unittest.TestCase):
    """t_vision._describe_image_directly: llamada de visión limpia -> texto."""

    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def test_describes_via_clean_vision_call(self):
        # imagen real (un PNG temporal mínimo) + cliente mockeado.
        td = Path(tempfile.mkdtemp())
        img = td / "shot.png"
        # PNG 1x1 válido mínimo
        img.write_bytes(bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c6360000002000154a24f5f0000000049454e44ae426082"))
        tools = self.ag.tools
        tools.parent_agent = self.ag
        fake_resp = {"choices": [{"message": {"content": "Se ve una ventana con código."}}]}
        with mock.patch.object(self.ag.client, "chat", return_value=fake_resp) as chat:
            out = tools._describe_image_directly(str(img))
        self.assertEqual(out, "Se ve una ventana con código.")
        # la llamada de descripción debe ir SIN tools y con thinking off
        _, kwargs = chat.call_args
        self.assertIsNone(kwargs.get("tools"))
        self.assertFalse(kwargs.get("enable_thinking"))

    def test_none_without_image(self):
        self.ag.tools.parent_agent = self.ag
        self.assertIsNone(self.ag.tools._describe_image_directly(None))


class ScreenDescriptionFastPathTest(unittest.TestCase):
    """vision.describe_screen debe cerrar el turno sin un segundo pase LLM."""

    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def test_describe_screen_result_is_final_without_followup_llm(self):
        text = "que ves en mi pantalla"
        tool_call = {
            "id": "call_vision_1",
            "type": "function",
            "function": {
                "name": "vision",
                "arguments": json.dumps({"action": "describe_screen"}),
            },
        }
        first_resp = {
            "choices": [{
                "message": {"content": "", "tool_calls": [tool_call]},
                "finish_reason": "tool_calls",
            }],
            "timings": {},
        }
        vision_result = {
            "ok": True,
            "tool": "vision",
            "action": "describe_screen",
            "status": "done",
            "verified": True,
            "description": "Se ve YouTube abierto.",
            "completion_status": "screen_described",
        }
        decision = TurnDecision(
            turn_id="t_screen_fast",
            mode=choose_mode(text, "quick_action", self.ag.config.max_tokens),
            plan=plan_mission(text),
            raw_text_early=text,
            selected_tool_names=["vision"],
            selected_schemas=[],
        )

        with (
            mock.patch.object(self.ag.client, "chat", return_value=first_resp) as chat,
            mock.patch.object(self.ag.tools, "execute", return_value=vision_result) as execute,
            mock.patch.object(self.ag, "_record_experience_turn") as record_exp,
        ):
            reply = self.ag._execute_turn(text, decision)

        self.assertEqual(reply.content, "Se ve YouTube abierto.")
        self.assertEqual(chat.call_count, 1)
        execute.assert_called_once()
        record_exp.assert_called_once()


if __name__ == "__main__":
    unittest.main()
