"""Tests de la capa UNIVERSAL de computer-use (computer_use.py).

Rediseño 2026-05-25: NO un macro por intención, sino el 4B emite un PLAN de
primitivas y UN ejecutor las corre. Estos tests cubren el parseo del plan
(vocabulario cerrado) y el dispatch del ejecutor (con tools mockeadas, sin GUI).
La validación e2e real (calc/browser/chat/notepad 16/16) está en
scripts/_measure_cu_optionA.py."""
from __future__ import annotations

import unittest
from unittest.mock import ANY, MagicMock, call, patch

from gemma4_agent.computer_use_pkg.computer_use import (
    parse_plan, PRIMITIVES, summarize_result, PlanExecutor,
)


class ParsePlanTest(unittest.TestCase):
    def test_parses_clean_json(self):
        t = '[{"op":"focus_app","arg":"discord"},{"op":"open_chat","arg":"juan"}]'
        self.assertEqual(parse_plan(t),
                         [{"op": "focus_app", "arg": "discord"},
                          {"op": "open_chat", "arg": "juan"}])

    def test_tolerates_markdown_fences_and_prose(self):
        t = "Claro, aquí tenés:\n```json\n[{\"op\":\"type\",\"arg\":\"2+2\"}]\n```\nlisto"
        self.assertEqual(parse_plan(t), [{"op": "type", "arg": "2+2"}])

    def test_rejects_unknown_primitive(self):
        # vocabulario CERRADO: un op fuera de PRIMITIVES invalida el plan.
        self.assertIsNone(parse_plan('[{"op":"hack_nasa","arg":"x"}]'))

    def test_rejects_non_list(self):
        self.assertIsNone(parse_plan('{"op":"type","arg":"x"}'))
        self.assertIsNone(parse_plan("no hay json acá"))
        self.assertIsNone(parse_plan(""))

    def test_all_primitives_accepted(self):
        for p in PRIMITIVES:
            self.assertEqual(parse_plan(f'[{{"op":"{p}","arg":""}}]'),
                             [{"op": p, "arg": ""}])


class SummarizeResultTest(unittest.TestCase):
    def test_message_sent(self):
        plan = [{"op": "focus_app", "arg": "discord"}, {"op": "open_chat", "arg": "juan"},
                {"op": "type", "arg": "hola"}, {"op": "send", "arg": ""}]
        res = {"ok": True, "steps": plan, "focused_app": "Discord"}
        self.assertIn("juan", summarize_result("x", plan, res))
        self.assertIn("hola", summarize_result("x", plan, res))

    def test_failure_is_honest(self):
        plan = [{"op": "focus_app", "arg": "discord"}, {"op": "open_chat", "arg": "zzz"}]
        res = {"ok": False, "failed_at": "open_chat",
               "steps": [{"op": "focus_app", "arg": "discord", "ok": True},
                         {"op": "open_chat", "arg": "zzz", "ok": False}],
               "focused_app": "Discord"}
        msg = summarize_result("x", plan, res)
        self.assertIn("zzz", msg)
        self.assertTrue("No encontré" in msg or "no pude" in msg.lower())


    def test_discord_control_verified_summary(self):
        plan = [{"op": "focus_app", "arg": "discord"},
                {"op": "discord_control", "arg": "mute"}]
        res = {"ok": True, "verified": True, "focused_app": "Discord",
               "steps": [{"op": "focus_app", "arg": "discord", "ok": True},
                         {"op": "discord_control", "arg": "mute", "ok": True,
                          "verified": True, "action": "mute"}]}
        msg = summarize_result("mutea mi microfono en discord", plan, res)
        self.assertIn("Discord", msg)
        self.assertIn("microfono", msg.lower())


