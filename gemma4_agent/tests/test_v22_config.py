"""Tests para los defaults v22 — Plan A2 (set always-on de tool-rules reducido).

Puros (sin modelo/GPU/archivos). El default FA-off + cache-ram del INI de router
(write_router_presets) se verifica on-demand con scripts/_verify_v22_defaults.py
(necesita el archivo del modelo presente, asi que no es un unit-test puro).
"""
import os
import unittest

from ..agent_core import core_tools_pareto as ctp


class TestPlanA2CoreRules(unittest.TestCase):
    def test_core_size_is_6(self):
        # v22 Plan A2: 15 -> 6 (piso del system prompt ~9.4k -> ~5k).
        self.assertEqual(ctp.CORE_SIZE, 6)

    def test_default_core_tools_is_the_6_set(self):
        self.assertEqual(
            ctp._default_core_tools(),
            ("app", "audio", "session", "system", "web", "window"),
        )

    def test_default_set_is_small(self):
        # Anti-regresion: que nadie lo vuelva a 15 silenciosamente.
        self.assertLessEqual(len(ctp._default_core_tools()), 8)

    def test_env_override_parsed_and_sorted(self):
        prev = os.environ.get("GEMMA4_CORE_RULES")
        try:
            os.environ["GEMMA4_CORE_RULES"] = "media, browser ,gui"
            self.assertEqual(ctp.read_user_core_tools(), ("browser", "gui", "media"))
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_CORE_RULES", None)
            else:
                os.environ["GEMMA4_CORE_RULES"] = prev

    def test_empty_override_ignored(self):
        prev = os.environ.get("GEMMA4_CORE_RULES")
        try:
            os.environ["GEMMA4_CORE_RULES"] = "   "
            # vacio -> NO override; cae al default (o al json del usuario si existe).
            # Verificamos que no explota y devuelve algo no-vacio.
            result = ctp.read_user_core_tools()
            self.assertIsInstance(result, tuple)
            self.assertGreaterEqual(len(result), 1)
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_CORE_RULES", None)
            else:
                os.environ["GEMMA4_CORE_RULES"] = prev


if __name__ == "__main__":
    unittest.main()
