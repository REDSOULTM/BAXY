"""Tests del splitter multi-intent (investigación 7).

"abrí Spotify y bajá el volumen" = 2 acciones. Un 4B causal colapsa el
multi-intent; lo partimos con regex ANTES del LLM. Conservador: no parte un "y"
entre sustantivos ni nombres propios.
"""
from __future__ import annotations

import os
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


from gemma4_agent.command_splitter import _ensure_action_centroids

_HAS_ENCODER = _ensure_action_centroids()


@unittest.skipUnless(_HAS_ENCODER, "encoder multilingüe no disponible")
class MultilingualSplitTest(unittest.TestCase):
    """CAPA 2: parte multi-intent en CUALQUIER idioma (no solo español), por
    embeddings. Sustantivos coordinados ('Tom and Jerry') NO parten. Principio
    universal del proyecto (CLAUDE.md): nada de regex es-only."""

    def setUp(self):
        os.environ["GEMMA4_SPLIT_MULTILANG"] = "1"

    def test_two_actions_split_multilang(self):
        for cmd in (
            "open Spotify and turn down the volume",   # en
            "öffne Spotify und mach leiser",            # de
            "abre o Spotify e baixa o volume",          # pt
            "ouvre Spotify et baisse le son",           # fr
        ):
            self.assertEqual(len(split_command(cmd)), 2, cmd)

    def test_coordinated_nouns_do_not_split_multilang(self):
        # 'y'/'and' entre sustantivos o nombres propios -> NO parte (1 sola)
        for cmd in (
            "play Tom and Jerry",
            "add salt and pepper to the list",
            "what is the weather and the time",
        ):
            self.assertEqual(len(split_command(cmd)), 1, cmd)

    def test_disabled_layer2_falls_back_to_spanish_only(self):
        os.environ["GEMMA4_SPLIT_MULTILANG"] = "0"
        try:
            # sin capa 2, un multi-intent inglés NO parte (degradación elegante)
            self.assertEqual(
                len(split_command("open Spotify and turn down the volume")), 1)
            # el español (capa 1) sigue partiendo
            self.assertEqual(
                len(split_command("abrí Spotify y bajá el volumen")), 2)
        finally:
            os.environ["GEMMA4_SPLIT_MULTILANG"] = "1"


if __name__ == "__main__":
    unittest.main()
