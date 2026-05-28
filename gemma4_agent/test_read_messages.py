"""Leer mensajes en voz para no-vidente (2026-05-27). El tool de WhatsApp solo
ENVÍA; no hay scraping. Lo UNIVERSAL para "leeme el último mensaje / qué me
escribió X" es LEER LA PANTALLA por visión (cualquier chat). t_whatsapp delega
las acciones de lectura a vision.describe_screen con foco en los mensajes.

Mock-only: t_vision mockeado (no captura pantalla real, no llama al modelo).
"""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.config import AgentConfig


class WhatsAppReadDelegatesToVisionTest(unittest.TestCase):
    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())
        self.calls = []
        def _vis(args):
            self.calls.append(dict(args or {}))
            return {"ok": True, "description": "Mamá: ya llegué a casa",
                    "completion_status": "screen_described"}
        self.ag.tools.t_vision = _vis

    def test_read_messages_delegates_to_vision(self):
        for act in ("read", "read_messages", "read_chat", "last_message",
                    "unread", "list_messages", "get_messages"):
            self.calls.clear()
            res = self.ag.tools.t_whatsapp({"action": act})
            self.assertTrue(res["ok"], act)
            self.assertEqual(res.get("description"), "Mamá: ya llegué a casa", act)
            self.assertEqual(len(self.calls), 1, act)
            self.assertEqual(self.calls[0]["action"], "describe_screen", act)
            # el foco debe orientar a leer los mensajes
            self.assertIn("mensaje", self.calls[0].get("target", "").lower(), act)

    def test_send_does_not_delegate_to_vision(self):
        # send_message NO debe ir a visión (es un envío, no una lectura)
        with mock.patch("gemma4_agent.tools.whatsapp_tool",
                        return_value={"ok": True, "sent": True}) as wt:
            res = self.ag.tools.t_whatsapp({"action": "send_message",
                                            "contact": "mama", "text": "ya voy"})
        self.assertEqual(len(self.calls), 0)   # vision NO llamado
        wt.assert_called_once()
        self.assertTrue(res["ok"])

    def test_status_does_not_delegate(self):
        with mock.patch("gemma4_agent.tools.whatsapp_tool",
                        return_value={"ok": True, "installed": True}):
            self.ag.tools.t_whatsapp({"action": "status"})
        self.assertEqual(len(self.calls), 0)


class DeterministicReplyTest(unittest.TestCase):
    """_deterministic_reply: backstop cuando el 4B se niega a responder un mensaje.
    Abre el chat pre-rellenado (auto_send=False); sin destinatario -> None (pide)."""

    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def test_reply_with_recipient_and_body_opens_chat(self):
        captured = {}
        def _exec(name, args):
            captured["name"] = name; captured["args"] = dict(args)
            return {"ok": True, "sent": False, "completion_status": "chat_opened_not_sent"}
        with mock.patch.object(self.ag.tools, "execute", side_effect=_exec):
            ev = self.ag._deterministic_reply("respondele a mama que ya voy")
        self.assertIsNotNone(ev)
        self.assertEqual(ev.name, "whatsapp")
        self.assertEqual(captured["name"], "whatsapp")
        self.assertEqual(captured["args"]["action"], "send_message")
        self.assertEqual(captured["args"]["contact"], "mama")
        self.assertIn("ya voy", captured["args"]["text"])
        # NO auto-envía: el usuario confirma
        self.assertFalse(captured["args"]["auto_send"])
        self.assertEqual(ev.result.get("reply_contact"), "mama")

    def test_reply_handles_en_minutos_not_as_app(self):
        captured = {}
        with mock.patch.object(self.ag.tools, "execute",
                               side_effect=lambda n, a: captured.update(a) or {"ok": True}):
            self.ag._deterministic_reply("contestale a juan que llego en 10 minutos")
        self.assertEqual(captured["contact"], "juan")
        self.assertIn("llego en 10 minutos", captured["text"])

    def test_reply_without_recipient_returns_none(self):
        # "contestale que si" no tiene 'a <X>' -> None (el LLM pregunta a quién)
        with mock.patch.object(self.ag.tools, "execute") as ex:
            ev = self.ag._deterministic_reply("contestale que si")
        self.assertIsNone(ev)
        ex.assert_not_called()

    def test_non_message_returns_none(self):
        with mock.patch.object(self.ag.tools, "execute") as ex:
            for q in ("que hora es", "abre discord", "subi el volumen"):
                self.assertIsNone(self.ag._deterministic_reply(q), q)
        ex.assert_not_called()

    def test_email_intent_not_hijacked_by_reply_net(self):
        # BUG medido: "mandale un correo a ana@gmail.com diciendo X" -> el verbo
        # "mandale" hacía que extract_message_to agarrara "un correo a ana@gmail.com"
        # como contacto -> WhatsApp a contacto basura. La red de mensaje DEBE ceder
        # ante intención de EMAIL.
        with mock.patch.object(self.ag.tools, "execute") as ex:
            for q in ("mandale un correo a ana@gmail.com diciendo que llego tarde",
                      "escribile un email a juan que nos vemos",
                      "envia un mail a pedro@x.com con asunto hola"):
                self.assertIsNone(self.ag._deterministic_reply(q), q)
        ex.assert_not_called()


