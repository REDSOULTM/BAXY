"""Bugs de las capturas 2026-06-09:

(1) "maximiza la aplicación de Steam" -> el router ofrecía steam+window+app; el 4B
    elegía steam(action=maximize), pero `steam` NO tiene 'maximize' (solo open/
    library/store/...) -> fallaba y reintentaba en loop. Fix: detector estructural
    _is_window_geometry_action retira la tool homónima (steam/app) y deja `window`.

(2) "cierra WhatsApp" -> app.close devuelve needs_confirmation (NO cerró nada,
    espera el OK), pero el 4B respondía "Listo, cerré la aplicación WhatsApp" —
    MENTIRA. Fix: el guard ante needs_confirmation, si el reply AFIRMA la acción
    completada, lo reemplaza por la pregunta de confirmación honesta.
"""
from __future__ import annotations

import unittest

from gemma4_agent.routing.planner import _is_window_geometry_action
from gemma4_agent.agent_core.agent_guards import guard_unverified_final


class _Ev:
    def __init__(self, result):
        self.result = result


def _needs_confirm_event():
    return [_Ev({"status": "needs_confirmation", "verified": False, "ok": False})]


class TestWindowGeometryDetector(unittest.TestCase):
    def test_detects_window_geometry_actions(self):
        for q in ("maximiza la aplicación de Steam", "maximiza Steam",
                  "minimiza Discord", "restaurar la ventana de Chrome",
                  "maximize Steam", "minimize the window"):
            self.assertTrue(_is_window_geometry_action(q), f"debió detectar: {q!r}")

    def test_open_close_are_NOT_window_geometry(self):
        # abrir/cerrar son app.open/close legítimos, NO geometría de ventana.
        for q in ("cierra WhatsApp", "abrí Steam", "cerrá Discord", "open Steam"):
            self.assertFalse(_is_window_geometry_action(q), f"NO debió detectar: {q!r}")


class TestCloseAppDetector(unittest.TestCase):
    """mission-eval 2026-06-10: "Ferme Steam"/"Chiudi Steam" -> el 4B elegía la tool
    homónima `steam` (que no cierra). Cerrar es app(close). El detector retira la
    homónima y deja `app`."""

    def test_detects_close_app_multilang(self):
        from gemma4_agent.routing.planner import _is_close_app_action
        for q in ("cierra Steam", "cerrá Discord", "close Steam", "Ferme Steam",
                  "Chiudi Steam", "schließe Steam", "fecha o Steam"):
            self.assertTrue(_is_close_app_action(q), f"debió detectar cerrar: {q!r}")

    def test_open_is_NOT_close(self):
        from gemma4_agent.routing.planner import _is_close_app_action
        for q in ("abrí Steam", "open Steam", "steam library", "maximiza Steam"):
            self.assertFalse(_is_close_app_action(q), f"NO es cerrar: {q!r}")

    def test_close_app_removes_homonym_tool(self):
        # "Ferme Steam" -> el subset NO debe incluir la tool homónima `steam`.
        from gemma4_agent.routing.planner import select_tool_names, plan_mission
        for q in ("Ferme Steam", "Chiudi Steam", "cierra Steam"):
            sub = select_tool_names(q, plan_mission(q))
            self.assertNotIn("steam", sub, f"{q!r}: steam no debe estar (cerrar=app)")
            self.assertIn("app", sub, f"{q!r}: app debe estar (app.close)")


class TestNeedsConfirmationHonesty(unittest.TestCase):
    def test_false_completed_claim_becomes_confirmation_question(self):
        # "Listo, cerré WhatsApp" sobre un needs_confirmation -> MENTIRA -> se
        # reemplaza por la pregunta de confirmación.
        for lie in ("Listo, cerré la aplicación WhatsApp.",
                    "Hecho, cerré WhatsApp.",
                    "Ya cerré la app."):
            out = guard_unverified_final(lie, _needs_confirm_event())
            self.assertNotEqual(out, lie, f"debió reemplazar la mentira: {lie!r}")
            self.assertIn("confirmación", out.lower())

    def test_reply_that_already_asks_passes_through(self):
        # si el reply YA pide confirmación, NO se toca.
        for ok in ("¿Querés que cierre WhatsApp? Necesito tu confirmación.",
                   "Esto requiere confirmación, ¿lo hago?"):
            out = guard_unverified_final(ok, _needs_confirm_event())
            self.assertEqual(out, ok, f"NO debió tocar el reply que ya pregunta: {ok!r}")


if __name__ == "__main__":
    unittest.main()
