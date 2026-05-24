"""Tests del router de contexto multi-turno MULTILINGÜE (investigación 4).

PRINCIPIO (CLAUDE.md): uso universal — cualquier hablante, cualquier idioma. La
deixis se detecta por embeddings multilingües, NO por regex en español. Estos
tests verifican: (1) atómicos en varios idiomas droppean historial, (2) deixis
en varios idiomas lo conservan, (3) FALLBACK SEGURO sin encoder (nunca droppea).
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.context_router import (
    needs_history, select_history, _ensure_centroids,
    MODE_NONE, MODE_LIGHT, MODE_FULL, LIGHT_TAIL_MESSAGES,
)

_HAS_ENCODER = _ensure_centroids()


class SafeFallbackTest(unittest.TestCase):
    """Invariantes que se cumplen SIEMPRE, con o sin encoder."""

    def setUp(self):
        os.environ["GEMMA4_CONTEXT_ROUTER"] = "1"

    def test_no_history_means_none(self):
        self.assertEqual(needs_history("open it", has_history=False), MODE_NONE)

    def test_open_toolcall_forces_full(self):
        self.assertEqual(
            needs_history("dale", has_history=True, has_open_toolcall=True),
            MODE_FULL)

    def test_empty_text_safe_full(self):
        self.assertEqual(needs_history("", has_history=True), MODE_FULL)
        self.assertEqual(needs_history("   ", has_history=True), MODE_FULL)

    def test_disabled_returns_full(self):
        os.environ["GEMMA4_CONTEXT_ROUTER"] = "0"
        try:
            self.assertEqual(
                needs_history("abrí Spotify", has_history=True), MODE_FULL)
        finally:
            os.environ["GEMMA4_CONTEXT_ROUTER"] = "1"

    def test_spanish_clitic_caught_without_encoder(self):
        # el atajo regex (aditivo) cubre clíticos español aunque no haya encoder
        import gemma4_agent.context_router as cr
        saved = (cr._C.ready, cr._C.dependent, cr._C.self_contained)
        cr._C.ready, cr._C.dependent, cr._C.self_contained = True, None, None
        try:
            self.assertEqual(needs_history("ponelo en pausa", has_history=True),
                             MODE_LIGHT)
            # SIN encoder y SIN hint regex -> FULL (nunca droppea a ciegas)
            self.assertEqual(needs_history("open it", has_history=True), MODE_FULL)
            self.assertEqual(needs_history("abrí Spotify", has_history=True),
                             MODE_FULL)
        finally:
            cr._C.ready, cr._C.dependent, cr._C.self_contained = saved


@unittest.skipUnless(_HAS_ENCODER, "encoder multilingüe no disponible")
class MultilingualSemanticTest(unittest.TestCase):
    """Con encoder: la decisión generaliza a varios idiomas (no es es-céntrica)."""

    def setUp(self):
        os.environ["GEMMA4_CONTEXT_ROUTER"] = "1"

    def test_atomic_commands_drop_history_multilang(self):
        for cmd in ("abrí Spotify", "qué hora es", "poné los Beatles",
                    "open Spotify", "what time is it",
                    "abre o Spotify", "ouvre Spotify", "öffne Spotify"):
            self.assertEqual(needs_history(cmd, has_history=True), MODE_NONE, cmd)

    def test_deixis_keeps_history_multilang(self):
        # incluye el caso que el usuario señaló: 'open it' en inglés NO debe
        # droppear historial (perdería el referente).
        for cmd in ("ponelo en pausa", "open it", "close it", "the other one",
                    "abre isso", "ouvre-le", "mach das auf"):
            self.assertIn(needs_history(cmd, has_history=True),
                          (MODE_LIGHT, MODE_FULL), cmd)
            self.assertNotEqual(needs_history(cmd, has_history=True), MODE_NONE, cmd)

    def test_short_continuation_multilang(self):
        for cmd in ("sí dale", "yes do it", "no, mejor a las once"):
            self.assertNotEqual(needs_history(cmd, has_history=True), MODE_NONE, cmd)

    def test_very_long_turn_keeps_full(self):
        long_turn = " ".join(["palabra"] * 40)
        self.assertEqual(needs_history(long_turn, has_history=True), MODE_FULL)


class SelectHistoryTest(unittest.TestCase):
    def _hist(self, n):
        return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
                for i in range(n)]

    def test_none_drops_all(self):
        self.assertEqual(select_history(self._hist(10), MODE_NONE), [])

    def test_light_keeps_tail(self):
        kept = select_history(self._hist(10), MODE_LIGHT)
        self.assertEqual(len(kept), LIGHT_TAIL_MESSAGES)
        self.assertEqual(kept[-1]["content"], "m9")

    def test_full_keeps_everything(self):
        h = self._hist(10)
        self.assertEqual(select_history(h, MODE_FULL), h)

    def test_light_shorter_than_tail_keeps_all(self):
        h = self._hist(2)
        self.assertEqual(select_history(h, MODE_LIGHT), h)


if __name__ == "__main__":
    unittest.main()
