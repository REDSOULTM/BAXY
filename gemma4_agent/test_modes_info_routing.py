"""Tests for F-004: mode selection must NOT route info queries
(explicaciones, comparaciones, listas, cronologias) to fast_action,
because fast_action caps max_tokens=384 and truncates mid-sentence.
"""
from __future__ import annotations

import unittest

from gemma4_agent.modes import _infer_mode


class TestInfoQueriesRoutedToResearch(unittest.TestCase):
    """Queries that need longer replies must go to research mode."""

    def _assert_research(self, prompt: str):
        self.assertEqual(
            _infer_mode(prompt), "research",
            f"prompt {prompt!r} should route to research, got {_infer_mode(prompt)!r}",
        )

    def _assert_fast_action(self, prompt: str):
        self.assertEqual(
            _infer_mode(prompt), "fast_action",
            f"prompt {prompt!r} should stay in fast_action, got {_infer_mode(prompt)!r}",
        )

    # ---- The 6 audit-listed prompts that NEED long replies ----

    def test_cronological_order_routes_to_research(self):
        self._assert_research("orden cronológico de la saga Batman Arkham")

    def test_compara_routes_to_research(self):
        self._assert_research("comparame Disney+ y Netflix")

    def test_explica_routes_to_research(self):
        self._assert_research("explicame cómo funciona CDP")

    def test_diferencia_routes_to_research(self):
        self._assert_research("cuál es la diferencia entre Gemma 3 y Gemma 4")

    def test_porque_routes_to_research(self):
        self._assert_research("porque el agente no me responde")

    def test_resumeme_routes_to_research(self):
        self._assert_research("resumime el paper de Gemma 3n")

    # ---- The 6 control prompts that MUST stay in fast_action ----

    def test_hola_stays_in_fast_action(self):
        self._assert_fast_action("hola")

    def test_que_hora_es_stays_in_fast_action(self):
        self._assert_fast_action("qué hora es")

    def test_ponme_loki_stays_in_fast_action(self):
        self._assert_fast_action("ponme Loki")

    # "abre Chrome" hits action_marker count >=1 but not >=2; len < 180.
    # That returns fast_action per current logic; let's verify.
    def test_abre_chrome_stays_in_fast_action(self):
        self._assert_fast_action("abre Chrome")

    def test_cuando_salio_stays_in_fast_action(self):
        # "cuándo salió GTA 5" — short factual question, no info marker.
        self._assert_fast_action("cuándo salió GTA 5")

    def test_si_stays_in_fast_action(self):
        self._assert_fast_action("sí")


if __name__ == "__main__":
    unittest.main()
