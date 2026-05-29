"""Bug medido (2026-05-27, captura del user): browser(action=open, target='canvas')
devolvía needs_user porque el handler t_browser solo leía url/query, IGNORANDO
`target` aunque el schema lo declara como propiedad legítima. Inconsistencia
schema↔handler — el 4B eligió la clave correcta según el schema pero la tool la
rechazaba.

Fix: leer también `target`, `site`, `domain` como aliases de `url`. NO incluir
`name` (lo usa el bloque LAUNCH-THE-APP para "lanzá Chrome").

Mock-only: no dispara el browser real. Stubeamos web_open_url y _resolve_site_by_search."""
from __future__ import annotations

import unittest
from unittest import mock


class BrowserOpenTargetAliasTest(unittest.TestCase):
    def _registry(self):
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        from gemma4_agent.memory_pkg.memory import MemoryStore
        from gemma4_agent.memory_pkg.state import AgentState
        import tempfile
        from pathlib import Path
        td = Path(tempfile.mkdtemp())
        mem = MemoryStore(td / "mem.json")
        st = AgentState(td / "state.json")
        reg = ToolRegistry(mem, td / "cap", st)
        reg.web_open_url = lambda a: {"ok": True, "url": a.get("url"), "opened": True}
        reg._resolve_site_by_search = lambda nm: f"https://www.{nm}.com/" if nm else None
        return reg

    def test_target_resolves_when_no_url(self):
        # Caso EXACTO de la captura del user: browser.open con target='canvas'.
        reg = self._registry()
        r = reg.t_browser({"action": "open", "target": "canvas"})
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r.get("resolved_from_name"), "canvas")
        self.assertIn("canvas", r.get("url", "").lower())

    def test_site_alias_works(self):
        reg = self._registry()
        r = reg.t_browser({"action": "open", "site": "gmail"})
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("resolved_from_name"), "gmail")

    def test_domain_alias_works(self):
        reg = self._registry()
        r = reg.t_browser({"action": "open", "domain": "youtube"})
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("resolved_from_name"), "youtube")

    def test_url_takes_precedence_over_target(self):
        # si vienen AMBOS, url gana (es la forma canónica del schema).
        reg = self._registry()
        r = reg.t_browser({"action": "open", "url": "github.com", "target": "ignored"})
        self.assertTrue(r.get("ok"))
        self.assertIn("github.com", r.get("url", ""))

    def test_name_still_means_browser_app_not_url(self):
        # Anti-regresión crítica: "name=Chrome" sin url debe LANZAR la app
        # Chrome, NO interpretar "Chrome" como sitio a navegar.
        reg = self._registry()
        reg.app_open = lambda a: {"ok": True, "stubbed_app_open": a.get("name")}
        r = reg.t_browser({"action": "open", "name": "Chrome"})
        self.assertTrue(r.get("ok"))
        # debe haber delegado a app_open, NO haber resuelto Chrome como sitio
        self.assertEqual(r.get("delegated_from"), "browser.open")
        self.assertEqual(r.get("stubbed_app_open"), "Chrome")

    def test_no_args_returns_needs_user(self):
        reg = self._registry()
        r = reg.t_browser({"action": "open"})
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("status"), "needs_user")


if __name__ == "__main__":
    unittest.main()
