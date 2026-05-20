"""Tests for the planner's colloquial-abbreviation expansion.

2026-05-20: short/abbreviated queries ("baja el vol a 10", "cierra wsp")
were mis-routed because the multilingual embedder doesn't map "vol" near
"volumen". We expand the shorthand to its full word BEFORE routing, so the
query routes by meaning. These tests pin that the expansion fires for the
shorthand AND — critically — never corrupts a longer word that merely
contains the abbreviation ("volver", "evolucion").

Pure string logic, no model load.
"""
from __future__ import annotations

import unittest

from gemma4_agent.planner import _expand_abbreviations as _x


class TestExpandAbbreviations(unittest.TestCase):

    def test_volume_shorthand(self):
        self.assertIn("volumen", _x("baja el vol a 10"))
        self.assertIn("volumen", _x("sube el VOL"))

    def test_messaging_shorthand(self):
        self.assertIn("whatsapp", _x("cierra wsp"))
        self.assertIn("whatsapp", _x("mandale un wpp a Ana"))

    def test_word_boundaries_are_respected(self):
        # The abbreviation must NOT be expanded inside a larger word.
        for safe in ("volver a casa", "evolucion", "appenzeller",
                     "appartamento", "ytong"):
            self.assertEqual(_x(safe), safe, f"corrupted {safe!r}")

    def test_no_shorthand_is_a_noop(self):
        s = "abre Steam y pon una cancion"
        self.assertEqual(_x(s), s)


if __name__ == "__main__":
    unittest.main()
