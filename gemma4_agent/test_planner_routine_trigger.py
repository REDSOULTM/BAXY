"""Pins the routine-trigger routing for the "te"-less Alexa phrasing.

2026-05-20 live repro: "cuando diga buenos dias abre Spotify" routed to the
action/notification tools instead of `routine` — the keyword pattern only
had "cuando TE diga". A routine command must surface the `routine` tool so
the trigger is registered (not executed now). Plain actions and the date
noun must NOT trigger it.
"""
from __future__ import annotations

import unittest

from gemma4_agent.planner import select_tool_names, plan_mission


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


if __name__ == "__main__":
    unittest.main()
