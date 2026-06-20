"""Lecturas VOLÁTILES del SO (RAM/disco/CPU/batería libre/usado, %, °C, GHz) NO son
hechos durables: guardadas como memoria envenenan el recall con datos rancios.

CAUSA RAÍZ medida 2026-06-20: una "free_memory: 14410756 MB" rancia hacía que
"cuánta memoria tengo" recordara ese dato viejo (vía el tool memory) en vez de
consultar el system tool en vivo -> respuesta confabulada. El save explícito NO
pasaba por ningún filtro. Doble capa: (1) el store rechaza la lectura volátil al
guardar (explícito y auto); (2) el honesty-guard caza la medida de sistema sin
fundamento cuando el único tool fue memory/reminder (no pueden leer el SO)."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gemma4_agent.memory_pkg.memory import MemoryStore, _is_volatile_system_reading
from gemma4_agent.safety_pkg.reply_validator import system_value_claim_unfounded


class VolatileReadingDetectTest(unittest.TestCase):
    def test_volatile_readings_detected(self):
        for k, v in [
            ("free_memory", "14410756 MB"), ("disk_free", "181 GB"),
            ("cpu_usage", "85%"), ("ram_libre", "13.7 GB"), ("battery", "90%"),
            ("gpu_temp", "72 °C"), ("memoria disponible", "8 GB"),
        ]:
            self.assertTrue(_is_volatile_system_reading(k, v), f"{k}={v} debería ser volátil")

    def test_durable_facts_not_blocked(self):
        for k, v in [
            ("user_name", "red"), ("prefencia_cafe", "me gusta el café"),
            ("mi_pc", "mi PC tiene 16 GB de RAM"),  # descriptivo, no medida pelada
            ("cumpleaños", "marzo"), ("altura", "1.80 m"), ("precio", "5000"),
            ("programa", "diagrama listo"),  # 'ram'/'gram' dentro de palabra, sin medida
        ]:
            self.assertFalse(_is_volatile_system_reading(k, v), f"{k}={v} NO debería bloquearse")


class VolatileSaveGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = MemoryStore(Path(self._tmp.name) / "mem.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_explicit_save_rejects_volatile(self):
        r = self.store.save("free_memory", "14410756 MB")
        self.assertFalse(r["ok"])
        self.assertNotIn("free_memory", self.store.recall()["items"])

    def test_explicit_save_keeps_durable(self):
        r = self.store.save("mi_pc", "mi PC tiene 16 GB de RAM")
        self.assertTrue(r["ok"])
        self.assertIn("mi_pc", self.store.recall()["items"])

    def test_auto_save_skips_volatile(self):
        r = self.store.auto_save([
            {"key": "free_memory", "value": "14410756 MB"},
            {"key": "color", "value": "le gusta el azul"},
        ])
        self.assertIn("auto:color", self.store.recall()["items"])
        self.assertNotIn("auto:free_memory", self.store.recall()["items"])
        self.assertTrue(any(s.get("reason") == "volatile_reading" for s in r["skipped"]))


class HonestyGuardNonGroundingTest(unittest.TestCase):
    def test_memory_only_does_not_ground_system_measure(self):
        calls = [{"name": "memory", "args": {}, "result": {"items": {}}}]
        self.assertTrue(system_value_claim_unfounded(
            "cuánta memoria tengo", "Tienes 16 GB de memoria libre.", calls))

    def test_web_still_exempts(self):
        calls = [{"name": "web", "args": {}, "result": {"text": "la PS5 tiene 16 GB"}}]
        self.assertFalse(system_value_claim_unfounded(
            "cuánta ram tiene la ps5", "Tiene 99 GB.", calls))

    def test_grounded_number_not_flagged(self):
        calls = [{"name": "memory", "args": {}, "result": {"items": {"x": {"value": "42 GB"}}}}]
        self.assertFalse(system_value_claim_unfounded(
            "qué guardaste", "Guardaste 42 GB.", calls))

    def test_no_space_unit_still_caught(self):
        # "16GB" pegado (sin espacio) también es una medida -> el \b inicial de la
        # unidad no debe impedir detectarla (regresión 2026-06-20: se colaba el confab).
        calls = [{"name": "memory", "args": {}, "result": {"items": {}}}]
        self.assertTrue(system_value_claim_unfounded(
            "cuánta memoria tengo", "Tengo 16GB de memoria RAM.", calls))


if __name__ == "__main__":
    unittest.main()
