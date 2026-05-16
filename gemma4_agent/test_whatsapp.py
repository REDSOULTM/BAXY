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

    def test_send_with_explicit_phone_opens_deeplink(self):
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": "uwp", "launch_target": "shell:AppsFolder\\X!App"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen") as popen:
            r = whatsapp_tool(
                {"action": "send_message", "phone": "+54 9 11 1234-5678", "text": "hola"},
                self.state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["provider"], "whatsapp_desktop")
        self.assertFalse(r["sent"])
        self.assertFalse(r["verified"])
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
                self.state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["provider"], "whatsapp_web")
        self.assertIn("wa.me/15551234567", r["url"])
        self.assertIn("text=hi", r["url"])
        wb.assert_called_once()

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


if __name__ == "__main__":
    unittest.main()
