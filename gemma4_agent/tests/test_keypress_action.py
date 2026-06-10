"""Routing del KEYPRESS-EN-APP (2026-06-01).

MEDIDO en vivo: "en la calculadora apretá el 5" -> extract_app_action lo detectaba
(pattern=in_app_act, app_hint='la calculadora') pero NO había constructor de plan
determinista para un keypress simple -> el short-circuit armaba cu(goal genérico) -> el
4B planner devolvía "no pude planificar la acción" para un keypress trivial. (En cambio
"abrí la calculadora y apretá el 5" SÍ andaba: toma el patrón nav_action.) Fix:
parse_keypress_action en command_splitter + cableo en _decide_turn que arma el plan
[focus_app(app), keypress(key)] saltando el planner del 4B.

Mock-only: NO LLM, NO GUI/SendInput. Mockeamos tools.t_computer_use para capturar el
plan SIN ejecutar input físico (que afectaría la ventana en foco).
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.agent_core.agent import Gemma4Agent


def _agent():
    return Gemma4Agent(AgentConfig.from_env())


class KeypressActionRoutingTest(unittest.TestCase):
    def setUp(self):
        self.ag = _agent()

    def _decide(self, text):
        """_decide_turn con t_computer_use mockeado; devuelve (decision, mock)."""
        with mock.patch.object(
            self.ag.tools, "t_computer_use",
            return_value={"ok": True, "verified": True, "reply": "Listo."},
        ) as m:
            dec = self.ag._decide_turn(text)
        return dec, m

    def test_in_app_first_builds_focus_keypress(self):
        # "en la calculadora apretá el 5" -> [focus_app(calculadora), keypress(5)].
        # (app_hint 'la calculadora' resuelve via AppResolver -> calc; el caller
        # pela el artículo inicial.)
        dec, m = self._decide("en la calculadora apretá el 5")
        m.assert_called_once()
        steps = m.call_args.args[0]["steps"]
        ops = [(s["op"], s["arg"]) for s in steps]
        self.assertEqual(ops, [("focus_app", "calculadora"), ("keypress", "5")])
        self.assertIsNotNone(dec.early_reply)

    def test_action_first_builds_focus_keypress(self):
        dec, m = self._decide("apretá el 5 en la calculadora")
        m.assert_called_once()
        steps = m.call_args.args[0]["steps"]
        ops = [(s["op"], s["arg"]) for s in steps]
        self.assertEqual(ops, [("focus_app", "calculadora"), ("keypress", "5")])
        self.assertIsNotNone(dec.early_reply)

    def test_named_key_in_known_app(self):
        # "en Discord apretá enter" -> keypress(enter) en Discord.
        dec, m = self._decide("en Discord apretá enter")
        m.assert_called_once()
        steps = m.call_args.args[0]["steps"]
        ops = [(s["op"], s["arg"]) for s in steps]
        self.assertEqual(ops, [("focus_app", "Discord"), ("keypress", "enter")])

    def test_chained_open_then_keypress_still_works(self):
        # "abrí la calculadora y apretá el 5" = patrón nav_action -> goal-only via
        # execute (camino que YA andaba; NO debe romperse ni armar plan keypress acá).
        with mock.patch.object(
            self.ag.tools, "execute",
            return_value={"ok": True, "verified": True, "reply": "Listo."},
        ) as m:
            dec = self.ag._decide_turn("abrí la calculadora y apretá el 5")
        m.assert_called()
        tool, args = m.call_args.args[0], m.call_args.args[1]
        self.assertEqual(tool, "computer_use")
        self.assertNotIn("steps", args)           # goal-only, lo planifica el 4B
        self.assertIsNotNone(dec.early_reply)

    def test_does_not_steal_button_or_media(self):
        # 'apretá enviar' = botón (click_button), 'tocá una canción' = play (media):
        # NO deben armar un plan keypress (key no inequívoca -> parser None).
        for text in ("apretá enviar en WhatsApp", "tocá una canción en Spotify"):
            with mock.patch.object(
                self.ag.tools, "t_computer_use",
                return_value={"ok": True, "reply": "x"},
            ) as m:
                self.ag._decide_turn(text)
            for call in m.call_args_list:
                self.assertNotIn("steps", call.args[0], msg=text)

    def test_gate_disables_shortcircuit(self):
        # GEMMA4_APP_ACTION_NET=0 apaga TODO el short-circuit app-action (incl keypress).
        os.environ["GEMMA4_APP_ACTION_NET"] = "0"
        try:
            _dec, m = self._decide("en la calculadora apretá el 5")
            m.assert_not_called()
        finally:
            os.environ.pop("GEMMA4_APP_ACTION_NET", None)


if __name__ == "__main__":
    unittest.main()
