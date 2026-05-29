"""Pins the routine-trigger routing for the "te"-less Alexa phrasing.

2026-05-20 live repro: "cuando diga buenos dias abre Spotify" routed to the
action/notification tools instead of `routine` — the keyword pattern only
had "cuando TE diga". A routine command must surface the `routine` tool so
the trigger is registered (not executed now). Plain actions and the date
noun must NOT trigger it.
"""
from __future__ import annotations

import unittest

from gemma4_agent.routing.planner import select_tool_names, plan_mission


def _has_routine(q: str) -> bool:
    return "routine" in set(
        select_tool_names(q, plan_mission(q), safety_enabled=True)
    )


class TestRoutineTriggerRouting(unittest.TestCase):

    def test_cuando_diga_phrasings_route_routine(self):
        for q in [
            "cuando diga buenos dias abre Spotify",
            "cuando diga hola pon musica",
            "cuando digas tiempo pausa el video",
            "cuando dija pantallazo saca una captura",
        ]:
            self.assertTrue(_has_routine(q), f"expected routine for {q!r}")

    def test_plain_actions_do_not_trigger_routine(self):
        for q in ["abre Spotify", "pon musica", "saca una captura"]:
            self.assertFalse(_has_routine(q), f"unexpected routine for {q!r}")

    def test_date_and_diga_words_do_not_collide(self):
        # "dia"/"diga" inside ordinary requests must not be read as triggers.
        for q in ["que dia es hoy", "me diga la verdad", "dime el dia de hoy"]:
            self.assertFalse(_has_routine(q), f"unexpected routine for {q!r}")


def _has_calendar(q: str) -> bool:
    return "local_calendar" in set(
        select_tool_names(q, plan_mission(q), safety_enabled=True)
    )


class TestCalendarReadRouting(unittest.TestCase):
    """Calendar READ phrasings routed to nothing while write was fine (live
    repro 2026-05-20: "que tengo agendado para hoy"). \\bagenda\\b doesn't
    match "agendado"; "reuniones"/"eventos" weren't covered."""

    def test_calendar_reads_route_local_calendar(self):
        for q in [
            "que tengo agendado para hoy",
            "que reuniones tengo hoy",
            "que eventos tengo esta semana",
            "tengo una cita medica el lunes",
        ]:
            self.assertTrue(_has_calendar(q), f"expected local_calendar for {q!r}")

    def test_quote_and_folder_do_not_route_calendar(self):
        # "cita" as a quote, and a folder listing, must NOT pull calendar.
        self.assertFalse(_has_calendar("dame una cita de Einstein"))
        self.assertFalse(_has_calendar("que tengo en la carpeta descargas"))


if __name__ == "__main__":
    unittest.main()
