"""Unit tests for whatsapp_tool."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from .config import AgentConfig
from .domain_tools import (
    _normalize_phone_for_whatsapp,
    _resolve_whatsapp_recipient,
    whatsapp_tool,
)
from .state import AgentState


def _fresh_state() -> AgentState:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return AgentState(path=p)


class TestPhoneNormalize(unittest.TestCase):

    def test_strips_separators(self):
        self.assertEqual(_normalize_phone_for_whatsapp("+54 9 11 1234-5678"), "5491112345678")

    def test_strips_parens(self):
        self.assertEqual(_normalize_phone_for_whatsapp("+1 (555) 123-4567"), "15551234567")

    def test_empty(self):
        self.assertEqual(_normalize_phone_for_whatsapp(""), "")

    def test_already_digits(self):
        self.assertEqual(_normalize_phone_for_whatsapp("5491112345678"), "5491112345678")


class TestWhatsappStatus(unittest.TestCase):

    def test_status_reports_installed_when_app_present(self):
        state = _fresh_state()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "shell:AppsFolder\\X!App"}):
            r = whatsapp_tool({"action": "status"}, state)
        self.assertTrue(r["ok"])
        self.assertTrue(r["installed"])
        self.assertEqual(r["app_kind"], "uwp")

    def test_status_reports_not_installed(self):
        state = _fresh_state()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": None, "launch_target": None}):
            r = whatsapp_tool({"action": "status"}, state)
        self.assertTrue(r["ok"])
        self.assertFalse(r["installed"])


class TestWhatsappSendMessage(unittest.TestCase):

    def setUp(self):
        self.state = _fresh_state()

    def test_send_with_explicit_phone_opens_deeplink_no_executor(self):
        # Sin executor (CLI / tests), auto_send se desactiva graceful y solo
        # se abre el chat — sent=False es correcto en este path.
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "shell:AppsFolder\\X!App"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen") as popen:
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+54 9 11 1234-5678", "text": "hola"},
                self.state, executor=None,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["provider"], "whatsapp_desktop")
        self.assertFalse(r["sent"])
        self.assertEqual(r["recipient_normalized"], "5491112345678")
        self.assertIn("whatsapp://send?phone=5491112345678", r["deeplink"])
        self.assertIn("text=hola", r["deeplink"])
        popen.assert_called_once()

    def test_send_falls_back_to_web_when_no_app(self):
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": None, "launch_target": None}), \
             patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True) as wb:
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567", "text": "hi"},
                self.state, executor=None,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["provider"], "whatsapp_web")
        self.assertIn("wa.me/15551234567", r["url"])
        self.assertIn("text=hi", r["url"])
        wb.assert_called_once()
        # Web nunca auto-envia.
        self.assertFalse(r["sent"])

    def test_send_without_recipient_fails(self):
        r = whatsapp_tool({"action": "send_message", "text": "hola"}, self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertIn("recipient", r["error"].lower())

    def test_send_without_text_fails(self):
        r = whatsapp_tool(
            {"action": "send_message", "phone": "+1 555 123 4567"},
            self.state,
        )
        self.assertFalse(r["ok"])
        self.assertIn("text", r["error"].lower())

    def test_invalid_phone_format_fails(self):
        r = whatsapp_tool(
            {"action": "send_message", "phone": "totally not a phone", "text": "X"},
            self.state,
        )
        self.assertFalse(r["ok"])
        self.assertIn("invalid phone", r["error"].lower())

    def test_phone_too_short_fails(self):
        r = whatsapp_tool(
            {"action": "send_message", "phone": "+1 23", "text": "X"},
            self.state,
        )
        self.assertFalse(r["ok"])
        # Either invalid format or too short — both are needs_user.
        self.assertEqual(r["status"], "needs_user")

    def test_open_chat_without_text(self):
        # open_chat NO requiere text.
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "open_chat", "phone": "+54 9 11 1234-5678"},
                self.state,
            )
        self.assertTrue(r["ok"])
        # Deeplink no debe llevar &text=
        self.assertNotIn("text=", r["deeplink"])

    def test_unknown_action_fails(self):
        r = whatsapp_tool({"action": "fly_to_mars", "phone": "+1 555 123 4567"}, self.state)
        self.assertFalse(r["ok"])


class TestWhatsappContactResolution(unittest.TestCase):
    """contact='<name>' debe buscar phone en el contacts store."""

    def setUp(self):
        self.state = _fresh_state()
        # Register a contact with phone
        self.state.register_resource(
            "contact", "Juan Perez",
            metadata={"name": "Juan Perez", "phone": "+54 9 11 8765-4321", "email": ""},
        )
        self.state.register_resource(
            "contact", "Maria Sin Phone",
            metadata={"name": "Maria Sin Phone", "phone": "", "email": "maria@x.com"},
        )

    def test_send_by_contact_name_uses_stored_phone(self):
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen") as popen:
            r = whatsapp_tool(
                {"action": "send_message", "contact": "Juan", "text": "hola"},
                self.state,
            )
        self.assertTrue(r["ok"], f"expected ok, got: {r}")
        self.assertEqual(r["recipient_normalized"], "5491187654321")
        self.assertTrue(r["recipient_source"].startswith("contact:"))
        popen.assert_called_once()

    def test_contact_without_phone_falls_back_to_gui_search(self):
        # Post 2026-05-15: en vez de fallar cuando el contacto no tiene
        # phone, el resolver indica gui_search para que el caller use la
        # busqueda dentro de WhatsApp Desktop.
        result = _resolve_whatsapp_recipient(
            {"contact": "Maria"}, self.state,
        )
        self.assertIsInstance(result, tuple)
        raw, normalized, source, name = result
        self.assertIsNone(raw)
        self.assertIsNone(normalized)
        self.assertEqual(source, "gui_search")
        self.assertEqual(name, "Maria")

    def test_unknown_contact_falls_back_to_gui_search(self):
        # Mismo flujo: contacto no esta en store local -> tirar al GUI search.
        # En el tool real (con executor), eso usara WhatsApp UI para buscar.
        # Sin executor (este test), retorna error needs_user pidiendo CLI.
        r = whatsapp_tool(
            {"action": "send_message", "contact": "Persona Inexistente", "text": "hola"},
            self.state, executor=None,
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        # Mensaje debe mencionar gui_search O cli mode.
        err_low = r["error"].lower()
        self.assertTrue("gui search" in err_low or "cli mode" in err_low,
                        f"expected GUI-search-related error, got: {r['error']}")

    def test_resolve_recipient_helper_returns_4tuple(self):
        # Nueva firma: (raw, normalized, source, name_for_gui_search).
        result = _resolve_whatsapp_recipient(
            {"contact": "Juan"}, self.state,
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        raw, normalized, source, name = result
        self.assertEqual(normalized, "5491187654321")
        self.assertTrue(source.startswith("contact:"))
        self.assertIsNone(name)  # no necesario porque tenemos phone


class TestWhatsappAliases(unittest.TestCase):
    """Aceptamos varios alias para los campos."""

    def setUp(self):
        self.state = _fresh_state()

    def test_to_alias_works(self):
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "to": "+1 555 123 4567", "message": "hi"},
                self.state,
            )
        # "to" se interpreta como nombre de contacto (no como phone) y falla
        # porque no hay contacto que matchee.
        # Por design: phone va a "phone" / "number". "to" es nombre.
        # Esto es esperado — el LLM debe usar phone= para numeros.
        self.assertFalse(r["ok"])

    def test_message_alias_for_text(self):
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567", "message": "hola via alias"},
                self.state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["text"], "hola via alias")

    def test_body_alias_for_text(self):
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567", "body": "via body"},
                self.state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["text"], "via body")


class TestWhatsappAutoSend(unittest.TestCase):
    """Auto-send: tras abrir el chat, esperar y mandar Enter solo si la
    ventana activa es WhatsApp."""

    def setUp(self):
        self.state = _fresh_state()
        # Patch time.sleep para que los tests no esperen 1.8s real.
        self._sleep_patcher = patch("time.sleep")
        self._sleep_patcher.start()

    def tearDown(self):
        self._sleep_patcher.stop()

    def _mock_executor_focus_ok(self):
        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True, "title": "WhatsApp"}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "WhatsApp - Juan", "pid": 123}}
            if name == "gui" and args.get("action") == "keypress":
                return {"ok": True, "keys": "enter"}
            return {"ok": False, "error": f"unexpected: {name}({args})"}
        return MagicMock(side_effect=_exec)

    def test_auto_send_default_true_for_send_message(self):
        executor = self._mock_executor_focus_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567", "text": "hi"},
                self.state, executor=executor,
            )
        self.assertTrue(r["ok"])
        self.assertTrue(r["sent"], f"expected sent=True, got {r}")
        self.assertTrue(r["verified"])
        self.assertEqual(r["completion_status"], "message_sent")
        # Executor llamado para focus, active, keypress (al menos 3 calls).
        self.assertGreaterEqual(executor.call_count, 3)

    def test_auto_send_aborts_when_wrong_window_focused(self):
        def _exec_wrong(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": False, "error": "window not found"}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "VS Code - test.py", "pid": 999}}
            return {"ok": True}
        executor = MagicMock(side_effect=_exec_wrong)
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567", "text": "rm -rf /"},
                self.state, executor=executor,
            )
        # CRITICO: no debe haber enviado Enter porque la ventana activa es VS Code.
        self.assertFalse(r["sent"], "MUST NOT send Enter to VS Code")
        # Debe registrar la razon del abort.
        self.assertIn("not WhatsApp", r["auto_send_info"]["abort_reason"])
        # Y NUNCA debe haber llamado gui.keypress.
        keypress_calls = [c for c in executor.call_args_list
                          if c.args[0] == "gui" and c.args[1].get("action") == "keypress"]
        self.assertEqual(len(keypress_calls), 0)

    def test_auto_send_false_skips_enter_completely(self):
        executor = self._mock_executor_focus_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567",
                 "text": "hi", "auto_send": False},
                self.state, executor=executor,
            )
        self.assertTrue(r["ok"])
        self.assertFalse(r["sent"])
        self.assertFalse(r["auto_send_attempted"])
        # Executor NO debe haberse llamado para auto-send.
        executor.assert_not_called()

    def test_auto_send_false_via_string(self):
        # LLM puede pasar "false" como string en JSON args.
        executor = self._mock_executor_focus_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567",
                 "text": "hi", "auto_send": "false"},
                self.state, executor=executor,
            )
        self.assertFalse(r["auto_send_attempted"])

    def test_open_chat_never_auto_sends(self):
        # action=open_chat es solo "abre el chat", nunca enviar.
        executor = self._mock_executor_focus_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "open_chat", "phone": "+1 555 123 4567"},
                self.state, executor=executor,
            )
        self.assertTrue(r["ok"])
        self.assertFalse(r["sent"])
        executor.assert_not_called()

    def test_wait_seconds_is_clamped(self):
        # wait_seconds=999 debe clampearse a 10s max.
        executor = self._mock_executor_focus_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567",
                 "text": "hi", "wait_seconds": 999},
                self.state, executor=executor,
            )
        self.assertLessEqual(r["auto_send_info"]["wait_seconds"], 10.0)

    def test_executor_exception_aborts_safely(self):
        # Si executor(window.focus) lanza excepcion, no debe explotar todo.
        def _exec_explode(name, args):
            raise RuntimeError("simulated executor crash")
        executor = MagicMock(side_effect=_exec_explode)
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567", "text": "hi"},
                self.state, executor=executor,
            )
        # Result aun debe ser ok (chat abierto) pero sent=False.
        self.assertTrue(r["ok"])
        self.assertFalse(r["sent"])
        self.assertIn("focus call failed", r["auto_send_info"]["abort_reason"])

    def test_web_fallback_never_auto_sends(self):
        # Path 2 (wa.me) nunca auto-envia, aunque auto_send=true.
        executor = self._mock_executor_focus_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": None, "launch_target": None}), \
             patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+1 555 123 4567",
                 "text": "hi", "auto_send": True},
                self.state, executor=executor,
            )
        self.assertEqual(r["provider"], "whatsapp_web")
        self.assertFalse(r["sent"])
        # Executor NO debe haber sido llamado para auto-send en web path.
        executor.assert_not_called()


class TestWhatsappGuiSearch(unittest.TestCase):
    """GUI search path: cuando el contacto NO esta en el store local pero SI
    existe en el WhatsApp del user (Meta tiene los contactos sincronizados
    desde el telefono).
    """

    def setUp(self):
        self.state = _fresh_state()
        self._sleep = patch("time.sleep")
        self._sleep.start()

    def tearDown(self):
        self._sleep.stop()

    def _mock_executor_ok(self):
        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "WhatsApp"}}
            if name == "gui":
                return {"ok": True}
            return {"ok": False}
        return MagicMock(side_effect=_exec)

    def test_gui_search_end_to_end_sends(self):
        executor = self._mock_executor_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "contact": "Amor", "text": "te amo"},
                self.state, executor=executor,
            )
        self.assertTrue(r["ok"])
        self.assertTrue(r["sent"], f"expected sent=True, got {r}")
        self.assertEqual(r["provider"], "whatsapp_desktop_gui_search")
        self.assertEqual(r["recipient_source"], "gui_search")
        # Steps esperados: dispatch + focus + ctrl+f + type name + enter + type msg + enter.
        steps = r["gui_search_info"]["steps"]
        self.assertIn("dispatched_deeplink", steps)
        self.assertIn("opened_search", steps)
        self.assertIn("typed_contact_name", steps)
        self.assertIn("selected_first_match", steps)
        self.assertIn("typed_message", steps)
        self.assertIn("sent_enter", steps)

    def test_gui_search_aborts_when_focus_lost(self):
        # Si la ventana activa cambia mid-flow, abort sin completar.
        call_count = [0]
        def _exec(name, args):
            call_count[0] += 1
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                # Primera vez WhatsApp, despues VS Code (user cambia).
                if call_count[0] <= 2:
                    return {"ok": True, "active": {"title": "WhatsApp"}}
                return {"ok": True, "active": {"title": "VS Code - main.py"}}
            return {"ok": True}
        executor = MagicMock(side_effect=_exec)
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "contact": "Amor", "text": "rm -rf /"},
                self.state, executor=executor,
            )
        self.assertFalse(r["sent"])
        self.assertIn("focus", r["gui_search_info"]["abort_reason"].lower())

    def test_gui_search_auto_send_false_stops_after_message(self):
        executor = self._mock_executor_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = whatsapp_tool(
                {"action": "send_message", "contact": "Amor", "text": "hola",
                 "auto_send": False},
                self.state, executor=executor,
            )
        self.assertFalse(r["sent"])
        self.assertTrue(r["chat_opened"])
        steps = r["gui_search_info"]["steps"]
        self.assertIn("typed_message", steps)
        self.assertNotIn("sent_enter", steps)

    def test_gui_search_requires_executor(self):
        # Sin executor -> error informativo, no crash.
        r = whatsapp_tool(
            {"action": "send_message", "contact": "Amor", "text": "hi"},
            self.state, executor=None,
        )
        self.assertFalse(r["ok"])
        self.assertIn("gui search", r["error"].lower())

    def test_gui_search_no_whatsapp_app_returns_error(self):
        executor = self._mock_executor_ok()
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": None, "launch_target": None}):
            r = whatsapp_tool(
                {"action": "send_message", "contact": "Amor", "text": "hi"},
                self.state, executor=executor,
            )
        self.assertFalse(r["ok"])
        self.assertIn("not installed", r["error"].lower())


class TestSpotifyAutoPlay(unittest.TestCase):

    def setUp(self):
        self._sleep = patch("time.sleep")
        self._sleep.start()

    def tearDown(self):
        self._sleep.stop()

    def _mock_executor_spotify_ok(self):
        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "Spotify Premium"}}
            if name == "gui" and args.get("action") == "keypress":
                return {"ok": True}
            return {"ok": False}
        return MagicMock(side_effect=_exec)

    def test_spotify_auto_plays_first_result(self):
        from .domain_tools import media_tool
        executor = self._mock_executor_spotify_ok()
        with patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": "exe", "launch_target": "C:/spotify.exe"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = media_tool(
                {"action": "play", "provider": "spotify", "query": "benson boone"},
                executor,
            )
        self.assertTrue(r["ok"])
        self.assertTrue(r["played"], f"expected played=True, got {r}")
        self.assertEqual(r["completion_status"], "media_playing")
        # Executor llamado al menos 3 veces: focus, active, keypress.
        self.assertGreaterEqual(executor.call_count, 3)

    def test_spotify_auto_play_aborts_on_wrong_window(self):
        from .domain_tools import media_tool
        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "VS Code"}}
            return {"ok": True}
        executor = MagicMock(side_effect=_exec)
        with patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": "exe", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = media_tool(
                {"action": "play", "provider": "spotify", "query": "test"},
                executor,
            )
        self.assertFalse(r["played"])
        self.assertIn("not Spotify", r["auto_play_info"]["abort_reason"])
        # Y NUNCA debe haber llamado keypress.
        kp_calls = [c for c in executor.call_args_list
                    if c.args[0] == "gui" and c.args[1].get("action") == "keypress"]
        self.assertEqual(len(kp_calls), 0)

    def test_spotify_auto_play_false_skips_keypress(self):
        from .domain_tools import media_tool
        executor = self._mock_executor_spotify_ok()
        with patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": "exe", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"):
            r = media_tool(
                {"action": "play", "provider": "spotify", "query": "x",
                 "auto_play": False},
                executor,
            )
        self.assertFalse(r["played"])
        # Sin auto_play, executor NO debe llamarse (no focus/keypress).
        executor.assert_not_called()

    def test_netflix_does_not_auto_play(self):
        # Netflix no soporta auto_play (Enter en search ambiguo).
        from .domain_tools import media_tool
        executor = self._mock_executor_spotify_ok()
        with patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": None, "launch_target": None}), \
             patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "stranger things"},
                executor,
            )
        # Netflix sin app -> web. No tiene played (no auto_play path).
        self.assertTrue(r["ok"])
        self.assertNotIn("played", r)


if __name__ == "__main__":
    unittest.main()
