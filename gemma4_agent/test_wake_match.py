"""Tests for `match_wake_phrase` — the textual gate that decides whether a
Vosk result counts as a wake-word.

Rationale: pre-2026-05-17 the matcher accepted "gemma" in ANY position of
the Vosk result, including mid-sentence ("le dije a Gemma que..."), which
caused user-reported FPs during human conversations about the agent. The
new gate requires the wake-word to be at position 0. WAKE_MIN_CONFIDENCE
stays at 0.85 — we are NOT trading FPs for TPs by loosening confidence.
"""
from __future__ import annotations

import unittest

from gemma4_agent.voice.wake import match_wake_phrase


class MatchWakePhraseTest(unittest.TestCase):
    # --- Positive cases: must wake -----------------------------------

    def test_exact_gemma(self) -> None:
        self.assertEqual(match_wake_phrase("gemma"), "gemma")

    def test_exact_hey_gemma(self) -> None:
        self.assertEqual(match_wake_phrase("hey gemma"), "hey gemma")

    def test_gemma_at_start_with_command(self) -> None:
        self.assertEqual(match_wake_phrase("gemma abre spotify"), "gemma")

    def test_hey_gemma_at_start_with_command(self) -> None:
        self.assertEqual(match_wake_phrase("hey gemma como estas"), "hey gemma")

    def test_uppercase_and_trailing_whitespace(self) -> None:
        # Vosk emits lowercase + no punctuation by default; we still call
        # .strip().lower() inside the matcher for defense in depth.
        self.assertEqual(match_wake_phrase("  GEMMA abrime el word  "), "gemma")

    def test_gemma_with_command(self) -> None:
        self.assertEqual(match_wake_phrase("gemma que hora es"), "gemma")

    # --- Negative cases: must NOT wake (the FP regression set) -------

    def test_gemma_in_middle_of_conversation(self) -> None:
        # "le dije a gemma que probara la nueva feature"
        self.assertIsNone(match_wake_phrase("le dije a gemma que probara la nueva feature"))

    def test_gemma_at_end_of_sentence(self) -> None:
        self.assertIsNone(match_wake_phrase("le pregunte a gemma"))

    # Note: "gemma me parece util pero a veces falla" intentionally NOT
    # listed as a negative. It starts with "gemma" so it will wake. In
    # practice this is rare (people rarely start a casual sentence with
    # the agent's name), and the alternative (parsing intent before
    # waking) would defeat the whole point of a cheap on-device wake.

    def test_not_a_wake_word_at_all(self) -> None:
        self.assertIsNone(match_wake_phrase("hola como estas"))

    def test_phonetic_lookalike_does_not_wake(self) -> None:
        # Vosk's WAKE_VOCAB restricts to [gemma, hey gemma, [unk]] so this
        # wouldn't normally come through, but if a similar phoneme ever
        # got mapped, position-gate still kills it.
        self.assertIsNone(match_wake_phrase("tema importante"))

    def test_empty_string(self) -> None:
        self.assertIsNone(match_wake_phrase(""))

    def test_only_whitespace(self) -> None:
        self.assertIsNone(match_wake_phrase("   "))

    def test_hey_alone_does_not_wake(self) -> None:
        self.assertIsNone(match_wake_phrase("hey"))

    def test_gemma_preceded_by_other_words(self) -> None:
        # The regression case: a final result from Vosk like "abrir gemma"
        # would have triggered the old `"gemma" in text.split()` matcher.
        self.assertIsNone(match_wake_phrase("abrir gemma"))


if __name__ == "__main__":
    unittest.main()
