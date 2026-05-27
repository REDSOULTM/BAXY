"""window.open NO existe como acción de window (window controla ventanas, no
abre páginas). El 4B a veces la llama igual. Antes daba error duro y dejaba la
tarea trabada (mal para movilidad/no_vidente). Ahora:
  - window.open con una URL/dominio explícito -> abre en el navegador por defecto
    (delega a web_open_url).
  - window.open con un nombre de sitio SIN URL ('Instant Gaming') -> error
    ACCIONABLE que reencamina a web(search)->browser.open (no adivina el dominio).
Mock-only: web_open_url parcheado, no abre navegador real.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .memory import MemoryStore
from .state import AgentState
from .tools import ToolRegistry


def _make_registry() -> ToolRegistry:
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_winopen_"))
    memory = MemoryStore(tmp / "mem.json")
    state = AgentState(tmp / "data" / "state.json")
    return ToolRegistry(memory, tmp / "captures", state=state, safety_enabled=False)


class WindowOpenDelegationTest(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()

    def test_window_open_with_explicit_url_opens_browser(self):
        with mock.patch.object(self.reg, "web_open_url",
                               return_value={"ok": True, "url": "https://instant-gaming.com"}) as wo:
            r = self.reg.t_window({"action": "open", "url": "https://instant-gaming.com"})
        wo.assert_called_once()
        self.assertTrue(r["ok"])
        self.assertEqual(r.get("delegated_from"), "window.open")

    def test_window_open_with_bare_domain_opens_browser(self):
        with mock.patch.object(self.reg, "web_open_url",
                               return_value={"ok": True}) as wo:
            r = self.reg.t_window({"action": "open", "query": "instant-gaming.com"})
        wo.assert_called_once()
        self.assertTrue(r["ok"])

    def test_window_open_with_site_name_no_url_returns_actionable_error(self):
        # 'Instant Gaming' no es URL -> NO adivinamos dominio -> error accionable.
        with mock.patch.object(self.reg, "web_open_url") as wo:
            r = self.reg.t_window({"action": "open", "query": "Instant Gaming"})
        wo.assert_not_called()  # no abrió nada a ciegas
        self.assertFalse(r["ok"])
        self.assertIn("search", r.get("hint", "").lower())  # reencamina a web(search)

    def test_window_focus_still_works_normally(self):
        # no rompimos las acciones reales de window.
        with mock.patch.object(self.reg, "window_control",
                               return_value={"ok": True, "action": "focus"}) as wc:
            r = self.reg.t_window({"action": "focus", "title": "Opera"})
        wc.assert_called_once()
        self.assertTrue(r["ok"])

    def test_unknown_window_action_still_errors(self):
        r = self.reg.t_window({"action": "teleport"})
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
