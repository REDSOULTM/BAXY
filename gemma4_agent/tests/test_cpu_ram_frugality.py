"""Ola 2.4 RAM-frugality (perfection roadmap 2026-05-29): el perfil CPU limita
threads (-t) y baja prioridad (--prio low) para no robarle CPU al juego que
motivó el fallback. El path GPU queda byte-idéntico (anti-regresión CUDA).

Verificado en la build (b9090+): -t y --prio existen; --keep-alive/idle-unload
NO -> no se promete unload-on-idle (regla #3: no celebrar sin medir).
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.infra.llama_server import llama_command
from gemma4_agent.infra.profiles import PROFILES
from gemma4_agent.infra.config import AgentConfig


def _cmd(profile_name: str) -> list[str]:
    return llama_command(AgentConfig.from_env(), PROFILES[profile_name])


class CpuThrottleTest(unittest.TestCase):

    def test_cpu_profile_has_threads(self):
        cmd = _cmd("cpu")
        self.assertIn("-t", cmd)
        self.assertEqual(cmd[cmd.index("-t") + 1], "4")  # cpu_threads=4

    def test_cpu_profile_has_low_prio(self):
        cmd = _cmd("cpu")
        self.assertIn("--prio", cmd)
        self.assertEqual(cmd[cmd.index("--prio") + 1], "-1")  # low

    def test_cpu_profile_is_ngl_zero(self):
        cmd = _cmd("cpu")
        self.assertEqual(cmd[cmd.index("-ngl") + 1], "0")

    def test_gpu_profile_unchanged(self):
        # vram4 (GPU) NO debe recibir -t ni --prio (path byte-idéntico).
        cmd = _cmd("vram4")
        self.assertNotIn("-t", cmd)
        self.assertNotIn("--prio", cmd)
        self.assertEqual(cmd[cmd.index("-ngl") + 1], "99")

    def test_cpu_threads_env_override(self):
        prev = os.environ.get("GEMMA4_CPU_THREADS")
        os.environ["GEMMA4_CPU_THREADS"] = "2"
        try:
            cmd = _cmd("cpu")
            self.assertEqual(cmd[cmd.index("-t") + 1], "2")
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_CPU_THREADS", None)
            else:
                os.environ["GEMMA4_CPU_THREADS"] = prev

    def test_cpu_prio_opt_out(self):
        prev = os.environ.get("GEMMA4_CPU_PRIO_LOW")
        os.environ["GEMMA4_CPU_PRIO_LOW"] = "0"
        try:
            cmd = _cmd("cpu")
            self.assertNotIn("--prio", cmd)
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_CPU_PRIO_LOW", None)
            else:
                os.environ["GEMMA4_CPU_PRIO_LOW"] = prev


if __name__ == "__main__":
    unittest.main()