class ReplyShortCircuitTest(unittest.TestCase):
    """El short-circuit PRE-LLM de run_content: 'respondele a X que Y' (claro)
    dispara el net sin tocar el LLM; sin destinatario o no-mensaje -> NO dispara."""

    def setUp(self):
        self.ag = Gemma4Agent(AgentConfig.from_env())

    def test_clear_reply_shortcircuits_without_llm(self):
        # execute mockeado (no abre WhatsApp); client.chat NO debe llamarse.
        with mock.patch.object(self.ag.tools, "execute",
                               return_value={"ok": True, "sent": False}) as ex, \
             mock.patch.object(self.ag.client, "chat") as chat:
            r = self.ag.run_content("respondele a mama que ya voy")
        # el LLM NO se invocó (short-circuit determinista)
        chat.assert_not_called()
        # se ejecutó whatsapp send_message, auto_send=False (no envía)
        self.assertEqual(ex.call_args.args[0], "whatsapp")
        self.assertEqual(ex.call_args.args[1]["contact"], "mama")
        self.assertFalse(ex.call_args.args[1]["auto_send"])
        self.assertEqual([e.name for e in r.tool_events], ["whatsapp"])

    def test_no_recipient_does_not_shortcircuit(self):
        # "contestale que si" no tiene 'a <X>' -> NO short-circuit (cae al LLM).
        # client.chat se mockea para que el turno termine sin tocar el server real.
        with mock.patch.object(self.ag.client, "chat",
                               return_value={"choices": [{"message": {"content": "¿A quién le contesto?"}}]}) as chat, \
             mock.patch.object(self.ag.tools, "execute") as ex:
            self.ag.run_content("contestale que si")
        chat.assert_called()           # SÍ pasó por el LLM
        # no se ejecutó whatsapp por short-circuit (execute pudo no llamarse o no para whatsapp)
        for call in ex.call_args_list:
            self.assertNotEqual(call.args[0] if call.args else None, "whatsapp")

    def test_env_flag_disables_shortcircuit(self):
        # con el flag off, el short-circuit PRE-LLM NO corre -> el turno SÍ pasa
        # por el LLM. (La red de seguridad in-loop puede seguir cubriendo, pero la
        # decisión deja de ser determinista pre-LLM.)
        with mock.patch.dict("os.environ", {"GEMMA4_REPLY_NET": "0"}), \
             mock.patch.object(self.ag.client, "chat",
                               return_value={"choices": [{"message": {"content": "ok"}}]}) as chat, \
             mock.patch.object(self.ag.tools, "execute",
                               return_value={"ok": True, "sent": False}):
            self.ag.run_content("respondele a mama que ya voy")
        chat.assert_called()  # el flag off => pasó por el LLM (no short-circuit)


if __name__ == "__main__":
    unittest.main()
