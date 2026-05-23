"""Tests del chaining-nudge (Problema B): empujar a encadenar search→acción.

Bug sesión #847: filesystem.search encontró el .docx pero el modelo (E4B, 4B)
NO encadenó office.open — paró en "ya busqué". El nudge inyecta un [system note]
tras una búsqueda EXITOSA con items para que use el primer resultado.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent import Gemma4Agent, ToolEvent


def _nudge(raw_calls, evs):
    ag = Gemma4Agent.__new__(Gemma4Agent)
    return ag._chaining_nudge(raw_calls, evs)


class ChainingNudgeTest(unittest.TestCase):
    def test_fires_on_search_with_results(self):
        rc = [{"function": {"name": "filesystem"}}]
        ev = [ToolEvent(name="filesystem", args={"action": "search"},
                        result={"ok": True, "action": "search",
                                "paths": ["C:/a.docx"]})]
        self.assertIsNotNone(_nudge(rc, ev))

    def test_silent_on_empty_search(self):
        # vacío -> el honesty guard responde "no encontré nada", sin nudge
        rc = [{"function": {"name": "filesystem"}}]
        ev = [ToolEvent(name="filesystem", args={"action": "search"},
                        result={"ok": True, "action": "search", "paths": []})]
        self.assertIsNone(_nudge(rc, ev))

    def test_silent_on_terminal_tool(self):
        rc = [{"function": {"name": "app"}}]
        ev = [ToolEvent(name="app", args={"action": "open"},
                        result={"ok": True, "action": "open"})]
        self.assertIsNone(_nudge(rc, ev))

    def test_silent_on_failed_search(self):
        rc = [{"function": {"name": "filesystem"}}]
        ev = [ToolEvent(name="filesystem", args={},
                        result={"ok": False, "action": "search"})]
        self.assertIsNone(_nudge(rc, ev))

    def test_fires_on_local_search_matches(self):
        rc = [{"function": {"name": "local_search"}}]
        ev = [ToolEvent(name="local_search", args={"action": "find"},
                        result={"ok": True, "action": "find",
                                "matches": ["song1.mp3"]})]
        self.assertIsNotNone(_nudge(rc, ev))


if __name__ == "__main__":
    unittest.main()
