"""Ola 2.2 (perfection roadmap C6, 2026-05-29): pre-flight de VRAM antes de
inyectar una imagen capturada A MITAD de turno.

El pre-flight de _decide_turn solo cubría mode=='vision_action' (imagen de
ENTRADA). Una imagen pedida por el LLM inline (gui.screenshot en turno de texto)
forzaba el preset de visión -> mmproj -> OOM en 4GB sin chequeo. Ahora
_image_inject_vram_safe actúa: seguro -> inyecta; inseguro -> recicla y re-mide;
sigue inseguro -> NO inyecta (+ nota honesta). Sin GPU -> no-op (True).

Tests con watchdog mockeado (sin GPU real ni server).
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.agent_core.agent import Gemma4Agent


def _agent_with_watchdog(wd):
    ag = Gemma4Agent.__new__(Gemma4Agent)
    ag.vram_watchdog = wd
    ag.trace = MagicMock()
    return ag


class ImageInjectVramSafeTest(unittest.TestCase):

    def test_safe_when_vision_safe_true(self):
        wd = MagicMock()
        wd.vision_safe.return_value = True
        ag = _agent_with_watchdog(wd)
        self.assertTrue(ag._image_inject_vram_safe("t1"))
        wd.vision_safe.assert_called()  # se consultó

    def test_no_watchdog_is_safe(self):
        ag = Gemma4Agent.__new__(Gemma4Agent)
        ag.vram_watchdog = None
        self.assertTrue(ag._image_inject_vram_safe("t1"))

    def test_unsafe_then_recycle_makes_safe(self):
        # 1ª medición insegura -> recicla -> 2ª medición segura -> True.
        wd = MagicMock()
        wd.vision_safe.side_effect = [False, True]
        wd.snapshot.return_value = MagicMock(free_mib=900, level="degrade")
        ag = _agent_with_watchdog(wd)
        with patch("gemma4_agent.infra.llama_server.get_shared_manager") as gsm:
            gsm.return_value.recycle_for_vision_leak.return_value = True
            self.assertTrue(ag._image_inject_vram_safe("t1"))
            gsm.return_value.recycle_for_vision_leak.assert_called_once()

    def test_unsafe_even_after_recycle_blocks(self):
        # insegura antes Y después del recycle -> False (no inyectar -> nota honesta).
        wd = MagicMock()
        wd.vision_safe.side_effect = [False, False]
        wd.snapshot.return_value = MagicMock(free_mib=200, level="critical")
        ag = _agent_with_watchdog(wd)
        with patch("gemma4_agent.infra.llama_server.get_shared_manager") as gsm:
            gsm.return_value.recycle_for_vision_leak.return_value = False
            self.assertFalse(ag._image_inject_vram_safe("t1"))

    def test_watchdog_error_fails_open(self):
        # un error del watchdog NO debe bloquear (fail-open: no empeorar el path viejo).
        wd = MagicMock()
        wd.vision_safe.side_effect = RuntimeError("nvidia-smi exploded")
        ag = _agent_with_watchdog(wd)
        self.assertTrue(ag._image_inject_vram_safe("t1"))

    def test_no_gpu_watchdog_is_noop(self):
        # Sin GPU NVIDIA el watchdog real devuelve vision_safe()=True (no-op).
        wd = MagicMock()
        wd.vision_safe.return_value = True  # available=False -> True en el real
        ag = _agent_with_watchdog(wd)
        self.assertTrue(ag._image_inject_vram_safe("t1"))


if __name__ == "__main__":
    unittest.main()
