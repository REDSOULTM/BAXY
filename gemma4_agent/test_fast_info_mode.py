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

    def test_win_is_profile_agnostic(self):
        """El big win (thinking OFF en preguntas) NO debe depender del perfil. La
        única entrada que varía por perfil en choose_mode es base_max_tokens. A/B
        en vivo (2026-05-22) confirmó que thinking-OFF da respuestas correctas en
        E2B-Q4 (vram3, el modelo más débil: 0.25-0.52s, todas correctas) igual que
        en E4B-Q6 (vram12). Este test pina que el routing + el thinking-OFF + el
        cap conciso son IDÉNTICOS sea cual sea el base_max_tokens del perfil
        (vram3..vram16). Una regresión que ate el win a un perfil falla acá."""
        q = "explica que es la fotosintesis"
        # base_max_tokens spans the realistic per-profile range (config default
        # 1280; standby 4096-ctx profiles still feed the same agent max_tokens).
        for base in (128, 256, 512, 1280, 2048):
            m = choose_mode(q, "auto", base)
            self.assertEqual(m.name, "fast_info", f"base={base} must still route fast_info")
            self.assertFalse(m.enable_thinking, f"base={base} must keep thinking OFF")
            self.assertLessEqual(m.max_tokens, 320,
                                 f"base={base}: concise cap holds (no per-profile blow-up)")

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
