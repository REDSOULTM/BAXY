"""Lectura de pantalla para no-vidente (2026-05-27): vision describe_screen
DESCRIBE directo (visión limpia) y el agente surfacea esa descripción como reply
— el 4B débil no la relata fiable desde el tool-result (medido). Mock-only.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.agent import Gemma4Agent, ToolEvent
from gemma4_agent.config import AgentConfig


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


if __name__ == "__main__":
    unittest.main()
