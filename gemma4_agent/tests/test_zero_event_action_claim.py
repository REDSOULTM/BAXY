"""Bug "J Balvin" (2026-06-09): ante "¿has escuchado canciones de X?", el 4B a
veces alucina un media(playback_status) y dice "revisé qué música suena" / la
lang-repair lo vuelve "Ya lo hice." — un claim de acción COMPLETADA que NINGÚN
tool ejecutó (0 events). guard_unverified_final salía temprano en `if not events`
y dejaba pasar la mentira. Fix: en 0 events, si el reply reclama una acción, se
reemplaza por una nota honesta.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_core.agent_guards import (
    guard_unverified_final,
    reply_claims_action,
)


class TestZeroEventActionClaim(unittest.TestCase):
    def test_false_completed_action_claims_are_replaced(self):
        # 0 events + claim de acción COMPLETADA -> reemplazado (no se entrega).
        for bad in (
            "Ya lo hice.",
            "Revisé qué música está sonando en tu dispositivo.",
            "I checked what music is currently playing.",
            "Done.",
        ):
            out = guard_unverified_final(bad, [])
            self.assertNotEqual(out, bad, f"debió reemplazar: {bad!r}")
            self.assertNotIn("ya lo hice", out.lower())
            self.assertNotIn("revisé", out.lower())

    def test_false_future_action_promises_are_replaced(self):
        # también la PROMESA de acción ("voy a revisar Spotify") en 0 events.
        out = guard_unverified_final(
            "Voy a revisar tu reproducción actual en Spotify para ver si es J Balvin.",
            [])
        self.assertNotIn("voy a revisar", out.lower())

    def test_knowledge_replies_are_not_touched(self):
        # respuestas de CONOCIMIENTO (lo que el LLM DEBE poder responder) intactas.
        for good in (
            "Sí, conozco a Michael Jackson, fue un cantante muy influyente.",
            "Sí, conozco muchas canciones de Shakira como 'Waka Waka'.",
            "J Balvin es un cantante de reggaetón colombiano.",
            "No tengo información sobre eso.",
        ):
            self.assertEqual(guard_unverified_final(good, []), good,
                             f"NO debió tocar la respuesta de conocimiento: {good!r}")

    def test_reply_claims_action_covers_completion_verbs(self):
        # el detector ahora cubre verbos de consumación/verificación, no solo
        # "abrí/envié".
        self.assertTrue(reply_claims_action("Ya lo hice."))
        self.assertTrue(reply_claims_action("Revisé la música."))
        self.assertTrue(reply_claims_action("I checked the music."))
        self.assertFalse(reply_claims_action("Sí, conozco a Michael Jackson."))
        self.assertFalse(reply_claims_action("J Balvin es un cantante."))


if __name__ == "__main__":
    unittest.main()
