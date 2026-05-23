"""Tests del auto-repair de path (informe B): rellenar path desde filesystem.search.

Cuando el modelo encadena search->open pero llama office.open/media.play/
filesystem.read con path ausente/inválido (no copia el resultado), rellenamos
el path con el primer resultado del search exitoso más reciente. Determinista,
NO ejecuta tools no elegidas — solo repara el argumento.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent import Gemma4Agent, ToolEvent


def _ar(name, args, evs):
    ag = Gemma4Agent.__new__(Gemma4Agent)
    return ag._autorepair_path_from_search(name, args, evs)


_SEARCH = ToolEvent(
    name="filesystem", args={"action": "search"},
    result={"ok": True, "action": "search", "root": "C:/Users/u/Downloads",
            "matches": [{"path": "C:/Users/u/Downloads/x.docx", "type": "file"}]})


class AutoRepairPathTest(unittest.TestCase):
    def test_fills_missing_path(self):
        self.assertEqual(_ar("office", {"action": "open"}, [_SEARCH]),
                         "C:/Users/u/Downloads/x.docx")

    def test_keeps_existing_absolute_path(self):
        self.assertIsNone(_ar("office", {"action": "open",
                                         "path": "C:/other.docx"}, [_SEARCH]))

    def test_non_consumer_tool_ignored(self):
        self.assertIsNone(_ar("app", {"action": "open"}, [_SEARCH]))

    def test_no_search_no_repair(self):
        self.assertIsNone(_ar("office", {"action": "open"}, []))

    def test_relative_path_resolved_to_root(self):
        ev = ToolEvent(name="filesystem", args={},
                       result={"ok": True, "action": "search",
                               "root": "C:/Users/u/Downloads",
                               "matches": [{"path": "sub/y.docx"}]})
        got = _ar("office", {"action": "open"}, [ev])
        self.assertIn("Downloads", got)
        self.assertIn("y.docx", got)

    def test_media_play_also_repaired(self):
        self.assertEqual(_ar("media", {"action": "play"}, [_SEARCH]),
                         "C:/Users/u/Downloads/x.docx")


if __name__ == "__main__":
    unittest.main()
