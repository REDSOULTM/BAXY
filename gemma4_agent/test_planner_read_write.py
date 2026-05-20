"""Pins routing for read/write phrasings that were missing keyword coverage.

2026-05-20 live probe batch 7: several tools routed to NOTHING on natural
phrasings the existing patterns didn't cover — contacts ("tengo el numero
de Juan", "agrega a Pedro"), notes_tasks (plural "notas", verb "anota"),
package (the READ "esta instalado X"), habit_tracker ("registra que hice
ejercicio"). These are pure keyword gaps; the fix widened each pattern
without colliding with unrelated requests.
"""
from __future__ import annotations

import unittest

from gemma4_agent.planner import select_tool_names, plan_mission


def _tools(q: str) -> set[str]:
    return set(select_tool_names(q, plan_mission(q), safety_enabled=True))


class TestReadWriteRouting(unittest.TestCase):

    def test_contacts_read_and_write(self):
        for q in [
            "tengo el numero de Juan",
            "agrega a Pedro con numero 300123",
            "tienes guardado el contacto de mi mama",
        ]:
            self.assertIn("contacts", _tools(q), q)

    def test_notes_plural_and_verb(self):
        for q in ["que notas tengo guardadas", "anota que tengo que comprar pan",
                  "hazme una lista de compras"]:
            self.assertIn("notes_tasks", _tools(q), q)

    def test_package_read(self):
        for q in ["esta instalado discord", "que version de chrome tengo instalada"]:
            self.assertIn("package", _tools(q), q)

    def test_habit_tracker(self):
        for q in ["registra que hoy hice ejercicio", "llevo 5 dias meditando"]:
            self.assertIn("habit_tracker", _tools(q), q)

    def test_no_false_positives(self):
        # Unrelated requests must NOT pull these tools.
        self.assertNotIn("notes_tasks", _tools("que dia es hoy"))
        self.assertNotIn("package", _tools("pon el volumen a 30"))
        self.assertNotIn("contacts", _tools("que hora es"))


if __name__ == "__main__":
    unittest.main()
