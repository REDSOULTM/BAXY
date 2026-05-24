"""R7: el matcher cross-lingual usa embeddings multilingües (label↔UI) con
umbral + margen. Verifica que el encoder del router resuelve translation-pairs
(five↔Cinco) y NO confunde distractores."""
from __future__ import annotations

import unittest


def _cos(a, b):
    return float(sum(x * y for x, y in zip(a, b)))


class XLingualEmbedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gemma4_agent.semantic_router import embed
        cls.embed = staticmethod(embed)
        cls.available = embed("five") is not None

    def test_translation_pair_high_similarity(self):
        if not self.available:
            self.skipTest("encoder multilingüe no disponible")
        five = self.embed("five")
        cinco = self.embed("Cinco")
        nueve = self.embed("Nueve")
        sim_pair = _cos(five, cinco)
        sim_distractor = _cos(five, nueve)
        # five↔Cinco debe superar el umbral del matcher (0.75) y sacarle margen
        # claro al distractor (Nueve).
        self.assertGreater(sim_pair, 0.75)
        self.assertGreater(sim_pair - sim_distractor, 0.10)

    def test_low_confidence_pairs_below_threshold(self):
        # HONESTO: no todos los pares cross-lingual son fáciles. "open"↔"Abrir"
        # (palabra suelta capitalizada) NO supera el umbral 0.75 en este encoder
        # (medido: open~Abrir=0.369, open~Cerrar=0.548). El matcher DEBE ABSTENERSE
        # en esos casos (margen/umbral) en vez de clickear mal -> es el fallback
        # seguro. Este test fija que el umbral 0.75 efectivamente filtra el caso
        # ambiguo (no que el embed acierte el par).
        if not self.available:
            self.skipTest("encoder multilingüe no disponible")
        op = self.embed("open")
        top = max(_cos(op, self.embed(w)) for w in ("Abrir", "Cerrar", "Minimizar"))
        from gemma4_agent.tools import ToolRegistry
        self.assertLess(top, ToolRegistry._XLING_SIM_MIN)  # abstiene -> seguro


class XLingualGateTest(unittest.TestCase):
    """El matcher semántico respeta el gate GEMMA4_GUI_XLING y los umbrales."""

    def test_gate_off_returns_none(self):
        import os
        from gemma4_agent import tools as T
        os.environ["GEMMA4_GUI_XLING"] = "0"
        try:
            tb = T.ToolRegistry.__new__(T.ToolRegistry)
            self.assertIsNone(tb._uia_find_clickable_semantic("five", "Calculadora"))
        finally:
            os.environ.pop("GEMMA4_GUI_XLING", None)

    def test_thresholds_present(self):
        from gemma4_agent import tools as T
        self.assertGreaterEqual(T.ToolRegistry._XLING_SIM_MIN, 0.5)
        self.assertGreater(T.ToolRegistry._XLING_MARGIN, 0.0)


if __name__ == "__main__":
    unittest.main()
