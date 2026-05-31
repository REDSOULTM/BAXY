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


if __name__ == "__main__":
    unittest.main()
