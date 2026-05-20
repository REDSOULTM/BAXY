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

    def test_release_dates_route_web(self):
        # Release/premiere dates the model can't know — real fail logs.
        for q in [
            "Cuando sale gta 6",
            "cuando se estrena la nueva pelicula de batman",
            "cuando lanzan el iphone 17",
            "fecha de lanzamiento de GTA 6",
        ]:
            self.assertTrue(_has_web(q), f"expected web for {q!r}")

    def test_tiempo_as_duration_does_not_route_web(self):
        # "tiempo" meaning duration / the bare routine word must NOT pull web.
        for q in ["cuanto tiempo falta", "hace tiempo que no juego", "tiempo"]:
            self.assertFalse(_has_web(q), f"unexpected web for {q!r}")

    def test_plain_action_does_not_route_web(self):
        self.assertFalse(_has_web("pon el volumen a 30"))


def _has_fs(q: str) -> bool:
    return "filesystem" in set(
        select_tool_names(q, plan_mission(q), safety_enabled=True)
    )


class TestFileExtensionRouting(unittest.TestCase):
    """A filename with an extension is an unambiguous file operation, whatever
    the verb. Live repro 2026-05-20: "agrega una linea al final de notas.txt"
    routed to notes_tasks (the word "notas") instead of filesystem."""

    def test_filename_with_extension_routes_filesystem(self):
        for q in [
            "agrega una linea al final de notas.txt",
            "lee CHANGELOG.md y dime si puedo seguir",
            "abre el reporte.pdf",
            "convierte data.csv a otra cosa",
        ]:
            self.assertTrue(_has_fs(q), f"expected filesystem for {q!r}")

    def test_domain_and_plain_note_do_not_force_filesystem(self):
        # ".com" is not a file extension; "agrega una nota" is a real note.
        self.assertFalse(_has_fs("abre google.com"))
        self.assertFalse(_has_fs("agrega una nota a mi lista"))


if __name__ == "__main__":
    unittest.main()
