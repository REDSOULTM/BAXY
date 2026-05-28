"""Bug medido (2026-05-27, capturas del user): verify_window_exists con un DOMINIO
("portal2.uniej.cl") devolvía found=False aunque el navegador SÍ estuviera abierto
con esa URL, porque el título de la ventana del navegador casi nunca contiene el
dominio crudo (lleva el title de la pestaña activa). El agente terminaba narrando
"No pude verificar si X se abrió correctamente" tras un browser.open exitoso.

FIX honesto (sin mentir): si el query parece dominio Y match fuerte fracasa,
intentar (a) CDP :9222 -> URL real, (b) si CDP no responde y hay una ventana de
navegador conocido abierta, devolver found=True + verified_by=browser_window_present
+ caveat explícito. El caveat le dice al LLM/usuario el LÍMITE de la verificación
(no se puede leer la URL del perfil real del user por hardening de Chromium 136+,
ver project_browser_cdp_dedicated_instance_2026_05_26).

Mock-only: stubbeamos list_windows (no procesos reales) y el CDP HTTP."""
from __future__ import annotations

import unittest
from unittest import mock


class VerifyWindowDomainHonestTest(unittest.TestCase):
    def _registry(self, windows):
        from gemma4_agent.tools import ToolRegistry
        from gemma4_agent.memory import MemoryStore
        from gemma4_agent.state import AgentState
        import tempfile
        from pathlib import Path
        td = Path(tempfile.mkdtemp())
        mem = MemoryStore(td / "mem.json")
        st = AgentState(td / "state.json")
        reg = ToolRegistry(mem, td / "cap", st)
        reg.list_windows = lambda a: {"windows": list(windows)}
        return reg

    # --- (1) match fuerte: el título del proceso/ventana coincide ----------

    def test_strong_match_keeps_window_title_verifier(self):
        reg = self._registry([
            {"process": "opera.exe", "title": "Wiki - Wikipedia - Opera",
             "pid": 1, "hwnd": 1},
        ])
        with mock.patch.object(reg, "_cdp_url_match", return_value=None):
            r = reg.verify_window_exists({"title": "opera"})
        self.assertTrue(r["found"])
        self.assertEqual(r["verified_by"], "window_title")

    # --- (2) dominio + CDP vivo + URL real coincide -> verificación fuerte -

    def test_domain_with_cdp_alive_strong_verification(self):
        reg = self._registry([])  # ventanas vacías a propósito
        cdp_hit = {"found": True, "url": "https://portal2.uniej.cl/x", "title": "Portal"}
        with mock.patch.object(reg, "_cdp_url_match", return_value=cdp_hit):
            r = reg.verify_window_exists({"title": "portal2.uniej.cl"})
        self.assertTrue(r["found"])
        self.assertEqual(r["verified_by"], "cdp_url")

    def test_domain_with_cdp_alive_but_url_not_present(self):
        reg = self._registry([])
        cdp_miss = {"found": False, "url": None, "title": None}
        with mock.patch.object(reg, "_cdp_url_match", return_value=cdp_miss):
            r = reg.verify_window_exists({"title": "no-esta-aca.cl"})
        self.assertFalse(r["found"])
        self.assertEqual(r["verified_by"], "cdp_url")

    # --- (3) dominio + CDP no responde + navegador abierto -> inferida -----

    def test_domain_no_cdp_but_browser_present_inferred_match(self):
        reg = self._registry([
            {"process": "opera.exe",
             "title": "backrooms pelicula - Google - Opera",
             "pid": 1, "hwnd": 1},
        ])
        with mock.patch.object(reg, "_cdp_url_match", return_value=None):
            r = reg.verify_window_exists({"title": "portal2.uniej.cl"})
        self.assertTrue(r["found"])
        self.assertEqual(r["verified_by"], "browser_window_present")
        self.assertIn("caveat", r)

    # --- (4) dominio sin navegador abierto -> honesto found=False ----------

    def test_domain_no_browser_open_returns_false(self):
        reg = self._registry([
            {"process": "notepad.exe", "title": "Untitled - Notepad",
             "pid": 1, "hwnd": 1},
        ])
        with mock.patch.object(reg, "_cdp_url_match", return_value=None):
            r = reg.verify_window_exists({"title": "portal2.uniej.cl"})
        self.assertFalse(r["found"])
        self.assertEqual(r["verified_by"], "none")

    # --- (5) no-dominio que no matchea: comportamiento previo, sin cambios -

    def test_non_domain_no_match_returns_false(self):
        reg = self._registry([
            {"process": "opera.exe", "title": "YouTube - Opera",
             "pid": 1, "hwnd": 1},
        ])
        with mock.patch.object(reg, "_cdp_url_match", return_value=None):
            r = reg.verify_window_exists({"title": "Photoshop"})
        self.assertFalse(r["found"])
        self.assertEqual(r["verified_by"], "none")

    # --- (6) heurística estructural _looks_like_domain ---------------------

    def test_looks_like_domain_heuristic(self):
        from gemma4_agent.tools import ToolRegistry
        f = ToolRegistry._looks_like_domain
        # positivos
        self.assertTrue(f("foo.com"))
        self.assertTrue(f("sub.dom.cl"))
        self.assertTrue(f("portal2.uniej.cl/ingresar"))
        # negativos
        self.assertFalse(f("Photoshop"))
        self.assertFalse(f(""))
        self.assertFalse(f("hola que tal"))  # espacio
        self.assertFalse(f("foo."))           # sin TLD


if __name__ == "__main__":
    unittest.main()
