"""Modo visión SIEMPRE activo (mmproj residente) — 2026-06-09.

Pedido del usuario: que la visión esté siempre cargada salvo que la apague, para
que una imagen NO pague la carga on-demand del mmproj (~2-5s del router-mode lazy).
MEDIDO en build llama.cpp 9090: el mmproj residente NO penaliza el cache de texto
(issue ggml-org #21133 ya fixeado; turno warm re-evaluó 10 tok/22ms con flags de
prod). Por eso el default es ON.

Estos tests cubren la LÓGICA de gating (vision_always vs router_mode), no la
medición de latencia (esa vive en scripts/_diag/_measure_mmproj_text_cache.py).
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from gemma4_agent.infra import llama_server as ls


class TestVisionAlwaysGating(unittest.TestCase):
    def _env(self, **kw):
        return mock.patch.dict(os.environ, kw, clear=False)

    def test_default_is_vision_always_on(self):
        # sin env var -> visión residente por default.
        with self._env():
            os.environ.pop("GEMMA4_VISION_ALWAYS", None)
            self.assertTrue(ls.vision_always_enabled())

    def test_vision_always_disables_router_mode(self):
        # visión residente y router-mode (lazy) son mutuamente excluyentes:
        # si la visión va SIEMPRE cargada, NO se usa el router-mode.
        with self._env(GEMMA4_VISION_ALWAYS="1"):
            self.assertTrue(ls.vision_always_enabled())
            self.assertFalse(ls.router_mode_enabled())

    def test_off_falls_back_to_router_mode(self):
        # apagar visión-siempre -> vuelve el router-mode lazy (default ON).
        with self._env(GEMMA4_VISION_ALWAYS="0"):
            os.environ.pop("GEMMA4_ROUTER_MODE", None)
            self.assertFalse(ls.vision_always_enabled())
            self.assertTrue(ls.router_mode_enabled())

    def test_off_respects_explicit_router_off(self):
        # con visión-siempre OFF, GEMMA4_ROUTER_MODE=0 sigue valiendo (single model
        # clásico sin router ni residencia forzada).
        with self._env(GEMMA4_VISION_ALWAYS="0", GEMMA4_ROUTER_MODE="0"):
            self.assertFalse(ls.vision_always_enabled())
            self.assertFalse(ls.router_mode_enabled())

    def test_various_falsey_values(self):
        for val in ("0", "false", "no", "off", "FALSE", "Off"):
            with self._env(GEMMA4_VISION_ALWAYS=val):
                self.assertFalse(ls.vision_always_enabled(),
                                 f"{val!r} debería desactivar visión-siempre")

    def test_various_truthy_values(self):
        for val in ("1", "true", "yes", "on", "anything"):
            with self._env(GEMMA4_VISION_ALWAYS=val):
                self.assertTrue(ls.vision_always_enabled(),
                                f"{val!r} debería mantener visión-siempre ON")


class TestVisionAlwaysToggleMapping(unittest.TestCase):
    def test_toggle_maps_to_env_var(self):
        # el toggle de la GUI 'visionAlways' debe mapear a GEMMA4_VISION_ALWAYS.
        from gemma4_agent.infra.server import _TOGGLE_ENV_MAP
        self.assertEqual(_TOGGLE_ENV_MAP.get("visionAlways"), "GEMMA4_VISION_ALWAYS")

    def test_apply_toggle_writes_env(self):
        from gemma4_agent.infra.server import _apply_toggle_env_vars
        with mock.patch.dict(os.environ, {}, clear=False):
            _apply_toggle_env_vars({"visionAlways": True})
            self.assertEqual(os.environ.get("GEMMA4_VISION_ALWAYS"), "true")
            _apply_toggle_env_vars({"visionAlways": False})
            self.assertEqual(os.environ.get("GEMMA4_VISION_ALWAYS"), "false")


if __name__ == "__main__":
    unittest.main()