class OpenUrlVerifyTest(unittest.TestCase):
    """El verify de open_url normaliza (quita espacios/puntuación) en AMBOS lados:
    el título "espacia" el dominio ("stackoverflow"->"Stack Overflow") y el match
    contiguo daba falso-negativo (bug medido en la maratón 2026-05-25)."""

    def _run(self, url, fg_title):
        import gemma4_agent.computer_use_pkg.computer_use as cu
        from unittest.mock import patch
        ag = MagicMock()
        ag._app_window_title.return_value = ""
        ag.tools._focus_window_chen.return_value = True
        ag.tools.execute.return_value = {"ok": True}
        ex = cu.PlanExecutor(ag)
        with patch.object(cu, "_foreground_title", return_value=fg_title):
            return ex._open_url(url, "opera")

    def test_spaced_domain_title_matches(self):
        self.assertTrue(self._run("stackoverflow.com", "Newest Questions - Stack Overflow - Opera")["ok"])
        self.assertTrue(self._run("duckduckgo.com", "DuckDuckGo — Privacy - Opera")["ok"])

    def test_plain_domain_title_matches(self):
        self.assertTrue(self._run("python.org", "Welcome to Python.org - Opera")["ok"])

    def test_wrong_page_does_not_match(self):
        self.assertFalse(self._run("github.com", "Welcome to Python.org - Opera")["ok"])


class OpenUrlGenericBrowserTest(unittest.TestCase):
    """FIX 2026-05-26: 'andá al navegador y abrí X' fallaba porque
    focus_app('navegador') no resuelve y se tipeaba en la ventana equivocada.
    Ahora open_url usa el navegador POR DEFECTO del SO (web_open_url) salvo que
    se nombre un navegador CONCRETO (Opera/Chrome/...)."""

    def _run(self, url, app_hint, fg_title):
        import gemma4_agent.computer_use_pkg.computer_use as cu
        from unittest.mock import patch
        ag = MagicMock()
        ag.tools._focus_window_chen.return_value = True
        ag.tools.execute.return_value = {"ok": True}
        ag.tools.web_open_url.return_value = {"ok": True}
        ex = cu.PlanExecutor(ag)
        with patch.object(cu, "_foreground_title", return_value=fg_title):
            res = ex._open_url(url, app_hint)
        return ag, res

    def test_generic_navegador_uses_default_browser(self):
        # app_hint genérico -> NO se tipea en una ventana (no ctrl+l), se usa
        # web_open_url (default del SO).
        ag, res = self._run("instant-gaming.com", "navegador",
                            "Resident Evil - Instant-Gaming - Opera")
        ag.tools.web_open_url.assert_called_once()
        # no debió teclear la URL por la barra (esa vía es solo para navegador concreto)
        gui_calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertFalse(any(
            len(a) > 1 and a[1].get("action") == "type" for a in gui_calls))
        self.assertTrue(res["ok"])  # verify por título OK

    def test_empty_hint_uses_default_browser(self):
        ag, res = self._run("youtube.com", "", "YouTube - Opera")
        ag.tools.web_open_url.assert_called_once()

    def test_concrete_browser_uses_address_bar(self):
        # navegador CONCRETO -> sí usa la barra de direcciones (ctrl+l + type).
        ag, res = self._run("python.org", "Opera GX", "Welcome to Python.org - Opera GX")
        ag.tools.web_open_url.assert_not_called()
        gui_calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertTrue(any(
            len(a) > 1 and a[1].get("action") == "type" for a in gui_calls))


class OpenChatFuzzyTest(unittest.TestCase):
    """open_chat es tolerante a typos: el quick-switcher de las apps de chat hace
    fuzzy match ("shotercock"->"ShooterCOCK"). Si el título CAMBIÓ a un chat nuevo,
    es éxito y se reporta el chat REAL abierto (no el typo). Bug medido 2026-05-25:
    el usuario veía "No encontré" de un éxito real."""

    def _exec(self, before_title, after_title):
        from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor
        ag = MagicMock()
        # _app_window_title devuelve before en la 1ª llamada, after en la 2ª.
        ag._app_window_title.side_effect = [before_title, after_title]
        ag._title_now_matches.return_value = False  # no match exacto del typo
        ex = PlanExecutor(ag)
        return ex._open_chat("shotercock", "Discord")

    def test_fuzzy_navigation_is_success_and_reports_real_name(self):
        r = self._exec("@CbaYeah - Discord", "@ShooterCOCK - Discord")
        self.assertTrue(r["ok"])
        self.assertTrue(r["fuzzy"])
        self.assertEqual(r["opened"], "ShooterCOCK")  # nombre REAL, no el typo

    def test_no_navigation_is_failure(self):
        # el título NO cambió -> no navegó -> fallo honesto.
        r = self._exec("@CbaYeah - Discord", "@CbaYeah - Discord")
        self.assertFalse(r["ok"])


