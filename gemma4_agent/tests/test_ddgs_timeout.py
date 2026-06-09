"""ddgs_search debe pasar un TIMEOUT corto por backend a la librería ddgs.

MEDIDO 2026-06-09 (datos móviles/red mala): sin timeout, ddgs default a 10 s por
petición y `ddgs_search` prueba hasta 3 backends (google→brave→auto) → peor caso
30 s, y el 2do pase del LLM no podía empezar hasta que la búsqueda terminara (lo
que el usuario siente como 'tarda mucho en arrancar la GPU'). El fix acota el
timeout por backend (default 5 s, override GEMMA4_DDGS_TIMEOUT). Con red buena no
cambia nada (el backend responde antes del timeout).
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock


def _install_fake_ddgs(captured_timeouts, results_by_call=None):
    """Inyecta un módulo `ddgs` falso que registra el timeout con que se construye
    DDGS y devuelve resultados controlados. Devuelve el módulo para limpiar."""
    fake = types.ModuleType("ddgs")

    class _FakeDDGS:
        def __init__(self, *a, **kw):
            captured_timeouts.append(kw.get("timeout"))

        def text(self, query, **kw):
            if results_by_call is not None and results_by_call:
                return results_by_call.pop(0)
            return [{"title": "x", "href": "https://example.com/", "body": "y"}]

    fake.DDGS = _FakeDDGS
    return fake


class TestDdgsTimeout(unittest.TestCase):
    def setUp(self):
        # Asegurar que site_resolver esté importado (la func hace import lazy de ddgs).
        from gemma4_agent.tools_pkg import site_resolver  # noqa: F401
        self._sr = sys.modules["gemma4_agent.tools_pkg.site_resolver"]

    def test_default_timeout_is_passed(self):
        captured: list = []
        fake = _install_fake_ddgs(captured)
        with mock.patch.dict(sys.modules, {"ddgs": fake}), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMMA4_DDGS_TIMEOUT", None)
            self._sr.ddgs_search("rust language", limit=5)
        # primer backend (google) respondió -> 1 construcción de DDGS con timeout=5.
        self.assertTrue(captured)
        self.assertEqual(captured[0], 5)

    def test_env_override_clamped(self):
        captured: list = []
        fake = _install_fake_ddgs(captured)
        with mock.patch.dict(sys.modules, {"ddgs": fake}), \
             mock.patch.dict(os.environ, {"GEMMA4_DDGS_TIMEOUT": "3"}):
            self._sr.ddgs_search("rust", limit=3)
        self.assertEqual(captured[0], 3)

    def test_timeout_floor_and_ceiling(self):
        # fuera de [2,10] se clampa.
        for raw, want in (("1", 2), ("99", 10), ("xxx", 5)):
            captured: list = []
            fake = _install_fake_ddgs(captured)
            with mock.patch.dict(sys.modules, {"ddgs": fake}), \
                 mock.patch.dict(os.environ, {"GEMMA4_DDGS_TIMEOUT": raw}):
                self._sr.ddgs_search("q", limit=2)
            self.assertEqual(captured[0], want, f"raw={raw!r}")

    def test_explicit_timeout_arg_wins(self):
        captured: list = []
        fake = _install_fake_ddgs(captured)
        with mock.patch.dict(sys.modules, {"ddgs": fake}), \
             mock.patch.dict(os.environ, {"GEMMA4_DDGS_TIMEOUT": "5"}):
            self._sr.ddgs_search("q", limit=2, timeout=7)
        self.assertEqual(captured[0], 7)  # el arg explícito pasa tal cual


if __name__ == "__main__":
    unittest.main()
