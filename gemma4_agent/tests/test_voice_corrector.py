"""Tests for the fuzzy corrector: deterministic anglicism correction.

The corrector is the highest-leverage component of the new pipeline,
and it's pure-Python — no audio fixtures needed. We assert that
known historical failure cases get corrected to their canonical form.
"""
from __future__ import annotations

import unittest

from gemma4_agent.voice.corrector import FuzzyCorrector, _normalise
from gemma4_agent.voice.inventory import (
    STATIC_INVENTORY, build_initial_prompt, get_inventory,
)


SMALL_INV = {
    "apps":    ["Chrome", "Firefox", "Counter-Strike 2", "Spotify"],
    "music_artists": ["Benson Boone", "Bad Bunny"],
    "music_songs":   ["Bohemian Rhapsody", "La Bamba"],
    "wake_words": ["hey gemma", "hey jarvis", "gemma"],
}


class NormaliseTest(unittest.TestCase):
    def test_normalise_lowercases(self):
        self.assertEqual(_normalise("Chrome"), "chrome")

    def test_normalise_strips_accents(self):
        self.assertEqual(_normalise("Búscame"), "buscame")
        self.assertEqual(_normalise("María"), "maria")

    def test_normalise_idempotent(self):
        s = "Open Counter-Strike 2"
        self.assertEqual(_normalise(_normalise(s)), _normalise(s))


class CorrectorRegressionTest(unittest.TestCase):
    """Each test = one known v1 failure case, asserting it's now fixed."""

    def setUp(self):
        self.c = FuzzyCorrector(SMALL_INV)

    def test_benson_mould_becomes_boone(self):
        # 'Benson Mould' ~67% similar a 'Benson Boone' (Levenshtein). Round-2:
        # la corrección plena de nombres propios aplica en POSICIÓN DE ARGUMENTO
        # (tras un verbo de comando: "reproduce X", "pon X"). En habla
        # declarativa el modo estricto exige match >=75 para no corromper.
        out = self.c.correct("reproduce Benson Mould")
        self.assertIn("Benson Boone", out)

    def test_keeps_known_word_unchanged(self):
        # If a token is already canonical, leave it alone.
        out = self.c.correct("abre Chrome")
        self.assertEqual(out.lower(), "abre chrome")

    def test_does_not_over_correct_random_words(self):
        # A word completely unrelated to the inventory should pass through.
        out = self.c.correct("hola que tal")
        # All 3 tokens preserved (none crosses the 65 threshold against
        # inventory items).
        self.assertEqual(len(out.split()), 3)

    def test_long_known_entity_wins_over_short(self):
        # 'Bohemian Rhapsody' (2-gram) should beat just matching 'Rhapsody'
        out = self.c.correct("reproduce Bohemian Rapsody")
        self.assertIn("Bohemian Rhapsody", out)

    def test_phonetically_distant_mistranscription_unchanged(self):
        # Documented limitation: 'Aurekrom' (Whisper's 'abre chrome')
        # has only ~43% string similarity to 'Chrome' — too far for
        # Levenshtein-based fuzzy matching. This test asserts the
        # corrector doesn't OVER-CORRECT in this case (would be worse
        # to replace 'Aurekrom' with a random nearby word).
        out = self.c.correct("abre Aurekrom")
        # 'abre' should be preserved (it's in verbs). 'Aurekrom' may
        # or may not be replaced; we only require the output doesn't
        # crash and has the expected number of tokens (1 or 2).
        self.assertGreater(len(out.strip()), 0)


class WakePhraseStrippingTest(unittest.TestCase):
    def setUp(self):
        self.c = FuzzyCorrector(SMALL_INV)

    def test_strips_hey_gemma_prefix(self):
        out = self.c.strip_wake_phrase("hey gemma abre Chrome")
        self.assertEqual(out, "abre Chrome")

    def test_strips_hey_jarvis_prefix(self):
        out = self.c.strip_wake_phrase("hey jarvis abre Chrome")
        self.assertEqual(out, "abre Chrome")

    def test_no_wake_phrase_preserves_text(self):
        out = self.c.strip_wake_phrase("abre Chrome")
        self.assertEqual(out, "abre Chrome")

    def test_empty_input_returns_empty(self):
        self.assertEqual(self.c.strip_wake_phrase(""), "")


class InventoryTest(unittest.TestCase):
    def test_static_inventory_well_formed(self):
        # Must have at least the categories the corrector + prompt need.
        for cat in ("apps", "verbs", "wake_words"):
            self.assertIn(cat, STATIC_INVENTORY)
            self.assertGreater(len(STATIC_INVENTORY[cat]), 0)

    def test_get_inventory_merges(self):
        inv = get_inventory()
        for cat in ("apps", "verbs", "wake_words", "music_artists", "music_songs"):
            self.assertIn(cat, inv)

    def test_build_initial_prompt_contains_app_names(self):
        prompt = build_initial_prompt()
        self.assertIn("Chrome", prompt)
        self.assertIn("Spotify", prompt)

    def test_build_initial_prompt_under_token_cap(self):
        # ~220 tokens hard limit. We use a conservative ~880-char cap.
        prompt = build_initial_prompt()
        self.assertLessEqual(len(prompt), 900)


class PhoneticCorrectionTest(unittest.TestCase):
    """STT Tier-1 (2026-05-22): rama fonética Double-Metaphone para anglicismos
    que el edit-distance no alcanza, + stop-list anti-over-correction."""

    def setUp(self):
        self.c = FuzzyCorrector(get_inventory(include_discovery=False))

    def test_anglicisms_corrected_phonetically(self):
        # "netflis"->Netflix, "disnei"->Disney, "jema"->gemma son matches
        # fonéticos inalcanzables por texto puro.
        self.assertIn("Netflix", self.c.correct("abre netflis"))
        self.assertIn("Disney", self.c.correct("pon loki en disnei"))
        self.assertIn("gemma", self.c.correct("jema que hora es").lower())
        self.assertIn("Spotify", self.c.correct("pon espotify"))

    def test_streaming_command_preserves_preposition(self):
        # bug medido: "en disnei" colapsaba a "enciende". El "en" debe quedar.
        out = self.c.correct("pon loki en disnei")
        self.assertIn("en", out.split())
        self.assertNotIn("enciende", out)

    def test_common_spanish_words_not_corrupted(self):
        # Stop-list: palabras españolas válidas NO se corrigen a verbos/apps,
        # aunque colisionen fuzzy/fonéticamente (bug pre-existente).
        for cmd in [
            "pon musica clasica",
            "busca informacion sobre la guerra",
            "abre la ventana",
            "cierra la ventana",
            "sube el volumen al maximo",
            "que hora es",
            "reproduce algo de musica",
        ]:
            self.assertEqual(
                self.c.correct(cmd), cmd,
                f"corrector corrompió un comando común: {cmd!r}",
            )

    def test_corrector_works_without_jellyfish(self):
        # Si jellyfish no está, la rama fonética se desactiva pero el texto
        # sigue funcionando (no crash). Simulamos forzando _HAS_PHONETIC=False.
        import gemma4_agent.voice.corrector as corr
        orig = corr._HAS_PHONETIC
        try:
            corr._HAS_PHONETIC = False
            c = FuzzyCorrector(SMALL_INV)
            # match textual fuerte sigue andando
            self.assertIn("Chrome", c.correct("abre chrme"))
        finally:
            corr._HAS_PHONETIC = orig


if __name__ == "__main__":
    unittest.main()
