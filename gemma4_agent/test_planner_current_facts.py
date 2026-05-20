"""Pins web routing for current-facts the model can't know from training.

2026-05-20 live repro: "que temperatura hay en Madrid" / "weather in London"
routed to NOTHING — the embedder doesn't tie clima/tiempo/weather to web
search, and there was no keyword. Weather, live prices and scores need web.
The fix must NOT collide with "tiempo" used as duration / the routine word.
"""
from __future__ import annotations

import unittest

from gemma4_agent.planner import select_tool_names, plan_mission


def _has_web(q: str) -> bool:
    return "web" in set(select_tool_names(q, plan_mission(q), safety_enabled=True))


class TestCurrentFactsRouting(unittest.TestCase):

    def test_weather_routes_web(self):
        for q in [
            "que temperatura hay en Madrid",
            "que tiempo hace en Tokio",
            "el clima de hoy",
            "va a llover manana",
            "weather in London",
            "cual es el pronostico para el fin de semana",
        ]:
            self.assertTrue(_has_web(q), f"expected web for {q!r}")

    def test_live_prices_route_web(self):
        for q in ["cuanto vale el dolar", "precio actual del bitcoin"]:
            self.assertTrue(_has_web(q), f"expected web for {q!r}")

    def test_tiempo_as_duration_does_not_route_web(self):
        # "tiempo" meaning duration / the bare routine word must NOT pull web.
        for q in ["cuanto tiempo falta", "hace tiempo que no juego", "tiempo"]:
            self.assertFalse(_has_web(q), f"unexpected web for {q!r}")

    def test_plain_action_does_not_route_web(self):
        self.assertFalse(_has_web("pon el volumen a 30"))


if __name__ == "__main__":
    unittest.main()
