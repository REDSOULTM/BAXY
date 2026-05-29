"""Unit tests for requires_server_restart (Fix: avoid avoidable restarts).

2026-05-26: el sistema se colapsó a un solo perfil operante (vram4) + standby.
`requires_server_restart` sigue siendo la misma lógica; estos tests la ejercen
con el perfil real (vram4) como base "corriendo" y standby como "server off",
más perfiles SINTÉTICOS vía dataclasses.replace() para los cambios de un solo
campo (ctx/model/vision/flags). No dependen de perfiles eliminados.
"""
from __future__ import annotations

import unittest
from dataclasses import replace

from ..infra.profiles import PROFILES, Profile, requires_server_restart


class TestRequiresServerRestart(unittest.TestCase):

    def setUp(self):
        self.run = PROFILES["vram4"]       # único perfil con server corriendo
        self.standby = PROFILES["standby"]  # server apagado

    def test_first_apply_with_server_running_needs_start(self):
        self.assertTrue(requires_server_restart(None, self.run))

    def test_first_apply_standby_does_not_need_restart(self):
        self.assertFalse(requires_server_restart(None, self.standby))

    def test_same_profile_no_restart(self):
        self.assertFalse(requires_server_restart(self.run, self.run))

    def test_context_change_needs_restart(self):
        modified = replace(self.run, context_size=self.run.context_size + 4096)
        self.assertTrue(requires_server_restart(self.run, modified))

    def test_model_path_change_needs_restart(self):
        modified = replace(self.run, model_path="/other/model.gguf")
        self.assertTrue(requires_server_restart(self.run, modified))

    def test_vision_change_needs_restart(self):
        modified = replace(self.run, vision_enabled=False)
        self.assertTrue(requires_server_restart(self.run, modified))

    def test_server_off_to_on_needs_restart(self):
        self.assertTrue(requires_server_restart(self.standby, self.run))

    def test_server_on_to_off_needs_restart(self):
        self.assertTrue(requires_server_restart(self.run, self.standby))

    def test_both_off_no_restart(self):
        modified = replace(self.standby, fact_extraction=True)
        # standby is server_running=False; both off -> no restart needed
        self.assertFalse(requires_server_restart(self.standby, modified))

    def test_only_parallel_tools_change_no_restart(self):
        """Cambiar solo parallel_tools (flag del cliente Python) NO requiere
        reiniciar el binario llama-server."""
        modified = replace(self.run, parallel_tools=not self.run.parallel_tools)
        self.assertFalse(requires_server_restart(self.run, modified))

    def test_only_fact_extraction_change_no_restart(self):
        modified = replace(self.run, fact_extraction=not self.run.fact_extraction)
        self.assertFalse(requires_server_restart(self.run, modified))

    def test_only_rerank_change_no_restart(self):
        modified = replace(self.run, rerank_enabled=not self.run.rerank_enabled)
        self.assertFalse(requires_server_restart(self.run, modified))

    def test_only_voice_change_no_restart(self):
        modified = replace(self.run, voice_enabled=not self.run.voice_enabled)
        self.assertFalse(requires_server_restart(self.run, modified))

    def test_cross_profile_vram4_to_standby_needs_restart(self):
        # Real: pasar de vram4 (server on, modelo cargado) a standby (server off)
        # DEBE reiniciar (se apaga el server). Es el único cambio de perfil real
        # que queda tras colapsar a un solo perfil operante.
        self.assertTrue(requires_server_restart(self.run, self.standby))


if __name__ == "__main__":
    unittest.main()
