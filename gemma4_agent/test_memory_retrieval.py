"""Tests de la memoria en capas para el prompt (investigación 2 §1).

core (identidad, siempre) + retrieval semántico por turno cuando el store crece.
Store chico == volcar todo (sin cambio). Universal (encoder multilingüe) +
fallback seguro (sin encoder -> volcar todo, nunca esconder hechos).
"""
from __future__ import annotations

import unittest

from gemma4_agent import memory_retrieval as mr
from gemma4_agent.memory_retrieval import build_memory_section, _is_core


def _big_store():
    return {
        "user_name": {"value": "Emmanuel"},
        "auto:idioma": {"value": "español"},
        "auto:mama_nombre": {"value": "María, +5491111"},
        "auto:plataforma_video": {"value": "usa Netflix y Disney"},
        "auto:artista_fav": {"value": "le gusta Benson Boone"},
        "auto:editor_codigo": {"value": "usa VS Code"},
        "auto:navegador": {"value": "Chrome por defecto"},
        "auto:juego_fav": {"value": "juega Valorant"},
        "auto:musica_genero": {"value": "escucha pop y rock"},
        "auto:ciudad": {"value": "Curicó"},
        "auto:trabajo": {"value": "hace música"},
        "auto:mascota": {"value": "tiene un gato Tom"},
        "auto:comida_fav": {"value": "le gusta el sushi"},
        "auto:deporte": {"value": "corre de mañana"},
    }


class IsCoreTest(unittest.TestCase):
    def test_explicit_facts_are_core(self):
        self.assertTrue(_is_core("user_name"))      # no auto: -> el user lo guardó
        self.assertTrue(_is_core("preferencia"))

    def test_identity_auto_facts_are_core(self):
        for k in ("auto:nombre", "auto:idioma", "auto:ciudad",
                  "auto:mama_nombre", "auto:timezone"):
            self.assertTrue(_is_core(k), k)

    def test_domain_auto_facts_not_core(self):
        for k in ("auto:juego_fav", "auto:plataforma_video", "auto:comida_fav"):
            self.assertFalse(_is_core(k), k)


class BuildSectionTest(unittest.TestCase):
    def test_empty_store(self):
        self.assertEqual(build_memory_section({}, "hola"), "No persistent memory saved.")

    def test_small_store_injects_all(self):
        small = {f"auto:k{i}": {"value": f"v{i}"} for i in range(6)}
        out = build_memory_section(small, "qué hora es")
        for i in range(6):
            self.assertIn(f"auto:k{i}", out)
        self.assertNotIn("no relevantes", out)  # sin recorte


@unittest.skipUnless(
    __import__("gemma4_agent.semantic_router", fromlist=["_ensure_loaded"])._ensure_loaded(),
    "encoder multilingüe no disponible")
class LayeredRetrievalTest(unittest.TestCase):
    def test_core_always_present(self):
        out = build_memory_section(_big_store(), "pon algo de música")
        for k in ("user_name", "auto:idioma", "auto:mama_nombre"):
            self.assertIn(k, out, k)

    def test_relevant_facts_surface(self):
        out = build_memory_section(_big_store(), "abrí mi editor de código")
        self.assertIn("auto:editor_codigo", out)

    def test_irrelevant_facts_hidden(self):
        out = build_memory_section(_big_store(), "abrí mi editor de código")
        # deporte/comida no tienen que ver con el editor -> ocultos
        self.assertNotIn("auto:deporte", out)
        self.assertIn("no relevantes", out)  # hay pointer a los ocultos

    def test_retrieval_is_multilingual(self):
        # turno en inglés debe traer hechos de música igual (encoder, no es-regex)
        out = build_memory_section(_big_store(), "play some music")
        self.assertTrue(
            "auto:musica_genero" in out or "auto:artista_fav" in out,
            "el retrieval debe generalizar a inglés")


class SafeFallbackTest(unittest.TestCase):
    def test_no_encoder_dumps_all(self):
        # sin encoder, _retrieve_relevant devuelve None -> volcar todo (no esconder)
        orig = mr.__dict__.get("_retrieve_relevant")
        mr._retrieve_relevant = lambda rest, txt: None
        try:
            out = build_memory_section(_big_store(), "lo que sea")
            self.assertIn("auto:deporte", out)  # TODO presente
            self.assertNotIn("no relevantes", out)
        finally:
            mr._retrieve_relevant = orig

    def test_never_raises(self):
        # entradas raras no deben romper
        weird = {"auto:x": {}, "y": {"value": None}}
        try:
            build_memory_section(weird, None)
        except Exception as exc:  # pragma: no cover
            self.fail(f"no debe lanzar: {exc}")


class AntiJunkFilterTest(unittest.TestCase):
    """auto_save NO debe envenenar la memoria con basura de pruebas (inv 2 §4).
    El save explícito (pedido por el user) NO se filtra."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from gemma4_agent.memory import MemoryStore
        self.store = MemoryStore(Path(tempfile.mktemp(suffix=".json")))

    def test_junk_values_rejected_on_auto_save(self):
        r = self.store.auto_save([
            {"key": "a", "value": "test"},
            {"key": "b", "value": "asdf"},
            {"key": "c", "value": "1234"},
            {"key": "d", "value": "usa Netflix"},   # real -> se guarda
        ])
        self.assertEqual(len(r["added"]), 1)
        self.assertTrue(r["added"][0].endswith("d"))
        self.assertEqual(len(r["skipped"]), 3)
        self.assertTrue(all(s["reason"] == "junk_value" for s in r["skipped"]))

    def test_real_facts_pass(self):
        r = self.store.auto_save([
            {"key": "nombre", "value": "Emmanuel"},
            {"key": "ciudad", "value": "Curicó"},
            {"key": "mascota", "value": "Tom"},  # corto pero real
        ])
        self.assertEqual(len(r["added"]), 3)

    def test_explicit_save_not_filtered(self):
        # el user pidió guardar esto explícitamente -> NO se filtra aunque sea raro
        from gemma4_agent.memory import _is_junk_value
        self.assertTrue(_is_junk_value("test"))  # sería junk en auto_save
        r = self.store.save("recordatorio", "test")  # pero explícito pasa
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
