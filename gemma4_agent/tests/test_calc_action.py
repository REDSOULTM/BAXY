"""Routing del CALC-EN-APP (2026-05-31).

MEDIDO en vivo: "Suma 2 más 2 en la Calculadora" -> el 4B hacía `gui.type("2+2")` SIN
enfocar la Calc -> el sendinput iba a la ventana equivocada (ok:True igual) -> el
verifier no encontraba "2+2" ("type failed: ?") -> el agente REINTENTABA idéntico 4
veces ("4 no confirmadas" + 18s). Fix: short-circuit determinista en _decide_turn que
arma el plan [focus_app(calc), type(expr), keypress(enter)] -> abre/enfoca ANTES de
tipear, el type aterriza y el verifier confirma.

Mock-only: NO LLM, NO GUI/SendInput. Mockeamos tools.t_computer_use para capturar el
plan SIN ejecutar input físico (que cerraría VS Code).
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.agent_core.agent import Gemma4Agent


def _agent():
    return Gemma4Agent(AgentConfig.from_env())


class CalcActionRoutingTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def _decide(self, text):
        """Llama _decide_turn con t_computer_use mockeado; devuelve (decision, mock)."""
        with mock.patch.object(
            self.ag.tools, "t_computer_use",
            return_value={"ok": True, "reply": "Listo, lo hice en la calculadora."},
        ) as m:
            dec = self.ag._decide_turn(text)
        return dec, m

    def test_routes_to_computer_use_with_focus_type_enter(self):
        for text in ("Suma 2 más 2 en la Calculadora",
                     "Suma dos más dos en la Calculadora",
                     "gemma Suma 2 más 2 en la Calculadora"):
            dec, m = self._decide(text)
            m.assert_called_once()
            steps = m.call_args.args[0]["steps"]
            ops = [(s["op"], s["arg"]) for s in steps]
            self.assertEqual(ops, [("focus_app", "calc"),
                                   ("type", "2+2"),
                                   ("keypress", "enter")], msg=text)
            # devuelve early_reply (no pasa por el LLM)
            self.assertIsNotNone(dec.early_reply, msg=text)

    def test_other_expression_and_operator(self):
        dec, m = self._decide("multiplicá 6 por 7 en la calc")
        m.assert_called_once()
        steps = m.call_args.args[0]["steps"]
        self.assertEqual(steps[1], {"op": "type", "arg": "6*7"})

    def test_does_not_fire_without_arithmetic(self):
        # "abrí la calculadora" (sin operación) NO debe disparar el plan de tipeo.
        _dec, m = self._decide("abrí la calculadora")
        m.assert_not_called()

    def test_pure_arithmetic_still_answers_inline(self):
        # "cuánto es 2+2" (sin app) sigue contestando "Es 4" (aritmética), NO abre Calc.
        dec, m = self._decide("cuánto es 2 más 2")
        m.assert_not_called()
        self.assertIsNotNone(dec.early_reply)
        self.assertIn("4", dec.early_reply.content)

    def test_gate_disables_shortcircuit(self):
        os.environ["GEMMA4_CALC_ACTION"] = "0"
        try:
            _dec, m = self._decide("Suma 2 más 2 en la Calculadora")
            m.assert_not_called()
        finally:
            os.environ.pop("GEMMA4_CALC_ACTION", None)


if __name__ == "__main__":
    unittest.main()
