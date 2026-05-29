"""Regression test for the planner office-routing bug found post-Sprint 7.

User said "Puedes hacerme un power point?" and the agent answered "no
tengo herramienta" because:

1. planner._suggest_tools regex was `\bpowerpoint\b` (one word).
2. "power point" (two words) did not match.
3. The catch-all interrogative branch then added "web" instead.
4. The LLM saw web/source_manager/session in subset and concluded
   no office tool was available.

This test pins the multi-word variants so the regression doesn't
return. See traces.jsonl turn 20260517_104715_65549089 for the
original failure.
"""
from __future__ import annotations

import unittest

from gemma4_agent.routing.planner import _suggest_tools


class OfficeRoutingMultiWordTest(unittest.TestCase):
    """Office tool must be suggested for both single- and multi-word forms."""

    def test_power_point_two_words_es(self):
        result = _suggest_tools("puedes hacerme un power point?")
        self.assertIn("office", result,
                      f"'power point' (two words) should route to office, got {result}")

    def test_powerpoint_one_word_es(self):
        result = _suggest_tools("puedes hacerme un powerpoint?")
        self.assertIn("office", result)

    def test_powerpoint_with_topic(self):
        result = _suggest_tools("haz un powerpoint de 5 diapositivas")
        self.assertIn("office", result)

    def test_presentacion_no_accent(self):
        result = _suggest_tools("armame una presentacion")
        self.assertIn("office", result)

    def test_presentacion_with_accent(self):
        result = _suggest_tools("armame una presentación")
        self.assertIn("office", result)

    def test_hoja_de_calculo_no_accent(self):
        result = _suggest_tools("necesito una hoja de calculo")
        self.assertIn("office", result)

    def test_hoja_de_calculo_with_accent(self):
        result = _suggest_tools("necesito una hoja de cálculo")
        self.assertIn("office", result)

    def test_excel_still_works(self):
        # Sanity: existing single-word forms continue working.
        result = _suggest_tools("abre un excel")
        self.assertIn("office", result)

    def test_word_doc_still_works(self):
        result = _suggest_tools("escribe un docx")
        self.assertIn("office", result)


if __name__ == "__main__":
    unittest.main()
