"""Pulido del replay 2026-05-30:
  (1) Net UNIVERSAL de empty-reply: el user NUNCA recibe silencio.
  (2) whatsapp-open: "abre whatsapp" (sin contacto/mensaje) abre la APP, no mensajea.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ..agent_core.agent import AgentReply, Gemma4Agent


class EmptyReplyNet(unittest.TestCase):
    """_ensure_nonempty_reply: fallback honesto context-aware (sin init del agente)."""
    def _fake(self):
        return SimpleNamespace(trace=SimpleNamespace(event=lambda *a, **k: None))

    def _ens(self, reply):
        return Gemma4Agent._ensure_nonempty_reply(self._fake(), reply)

    def test_empty_no_tools_asks_rephrase(self):
        r = self._ens(AgentReply(content="", tool_events=[]))
        self.assertTrue(r.content.strip())
        self.assertIn("reformul", r.content.lower())

    def test_empty_with_tools_confirms(self):
        ev = [SimpleNamespace(name="gui")]
        r = self._ens(AgentReply(content="   ", tool_events=ev))
        self.assertEqual(r.content, "Listo.")

    def test_empty_with_error_says_technical(self):
        r = self._ens(AgentReply(content="", tool_events=[], error="llm_timeout"))
        self.assertTrue(r.content.strip())
        self.assertIn("problema", r.content.lower())

    def test_nonempty_untouched(self):
        r = self._ens(AgentReply(content="Listo, abrí Chrome.", tool_events=[]))
        self.assertEqual(r.content, "Listo, abrí Chrome.")

    def test_none_safe(self):
        self.assertIsNone(self._ens(None))


class WhatsappOpenDelegates(unittest.TestCase):
    """t_whatsapp: abrir la app vs enviar un mensaje."""
    def _reg(self):
        from ..memory_pkg.memory import MemoryStore
        from ..memory_pkg.state import AgentState
        from ..tools_pkg.tools import ToolRegistry
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_wa_"))
        return ToolRegistry(MemoryStore(tmp / "mem.json"), tmp / "captures",
                            state=AgentState(tmp / "data" / "state.json"))

    def test_open_no_recipient_delegates_to_app(self):
        reg = self._reg()
        with mock.patch.object(reg, "t_app", return_value={"ok": True, "opened": "WhatsApp"}) as m:
            res = reg.t_whatsapp({"action": "open"})
        m.assert_called_once()
        self.assertEqual(m.call_args[0][0].get("name"), "WhatsApp")
        self.assertEqual(res.get("delegated_from"), "whatsapp(open-app)")

    def test_bare_no_action_delegates_to_app(self):
        reg = self._reg()
        with mock.patch.object(reg, "t_app", return_value={"ok": True}) as m:
            reg.t_whatsapp({})
        m.assert_called_once()

    def test_send_with_body_does_not_delegate_to_app(self):
        reg = self._reg()
        with mock.patch.object(reg, "t_app") as m_app, \
             mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        return_value={"ok": True}) as m_wa:
            reg.t_whatsapp({"action": "send_message", "contact": "Juan", "text": "hola"})
        m_app.assert_not_called()
        m_wa.assert_called_once()

    def test_status_does_not_delegate(self):
        reg = self._reg()
        with mock.patch.object(reg, "t_app") as m_app, \
             mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        return_value={"ok": True}):
            reg.t_whatsapp({"action": "status"})
        m_app.assert_not_called()


class WhatsappPhoneGrounding(unittest.TestCase):
    """Guarda C1: el 4B NO debe mandar a un teléfono que el user no dictó.

    Caso real (2026-05-30): 'manda un mensaje por wsp' (sin destinatario) -> el 4B
    alucinó phone='+34 123456' -> WhatsApp abrió y mostró 'el número +34 123456 no
    está en WhatsApp'. La guarda mide PROCEDENCIA (¿el user dictó esos dígitos?).
    """
    def _reg(self, user_text=None):
        from ..memory_pkg.memory import MemoryStore
        from ..memory_pkg.state import AgentState
        from ..tools_pkg.tools import ToolRegistry
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_wph_"))
        reg = ToolRegistry(MemoryStore(tmp / "mem.json"), tmp / "captures",
                           state=AgentState(tmp / "data" / "state.json"))
        if user_text is not None:
            reg._current_user_text = user_text
        return reg

    def test_fabricated_phone_no_name_asks(self):
        """Número inventado + sin nombre -> needs_user, NO abre el chat."""
        reg = self._reg(user_text="manda un mensaje por wsp")
        with mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool") as m_wa:
            res = reg.t_whatsapp({"action": "send_message",
                                  "phone": "+34 123456", "text": "x"})
        m_wa.assert_not_called()  # nunca llega al tool real (no deeplink)
        self.assertEqual(res.get("status"), "needs_user")
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("fabricated_phone"), "+34 123456")

    def test_fabricated_phone_with_name_drops_phone(self):
        """Número inventado PERO hay contacto -> suelta el phone, usa el nombre."""
        reg = self._reg(user_text="mandale a juan por wsp que llego")
        with mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        return_value={"ok": True}) as m_wa:
            reg.t_whatsapp({"action": "send_message", "phone": "+34 123456",
                            "contact": "juan", "text": "que llego"})
        m_wa.assert_called_once()
        passed_args = m_wa.call_args[0][0]
        self.assertNotIn("phone", passed_args)   # teléfono fabricado descartado
        self.assertEqual(passed_args.get("contact"), "juan")

    def test_dictated_phone_proceeds(self):
        """El user dictó el número completo -> pasa al tool (procedencia OK)."""
        reg = self._reg(user_text="mandale al +54 9 11 5003 5001 que ya voy")
        with mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        return_value={"ok": True}) as m_wa:
            reg.t_whatsapp({"action": "send_message",
                            "phone": "+54 9 11 5003 5001", "text": "ya voy"})
        m_wa.assert_called_once()
        self.assertIn("phone", m_wa.call_args[0][0])

    def test_dictated_national_4b_adds_country_code_proceeds(self):
        """User dicta el nacional, el 4B completa el código de país -> grounded."""
        reg = self._reg(user_text="mandale al 11 5003 5001 que ya voy")
        with mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        return_value={"ok": True}) as m_wa:
            reg.t_whatsapp({"action": "send_message",
                            "phone": "+54 9 11 5003 5001", "text": "ya voy"})
        m_wa.assert_called_once()  # "1150035001" ⊂ "5491150035001" -> grounded

    def test_no_user_text_is_noop(self):
        """Sin texto del turno plumeado (tests/CLI) -> no falsa-ask, pasa igual."""
        reg = self._reg(user_text=None)  # registry sin _current_user_text
        with mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        return_value={"ok": True}) as m_wa:
            reg.t_whatsapp({"action": "send_message",
                            "phone": "+34 123456", "text": "x"})
        m_wa.assert_called_once()  # comportamiento previo intacto

    def test_contact_only_unaffected(self):
        """send por contacto (sin phone explícito) no toca la guarda."""
        reg = self._reg(user_text="mandale a mama que llego")
        with mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        return_value={"ok": True}) as m_wa:
            reg.t_whatsapp({"action": "send_message",
                            "contact": "mama", "text": "que llego"})
        m_wa.assert_called_once()
        self.assertEqual(m_wa.call_args[0][0].get("contact"), "mama")


if __name__ == "__main__":
    unittest.main()
