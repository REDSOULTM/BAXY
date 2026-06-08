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
        from gemma4_agent.routing.semantic_router import embed
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

    def test_unrelated_label_below_threshold(self):
        # HONESTO: el matcher DEBE ABSTENERSE cuando el label NO tiene un botón
        # relacionado (en vez de clickear el menos-malo). 2026-06-07: tras
        # reentrenar el encoder con ejemplos de acción multilingües, "open"↔"Abrir"
        # AHORA sí matchea con margen seguro (open~Abrir=0.849 vs Cerrar=0.639 ->
        # mejora real: clickea el botón correcto). Así que el test del fallback
        # seguro usa un label SIN destino plausible: una palabra ajena a los
        # botones (no es una traducción de ninguno) debe quedar bajo el umbral
        # 0.75 -> el matcher se abstiene en vez de clickear cualquier cosa.
        if not self.available:
            self.skipTest("encoder multilingüe no disponible")
        op = self.embed("xyzzy")  # palabra sin sentido: no es ningún botón
        top = max(_cos(op, self.embed(w)) for w in ("Abrir", "Cerrar", "Minimizar"))
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        self.assertLess(top, ToolRegistry._XLING_SIM_MIN)  # abstiene -> seguro

    def test_open_now_matches_abrir_with_margin(self):
        # Mejora del reentreno (2026-06-07): el encoder ahora relaciona "open" con
        # "Abrir" por encima del umbral Y con margen claro sobre los distractores
        # (Cerrar/Minimizar) -> el matcher clickea el botón correcto en vez de
        # abstenerse. Antes el encoder no lo lograba (se abstenía). Esto fija la
        # capacidad ganada sin perder la seguridad del margen.
        if not self.available:
            self.skipTest("encoder multilingüe no disponible")
        op = self.embed("open")
        sims = sorted((_cos(op, self.embed(w)) for w in ("Abrir", "Cerrar", "Minimizar")), reverse=True)
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        self.assertGreater(sims[0], ToolRegistry._XLING_SIM_MIN)        # Abrir supera el umbral
        self.assertGreater(sims[0] - sims[1], ToolRegistry._XLING_MARGIN)  # con margen sobre el 2do


class XLingualGateTest(unittest.TestCase):
    """El matcher semántico respeta el gate GEMMA4_GUI_XLING y los umbrales."""

    def test_gate_off_returns_none(self):
        import os
        from gemma4_agent.tools_pkg import tools as T

        os.environ["GEMMA4_GUI_XLING"] = "0"
        try:
            tb = T.ToolRegistry.__new__(T.ToolRegistry)
            self.assertIsNone(tb._uia_find_clickable_semantic("five", "Calculadora"))
        finally:
            os.environ.pop("GEMMA4_GUI_XLING", None)

    def test_thresholds_present(self):
        from gemma4_agent.tools_pkg import tools as T

        self.assertGreaterEqual(T.ToolRegistry._XLING_SIM_MIN, 0.5)
        self.assertGreater(T.ToolRegistry._XLING_MARGIN, 0.0)


if __name__ == "__main__":
    unittest.main()
