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


class AppOpenWebFallbackTest(unittest.TestCase):
    """app.open de un NOMBRE que no es app instalada (p.ej. 'pivigames') cae a
    NAVEGAR por web (resuelto por búsqueda). Una app real NO cae a web. Incidente:
    've a pivigames' -> el 4B rutea a app.open -> 'app not found' -> se quedaba sin
    abrir el sitio. Mock-only: app_open/web_search/web_open_url mockeados."""

    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())
        self.opened = []
        self.ag.tools.web_open_url = lambda a: (
            self.opened.append(a.get("url")),
            {"ok": True, "url": a.get("url"), "opened": True})[1]

    def test_unknown_app_name_falls_back_to_web(self):
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": False, "error": "app not found"}), \
             mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": [
                                   {"url": "https://pivigames.wordpress.com/", "title": "x"}]}):
            res = self.ag.tools.t_app({"action": "open", "name": "pivigames"})
        self.assertTrue(res["ok"])
        self.assertEqual(res.get("delegated_from"), "app.open")
        self.assertEqual(self.opened[-1], "https://pivigames.wordpress.com/")

    def test_installed_app_does_not_fall_back(self):
        # app real (ok=True) -> NO toca la web.
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": True, "name": "Calculadora"}), \
             mock.patch.object(self.ag.tools, "web_search") as ws:
            res = self.ag.tools.t_app({"action": "open", "name": "calculadora"})
        self.assertTrue(res["ok"])
        self.assertIsNone(res.get("delegated_from"))
        ws.assert_not_called()
        self.assertEqual(self.opened, [])

    def test_app_not_found_and_no_web_result_keeps_honest_error(self):
        # ni app ni sitio -> devuelve el 'not found' honesto (no inventa).
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": False, "error": "app not found"}), \
             mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": []}):
            res = self.ag.tools.t_app({"action": "open", "name": "zzqwerty"})
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("error"), "app not found")
        self.assertEqual(self.opened, [])

    def test_path_like_name_does_not_fall_back(self):
        # un nombre con ruta no es un sitio -> no web fallback.
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": False, "error": "app not found"}), \
             mock.patch.object(self.ag.tools, "web_search") as ws:
            res = self.ag.tools.t_app({"action": "open", "name": "C:/foo/bar.exe"})
        self.assertFalse(res.get("ok"))
        ws.assert_not_called()


class OpenInSpecificBrowserTest(unittest.TestCase):
    """'pon X en Opera' -> abrir la URL EN Opera (no en el navegador por defecto).
    El navegador nombrado se lanza con la URL como arg y se verifica la ventana.
    Si no se resuelve ese navegador -> fallback honesto al default con browser_note.
    Mock-only: apps.find/open y verify_app_opened mockeados (no lanza nada real)."""

    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())
        self.opened_default = []
        self.ag.tools.web_open_url = lambda a: (
            self.opened_default.append(a.get("url")),
            {"ok": True, "url": a.get("url"), "opened": True, "verified": False})[1]

    def _fake_candidate(self):
        from gemma4_agent.app_resolver import AppCandidate
        return AppCandidate(name="Opera GX", launch="C:/x/opera.exe",
                            launch_type="file", source="path")

    def test_named_browser_opens_url_in_it(self):
        cand = self._fake_candidate()
        with mock.patch.object(self.ag.tools.apps, "find", return_value=[cand]), \
             mock.patch.object(self.ag.tools.apps, "open",
                               return_value={"ok": True, "candidate": {
                                   "name": "Opera GX", "navigated_url": "https://pivigames.com"}}) as mo, \
             mock.patch.object(self.ag.tools, "verify_app_opened", return_value={"found": True}):
            res = self.ag.tools.t_browser({"action": "open", "browser": "Opera",
                                           "url": "https://pivigames.com"})
        self.assertTrue(res["ok"])
        self.assertEqual(res.get("browser"), "Opera")
        self.assertEqual(res.get("navigated_url"), "https://pivigames.com")
        self.assertTrue(res.get("verified"))
        # la URL fue al navegador (apps.open con url_arg), NO al default
        self.assertEqual(mo.call_args.kwargs.get("url_arg"), "https://pivigames.com")
        self.assertEqual(self.opened_default, [])

    def test_named_browser_with_bare_sitename_resolves_then_opens_in_browser(self):
        # "pon pivigames en opera" (url='pivigames') -> resuelve sitio + abre en Opera
        cand = self._fake_candidate()
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": [
                                   {"url": "https://pivigames.wordpress.com/", "title": "x"}]}), \
             mock.patch.object(self.ag.tools.apps, "find", return_value=[cand]), \
             mock.patch.object(self.ag.tools.apps, "open",
                               return_value={"ok": True, "candidate": {
                                   "name": "Opera GX", "navigated_url": "https://pivigames.wordpress.com/"}}) as mo, \
             mock.patch.object(self.ag.tools, "verify_app_opened", return_value={"found": True}):
            res = self.ag.tools.t_browser({"action": "open", "browser": "Opera",
                                           "url": "pivigames"})
        self.assertTrue(res["ok"])
        self.assertEqual(res.get("resolved_from_name"), "pivigames")
        self.assertEqual(mo.call_args.kwargs.get("url_arg"), "https://pivigames.wordpress.com/")

    def test_unresolvable_browser_falls_back_to_default_honestly(self):
        # navegador no encontrado -> abre en default + nota honesta (no finge).
        with mock.patch.object(self.ag.tools.apps, "find", return_value=[]):
            res = self.ag.tools.t_browser({"action": "open", "browser": "NavegadorRaro",
                                           "url": "https://pivigames.com"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.opened_default[-1], "https://pivigames.com")
        self.assertIn("browser_note", res)
        self.assertIn("NavegadorRaro", res["browser_note"])

    def test_no_browser_named_uses_default(self):
        with mock.patch.object(self.ag.tools.apps, "find") as mf:
            res = self.ag.tools.t_browser({"action": "open", "url": "https://x.com"})
        self.assertTrue(res["ok"])
        mf.assert_not_called()   # sin browser= no toca el resolver
        self.assertEqual(self.opened_default[-1], "https://x.com")


if __name__ == "__main__":
    unittest.main()
