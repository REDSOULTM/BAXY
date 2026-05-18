"""Regression test for the Bag of Hallucinations filter.

Hotfix M 2026-05-18: the standalone 'musica' entry in
SPANISH_HALLUCINATION_PHRASES was rejecting legitimate user
queries like 'pon musica' / 'quiero escuchar musica'. Diagnosis
via Sprint L recordings: 7 silent rejects in a single 12:08
session, all real speech, all containing 'musica'. The fix
removed the standalone entry and kept only the bracketed/
parenthesized forms ([musica], (musica)) which are Whisper's
actual silence hallucinations.

This test pins the contract: legitimate 'musica' queries pass,
true sound-effect tags get rejected.
"""
from __future__ import annotations

import unittest

from gemma4_agent.voice.stt import (
    SPANISH_HALLUCINATION_PHRASES,
    looks_like_hallucination,
)


class BoHFilterTest(unittest.TestCase):
    # --- Negative cases: must NOT be flagged as hallucination ---

    def test_pon_musica_is_not_hallucination(self) -> None:
        # The motivating bug for hotfix M.
        self.assertFalse(looks_like_hallucination("Pon musica"))
        self.assertFalse(looks_like_hallucination("Pon musica."))
        self.assertFalse(looks_like_hallucination("Pon musica. Gemma."))

    def test_pon_musica_with_diacritics_is_not_hallucination(self) -> None:
        self.assertFalse(looks_like_hallucination("Pon música"))
        self.assertFalse(looks_like_hallucination("Pon música."))

    def test_other_legitimate_musica_queries(self) -> None:
        # Real user phrasings that mention 'musica'.
        for q in [
            "quiero musica",
            "pone musica relajante",
            "escucha musica",
            "stop musica",
            "musica clasica por favor",
            "baja la musica",
            "no quiero musica ahora",
        ]:
            with self.subTest(q=q):
                self.assertFalse(
                    looks_like_hallucination(q),
                    f"{q!r} falsely flagged as hallucination",
                )

    # --- Positive cases: still must catch real hallucinations ---

    def test_bracketed_musica_tag_is_hallucination(self) -> None:
        # Whisper's actual silence hallucination.
        self.assertTrue(looks_like_hallucination("[musica]"))
        self.assertTrue(looks_like_hallucination("(musica)"))
        self.assertTrue(looks_like_hallucination("[Musica]"))

    def test_bracketed_aplausos_tag_is_hallucination(self) -> None:
        self.assertTrue(looks_like_hallucination("[aplausos]"))
        self.assertTrue(looks_like_hallucination("(aplausos)"))

    def test_bracketed_risas_tag_is_hallucination(self) -> None:
        self.assertTrue(looks_like_hallucination("[risas]"))
        self.assertTrue(looks_like_hallucination("(risas)"))

    def test_subscribe_phrases_still_caught(self) -> None:
        # Regression check: the other BoH entries still work.
        self.assertTrue(looks_like_hallucination("Suscribete al canal"))
        self.assertTrue(looks_like_hallucination("gracias por ver el video"))
        self.assertTrue(looks_like_hallucination(
            "subtitulos por la comunidad de amara"
        ))

    def test_phrases_list_no_longer_contains_standalone_musica(self) -> None:
        # Pin: ensure the standalone entry doesn't sneak back in.
        self.assertNotIn("musica", SPANISH_HALLUCINATION_PHRASES)
        # Bracketed forms remain.
        self.assertIn("[musica]", SPANISH_HALLUCINATION_PHRASES)
        self.assertIn("(musica)", SPANISH_HALLUCINATION_PHRASES)


if __name__ == "__main__":
    unittest.main()
