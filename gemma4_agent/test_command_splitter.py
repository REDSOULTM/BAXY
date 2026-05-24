"""Tests del splitter multi-intent (investigación 7).

"abrí Spotify y bajá el volumen" = 2 acciones. Un 4B causal colapsa el
multi-intent; lo partimos con regex ANTES del LLM. Conservador: no parte un "y"
entre sustantivos ni nombres propios.
"""
from __future__ import annotations

import unittest

from gemma4_agent.command_splitter import (
    split_command, has_back_reference, plan_clauses,
)


class SplitterTest(unittest.TestCase):
    def test_two_actions_split(self):
        for cmd in (
            "abrí Spotify y bajá el volumen",
            "abre Steam y pon música",
            "muteá el sonido y abrí la calculadora",
        ):
            self.assertEqual(len(split_command(cmd)), 2, cmd)

    def test_innocent_y_does_not_split(self):
        # 'y' entre sustantivos / nombres propios / dentro de un mensaje -> NO parte
        for cmd in (
            "pon sal y pimienta en la lista",
            "reproducí Tom y Jerry",
            "mandale a mamá que la quiero y la extraño",
            "¿qué hora es?",
            "abre Spotify",
        ):
            self.assertEqual(len(split_command(cmd)), 1, cmd)

    def test_dependent_clause_detected(self):
        clauses = plan_clauses("buscá un Word y abrilo")
        self.assertEqual(len(clauses), 2)
        self.assertFalse(clauses[0]["depends_on_prev"])
        self.assertTrue(clauses[1]["depends_on_prev"])  # 'abrilo' refiere al Word

    def test_back_reference_helper(self):
        self.assertTrue(has_back_reference("abrilo"))
        self.assertTrue(has_back_reference("ciérralo"))
        self.assertTrue(has_back_reference("ponelo en pausa"))
        self.assertFalse(has_back_reference("abrí Chrome"))

    def test_cap_on_too_many_clauses(self):
        # más de MAX_CLAUSES -> no confiar, tratar como un comando
        cmd = "abre A y abre B y abre C y abre D y abre E"
        self.assertEqual(len(split_command(cmd)), 1)

    def test_empty_and_none_safe(self):
        self.assertEqual(split_command(""), [""])
        self.assertEqual(split_command("   "), ["   "])


if __name__ == "__main__":
    unittest.main()
