"""Honestidad de los early_reply de ACCIÓN (Ola 1, 2026-06-01).

BUG (MEDIDO en vivo contra el 4B real, confirmado pre-existente en d9f776b):
los short-circuits de acción de `_decide_turn` (calc_action / app_action /
app_open) devuelven `TurnDecision(early_reply=AgentReply(content=...))`
SALTÁNDOSE `_finalize_turn` — y con él `guard_unverified_final`, el guard que
reescribe replies que afirman éxito cuando el tool NO confirmó
(`verified=False/None`, `status=attempted/needs_verification`). Resultado: el
tool reportaba honesto pero el reply al usuario MENTÍA ("Hecho." / "Listo,
abrí X").

GATE: 0 replies que afirmen éxito cuando el tool cae bajo el guard de
no-confirmación. El camino feliz (verified=True) NO se toca. `status=dispatched`
(launch_requested) queda FUERA del gate por diseño ("lo despaché" es honesto —
la app puede seguir cargando; ver test_app_open_honesty.py).

FIX (estructural, no listas de frases): `agent_guards.honest_action_reply`
aplica el MISMO `guard_unverified_final` al content del early_reply usando sus
tool_events. Una sola fuente de verdad para las exenciones.

Mock-only: NO LLM, NO GUI/SendInput (t_computer_use / execute mockeados).
"""
from __future__ import annotations

import re
import unittest
from unittest import mock

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.agent_core.agent import Gemma4Agent, AgentReply, ToolEvent
from gemma4_agent.agent_core import agent_guards


# La FORMA de la honestidad: el guard agrega una nota de "sin evidencia".
_HONEST_NOTE = re.compile(
    r"(no dej[oó] evidencia|no pude|no se pudo|no confirm|verifi)", re.IGNORECASE)


def _agent():
    return Gemma4Agent(AgentConfig.from_env())


class HonestActionReplyUnitTest(unittest.TestCase):
    """El helper compartido reescribe SOLO los casos bajo el guard."""

    def _reply(self, result):
        return AgentReply(
            content="Hecho.",
            tool_events=[ToolEvent(name="computer_use", args={}, result=result)])

    def test_unverified_false_gets_honest_note(self):
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": False, "status": "attempted"}))
        self.assertTrue(_HONEST_NOTE.search(r.content), r.content)

    def test_none_needs_verification_gets_honest_note(self):
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": None, "status": "needs_verification"}))
        self.assertTrue(_HONEST_NOTE.search(r.content), r.content)

    def test_verified_true_is_untouched(self):
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": True, "status": "done"}))
        self.assertEqual(r.content, "Hecho.")

    def test_dispatched_is_untouched(self):
        # launch despachado: "lo despaché" es honesto -> el guard lo exime.
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": None, "status": "dispatched",
             "completion_status": "launch_requested"}))
        self.assertEqual(r.content, "Hecho.")

    def test_no_tool_events_is_untouched(self):
        # un early_reply que NO es de acción (jarvis/profile/arithmetic) no se toca.
        r = agent_guards.honest_action_reply(AgentReply(content="Es 4.", tool_events=[]))
        self.assertEqual(r.content, "Es 4.")


class CalcActionEarlyReplyHonestyTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def _decide(self, text, tool_result):
        with mock.patch.object(self.ag.tools, "t_computer_use",
                               return_value=tool_result):
            return self.ag._decide_turn(text)

    def test_unverified_calc_does_not_claim_success(self):
        dec = self._decide("Suma 2 más 2 en la Calculadora",
                           {"ok": True, "verified": False, "status": "attempted",
                            "reply": "Hecho."})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_HONEST_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)

    def test_verified_calc_still_claims_success(self):
        dec = self._decide("Suma 2 más 2 en la Calculadora",
                           {"ok": True, "verified": True, "status": "done",
                            "reply": "Listo, lo hice en la calculadora."})
        self.assertIsNotNone(dec.early_reply)
        self.assertEqual(dec.early_reply.content, "Listo, lo hice en la calculadora.")
        self.assertFalse(_HONEST_NOTE.search(dec.early_reply.content))


class AppActionEarlyReplyHonestyTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def _decide(self, text, tool_result):
        # app_action puede llamar t_computer_use (plan con steps) o execute
        # (goal-only/screen). Mockeamos AMBOS para cubrir cualquier camino.
        with mock.patch.object(self.ag.tools, "t_computer_use",
                               return_value=tool_result), \
             mock.patch.object(self.ag.tools, "execute",
                               return_value=tool_result):
            return self.ag._decide_turn(text)

    def test_unverified_discord_control_is_honest(self):
        # "en Discord apretá silenciar" -> verified=False -> NO "Hecho." pelado.
        dec = self._decide("en Discord apretá silenciar",
                           {"ok": True, "verified": False, "status": "attempted",
                            "reply": "Hecho."})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_HONEST_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)

    def test_unmeasurable_click_is_honest(self):
        dec = self._decide("en Discord apretá silenciar",
                           {"ok": True, "verified": None,
                            "status": "needs_verification", "reply": "Listo."})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_HONEST_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)

    def test_verified_action_still_claims_success(self):
        dec = self._decide("en Discord apretá silenciar",
                           {"ok": True, "verified": True, "status": "done",
                            "reply": "Listo, silencié en Discord."})
        self.assertIsNotNone(dec.early_reply)
        self.assertEqual(dec.early_reply.content, "Listo, silencié en Discord.")
        self.assertFalse(_HONEST_NOTE.search(dec.early_reply.content))


class AppOpenEarlyReplyHonestyTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def _decide(self, text, tool_result):
        with mock.patch.object(self.ag.tools, "execute",
                               return_value=tool_result):
            return self.ag._decide_turn(text)

    def test_verified_false_open_is_honest(self):
        # app.open con verified=False explícito (en el gate) -> nota honesta.
        dec = self._decide("abrí Discord",
                           {"ok": True, "verified": False, "status": "attempted",
                            "name": "Discord"})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_HONEST_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)

    def test_dispatched_open_keeps_listo(self):
        # launch despachado (verified=None, status=dispatched) -> "Listo, abrí X"
        # se mantiene (FUERA del gate: la app puede seguir cargando).
        dec = self._decide("abrí Discord",
                           {"ok": True, "verified": None, "status": "dispatched",
                            "completion_status": "launch_requested",
                            "name": "Discord"})
        self.assertIsNotNone(dec.early_reply)
        self.assertIn("Discord", dec.early_reply.content)
        self.assertFalse(_HONEST_NOTE.search(dec.early_reply.content),
                         dec.early_reply.content)

    def test_verified_open_keeps_listo(self):
        dec = self._decide("abrí Discord",
                           {"ok": True, "verified": True, "status": "done",
                            "completion_status": "launch_verified",
                            "name": "Discord"})
        self.assertIsNotNone(dec.early_reply)
        self.assertIn("Discord", dec.early_reply.content)
        self.assertFalse(_HONEST_NOTE.search(dec.early_reply.content))


if __name__ == "__main__":
    unittest.main()
