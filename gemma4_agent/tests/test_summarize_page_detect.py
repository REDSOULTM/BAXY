"""FORM gate de 'resumir esta página web' (feature CDP). El handler real (extracción +
resumen) es condicional a un browser Playwright adjunto; acá solo se congela el detector."""
import unittest
from gemma4_agent.agent_core.agent import _is_summarize_page_request as f


class SummarizePageDetectTest(unittest.TestCase):
    def test_positives(self):
        for q in ["resumime esta página", "resumí la página", "summarize this page",
                  "hacé un resumen de esta página web", "resumime el artículo que estoy leyendo",
                  "riassumi questa pagina", "résume cette page"]:
            self.assertTrue(f(q), q)

    def test_negatives_file(self):
        # un ARCHIVO no es la página web -> document.summarize, no este handler
        for q in ["resumime informe.pdf", "resumí el documento ventas.docx",
                  "resumime el excel reporte.xlsx"]:
            self.assertFalse(f(q), q)

    def test_negatives_other(self):
        for q in ["abrí la página de gmail", "qué hay en esta página",
                  "contame de Roma", "andá a la página de pivigames"]:
            self.assertFalse(f(q), q)


if __name__ == "__main__":
    unittest.main()
