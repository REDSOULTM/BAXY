"""browser.open por NOMBRE de sitio (2026-05-27). "ve a la página de pivigames"
da un nombre, no una URL. browser.open con un nombre suelto (sin dominio) lo
resuelve por BÚSQUEDA REAL y abre el primer resultado — NO adivina el TLD. Una
URL/dominio explícito va directo. Incidente real: "ve a la pagina de pivigames"
solo abría una búsqueda de Google y el reply mentía ("abrí la página").

Mock-only: web_search y web_open_url mockeados — no internet, no abre navegador.
"""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.config import AgentConfig


class BrowserOpenSiteNameTest(unittest.TestCase):
    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())
        self.opened = []
        self.ag.tools.web_open_url = lambda a: (
            self.opened.append(a.get("url")),
            {"ok": True, "url": a.get("url"), "opened": True})[1]

    def _search_returns(self, url):
        return mock.patch.object(
            self.ag.tools, "web_search",
            return_value={"ok": True, "verified": True,
                          "results": [{"url": url, "title": "x"}]})

    def test_bare_name_resolves_via_search(self):
        with self._search_returns("https://pivigames.wordpress.com/category/aviso/") as s:
            res = self.ag.tools.t_browser({"action": "open", "url": "pivigames"})
        s.assert_called_once()  # hubo búsqueda real (no adivinó dominio)
        self.assertEqual(res.get("resolved_from_name"), "pivigames")
        self.assertEqual(self.opened[-1], "https://pivigames.wordpress.com/category/aviso/")

    def test_multiword_name_resolves(self):
        with self._search_returns("https://www.instant-gaming.com/en/"):
            res = self.ag.tools.t_browser({"action": "open", "url": "instant gaming"})
        self.assertEqual(self.opened[-1], "https://www.instant-gaming.com/en/")
        self.assertEqual(res.get("resolved_from_name"), "instant gaming")

    def test_explicit_domain_goes_direct_no_search(self):
        with mock.patch.object(self.ag.tools, "web_search") as s:
            self.ag.tools.t_browser({"action": "open", "url": "github.com"})
        s.assert_not_called()                       # NO búsqueda para un dominio
        self.assertEqual(self.opened[-1], "github.com")

    def test_full_url_goes_direct(self):
        with mock.patch.object(self.ag.tools, "web_search") as s:
            self.ag.tools.t_browser({"action": "open", "url": "https://example.com/path"})
        s.assert_not_called()
        self.assertEqual(self.opened[-1], "https://example.com/path")

    def test_search_no_result_falls_through(self):
        # sin resultado fiable -> NO inventa; cae al flujo normal (host inválido).
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": []}):
            res = self.ag.tools.t_browser({"action": "open", "url": "zzqq"})
        # no resolvió por nombre; web_open_url recibió "zzqq" (flujo normal)
        self.assertIsNone(res.get("resolved_from_name"))

    def test_search_action_still_searches_not_open_top(self):
        # browser.search NO debe auto-abrir el top result: el usuario pidió buscar.
        # (cubre que el fix de open no contamina search)
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": [{"url": "https://x.com", "title": "x"}]}):
            res = self.ag.tools.t_browser({"action": "search", "query": "pivigames", "browser": ""})
        self.assertEqual(res.get("action"), "search")


if __name__ == "__main__":
    unittest.main()
