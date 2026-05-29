"""resolve_turn_model debe elegir el preset de VISIÓN para un turno con imagen
AUNQUE el preset de visión esté UNLOADED. En router mode (--models-max 1) el
preset de visión es lazy: arranca unloaded y se carga on-demand al pedirlo por
nombre. El bug (screenshot 2026-05-22): resolve_turn_model miraba solo `loaded`,
encontraba el -text cargado, y mandaba la imagen ahí -> HTTP 500 "image input is
not supported / provide the mmproj".

EJE del norte rector: FIABILIDAD (el agente no debe 500-ear ni degradar en
silencio cuando llega una imagen) + el mmproj se carga automáticamente. Aplica a
TODOS los perfiles (la lógica es shared en llama_server.resolve_turn_model).
Relacionado: [[project-router-mode-lazy-vision-2026-05-20]]."""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.infra import llama_server as ls



class TestLazyVisionResolve(unittest.TestCase):
    def tearDown(self):
        ls.reset_model_probe_cache()

    def _probe(self, ids, loaded):
        return mock.patch.object(ls, "_probe_server_models", return_value=(ids, loaded))

    def test_image_picks_unloaded_vision_preset(self):
        """EL bug: text loaded, vision UNLOADED. Una imagen DEBE rutear a -vision
        (que el router carga on-demand), NO a -text (que da 500)."""
        with self._probe(["vram12-text", "vram12-vision"], ["vram12-text"]):
            ls.reset_model_probe_cache()
            self.assertEqual(ls.resolve_turn_model(has_image=True), "vram12-vision")

    def test_text_turn_uses_loaded_text_preset(self):
        with self._probe(["vram12-text", "vram12-vision"], ["vram12-text"]):
            ls.reset_model_probe_cache()
            self.assertEqual(ls.resolve_turn_model(has_image=False), "vram12-text")

    def test_image_with_both_loaded_still_vision(self):
        with self._probe(["vram8-text", "vram8-vision"], ["vram8-text", "vram8-vision"]):
            ls.reset_model_probe_cache()
            self.assertEqual(ls.resolve_turn_model(has_image=True), "vram8-vision")

    def test_image_falls_back_to_text_when_no_vision_preset(self):
        # Perfil/server SIN soporte de visión (no hay -vision advertido): un turno
        # con imagen cae a -text para no 400/500-loopear (degradación honesta).
        with self._probe(["vram3-text"], ["vram3-text"]):
            ls.reset_model_probe_cache()
            self.assertEqual(ls.resolve_turn_model(has_image=True), "vram3-text")

    def test_non_router_server_returns_none(self):
        # Server con un solo modelo plano (no router) -> None (caller usa default).
        with self._probe(["gemma-4"], ["gemma-4"]):
            ls.reset_model_probe_cache()
            self.assertIsNone(ls.resolve_turn_model(has_image=True))

    def test_works_across_profiles(self):
        # La lógica es shared: el fix aplica a cualquier <perfil>-vision unloaded.
        for prof in ("vram3", "vram4", "vram6", "vram8", "vram12", "vram16"):
            with self._probe([f"{prof}-text", f"{prof}-vision"], [f"{prof}-text"]):
                ls.reset_model_probe_cache()
                self.assertEqual(ls.resolve_turn_model(has_image=True), f"{prof}-vision",
                                 f"{prof}: imagen debe rutear a vision aunque esté unloaded")


if __name__ == "__main__":
    unittest.main()
