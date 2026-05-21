"""Unit tests for requires_server_restart (Fix: avoid avoidable restarts)."""
from __future__ import annotations

import unittest
from dataclasses import replace

from .profiles import PROFILES, Profile, requires_server_restart


class TestRequiresServerRestart(unittest.TestCase):

    def setUp(self):
        # Renombrados por VRAM (2026-05-20): performance->vram16, balanced_8gb->vram8.
        self.perf = PROFILES["vram16"]
        self.bal8 = PROFILES["vram8"]
        self.standby = PROFILES["standby"]

    def test_first_apply_with_server_running_needs_start(self):
        self.assertTrue(requires_server_restart(None, self.perf))

    def test_first_apply_standby_does_not_need_restart(self):
        self.assertFalse(requires_server_restart(None, self.standby))

    def test_same_profile_no_restart(self):
        self.assertFalse(requires_server_restart(self.perf, self.perf))

    def test_context_change_needs_restart(self):
        # Use a value guaranteed != the profile's own ctx (vram16 is now 8192).
        modified = replace(self.perf, context_size=self.perf.context_size + 4096)
        self.assertTrue(requires_server_restart(self.perf, modified))

    def test_model_path_change_needs_restart(self):
        modified = replace(self.perf, model_path="/other/model.gguf")
        self.assertTrue(requires_server_restart(self.perf, modified))

    def test_vision_change_needs_restart(self):
        modified = replace(self.perf, vision_enabled=False)
        self.assertTrue(requires_server_restart(self.perf, modified))

    def test_server_off_to_on_needs_restart(self):
        self.assertTrue(requires_server_restart(self.standby, self.perf))

    def test_server_on_to_off_needs_restart(self):
        self.assertTrue(requires_server_restart(self.perf, self.standby))

    def test_both_off_no_restart(self):
        modified = replace(self.standby, fact_extraction=True)
        # standby is server_running=False; both off -> no restart needed
        self.assertFalse(requires_server_restart(self.standby, modified))

    def test_only_parallel_tools_change_no_restart(self):
        """Cambiar solo parallel_tools (flag del cliente Python) NO requiere
        reiniciar el binario llama-server."""
        modified = replace(self.perf, parallel_tools=not self.perf.parallel_tools)
        self.assertFalse(requires_server_restart(self.perf, modified))

    def test_only_fact_extraction_change_no_restart(self):
        modified = replace(self.perf, fact_extraction=not self.perf.fact_extraction)
        self.assertFalse(requires_server_restart(self.perf, modified))

    def test_only_rerank_change_no_restart(self):
        modified = replace(self.perf, rerank_enabled=not self.perf.rerank_enabled)
        self.assertFalse(requires_server_restart(self.perf, modified))

    def test_only_voice_change_no_restart(self):
        modified = replace(self.perf, voice_enabled=not self.perf.voice_enabled)
        self.assertFalse(requires_server_restart(self.perf, modified))

    def test_cross_profile_perf_to_bal8_needs_restart(self):
        # Real-world: cambiar de vram16 (ctx=32K, modelo del usuario) a vram8
        # (ctx=16K, E4B-Q4_K_XL) DEBE reiniciar (cambia context_size +
        # model_path). Ambos tienen visión ON, así que vision no cambia.
        self.assertTrue(requires_server_restart(self.perf, self.bal8))


if __name__ == "__main__":
    unittest.main()