class DiscordVoiceTest(unittest.TestCase):
    def _agent(self):
        ag = MagicMock()
        ag.tools.execute.return_value = {"ok": True}
        ag.tools._focus_window_chen.return_value = True
        ag._title_now_matches.return_value = False
        ag._app_window_title.side_effect = ["@general - Discord", "@musica - Discord"]
        return ag

    def test_open_voice_success_on_navigation(self):
        ag = self._agent()
        ex = PlanExecutor(ag)
        ex._discord_voice_status = MagicMock(side_effect=[
            {"ok": True, "voice_connected": False, "names": []},
            {"ok": True, "voice_connected": True, "names": ["Voice Connected", "musica"]},
        ])
        r = ex._open_voice("musica", "Discord")
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        ag._quick_switcher_nav.assert_called_once()

    def test_open_voice_fails_when_no_state_changed(self):
        ag = self._agent()
        ag._app_window_title.side_effect = ["@general - Discord", "@general - Discord"]
        ex = PlanExecutor(ag)
        ex._discord_voice_status = MagicMock(side_effect=[
            {"ok": True, "voice_connected": False, "names": []},
            {"ok": True, "voice_connected": False, "names": ["general"]},
        ])
        r = ex._open_voice("musica", "Discord")
        self.assertFalse(r["ok"])


class DiscordControlTest(unittest.TestCase):
    def _exec(self):
        ag = MagicMock()
        ag.tools._focus_window_chen.return_value = True
        ag.tools.execute.return_value = {"ok": True}
        return PlanExecutor(ag)

    def test_voice_status_uses_uia_patterns_and_bounds_not_labels(self):
        ex = self._exec()
        def el(x, y, patterns, toggle_state=None):
            return {
                "name": "",
                "control_type": "Button",
                "enabled": True,
                "offscreen": False,
                "patterns": patterns,
                "toggle_state": toggle_state,
                "bounds": {"x": x, "y": y, "width": 32, "height": 32},
                "clickable_point": {"x": x + 16, "y": y + 16},
            }
        ex.tools.execute.return_value = {
            "ok": True,
            "root": {"bounds": {"x": 0, "y": 0, "width": 1200, "height": 800}},
            "elements": [
                el(310, 650, ["Invoke"]),
                el(220, 710, ["Toggle"], "On"),
                el(260, 710, ["Toggle"], "Off"),
            ],
        }
        r = ex._discord_voice_status("Discord")
        self.assertTrue(r["mic_muted"])
        self.assertFalse(r["deafened"])
        self.assertTrue(r["voice_connected"])
        self.assertIsNotNone(r["disconnect_control"])

    def test_voice_status_does_not_treat_same_row_settings_as_disconnect(self):
        ex = self._exec()
        def el(x, y, patterns, toggle_state=None):
            return {
                "name": "",
                "control_type": "Button",
                "enabled": True,
                "offscreen": False,
                "patterns": patterns,
                "toggle_state": toggle_state,
                "bounds": {"x": x, "y": y, "width": 32, "height": 32},
                "clickable_point": {"x": x + 16, "y": y + 16},
            }
        ex.tools.execute.return_value = {
            "ok": True,
            "root": {"bounds": {"x": 0, "y": 0, "width": 1200, "height": 800}},
            "elements": [
                el(220, 710, ["Toggle"], "Off"),
                el(260, 710, ["Toggle"], "Off"),
                el(310, 710, ["Invoke"]),
            ],
        }
        r = ex._discord_voice_status("Discord")
        self.assertFalse(r["voice_connected"])
        self.assertIsNone(r["disconnect_control"])

    def test_mute_is_idempotent_when_already_muted(self):
        ex = self._exec()
        ex._discord_voice_status = MagicMock(return_value={
            "ok": True, "mic_muted": True,
            "deafened": False, "voice_connected": True, "names": ["Unmute"],
        })
        ex._keypress = MagicMock()
        r = ex._discord_control("mute", "Discord")
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        self.assertTrue(r["already"])
        ex._keypress.assert_not_called()

    def test_mute_uses_shortcut_and_verifies_state_change(self):
        ex = self._exec()
        ex._discord_voice_status = MagicMock(side_effect=[
            {"ok": True, "mic_muted": False,
             "deafened": False, "voice_connected": True, "names": ["Mute"]},
            {"ok": True, "mic_muted": True,
             "deafened": False, "voice_connected": True, "names": ["Unmute"]},
        ])
        ex._keypress = MagicMock(return_value={"ok": True, "keys": "ctrl+shift+m"})
        r = ex._discord_control("mute", "Discord")
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        ex._keypress.assert_called_once_with("ctrl+shift+m", "Discord")

    def test_deafen_failure_is_not_verified_success(self):
        ex = self._exec()
        ex._discord_voice_status = MagicMock(side_effect=[
            {"ok": True, "mic_muted": False, "deafened": False,
             "voice_connected": True, "names": ["Deafen"]},
            {"ok": True, "mic_muted": False, "deafened": False,
             "voice_connected": True, "names": ["Deafen"]},
        ])
        ex._keypress = MagicMock(return_value={"ok": True, "keys": "ctrl+shift+d"})
        r = ex._discord_control("deafen", "Discord")
        self.assertFalse(r["ok"])
        self.assertFalse(r["verified"])

    def test_unknown_mute_state_attempts_shortcut_without_claiming_verified(self):
        ex = self._exec()
        ex._discord_voice_status = MagicMock(side_effect=[
            {"ok": True, "mic_muted": None, "deafened": None,
             "voice_connected": False, "uia_degraded": True, "names": ["Chrome Legacy Window"]},
            {"ok": True, "mic_muted": None, "deafened": None,
             "voice_connected": False, "uia_degraded": True, "names": ["Chrome Legacy Window"]},
        ])
        ex._keypress = MagicMock(return_value={"ok": True, "keys": "ctrl+shift+m"})
        r = ex._discord_control("mute", "Discord")
        self.assertTrue(r["ok"])
        self.assertFalse(r["verified"])
        self.assertTrue(r["degraded"])
        ex._keypress.assert_called_once_with("ctrl+shift+m", "Discord")

    def test_disconnect_fails_without_voice_control(self):
        ex = self._exec()
        ex._discord_voice_status = MagicMock(return_value={
            "ok": True, "mic_muted": None, "deafened": None,
            "disconnect_control": None, "voice_connected": False, "names": [],
        })
        r = ex._discord_control("disconnect_voice", "Discord")
        self.assertFalse(r["ok"])
        self.assertFalse(r["verified"])


