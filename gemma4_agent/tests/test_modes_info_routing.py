"""Tests for F-004 + sprint de latencia (2026-05-22): mode selection must NOT
route info queries (explicaciones, comparaciones, listas, cronologias) to
fast_action (caps max_tokens at 128 -> truncates multi-paragraph answers).

SPRINT DE LATENCIA: estas preguntas YA NO van a `research` (thinking ON, 2048
tok) — MEDIDO en vivo que el thinking en preguntas de conocimiento es puro costo
de latencia Y a menudo PEOR calidad (reasoning se come el budget -> content
vacío; cx5 48s->1.1s, cx1 7s->1s). Ahora van a `fast_info`: thinking OFF, 320
tok, hint conciso de voz. Mantiene el budget de F-004 (no trunca) y elimina el
costo del thinking. Genuine retrieval ("buscame info actual", "noticias") sigue
en `research`.
"""
from __future__ import annotations

import unittest

from gemma4_agent.support.modes import _infer_mode


class TestInfoQueriesRoutedToResearch(unittest.TestCase):
    """Queries that need longer replies must go to fast_info (was research)."""

    def _assert_research(self, prompt: str):
        # Retrieval queries still go to research.
        self.assertEqual(
            _infer_mode(prompt), "research",
            f"prompt {prompt!r} should route to research, got {_infer_mode(prompt)!r}",
        )

    def _assert_fast_info(self, prompt: str):
        self.assertEqual(
            _infer_mode(prompt), "fast_info",
            f"prompt {prompt!r} should route to fast_info, got {_infer_mode(prompt)!r}",
        )

    def _assert_fast_action(self, prompt: str):
        self.assertEqual(
            _infer_mode(prompt), "fast_action",
            f"prompt {prompt!r} should stay in fast_action, got {_infer_mode(prompt)!r}",
        )

    def _assert_quick_action(self, prompt: str):
        self.assertEqual(
            _infer_mode(prompt), "quick_action",
            f"prompt {prompt!r} should route to quick_action, got {_infer_mode(prompt)!r}",
        )

    # ---- The 6 audit-listed prompts that NEED long replies (now fast_info) ----
    # These keep the F-004 guarantee (not truncated) but with thinking OFF for
    # latency — measured 7-48s -> 1-2s with equal/better quality.

    def test_cronological_order_routes_to_fast_info(self):
        self._assert_fast_info("orden cronológico de la saga Batman Arkham")

    def test_compara_routes_to_fast_info(self):
        self._assert_fast_info("comparame Disney+ y Netflix")

    def test_explica_routes_to_fast_info(self):
        self._assert_fast_info("explicame cómo funciona CDP")

    def test_diferencia_routes_to_fast_info(self):
        self._assert_fast_info("cuál es la diferencia entre Gemma 3 y Gemma 4")

    def test_porque_routes_to_fast_info(self):
        self._assert_fast_info("porque el agente no me responde")

    def test_resumeme_routes_to_fast_info(self):
        self._assert_fast_info("resumime el paper de Gemma 3n")

    # ---- Retrieval queries STILL go to research (web tools, no thinking loop) ----

    def test_buscame_info_actual_routes_to_research(self):
        self._assert_research("buscame informacion actual sobre el dolar")

    def test_noticias_routes_to_research(self):
        self._assert_research("que noticias hay sobre inteligencia artificial")

    # ---- The 6 control prompts that MUST stay in fast_action ----

    def test_hola_stays_in_fast_action(self):
        self._assert_fast_action("hola")

    def test_que_hora_es_stays_in_fast_action(self):
        self._assert_fast_action("qué hora es")

    # 2026-05-20: single-action commands whose verb is in the marker list
    # route to quick_action (thinking ON) — MEASURED that Gemma4 needs
    # reasoning to emit the tool-call reliably (2/6 OFF vs 6/6 ON).
    def test_abre_chrome_routes_to_quick_action(self):
        self._assert_quick_action("abre Chrome")

    # "ponme Loki" — the verb "ponme" is NOT in _infer_mode's marker list
    # ("pon" with spaces doesn't match the glued "ponme"). So _infer_mode
    # alone returns fast_action here. That's OK: the REAL guarantee is the
    # agent-level upgrade (agent.py) — when the planner selects a DOMAIN tool
    # (media, here), the turn is upgraded to quick_action regardless of the
    # keyword. This test pins the _infer_mode fast-path; the end-to-end
    # thinking-on behavior is covered by the agent's tool-driven upgrade.
    def test_ponme_loki_infer_is_fast_action(self):
        self._assert_fast_action("ponme Loki")

    def test_cuando_salio_routes_to_fast_info(self):
        # "cuándo salió GTA 5" — factual question (interrogativa). Sprint de
        # latencia: ahora va a fast_info para evitar que el router ofrezca tools
        # de acción por "GTA" y dispare el upgrade-a-thinking + forced-retry
        # (medido 16s); fast_info lo deja en ~2s, respuesta correcta.
        self._assert_fast_info("cuándo salió GTA 5")

    def test_si_stays_in_fast_action(self):
        self._assert_fast_action("sí")


if __name__ == "__main__":
    unittest.main()
