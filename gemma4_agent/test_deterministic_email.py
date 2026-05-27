"""Email para usuario sin manos (2026-05-27). MEDIDO en vivo: el 4B SÍ emite el
tool-call de `email` de forma fiable (3/3). El fix correcto es a NIVEL DE TOOL:
sin Graph token, `email send` arma y abre el REDACTOR web pre-rellenado (Gmail
compose URL) con la sesión logueada — sin enviar; el usuario confirma. La red
determinista (_deterministic_email) queda como BACKSTOP (4B no llama la tool) y
delega en la MISMA tool (una sola fuente de verdad para la URL). Mock-only.
"""
from __future__ import annotations

import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from gemma4_agent.agent import Gemma4Agent, ToolEvent
from gemma4_agent.config import AgentConfig
from gemma4_agent.ops_tools import email_tool
from gemma4_agent.state import AgentState


class ExtractEmailFieldsTest(unittest.TestCase):
    def test_email_address_and_body(self):
        f = Gemma4Agent._extract_email_fields(
            "mandale un correo a ana@gmail.com diciendo que llego tarde")
        self.assertEqual(f["to"], "ana@gmail.com")
        self.assertEqual(f["body"], "llego tarde")

    def test_name_recipient_stops_at_connector(self):
        f = Gemma4Agent._extract_email_fields(
            "escribile un email a juan con el asunto reunion diciendo nos vemos")
        self.assertEqual(f["to"], "juan")
        self.assertEqual(f["subject"], "reunion")
        self.assertEqual(f["body"], "nos vemos")

    def test_full_name(self):
        f = Gemma4Agent._extract_email_fields("escribi un correo a Pedro Gomez diciendo gracias")
        self.assertEqual(f["to"], "Pedro Gomez")

    def test_no_recipient_returns_none(self):
        self.assertIsNone(Gemma4Agent._extract_email_fields("escribi un correo"))
        self.assertIsNone(Gemma4Agent._extract_email_fields("mandar un email"))


class DeterministicEmailTest(unittest.TestCase):
    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def _patch_intent(self, val):
        return mock.patch("gemma4_agent.intent_router.wants_send_email", return_value=val)

    def test_delegates_to_email_tool_compose(self):
        # La red de seguridad delega en la MISMA tool `email` (action=send), que
        # sin token arma+abre la compose URL. Una sola fuente de verdad.
        captured = {}

        def _fake_execute(name, args):
            captured["name"] = name
            captured["args"] = args
            return {"ok": True, "fallback": "gmail_web_compose",
                    "compose_url": "https://mail.google.com/mail/?view=cm&fs=1&to=ana%40gmail.com&body=llego%20tarde",
                    "completion_status": "email_compose_url", "sent": False}

        with self._patch_intent(True), \
             mock.patch.object(self.ag.tools, "execute", side_effect=_fake_execute):
            ev = self.ag._deterministic_email(
                "mandale un correo a ana@gmail.com diciendo que llego tarde")
        self.assertIsInstance(ev, ToolEvent)
        self.assertEqual(ev.name, "email")
        # delega en la tool email con action=send y el destinatario extraído
        self.assertEqual(captured["name"], "email")
        self.assertEqual(captured["args"]["action"], "send")
        self.assertEqual(captured["args"]["to"], "ana@gmail.com")
        self.assertEqual(captured["args"]["body"], "llego tarde")
        # NO envía: la tool, sin token, abre el redactor (envío lo confirma user).
        self.assertEqual(ev.result.get("completion_status"), "email_compose_url")
        self.assertFalse(ev.result.get("sent"))

    def test_no_email_intent_returns_none(self):
        with self._patch_intent(False), mock.patch.object(self.ag.tools, "execute") as ex:
            ev = self.ag._deterministic_email("mandale un mensaje a juan por whatsapp")
        self.assertIsNone(ev)
        ex.assert_not_called()

    def test_email_intent_without_recipient_returns_none(self):
        with self._patch_intent(True), mock.patch.object(self.ag.tools, "execute") as ex:
            ev = self.ag._deterministic_email("quiero escribir un correo")
        self.assertIsNone(ev)
        ex.assert_not_called()


class EmailToolNoTokenFallbackTest(unittest.TestCase):
    """FIX REAL: email_tool send sin Graph token NO falla — arma la compose URL
    de Gmail y señala el fallback para que t_email abra el redactor."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self._td = tempfile.mkdtemp()
        self.state = AgentState(Path(self._td) / "state.json")

    def _no_token(self):
        # asegurar que NO hay token en el entorno durante el test
        return mock.patch.dict("os.environ",
                               {"GEMMA4_GRAPH_TOKEN": "", "MS_GRAPH_TOKEN": ""},
                               clear=False)

    def test_send_without_token_builds_compose_url(self):
        with self._no_token():
            res = email_tool({"action": "send", "to": "ana@gmail.com",
                              "subject": "hola", "body": "llego tarde"}, self.state)
        self.assertTrue(res["ok"])
        self.assertEqual(res["fallback"], "gmail_web_compose")
        self.assertFalse(res["sent"])
        url = res["compose_url"]
        q = parse_qs(urlparse(url).query)
        self.assertIn("mail.google.com", url)
        self.assertEqual(q.get("to"), ["ana@gmail.com"])
        self.assertEqual(q.get("su"), ["hola"])
        self.assertEqual(q.get("body"), ["llego tarde"])

    def test_send_without_token_requires_recipient(self):
        with self._no_token():
            res = email_tool({"action": "send", "subject": "x"}, self.state)
        self.assertFalse(res.get("ok", False))
        self.assertEqual(res.get("status"), "needs_user")

    def test_send_without_token_accepts_bare_name(self):
        # un NOMBRE pelado NO se rechaza (el redactor no envía; Gmail resuelve el
        # contacto y el usuario confirma). Abre la compose con recipient_resolved=False.
        with self._no_token():
            res = email_tool({"action": "send", "to": "juan", "body": "hola"}, self.state)
        self.assertTrue(res["ok"])
        self.assertEqual(res["fallback"], "gmail_web_compose")
        self.assertFalse(res["recipient_resolved"])
        self.assertFalse(res["sent"])
        self.assertIn("to=juan", res["compose_url"])

    def test_send_without_token_marks_email_resolved(self):
        with self._no_token():
            res = email_tool({"action": "send", "to": "ana@gmail.com"}, self.state)
        self.assertTrue(res["recipient_resolved"])

    def test_t_email_opens_compose_via_browser(self):
        # t_email (que SÍ tiene el browser) abre la compose URL del fallback.
        from gemma4_agent.config import AgentConfig as _Cfg
        ag = Gemma4Agent(_Cfg.from_env())
        opened = {}

        def _stub_open(args):
            opened["url"] = args.get("url")
            return {"ok": True, "url": args.get("url"), "opened": True}

        ag.tools.web_open_url = _stub_open  # type: ignore[assignment]
        with self._no_token():
            res = ag.tools.t_email({"action": "send", "to": "ana@gmail.com",
                                    "body": "hola"})
        self.assertTrue(res["ok"])
        self.assertTrue(res.get("opened_compose"))
        self.assertIn("mail.google.com", opened["url"])
        self.assertIn("ana%40gmail.com", opened["url"])


if __name__ == "__main__":
    unittest.main()