class CapabilityRouterTest(unittest.TestCase):
    def _exec(self):
        ag = MagicMock()
        ag.tools.execute.return_value = {"ok": True}
        ag.tools._focus_window_chen.return_value = True
        ag._window_title_in_text.return_value = "Opera GX"
        return PlanExecutor(ag)

    def test_router_owns_primitives_by_domain(self):
        ex = self._exec()
        router = ex.capabilities
        self.assertIs(router._by_op["focus_app"], router.apps)
        self.assertIs(router._by_op["open_url"], router.browser)
        self.assertIs(router._by_op["open_voice"], router.discord)
        self.assertIs(router._by_op["discord_control"], router.discord)
        self.assertIs(router._by_op["click"], router.generic_ui)

    def test_router_sends_browser_context_click_to_browser_capability(self):
        ex = self._exec()
        ex.capabilities.browser._click = MagicMock(return_value={"ok": True, "verified": True})
        res, app = ex.capabilities.run("click", "favorite-site", "Opera GX")
        self.assertTrue(res["ok"])
        self.assertEqual(app, "Opera GX")
        ex.capabilities.browser._click.assert_called_once_with("favorite-site", "Opera GX")

    def test_executor_uses_internal_capability_router(self):
        ex = self._exec()
        ex.capabilities.run = MagicMock(side_effect=[
            ({"ok": True, "focused": "Opera GX"}, "Opera GX"),
            ({"ok": True, "label": "favorite-site"}, "Opera GX"),
        ])
        with patch("gemma4_agent.computer_use.time.sleep"):
            r = ex.execute([
                {"op": "focus_app", "arg": "Opera GX"},
                {"op": "click", "arg": "favorite-site"},
            ], "t")
        self.assertTrue(r["ok"])
        ex.capabilities.run.assert_has_calls([
            call("focus_app", "Opera GX", "", snapshot=ANY, policy=ANY),
            call("click", "favorite-site", "Opera GX", snapshot=ANY, policy=ANY),
        ])


