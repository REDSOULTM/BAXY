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

    def test_contact_without_phone_fails_with_useful_message(self):
        r = whatsapp_tool(
            {"action": "send_message", "contact": "Maria", "text": "hola"},
            self.state,
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertIn("no phone", r["error"].lower())

    def test_unknown_contact_fails(self):
        r = whatsapp_tool(
            {"action": "send_message", "contact": "Persona Inexistente", "text": "hola"},
            self.state,
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertIn("no contact found", r["error"].lower())

    def test_resolve_recipient_helper_returns_tuple(self):
        result = _resolve_whatsapp_recipient(
            {"contact": "Juan"}, self.state,
        )
        self.assertIsInstance(result, tuple)
        raw, normalized, source = result
        self.assertEqual(normalized, "5491187654321")
        self.assertTrue(source.startswith("contact:"))


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


if __name__ == "__main__":
    unittest.main()
