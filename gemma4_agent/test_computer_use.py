"""Tests de la capa UNIVERSAL de computer-use (computer_use.py).

Rediseño 2026-05-25: NO un macro por intención, sino el 4B emite un PLAN de
primitivas y UN ejecutor las corre. Estos tests cubren el parseo del plan
(vocabulario cerrado) y el dispatch del ejecutor (con tools mockeadas, sin GUI).
La validación e2e real (calc/browser/chat/notepad 16/16) está en
scripts/_measure_cu_optionA.py."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gemma4_agent.computer_use import (
    parse_plan, PRIMITIVES, summarize_result, PlanExecutor,
)


class ParsePlanTest(unittest.TestCase):
    def test_parses_clean_json(self):
        t = '[{"op":"focus_app","arg":"discord"},{"op":"open_chat","arg":"juan"}]'
        self.assertEqual(parse_plan(t),
                         [{"op": "focus_app", "arg": "discord"},
                          {"op": "open_chat", "arg": "juan"}])

    def test_tolerates_markdown_fences_and_prose(self):
        t = "Claro, aquí tenés:\n```json\n[{\"op\":\"type\",\"arg\":\"2+2\"}]\n```\nlisto"
        self.assertEqual(parse_plan(t), [{"op": "type", "arg": "2+2"}])

    def test_rejects_unknown_primitive(self):
        # vocabulario CERRADO: un op fuera de PRIMITIVES invalida el plan.
        self.assertIsNone(parse_plan('[{"op":"hack_nasa","arg":"x"}]'))

    def test_rejects_non_list(self):
        self.assertIsNone(parse_plan('{"op":"type","arg":"x"}'))
        self.assertIsNone(parse_plan("no hay json acá"))
        self.assertIsNone(parse_plan(""))

    def test_all_primitives_accepted(self):
        for p in PRIMITIVES:
            self.assertEqual(parse_plan(f'[{{"op":"{p}","arg":""}}]'),
                             [{"op": p, "arg": ""}])


class SummarizeResultTest(unittest.TestCase):
    def test_message_sent(self):
        plan = [{"op": "focus_app", "arg": "discord"}, {"op": "open_chat", "arg": "juan"},
                {"op": "type", "arg": "hola"}, {"op": "send", "arg": ""}]
        res = {"ok": True, "steps": plan, "focused_app": "Discord"}
        self.assertIn("juan", summarize_result("x", plan, res))
        self.assertIn("hola", summarize_result("x", plan, res))

    def test_failure_is_honest(self):
        plan = [{"op": "focus_app", "arg": "discord"}, {"op": "open_chat", "arg": "zzz"}]
        res = {"ok": False, "failed_at": "open_chat",
               "steps": [{"op": "focus_app", "arg": "discord", "ok": True},
                         {"op": "open_chat", "arg": "zzz", "ok": False}],
               "focused_app": "Discord"}
        msg = summarize_result("x", plan, res)
        self.assertIn("zzz", msg)
        self.assertTrue("No encontré" in msg or "no pude" in msg.lower())


class OpenUrlVerifyTest(unittest.TestCase):
    """El verify de open_url normaliza (quita espacios/puntuación) en AMBOS lados:
    el título "espacia" el dominio ("stackoverflow"->"Stack Overflow") y el match
    contiguo daba falso-negativo (bug medido en la maratón 2026-05-25)."""

    def _run(self, url, fg_title):
        import gemma4_agent.computer_use as cu
        from unittest.mock import patch
        ag = MagicMock()
        ag._app_window_title.return_value = ""
        ag.tools._focus_window_chen.return_value = True
        ag.tools.execute.return_value = {"ok": True}
        ex = cu.PlanExecutor(ag)
        with patch.object(cu, "_foreground_title", return_value=fg_title):
            return ex._open_url(url, "opera")

    def test_spaced_domain_title_matches(self):
        self.assertTrue(self._run("stackoverflow.com", "Newest Questions - Stack Overflow - Opera")["ok"])
        self.assertTrue(self._run("duckduckgo.com", "DuckDuckGo — Privacy - Opera")["ok"])

    def test_plain_domain_title_matches(self):
        self.assertTrue(self._run("python.org", "Welcome to Python.org - Opera")["ok"])

    def test_wrong_page_does_not_match(self):
        self.assertFalse(self._run("github.com", "Welcome to Python.org - Opera")["ok"])


class OpenChatFuzzyTest(unittest.TestCase):
    """open_chat es tolerante a typos: el quick-switcher de las apps de chat hace
    fuzzy match ("shotercock"->"ShooterCOCK"). Si el título CAMBIÓ a un chat nuevo,
    es éxito y se reporta el chat REAL abierto (no el typo). Bug medido 2026-05-25:
    el usuario veía "No encontré" de un éxito real."""

    def _exec(self, before_title, after_title):
        from gemma4_agent.computer_use import PlanExecutor
        ag = MagicMock()
        # _app_window_title devuelve before en la 1ª llamada, after en la 2ª.
        ag._app_window_title.side_effect = [before_title, after_title]
        ag._title_now_matches.return_value = False  # no match exacto del typo
        ex = PlanExecutor(ag)
        return ex._open_chat("shotercock", "Discord")

    def test_fuzzy_navigation_is_success_and_reports_real_name(self):
        r = self._exec("@CbaYeah - Discord", "@ShooterCOCK - Discord")
        self.assertTrue(r["ok"])
        self.assertTrue(r["fuzzy"])
        self.assertEqual(r["opened"], "ShooterCOCK")  # nombre REAL, no el typo

    def test_no_navigation_is_failure(self):
        # el título NO cambió -> no navegó -> fallo honesto.
        r = self._exec("@CbaYeah - Discord", "@CbaYeah - Discord")
        self.assertFalse(r["ok"])


class ExecutorDispatchTest(unittest.TestCase):
    """El ejecutor llama las primitivas correctas. Mockeamos el agente/tools para
    no tocar la GUI; verificamos QUÉ tool-calls emite por cada op."""

    def _agent(self):
        ag = MagicMock()
        ag._window_title_in_text.return_value = "Calculadora"
        ag._app_window_title.return_value = "Calculadora"
        ag.tools._focus_window_chen.return_value = True
        ag.tools.execute.return_value = {"ok": True}
        return ag

    def test_type_keypress_dispatch(self):
        ag = self._agent()
        ex = PlanExecutor(ag)
        plan = [{"op": "focus_app", "arg": "Calculadora"},
                {"op": "type", "arg": "2+2"}, {"op": "keypress", "arg": "enter"}]
        res = ex.execute(plan, "t")
        self.assertTrue(res["ok"])
        # debe haberse llamado gui type con "2+2" y keypress enter
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertTrue(any(a[0] == "gui" and a[1].get("text") == "2+2" for a in calls))
        self.assertTrue(any(a[0] == "gui" and a[1].get("keys") == "enter" for a in calls))

    def test_nav_failure_stops_chain(self):
        # si open_chat falla (título no matchea), el ejecutor corta y NO teclea.
        ag = self._agent()
        ag._title_now_matches.return_value = False  # open_chat no confirma
        ex = PlanExecutor(ag)
        plan = [{"op": "focus_app", "arg": "discord"},
                {"op": "open_chat", "arg": "zzz"},
                {"op": "type", "arg": "hola"}]
        res = ex.execute(plan, "t")
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed_at"], "open_chat")
        # NO debe haber tecleado "hola" tras el fallo de navegación.
        calls = [c.args for c in ag.tools.execute.call_args_list]
        self.assertFalse(any(len(a) > 1 and a[1].get("text") == "hola" for a in calls))


if __name__ == "__main__":
    unittest.main()
