"""Parseo NL de fecha/hora -> ISO (datetime_parse). Universal + conservador:
resuelve idioms es que el 4B falla; ante ambigüedad peligrosa -> None (preguntar).
Determinista con base fija. Requiere dateparser (lib instalada).
"""
from __future__ import annotations

import unittest
from datetime import datetime

from gemma4_agent.datetime_parse import parse_when

# mié 27 may 2026, 16:00 — base fija para reproducibilidad.
BASE = datetime(2026, 5, 27, 16, 0, 0)


class ParseWhenTest(unittest.TestCase):
    def _p(self, t):
        return parse_when(t, base=BASE)

    def test_iso_passthrough(self):
        self.assertEqual(self._p("2026-06-01T09:00:00"), "2026-06-01T09:00:00")

    def test_spanish_de_la_tarde(self):
        # "X de la tarde" -> X+12h (hora correcta), día futuro defendible.
        self.assertTrue(self._p("las tres de la tarde").endswith("T15:00:00"))

    def test_spanish_manana_con_hora(self):
        self.assertEqual(self._p("manana a las 9"), "2026-05-28T09:00:00")

    def test_spanish_dia_semana_con_hora(self):
        self.assertEqual(self._p("el viernes a las cinco"), "2026-05-29T05:00:00")

    def test_spanish_de_la_manana(self):
        self.assertTrue(self._p("las 9 de la mañana").endswith("T09:00:00"))

    def test_relative_minutes(self):
        self.assertEqual(self._p("en diez minutos"), "2026-05-27T16:10:00")

    def test_english_still_works(self):
        self.assertEqual(self._p("tomorrow at 3pm"), "2026-05-28T15:00:00")

    def test_ambiguous_same_day_far_result_is_rejected(self):
        # "a las 5 de la tarde" SIN día -> dateparser saltaba a 2027 (bug); el
        # guardrail de cordura lo descarta -> None (el caller pregunta).
        self.assertIsNone(self._p("a las 5 de la tarde"))

    def test_empty_is_none(self):
        self.assertIsNone(self._p(""))
        self.assertIsNone(self._p("   "))

    def test_garbage_is_none(self):
        self.assertIsNone(self._p("fghjghk"))


if __name__ == "__main__":
    unittest.main()
