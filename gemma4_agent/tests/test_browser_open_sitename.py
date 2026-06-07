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

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra.config import AgentConfig


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
        # el dominio matchea el nombre -> NORMALIZA a la HOMEPAGE (no la subpágina
        # profunda). Incidente pivigames: abría /category/aviso/ (2018); ahora la raíz.
        with self._search_returns("https://pivigames.wordpress.com/category/aviso/") as s:
            res = self.ag.tools.t_browser({"action": "open", "url": "pivigames"})
        s.assert_called_once()  # hubo búsqueda real (no adivinó dominio)
        self.assertEqual(res.get("resolved_from_name"), "pivigames")
        self.assertEqual(self.opened[-1], "https://pivigames.wordpress.com/")

    def test_multiword_name_resolves(self):
        # 'instant gaming' matchea instant-gaming.com -> homepage, no /en/.
        with self._search_returns("https://www.instant-gaming.com/en/"):
            res = self.ag.tools.t_browser({"action": "open", "url": "instant gaming"})
        self.assertEqual(self.opened[-1], "https://www.instant-gaming.com/")
        self.assertEqual(res.get("resolved_from_name"), "instant gaming")

    def test_explicit_domain_goes_direct_no_search(self):
        # PROCEDENCIA (2026-06-07): si el user DICTÓ el dominio (aparece en su texto),
        # va directo SIN búsqueda. Es su intención explícita -> cero latencia.
        self.ag.tools._current_user_text = "abrí github.com"
        with mock.patch.object(self.ag.tools, "web_search") as s:
            self.ag.tools.t_browser({"action": "open", "url": "github.com"})
        s.assert_not_called()                       # NO búsqueda para un dominio dictado
        self.assertEqual(self.opened[-1], "github.com")

    def test_full_url_goes_direct(self):
        # URL con PATH real -> no es un dominio "adivinado" (el 4B no inventa paths) ->
        # va directo aunque no esté en el texto del user.
        with mock.patch.object(self.ag.tools, "web_search") as s:
            self.ag.tools.t_browser({"action": "open", "url": "https://example.com/path"})
        s.assert_not_called()
        self.assertEqual(self.opened[-1], "https://example.com/path")

    def test_guessed_domain_not_in_user_text_re_resolves(self):
        # PROCEDENCIA: el 4B emite 'pivigames.com' pero el user dijo 've a pivigames'
        # (el NOMBRE, no el dominio) -> el .com fue ADIVINADO -> re-resolver por
        # búsqueda al sitio real (pivigames.blog), NO abrir el adivinado. (2026-06-07.)
        self.ag.tools._current_user_text = "ve a pivigames"
        with self._search_returns("https://pivigames.blog/") as s:
            res = self.ag.tools.t_browser({"action": "open", "url": "https://www.pivigames.com/"})
        s.assert_called()                            # SÍ buscó (dominio adivinado)
        self.assertEqual(self.opened[-1], "https://pivigames.blog/")
        # re-resolvió: el campo guarda la URL adivinada original como "de dónde vino".
        self.assertEqual(res.get("resolved_from_name"), "https://www.pivigames.com/")

    def test_search_no_result_falls_through(self):
        # sin resultado fiable -> NO inventa; cae al flujo normal (host inválido).
        # el 2do pase (todos los backends) también vacío -> mock para no pegar a la red.
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": []}), \
             mock.patch.object(self.ag.tools, "_site_search_all_backends", return_value=[]):
            res = self.ag.tools.t_browser({"action": "open", "url": "zzqq"})
        # no resolvió por nombre; web_open_url recibió "zzqq" (flujo normal)
        self.assertIsNone(res.get("resolved_from_name"))

    def test_picks_domain_homepage_over_aggregators_and_deep_pages(self):
        # Incidente real pivigames: el #0 era un mirror viejo en SUBPÁGINA y había
        # redes/estado de por medio. La heurística debe: filtrar agregadores
        # (reddit/instagram/patreon/ipaddress), preferir el dominio que matchea el
        # nombre, y abrir su HOMEPAGE (no la subpágina).
        results = [
            {"url": "https://pivigames.wordpress.com/category/aviso/", "title": "AVISO"},
            {"url": "https://www.patreon.com/cw/pivigames_official", "title": "patreon"},
            {"url": "https://www.reddit.com/r/x/conocen_pivigames/", "title": "reddit"},
            {"url": "https://www.instagram.com/pivigames_official/", "title": "ig"},
            {"url": "https://www.ipaddress.com/website/pivigames.blog", "title": "ipaddr"},
        ]
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": results}):
            resolved = self.ag.tools._resolve_site_by_search("pivigames")
        # NO un agregador, SÍ el dominio pivigames, y su RAÍZ (no /category/aviso/).
        self.assertEqual(resolved, "https://pivigames.wordpress.com/")

    def test_prefers_sld_match_over_subdomain_blog(self):
        # 'youtube' -> youtube.com (SLD), NO blog.youtube (subdominio).
        results = [
            {"url": "https://blog.youtube/news/", "title": "YT blog"},
            {"url": "https://www.youtube.com/", "title": "YouTube"},
        ]
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": results}):
            resolved = self.ag.tools._resolve_site_by_search("youtube")
        self.assertEqual(resolved, "https://www.youtube.com/")

    def test_all_aggregators_returns_none_no_garbage(self):
        # si TODO es agregador (sitio sin web propia indexada), NO abrir basura:
        # error honesto (None). Cambio 2026-06-07 (guard anti-basura + CLAUDE.md):
        # antes abría el primer agregador (instagram.com/foo) = página equivocada.
        # El 2do pase (todos los backends) también mockeado vacío -> no pega a la red.
        results = [{"url": "https://www.instagram.com/foo/", "title": "ig"}]
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": results}), \
             mock.patch.object(self.ag.tools, "_site_search_all_backends", return_value=[]):
            resolved = self.ag.tools._resolve_site_by_search("foo")
        self.assertIsNone(resolved)

    def test_search_action_still_searches_not_open_top(self):
        # browser.search NO debe auto-abrir el top result: la intención es buscar,
        # no navegar. Cubre que la resolución de open no contamina search.
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
        # app real (ok=True), match fuerte -> NO toca la web.
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": True, "opened": {"name": "Spotify"}}), \
             mock.patch.object(self.ag.tools, "web_search") as ws:
            res = self.ag.tools.t_app({"action": "open", "name": "spotify"})
        self.assertTrue(res["ok"])
        self.assertIsNone(res.get("delegated_from"))
        ws.assert_not_called()
        self.assertEqual(self.opened, [])

    def test_single_word_alias_match_stays_app(self):
        # "calculadora" -> app_open resuelve a 'calc' (alias, _score 0) pero es la
        # app REAL. Consulta de 1 palabra -> NO weak-match -> sigue APP, no web.
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": True, "opened": {"name": "calc"}}), \
             mock.patch.object(self.ag.tools, "web_search") as ws:
            res = self.ag.tools.t_app({"action": "open", "name": "calculadora"})
        self.assertIsNone(res.get("delegated_from"))
        ws.assert_not_called()

    def test_domain_name_goes_web_even_if_app_matched(self):
        # "gmail.com" tiene punto -> es DOMINIO -> web, aunque app_open matcheara
        # un falso ("Visite Java.com"). Incidente real.
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": True, "opened": {"name": "Visite Java.com"}}), \
             mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": [{"url": "https://www.gmail.com/", "title": "x"}]}):
            res = self.ag.tools.t_app({"action": "open", "name": "gmail.com"})
        self.assertEqual(res.get("delegated_from"), "app.open")
        self.assertEqual(self.opened[-1], "https://www.gmail.com/")

    def test_multiword_weak_match_goes_web(self):
        # "portal uniej" (2 palabras) -> app_open matchea FALSO "Portal de realidad
        # mixta" (solo 'portal', score bajo) -> web. Incidente real.
        with mock.patch.object(self.ag.tools, "app_open",
                               return_value={"ok": True, "opened": {"name": "Portal de realidad mixta"}}), \
             mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": [{"url": "https://portal.uniej.edu.sv/", "title": "x"}]}):
            res = self.ag.tools.t_app({"action": "open", "name": "portal uniej"})
        self.assertEqual(res.get("delegated_from"), "app.open")
        self.assertIn("uniej", self.opened[-1])

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
        from gemma4_agent.tools_pkg.app_resolver import AppCandidate
        return AppCandidate(name="Opera GX", launch="C:/x/opera.exe",
                            launch_type="file", source="path")

    def test_named_browser_opens_url_in_it(self):
        cand = self._fake_candidate()
        # el user dictó el dominio -> va directo (no re-resuelve); el foco del test
        # es el RUTEO al navegador nombrado, no la resolución de sitio.
        self.ag.tools._current_user_text = "pon pivigames.com en opera"
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
        self.ag.tools._current_user_text = "abrí pivigames.com en NavegadorRaro"
        with mock.patch.object(self.ag.tools.apps, "find", return_value=[]):
            res = self.ag.tools.t_browser({"action": "open", "browser": "NavegadorRaro",
                                           "url": "https://pivigames.com"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.opened_default[-1], "https://pivigames.com")
        self.assertIn("browser_note", res)
        self.assertIn("NavegadorRaro", res["browser_note"])

    def test_no_browser_named_uses_default(self):
        self.ag.tools._current_user_text = "abrí https://x.com"
        with mock.patch.object(self.ag.tools.apps, "find") as mf:
            res = self.ag.tools.t_browser({"action": "open", "url": "https://x.com"})
        self.assertTrue(res["ok"])
        mf.assert_not_called()   # sin browser= no toca el resolver
        self.assertEqual(self.opened_default[-1], "https://x.com")

    def test_search_in_named_browser_uses_no_sendinput(self):
        # BUG 2026-05-27: browser.search con browser= TECLEABA la URL con
        # gui_keypress/gui_type (SendInput) -> frágil + cerró VS Code en dev.
        # Ahora lanza el navegador con la URL como arg (0 SendInput).
        sendinput = []
        self.ag.tools.gui_keypress = lambda a: (sendinput.append("kp"), {"ok": True})[1]
        self.ag.tools.gui_type = lambda a: (sendinput.append("ty"), {"ok": True})[1]
        cand = self._fake_candidate()
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": []}), \
             mock.patch.object(self.ag.tools.apps, "find", return_value=[cand]), \
             mock.patch.object(self.ag.tools.apps, "open",
                               return_value={"ok": True, "candidate": {
                                   "name": "Opera GX", "navigated_url": "https://www.google.com/search?q=pivigames"}}) as mo, \
             mock.patch.object(self.ag.tools, "verify_app_opened", return_value={"found": True}):
            res = self.ag.tools.t_browser({"action": "search", "browser": "Opera",
                                           "query": "pivigames"})
        self.assertTrue(res["ok"])
        self.assertEqual(sendinput, [])   # CERO SendInput (la clave del fix)
        # se lanzó el navegador con la URL de búsqueda como argumento
        self.assertIn("google.com/search", mo.call_args.kwargs.get("url_arg", ""))

    def test_search_named_browser_unresolvable_falls_back_no_sendinput(self):
        sendinput = []
        self.ag.tools.gui_keypress = lambda a: (sendinput.append("kp"), {"ok": True})[1]
        self.ag.tools.gui_type = lambda a: (sendinput.append("ty"), {"ok": True})[1]
        with mock.patch.object(self.ag.tools, "web_search",
                               return_value={"ok": True, "results": []}), \
             mock.patch.object(self.ag.tools.apps, "find", return_value=[]):
            res = self.ag.tools.t_browser({"action": "search", "browser": "NavRaro",
                                           "query": "x"})
        self.assertTrue(res["ok"])
        self.assertEqual(sendinput, [])   # tampoco SendInput en el fallback
        self.assertEqual(self.opened_default[-1], "https://www.google.com/search?q=x")
        self.assertIn("browser_note", res)


if __name__ == "__main__":
    unittest.main()
