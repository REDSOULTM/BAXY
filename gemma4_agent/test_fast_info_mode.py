"""fast_info mode (sprint de latencia 2026-05-22): info questions answered from
parametric knowledge route here — thinking OFF, concise voice hint, moderate
max_tokens. MEDIDO en vivo: thinking en estas preguntas es puro costo de latencia
y a menudo PEOR calidad (cx5 "RAM vs disco" 48s->1.1s; cx1 "fotosintesis" 7s->1s).

EJE del norte rector: LATENCIA con calidad PRESERVADA (medida: quality agregado
0.959 -> 0.967, subió). Pin: propiedades del modo + que las preguntas factuales/
informativas rutean acá y no a research (thinking ON)."""
from __future__ import annotations

import unittest

from gemma4_agent.modes import choose_mode, _infer_mode


class TestFastInfoMode(unittest.TestCase):
    def test_mode_properties(self):
        m = choose_mode("explica que es la fotosintesis", "auto", 512)
        self.assertEqual(m.name, "fast_info")
        self.assertFalse(m.enable_thinking, "info questions must NOT think (latency)")
        self.assertLessEqual(m.max_tokens, 320, "concise budget")
        self.assertGreater(m.max_tokens, 128, "but bigger than fast_action (no truncation)")
        # Timeout derived from budget, bounded.
        self.assertLessEqual(m.request_timeout_s, 60)

    def test_factual_questions_route_to_fast_info(self):
        for q in ["cuando salio GTA 5", "quien escribio el Quijote",
                  "cuantos planetas hay", "cual es la capital de Francia",
                  "que es la fotosintesis", "por que el cielo es azul"]:
            self.assertEqual(_infer_mode(q), "fast_info", f"{q!r} -> fast_info")

    def test_actions_do_not_route_to_fast_info(self):
        for q in ["abre Chrome", "pon musica", "cierra WhatsApp"]:
            self.assertNotEqual(_infer_mode(q), "fast_info", f"{q!r} is an action")

    def test_retrieval_still_research(self):
        for q in ["buscame informacion actual del dolar", "que noticias hay de IA"]:
            self.assertEqual(_infer_mode(q), "research", f"{q!r} needs web -> research")

    def test_smalltalk_stays_fast_action(self):
        for q in ["hola", "gracias", "si"]:
            self.assertEqual(_infer_mode(q), "fast_action")


if __name__ == "__main__":
    unittest.main()