class ExecutorDispatchTest(unittest.TestCase):
    """El ejecutor llama las primitivas correctas. Mockeamos el agente/tools para
    no tocar la GUI; verificamos QUÉ tool-calls emite por cada op."""

    def _agent(self):
        ag = MagicMock()
        ag._window_title_in_text.return_value = "Calculadora"
        ag._app_window_title.return_value = "Calculadora"
        ag.tools._focus_window_chen.return_value = True
        ag.tools.execute.return_value = {"ok": True, "verified": True}
        return ag

    def _executor(self, ag):
        ex = PlanExecutor(ag)
        ex.detector.snapshot = MagicMock(return_value={
            "ok": True,
            "app_kind": "native",
            "is_browser": False,
            "cdp_candidate": False,
            "uia_checked": False,
            "uia_available": True,
            "uia_degraded": False,
            "ocr_available": True,
            "vision_fallback_available": False,
            "error": "",
            "cached": False,
        })
        return ex

    def test_type_keypress_dispatch(self):
        ag = self._agent()
        ex = self._executor(ag)
        plan = [{"op": "focus_app", "arg": "Calculadora"},
                {"op": "type", "arg": "2+2"}, {"op": "keypress", "arg": "enter"}]
        res = ex.execute(plan, "t")
        self.assertTrue(res["ok"])
        # debe haberse llamado gui type con "2+2" y keypress enter
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertTrue(any(a[0] == "gui" and a[1].get("text") == "2+2" for a in calls))
        self.assertTrue(any(a[0] == "gui" and a[1].get("keys") == "enter" for a in calls))

    def test_focus_app_reports_failure_when_neither_focus_nor_launch_works(self):
        # _focus_app YA NO miente con ok:True: si no estaba al frente y app.open
        # falla y tampoco queda al frente, debe reportar ok:False (y como focus_app
        # es hard-fail, corta la cadena en vez de "verificar" un plan que ni abrió).
        ag = self._agent()
        ag._window_title_in_text.return_value = "Inexistente"
        ag.tools._focus_window_chen.return_value = False  # nunca queda al frente
        ag.tools.execute.return_value = {"ok": False}      # app.open falla
        ex = PlanExecutor(ag)
        with patch("gemma4_agent.computer_use.time.sleep"):
            r = ex._focus_app("appquenoexiste")
        self.assertFalse(r["ok"])

    def test_focus_app_ok_when_app_launches(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Nueva"
        ag.tools._focus_window_chen.side_effect = [False, True]
        ag.tools.execute.return_value = {"ok": True}       # app.open SÍ abre
        ex = self._executor(ag)
        with patch("gemma4_agent.computer_use.time.sleep"):
            r = ex._focus_app("alguna-app")
        self.assertTrue(r["ok"])
        self.assertTrue(r["launched_if_needed"])

    def test_focus_app_failure_stops_chain_and_does_not_type(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Inexistente"
        ag.tools._focus_window_chen.return_value = False
        ag.tools.execute.return_value = {"ok": False}
        ex = self._executor(ag)
        with patch("gemma4_agent.computer_use.time.sleep"):
            res = ex.execute([{"op": "focus_app", "arg": "noexiste"},
                              {"op": "type", "arg": "no debe tipearse"}], "t")
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed_at"], "focus_app")
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertFalse(any(
            len(a) > 1 and a[1].get("text") == "no debe tipearse" for a in calls))

    def test_critical_step_retries_before_aborting(self):
        # REINTENTO (2026-05-27): un paso CRÍTICO que falla TRANSITORIAMENTE (1ra
        # vez) pero anda al reintento NO debe abortar la cadena. Mockeamos
        # capabilities.run para fallar focus_app una vez y luego OK.
        ag = self._agent()
        ex = self._executor(ag)
        seq = [
            ({"ok": False, "verified": False}, "App"),   # focus_app intento 1: falla
            ({"ok": True, "verified": True}, "App"),     # focus_app intento 2: OK
            ({"ok": True, "verified": True}, "App"),     # open_url OK
        ]
        ex.capabilities.run = MagicMock(side_effect=seq)
        with patch("gemma4_agent.computer_use.time.sleep"):
            res = ex.execute([{"op": "focus_app", "arg": "App"},
                              {"op": "open_url", "arg": "example.com"}], "t")
        self.assertTrue(res["ok"])  # NO abortó pese al fallo transitorio
        self.assertIsNone(res.get("failed_at"))
        # focus_app se reintentó (3 llamadas totales: 2 focus_app + 1 open_url)
        self.assertEqual(ex.capabilities.run.call_count, 3)

    def test_prefer_cdp_set_when_chain_interacts_in_page(self):
        # prefer_cdp (2026-05-27): si la cadena tiene type/click/send DESPUÉS de
        # open_url, la capability de navegador debe preferir CDP (robusto, no roba
        # foco) para esos pasos en-página.
        ag = self._agent()
        ex = self._executor(ag)
        ex.capabilities.run = MagicMock(return_value=({"ok": True, "verified": True}, "X"))
        with patch("gemma4_agent.computer_use.time.sleep"):
            ex.execute([{"op": "open_url", "arg": "youtube.com"},
                        {"op": "type", "arg": "gatos"},
                        {"op": "send", "arg": ""}], "t")
        self.assertTrue(ex.capabilities.browser._prefer_cdp)

    def test_prefer_cdp_not_set_for_navigate_only(self):
        # cadena de SOLO navegar (sin interacción en página) -> NO fuerza CDP.
        ag = self._agent()
        ex = self._executor(ag)
        ex.capabilities.run = MagicMock(return_value=({"ok": True, "verified": True}, "X"))
        with patch("gemma4_agent.computer_use.time.sleep"):
            ex.execute([{"op": "open_url", "arg": "example.com"}], "t")
        self.assertFalse(ex.capabilities.browser._prefer_cdp)

    def test_critical_step_aborts_after_exhausting_retries(self):
        # Si el paso crítico falla SIEMPRE (agota reintentos), aborta honesto.
        ag = self._agent()
        ex = self._executor(ag)
        ex.capabilities.run = MagicMock(
            return_value=({"ok": False, "verified": False}, "App"))
        with patch("gemma4_agent.computer_use.time.sleep"):
            res = ex.execute([{"op": "focus_app", "arg": "App"},
                              {"op": "type", "arg": "no debe tipearse"}], "t")
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed_at"], "focus_app")
        # se intentó 1 + _STEP_RETRIES veces (no infinito)
        import gemma4_agent.computer_use_pkg.computer_use as _cu
        self.assertEqual(ex.capabilities.run.call_count, 1 + _cu._STEP_RETRIES)

    def test_nav_failure_stops_chain(self):
        # si open_chat falla (título no matchea), el ejecutor corta y NO teclea.
        ag = self._agent()
        ag._title_now_matches.return_value = False  # open_chat no confirma
        ex = self._executor(ag)
        plan = [{"op": "focus_app", "arg": "discord"},
                {"op": "open_chat", "arg": "zzz"},
                {"op": "type", "arg": "hola"}]
        res = ex.execute(plan, "t")
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed_at"], "open_chat")
        # NO debe haber tecleado "hola" tras el fallo de navegación.
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertFalse(any(len(a) > 1 and a[1].get("text") == "hola" for a in calls))


    def test_discord_type_forces_sendkeys_no_clipboard(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Discord"
        ex = self._executor(ag)
        plan = [{"op": "focus_app", "arg": "discord"},
                {"op": "type", "arg": "hola"}]
        with patch("gemma4_agent.computer_use._foreground_title", return_value="Discord"):
            res = ex.execute(plan, "t")
        self.assertTrue(res["ok"])
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertTrue(any(
            a[0] == "gui"
            and a[1].get("text") == "hola"
            and a[1].get("method") == "sendkeys"
            for a in calls
        ))

    def test_discord_control_failure_stops_chain(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Discord"
        ex = self._executor(ag)
        ex._discord_control = MagicMock(return_value={"ok": False, "verified": False})
        plan = [{"op": "focus_app", "arg": "discord"},
                {"op": "discord_control", "arg": "disconnect_voice"},
                {"op": "type", "arg": "no debe tipearse"}]
        res = ex.execute(plan, "t")
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed_at"], "discord_control")
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertFalse(any(
            len(a) > 1 and a[1].get("text") == "no debe tipearse" for a in calls
        ))

    def test_scroll_and_wait_dispatch_are_mock_safe(self):
        ag = self._agent()
        ex = self._executor(ag)
        with patch("gemma4_agent.computer_use.time.sleep"):
            res = ex.execute([
                {"op": "focus_app", "arg": "opera"},
                {"op": "scroll", "arg": "-6"},
                {"op": "wait", "arg": "0.2"},
            ], "t")
        self.assertTrue(res["ok"])
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertTrue(any(
            a[0] == "gui" and a[1].get("action") == "scroll" for a in calls
        ))

    def test_click_failure_stops_browser_chain(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Opera GX"
        ag.tools.execute.side_effect = [
            {"ok": False, "result": {"ok": False}},
        ]
        ex = self._executor(ag)
        plan = [{"op": "focus_app", "arg": "Opera GX"},
                {"op": "click", "arg": "favorite-site"},
                {"op": "type", "arg": "no debe tipearse"}]
        res = ex.execute(plan, "t")
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed_at"], "click")
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertFalse(any(
            len(a) > 1 and a[1].get("text") == "no debe tipearse" for a in calls
        ))

    def test_browser_chain_uses_cdp_when_visible_session_available(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Opera GX"
        ag.tools.execute.side_effect = [
            {"ok": True, "available": True},     # browser_real.status
            {"ok": True, "attached": True},      # browser_real.attach_visible
            {"ok": True, "verified": True, "url": "https://example.com"},  # goto
            {"ok": True, "verified": True, "state_changed": True,
             "completion_status": "clicked_accessible_verified"},
        ]
        ex = self._executor(ag)
        # _focus_app lee la ventana al frente con _foreground_title (real OS):
        # lo parcheamos para que el token quede en un navegador (Opera) de forma
        # determinista, sin leer el escritorio real del que corre el test.
        with patch("gemma4_agent.computer_use.time.sleep"), \
             patch("gemma4_agent.computer_use_caps.browser.time.sleep"), \
             patch("gemma4_agent.computer_use._foreground_title", return_value="Docs - Opera"):
            res = ex.execute([
                {"op": "focus_app", "arg": "Opera GX"},
                {"op": "open_url", "arg": "example.com"},
                {"op": "click", "arg": "Docs"},
            ], "t")
        self.assertTrue(res["ok"])
        self.assertTrue(res["verified"])
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertTrue(any(
            a[0] == "browser_real" and a[1].get("action") == "goto" for a in calls
        ))
        self.assertTrue(any(
            a[0] == "browser_real" and a[1].get("action") == "click_accessible"
            for a in calls
        ))

    def test_unverified_browser_click_makes_plan_unverified(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Opera GX"
        ag.tools.execute.side_effect = [
            {"ok": True, "available": True},
            {"ok": True, "attached": True},
            {"ok": True, "verified": True, "url": "https://example.com"},
            {"ok": True, "verified": False, "state_changed": False,
             "completion_status": "clicked_accessible_unverified"},
        ]
        ex = self._executor(ag)
        with patch("gemma4_agent.computer_use.time.sleep"), \
             patch("gemma4_agent.computer_use_caps.browser.time.sleep"), \
             patch("gemma4_agent.computer_use._foreground_title", return_value="Docs - Opera"):
            res = ex.execute([
                {"op": "focus_app", "arg": "Opera GX"},
                {"op": "open_url", "arg": "example.com"},
                {"op": "click", "arg": "Docs"},
            ], "t")
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed_at"], "click")

    def test_browser_type_and_send_use_structured_session_after_open_url(self):
        ag = self._agent()
        ag._window_title_in_text.return_value = "Opera GX"
        ag.tools.execute.side_effect = [
            {"ok": True, "available": True},
            {"ok": True, "attached": True},
            {"ok": True, "verified": True, "url": "https://example.com"},
            {"ok": True, "verified": True, "state_changed": True,
             "completion_status": "typed_text_verified"},
            {"ok": True, "verified": True, "pressed": "Enter"},
        ]
        ex = self._executor(ag)
        with patch("gemma4_agent.computer_use.time.sleep"), \
             patch("gemma4_agent.computer_use_caps.browser.time.sleep"), \
             patch("gemma4_agent.computer_use._foreground_title", return_value="Docs - Opera"):
            res = ex.execute([
                {"op": "focus_app", "arg": "Opera GX"},
                {"op": "open_url", "arg": "example.com"},
                {"op": "type", "arg": "hello"},
                {"op": "send", "arg": ""},
            ], "t")
        self.assertTrue(res["ok"])
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertTrue(any(
            a[0] == "browser_real" and a[1].get("action") == "type_text"
            and a[1].get("value") == "hello"
            for a in calls
        ))
        self.assertTrue(any(
            a[0] == "browser_real" and a[1].get("action") == "press"
            and a[1].get("key") == "Enter"
            for a in calls
        ))


if __name__ == "__main__":
    unittest.main()
