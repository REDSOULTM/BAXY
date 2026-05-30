"""ITEM 4 (perfection roadmap 2026-05-29): deíctico ring multilingüe.

CRÍTICO (anti-trampa): la detección es por EMBEDDINGS multilingües, NO un regex
por idioma. El test valida deixis en VARIOS idiomas (es/en/pt/fr) — un regex
español fallaría. El entity ring extrae identificadores ESTRUCTURALES (path/url),
no por idioma.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.routing import deictic_detector as D


class EntityRingTest(unittest.TestCase):
    def test_push_explicit_path_field(self):
        r = D.EntityRing()
        r.push_from_result("filesystem", {"path": "C:/Users/x/informe.docx", "ok": True})
        ent = r.most_recent()
        self.assertIsNotNone(ent)
        self.assertEqual(ent[0], "path")
        self.assertIn("informe.docx", ent[1])

    def test_push_url_field(self):
        r = D.EntityRing()
        r.push_from_result("browser", {"url": "https://example.com/p", "ok": True})
        self.assertEqual(r.most_recent()[0], "url")

    def test_extract_path_from_blob(self):
        r = D.EntityRing()
        r.push_from_result("x", {"note": "guardé en D:\\docs\\a.txt listo", "ok": True})
        self.assertEqual(r.most_recent()[0], "path")
        self.assertIn("a.txt", r.most_recent()[1])

    def test_most_recent_first(self):
        r = D.EntityRing()
        r.push_from_result("a", {"path": "C:/1.txt"})
        r.push_from_result("b", {"path": "C:/2.txt"})
        self.assertIn("2.txt", r.most_recent()[1])  # el último primero

    def test_maxlen_bounded(self):
        r = D.EntityRing(maxlen=3)
        for i in range(6):
            r.push_from_result("t", {"path": f"C:/{i}.txt"})
        self.assertIn("5.txt", r.most_recent()[1])

    def test_empty_result_no_push(self):
        r = D.EntityRing()
        r.push_from_result("t", {"ok": True})  # nada extraíble
        self.assertTrue(r.is_empty())

    def test_context_block_has_referent(self):
        r = D.EntityRing()
        r.push_from_result("fs", {"path": "C:/x/informe.docx"})
        block = D.deictic_context_block(r)
        self.assertIn("informe.docx", block)

    def test_context_block_empty_ring(self):
        self.assertEqual(D.deictic_context_block(D.EntityRing()), "")


class GateTest(unittest.TestCase):
    def test_default_on_after_validation(self):
        # 2026-05-29: flippeado a DEFAULT-ON tras validar en vivo (3/3 idiomas).
        prev = os.environ.pop("GEMMA4_DEICTIC", None)
        try:
            self.assertTrue(D.deictic_enabled())  # default ON
        finally:
            if prev is not None:
                os.environ["GEMMA4_DEICTIC"] = prev

    def test_kill_switch_off(self):
        prev = os.environ.get("GEMMA4_DEICTIC")
        os.environ["GEMMA4_DEICTIC"] = "0"
        try:
            self.assertFalse(D.deictic_enabled())
            self.assertFalse(D.needs_deictic_context("abrilo"))  # off -> False
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_DEICTIC", None)
            else:
                os.environ["GEMMA4_DEICTIC"] = prev


class MultilingualDetectionTest(unittest.TestCase):
    """La detección NO es monolingüe: funciona en varios idiomas (embeddings)."""

    def setUp(self):
        self._prev = os.environ.get("GEMMA4_DEICTIC")
        os.environ["GEMMA4_DEICTIC"] = "1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("GEMMA4_DEICTIC", None)
        else:
            os.environ["GEMMA4_DEICTIC"] = self._prev

    def test_deictic_multiple_languages(self):
        # es/en/pt/fr — un regex español fallaría en en/pt/fr.
        for t in ("abrilo", "open it", "abre isso", "ouvre-le", "súbelo"):
            self.assertTrue(D.needs_deictic_context(t), f"no detectó deixis: {t!r}")

    def test_non_deictic_rejected(self):
        for t in ("qué hora es", "hola cómo estás",
                  "abrí Spotify y poné rock música ahora por favor"):
            self.assertFalse(D.needs_deictic_context(t), f"falso positivo: {t!r}")

    def test_long_text_short_circuited(self):
        # Heurística agnóstica de idioma: >4 palabras no es deíctico-corto.
        self.assertFalse(D.needs_deictic_context("abrilo pero antes guardá todo esto"))


if __name__ == "__main__":
    unittest.main()
