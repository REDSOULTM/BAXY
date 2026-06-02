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
# (Genérica: matchea CUALQUIERA de las dos redacciones honestas.)
_HONEST_NOTE = re.compile(
    r"(no dej[oó] evidencia|no pude|no se pudo|no confirm|verifi)", re.IGNORECASE)

# TRI-ESTADO (2026-06-01): dos redacciones DISTINTAS según se haya MEDIDO o no.
# Antes este archivo usaba SOLO _HONEST_NOTE (laxo), que dejaba pasar la nota
# de FALLO ("no dejó evidencia suficiente de finalización") incluso para casos
# NO-MEDIBLES (verified=None) — violando la regla del usuario: "si no se pudo
# medir, decí 'lo hice, no pude confirmar el efecto', NO afirmar que falló".
# Endurecemos: el caso None exige la redacción SUAVE y PROHÍBE la de fallo.
_FAIL_NOTE = re.compile(r"no dej[oó] evidencia suficiente", re.IGNORECASE)
_UNMEASURED_NOTE = re.compile(r"no pude confirmar el efecto", re.IGNORECASE)


def _agent():
    return Gemma4Agent(AgentConfig.from_env())


class HonestActionReplyUnitTest(unittest.TestCase):
    """El helper compartido reescribe SOLO los casos bajo el guard."""

    def _reply(self, result):
        return AgentReply(
            content="Hecho.",
            tool_events=[ToolEvent(name="computer_use", args={}, result=result)])

    def test_unverified_false_gets_fail_note(self):
        # verified=False top-level SIN steps = fallo medido (la tool lo midió y
        # reportó False directo) -> nota DURA de no-confirmación.
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": False, "status": "attempted"}))
        self.assertTrue(_FAIL_NOTE.search(r.content), r.content)
        self.assertFalse(_UNMEASURED_NOTE.search(r.content), r.content)

    def test_none_needs_verification_gets_soft_note(self):
        # ENDURECIDO (2026-06-01): verified=None sin señal de fallo dura = NO
        # MEDIBLE. Debe recibir la redacción SUAVE ("no pude confirmar el
        # efecto"), NO la de fallo ("no dejó evidencia suficiente"). El criterio
        # viejo (regex laxo) dejaba pasar la nota de fallo aquí — eso mentía:
        # implicaba que la acción había fallado cuando solo no se pudo medir.
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": None, "status": "needs_verification"}))
        self.assertTrue(_UNMEASURED_NOTE.search(r.content), r.content)
        self.assertFalse(_FAIL_NOTE.search(r.content), r.content)

    def test_collapsed_topfalse_but_steps_none_is_soft(self):
        # CAMINO DE PRODUCCIÓN REAL: t_computer_use COLAPSA verified=None->False
        # al top-level (PlanExecutor.execute L1283 + tools.py L2432), pero la
        # verdad tri-estado SOBREVIVE en steps[*]. El guard debe leer steps y
        # dar la nota SUAVE, no la de fallo. (Antes daba la de fallo: mentía.)
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": False, "status": "attempted",
             "completion_status": "attempted",
             "steps": [{"op": "click_button", "verified": None,
                        "state_changed": None}]}))
        self.assertTrue(_UNMEASURED_NOTE.search(r.content), r.content)
        self.assertFalse(_FAIL_NOTE.search(r.content), r.content)

    def test_collapsed_topfalse_with_failed_step_is_fail(self):
        # Mismo colapso top-level, pero un step SÍ midió False -> fallo DURO.
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": True, "verified": False, "status": "attempted",
             "completion_status": "attempted",
             "steps": [{"op": "click_button", "verified": False,
                        "state_changed": False}]}))
        self.assertTrue(_FAIL_NOTE.search(r.content), r.content)
        self.assertFalse(_UNMEASURED_NOTE.search(r.content), r.content)

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

    def test_hard_fail_no_reply_key_does_not_claim_success(self):
        # HUECO ADVERSARIAL (2026-06-01): t_computer_use puede devolver un error
        # DURO ok=False/status=failed SIN clave "reply" (tools.py:2429/2438, p.ej.
        # "no pude planificar la acción"). Antes, el short-circuit caía al texto de
        # ÉXITO HARDCODEADO ("Hecho.") y guard_unverified_final lo EXIMÍA intacto en
        # la rama `status==failed and not ok` -> el reply AFIRMABA ÉXITO en un fallo
        # duro (mentira). El reply final NO debe afirmar éxito: nota DURA.
        r = agent_guards.honest_action_reply(self._reply(
            {"ok": False, "error": "no pude planificar la accion",
             "status": "failed", "goal": "sumar"}))
        self.assertNotEqual(r.content, "Hecho.")
        self.assertTrue(_FAIL_NOTE.search(r.content), r.content)

    def test_hard_fail_already_honest_content_is_untouched(self):
        # CONTRACAUTELA: el ok=False cuyo content YA es honesto (el flujo normal de
        # error ya lo surfaceó) NO se re-anota -> queda intacto (sin doble nota).
        r = agent_guards.honest_action_reply(AgentReply(
            content="No pude planificar la accion.",
            tool_events=[ToolEvent(name="computer_use", args={},
                                   result={"ok": False, "status": "failed",
                                           "error": "x"})]))
        self.assertEqual(r.content, "No pude planificar la accion.")


class CalcActionEarlyReplyHonestyTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def _decide(self, text, tool_result):
        with mock.patch.object(self.ag.tools, "t_computer_use",
                               return_value=tool_result):
            return self.ag._decide_turn(text)

    def test_unverified_calc_does_not_claim_success(self):
        # Camino real: steps no-medibles -> top-level colapsa a verified=False
        # pero steps[*].verified=None. Debe dar la nota SUAVE, no la de fallo.
        dec = self._decide("Suma 2 más 2 en la Calculadora",
                           {"ok": True, "verified": False, "status": "attempted",
                            "completion_status": "attempted",
                            "steps": [{"op": "type", "verified": None,
                                       "state_changed": None}],
                            "reply": "Hecho."})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_UNMEASURED_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)
        self.assertFalse(_FAIL_NOTE.search(dec.early_reply.content),
                         dec.early_reply.content)

    def test_verified_calc_still_claims_success(self):
        dec = self._decide("Suma 2 más 2 en la Calculadora",
                           {"ok": True, "verified": True, "status": "done",
                            "reply": "Listo, lo hice en la calculadora."})
        self.assertIsNotNone(dec.early_reply)
        self.assertEqual(dec.early_reply.content, "Listo, lo hice en la calculadora.")
        self.assertFalse(_HONEST_NOTE.search(dec.early_reply.content))

    def test_hard_fail_no_reply_key_calc_does_not_claim_success(self):
        # CAMINO DE PRODUCCIÓN REAL del hueco: t_computer_use devuelve el error DURO
        # ok=False/status=failed SIN clave "reply" (tools.py:2429 "no pude
        # planificar la acción"). El short-circuit calc cae al texto de ÉXITO
        # hardcodeado "Listo, lo hice en la calculadora." -> el reply final NO debe
        # afirmar éxito (debe llevar la nota DURA de no-confirmación).
        dec = self._decide("Suma 2 más 2 en la Calculadora",
                           {"ok": False, "error": "no pude planificar la accion",
                            "status": "failed", "goal": "suma 2 mas 2"})
        self.assertIsNotNone(dec.early_reply)
        self.assertNotEqual(dec.early_reply.content,
                            "Listo, lo hice en la calculadora.")
        self.assertTrue(_FAIL_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)


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

    def test_measured_failed_discord_control_is_fail_note(self):
        # step que SÍ midió no-cambio (state_changed=False) -> fallo DURO.
        dec = self._decide("en Discord apretá silenciar",
                           {"ok": True, "verified": False, "status": "attempted",
                            "completion_status": "attempted",
                            "steps": [{"op": "click_button", "verified": False,
                                       "state_changed": False}],
                            "reply": "Hecho."})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_FAIL_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)
        self.assertFalse(_UNMEASURED_NOTE.search(dec.early_reply.content),
                         dec.early_reply.content)

    def test_unmeasurable_click_is_soft_note(self):
        # ENDURECIDO (2026-06-01): click NO medible (UIA demorado en Electron/
        # Discord) -> steps[*].verified=None. NO afirma "Hecho." NI "falló":
        # redacción SUAVE "no pude confirmar el efecto". Este es el caso CENTRAL
        # del bug — antes recibía la nota de fallo y sonaba a que no funcionó.
        dec = self._decide("en Discord apretá silenciar",
                           {"ok": True, "verified": False,
                            "status": "attempted", "completion_status": "attempted",
                            "steps": [{"op": "click_button", "verified": None,
                                       "state_changed": None}],
                            "reply": "Listo."})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_UNMEASURED_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)
        self.assertFalse(_FAIL_NOTE.search(dec.early_reply.content),
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

    def test_verified_false_open_is_fail_note(self):
        # app.open con verified=False explícito y SIN steps (la cascada midió
        # ausencia del proceso) = fallo medido -> nota DURA. (Distinto de
        # status=dispatched/verified=None abajo, que mantiene "Listo, abrí X".)
        dec = self._decide("abrí Discord",
                           {"ok": True, "verified": False, "status": "attempted",
                            "name": "Discord"})
        self.assertIsNotNone(dec.early_reply)
        self.assertTrue(_FAIL_NOTE.search(dec.early_reply.content),
                        dec.early_reply.content)
        self.assertFalse(_UNMEASURED_NOTE.search(dec.early_reply.content),
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
