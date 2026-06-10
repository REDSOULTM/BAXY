"""Bug medido (2026-05-31, captura): comando "instalame doom
eternal en steam" y el agente SOLO abrió la página de la TIENDA del juego, NUNCA
disparó la instalación.

Causa raíz: el handler t_steam(action='install') exigía un `appid` NUMÉRICO. El
4B casi nunca lo conoce — emite steam(action='install', query='doom eternal').
Sin appid, el handler viejo caía a search_store -> solo ABRÍA la store page.

Fix: cuando no hay appid, resolver el NOMBRE -> AppID con la MISMA cascada que
store_page (biblioteca local de Steam -> búsqueda real en la store) y disparar
steam://install/<appid> (el diálogo de instalación NATIVO de Steam).

Mock-only: stubbeamos os.startfile (NUNCA lanzamos Steam de verdad) y la cascada
de resolución del AppID (sin red ni disco). Un test ejerce la cascada real con
find_steam_library / _steam_store_first_result stubbeados para probar el cableado.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class SteamInstallResolvesAppidTest(unittest.TestCase):
    def _registry(self, *, autoconfirm=False):
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        from gemma4_agent.memory_pkg.memory import MemoryStore
        from gemma4_agent.memory_pkg.state import AgentState
        td = Path(tempfile.mkdtemp())
        mem = MemoryStore(td / "mem.json")
        st = AgentState(td / "state.json")
        reg = ToolRegistry(mem, td / "cap", st)
        # Por defecto stubbeamos el confirmador del diálogo a "no confirmó" (sin
        # diálogo real en el test). autoconfirm=True simula que SÍ apretó Instalar.
        reg._steam_confirm_install_dialog = lambda game, **k: (
            {"confirmed": True, "button": "Instalar", "reason": "dialog_closed_after_invoke"}
            if autoconfirm else
            {"confirmed": False, "reason": "install_dialog_not_found"})
        return reg

    # ---- el caso de la captura: install por NOMBRE, sin appid ----
    def test_install_by_name_resolves_appid_and_fires_install_uri(self):
        reg = self._registry()
        reg._resolve_steam_appid = lambda q: {
            "appid": "782330", "match": {"name": "DOOM Eternal"},
            "source": "steam_store_search",
        }
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "install", "query": "doom eternal"})
        self.assertTrue(r.get("ok"), r)
        # CLAVE: disparó el diálogo de instalación de Steam, NO la store page.
        startfile.assert_called_once_with("steam://install/782330")
        self.assertEqual(r.get("appid"), "782330")
        self.assertEqual(r.get("uri"), "steam://install/782330")
        self.assertEqual(r.get("completion_status"), "opened_steam_install_dialog")
        self.assertEqual(r.get("action"), "install")

    def test_install_with_explicit_appid_skips_resolution(self):
        reg = self._registry()
        # Si _resolve_steam_appid se llamara, fallaría el test (no debe llamarse).
        reg._resolve_steam_appid = lambda q: self.fail("must not resolve when appid given")
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "install", "appid": "570"})
        self.assertTrue(r.get("ok"), r)
        startfile.assert_called_once_with("steam://install/570")
        self.assertEqual(r.get("appid"), "570")

    def test_play_or_install_alias_also_installs(self):
        # mission_goal trata 'play_or_install' como destructive_install; el
        # handler debe aceptarlo igual que 'install' (defensivo).
        reg = self._registry()
        reg._resolve_steam_appid = lambda q: {
            "appid": "1145360", "match": {"name": "Hades"}, "source": "local",
        }
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "play_or_install", "query": "hades"})
        self.assertTrue(r.get("ok"), r)
        startfile.assert_called_once_with("steam://install/1145360")

    # ---- fallback honesto cuando NO se puede resolver el AppID ----
    def test_install_unresolved_falls_back_to_store_page_honestly(self):
        reg = self._registry()
        reg._resolve_steam_appid = lambda q: None  # nada resuelve
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "install", "query": "juego inexistente xyz"})
        # Abrió ALGO (la store) pero lo dice honestamente: NO instaló.
        self.assertTrue(startfile.called)
        self.assertEqual(r.get("requested_action"), "install")
        self.assertEqual(r.get("install_status"), "appid_unresolved_opened_store_page")

    # ---- HONESTIDAD: install SIN nombre ni appid NO debe mentir que abrió algo
    # (review 2026-05-31: la store_page con query vacío devuelve _err sin abrir
    # nada, y el note viejo afirmaba que "se abrió la tienda" => mentira). ----
    def test_install_bare_no_query_no_appid_asks_instead_of_lying(self):
        reg = self._registry()
        # _resolve_steam_appid NO debe llamarse (cortamos antes).
        reg._resolve_steam_appid = lambda q: self.fail("must not resolve on bare install")
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "install"})
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("status"), "needs_user")
        # CLAVE: NO disparó nada y NO afirma haber abierto la tienda.
        self.assertFalse(startfile.called)
        self.assertNotIn("opened_store_page", str(r.get("install_status") or ""))

    def test_install_whitespace_query_also_asks(self):
        reg = self._registry()
        reg._resolve_steam_appid = lambda q: self.fail("must not resolve on blank install")
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "install", "query": "   "})
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("status"), "needs_user")
        self.assertFalse(startfile.called)

    # ---- WRONG-GAME risk: la resolución por búsqueda en la store es BAJA
    # confianza; el resultado debe marcarlo para que el reply diga QUÉ juego. ----
    def test_install_store_search_match_flagged_low_confidence(self):
        reg = self._registry()
        reg._resolve_steam_appid = lambda q: {
            "appid": "782330", "match": {"name": "DOOM Eternal"},
            "source": "steam_store_search",
        }
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "install", "query": "doom"})
        self.assertTrue(r.get("ok"), r)
        startfile.assert_called_once_with("steam://install/782330")
        self.assertEqual(r.get("resolution_confidence"), "low")
        self.assertEqual(r.get("resolved_game"), "DOOM Eternal")
        # el note debe nombrar el juego para que el usuario pueda cancelar.
        self.assertIn("DOOM Eternal", r.get("note", ""))

    def test_install_local_library_match_is_high_confidence(self):
        reg = self._registry()
        reg._resolve_steam_appid = lambda q: {
            "appid": "1145360", "match": {"name": "Hades"}, "source": "steam",
        }
        with mock.patch("os.startfile"):
            r = reg.t_steam({"action": "install", "query": "hades"})
        self.assertEqual(r.get("resolution_confidence"), "high")

    # ---- la cascada REAL de resolución (con sus dependencias stubbeadas) ----
    def test_resolve_appid_prefers_local_library(self):
        reg = self._registry()

        class _Cand:
            def __init__(self, name, launch, source):
                self.name, self.launch, self.source = name, launch, source

            def as_dict(self):
                return {"name": self.name, "launch": self.launch, "source": self.source}

        reg.apps.find_steam_library = lambda q, limit=5: [
            _Cand("DOOM Eternal", "steam://rungameid/782330", "steam")
        ]
        # Si el local resuelve, NO debe tocar la red.
        import gemma4_agent.tools_pkg.tools as tools_mod
        with mock.patch.object(tools_mod, "_steam_store_first_result",
                               side_effect=AssertionError("must not hit network")):
            resolved = reg._resolve_steam_appid("doom eternal")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["appid"], "782330")
        self.assertEqual(resolved["source"], "steam")

    def test_resolve_appid_falls_to_store_search_when_local_empty(self):
        reg = self._registry()
        reg.apps.find_steam_library = lambda q, limit=5: []
        import gemma4_agent.tools_pkg.tools as tools_mod
        with mock.patch.object(tools_mod, "_steam_store_first_result",
                               return_value={"appid": "292030", "name": "The Witcher 3"}):
            resolved = reg._resolve_steam_appid("witcher 3")
        self.assertEqual(resolved["appid"], "292030")
        self.assertEqual(resolved["source"], "steam_store_search")

    def test_resolve_appid_empty_query_returns_none(self):
        reg = self._registry()
        self.assertIsNone(reg._resolve_steam_appid(""))

    # ---- AUTO-CONFIRM (se pide INSTALAR, no que deje el diálogo) ----
    def test_high_confidence_autoconfirms_and_reports_download_started(self):
        # appid explícito = alta confianza -> auto-confirma el diálogo.
        reg = self._registry(autoconfirm=True)
        with mock.patch("os.startfile") as startfile:
            r = reg.t_steam({"action": "install", "appid": "570"})
        startfile.assert_called_once_with("steam://install/570")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r.get("completion_status"), "confirmed_install_download_started")
        self.assertTrue(r.get("confirm", {}).get("confirmed"))

    def test_local_library_match_autoconfirms(self):
        reg = self._registry(autoconfirm=True)
        reg._resolve_steam_appid = lambda q: {
            "appid": "1145360", "match": {"name": "Hades"}, "source": "steam",
        }
        with mock.patch("os.startfile"):
            r = reg.t_steam({"action": "install", "query": "hades"})
        self.assertEqual(r.get("completion_status"), "confirmed_install_download_started")

    def test_low_confidence_does_NOT_autoconfirm(self):
        # juego resuelto por búsqueda en la store = baja confianza -> NO aprieta
        # Instalar (evita descargar el juego equivocado), deja el diálogo abierto.
        reg = self._registry(autoconfirm=True)  # confirmer disponible, pero...
        called = {"n": 0}
        reg._steam_confirm_install_dialog = lambda game, **k: (
            called.__setitem__("n", called["n"] + 1) or {"confirmed": True})
        reg._resolve_steam_appid = lambda q: {
            "appid": "782330", "match": {"name": "DOOM Eternal"},
            "source": "steam_store_search",  # BAJA confianza
        }
        with mock.patch("os.startfile"):
            r = reg.t_steam({"action": "install", "query": "doom"})
        self.assertEqual(called["n"], 0, "no debe intentar auto-confirmar en baja confianza")
        self.assertEqual(r.get("completion_status"), "opened_steam_install_dialog")
        self.assertEqual(r.get("resolution_confidence"), "low")

    def test_env_gate_off_disables_autoconfirm(self):
        import os as _os
        reg = self._registry(autoconfirm=True)
        called = {"n": 0}
        reg._steam_confirm_install_dialog = lambda game, **k: (
            called.__setitem__("n", called["n"] + 1) or {"confirmed": True})
        with mock.patch.dict(_os.environ, {"GEMMA4_STEAM_AUTOCONFIRM_INSTALL": "0"}):
            with mock.patch("os.startfile"):
                r = reg.t_steam({"action": "install", "appid": "570"})
        self.assertEqual(called["n"], 0)
        self.assertEqual(r.get("completion_status"), "opened_steam_install_dialog")

    def test_dialog_not_found_reports_honestly_no_lie(self):
        # confirmer devuelve confirmed=False -> NO afirmar que instaló.
        reg = self._registry(autoconfirm=False)  # confirmer -> not found
        with mock.patch("os.startfile"):
            r = reg.t_steam({"action": "install", "appid": "570"})
        self.assertEqual(r.get("completion_status"), "opened_steam_install_dialog")
        self.assertFalse(r.get("confirm", {}).get("confirmed"))
        # el note NO debe afirmar que la descarga arrancó.
        self.assertNotIn("download is now running", r.get("note", ""))


if __name__ == "__main__":
    unittest.main()
