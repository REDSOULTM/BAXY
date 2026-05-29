"""Tests para la capa de modos de accesibilidad (accessibility.py).

Mock-only: no toca la GUI, no emite input, no arranca el LLM. Persistencia va a
un tmpdir parcheando ACTIVE_MODE_PATH.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.computer_use_pkg import accessibility as a11y



class ModeCatalogTest(unittest.TestCase):
    def test_three_modes_exist(self):
        names = a11y.list_names()
        self.assertEqual(names[0], "normal")  # normal siempre primero
        self.assertIn("no_vidente", names)
        self.assertIn("movilidad", names)

    def test_normal_is_a_noop_hint(self):
        self.assertEqual(a11y.get("normal").system_hint, "")
        self.assertFalse(a11y.get("normal").narrate_all_actions)
        self.assertFalse(a11y.get("normal").hands_free_only)

    def test_no_vidente_flags_are_perceptual(self):
        m = a11y.get("no_vidente")
        self.assertTrue(m.narrate_all_actions)
        self.assertTrue(m.read_screen_on_demand)
        self.assertFalse(m.hands_free_only)  # ve-no-importa: no es motor
        self.assertGreater(len(m.system_hint), 100)
        # B4: para "leeme la pantalla" el modo debe ofrecer la tool de visión.
        self.assertIn("vision", m.preferred_tools)

    def test_movilidad_flags_are_motor(self):
        m = a11y.get("movilidad")
        self.assertTrue(m.hands_free_only)
        self.assertTrue(m.confirm_irreversible_spoken)
        self.assertFalse(m.narrate_all_actions)  # ve la pantalla: no narra todo
        self.assertIn("computer_use", m.preferred_tools)

    def test_unknown_name_falls_back_to_normal(self):
        self.assertEqual(a11y.get("zzz-unknown").name, "normal")
        self.assertEqual(a11y.get(None).name, "normal")


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._path = Path(self._td.name) / "active_accessibility_mode.txt"
        self._patch = mock.patch.object(a11y, "ACTIVE_MODE_PATH", self._path)
        self._patch.start()
        # asegurar que el env no contamine
        self._env = os.environ.pop("GEMMA4_ACCESSIBILITY_MODE", None)

    def tearDown(self):
        self._patch.stop()
        self._td.cleanup()
        if self._env is not None:
            os.environ["GEMMA4_ACCESSIBILITY_MODE"] = self._env

    def test_default_is_normal_without_file(self):
        self.assertEqual(a11y.get_active_mode().name, "normal")

    def test_set_then_get_roundtrips(self):
        a11y.set_active_mode("no_vidente")
        self.assertTrue(self._path.is_file())
        self.assertEqual(a11y.get_active_mode().name, "no_vidente")

    def test_set_normalizes_case_and_space(self):
        a11y.set_active_mode("  Movilidad  ")
        self.assertEqual(a11y.get_active_mode().name, "movilidad")

    def test_set_unknown_raises(self):
        with self.assertRaises(ValueError):
            a11y.set_active_mode("supervista")

    def test_corrupt_file_falls_back_to_normal(self):
        self._path.write_text("garbage-mode", encoding="utf-8")
        self.assertEqual(a11y.get_active_mode().name, "normal")

    def test_env_overrides_file_without_writing_it(self):
        a11y.set_active_mode("normal")
        with mock.patch.dict(os.environ, {"GEMMA4_ACCESSIBILITY_MODE": "movilidad"}):
            self.assertEqual(a11y.get_active_mode().name, "movilidad")
        # el env NO debe haber pisado el archivo persistido
        self.assertEqual(self._path.read_text(encoding="utf-8").strip(), "normal")


if __name__ == "__main__":
    unittest.main()
