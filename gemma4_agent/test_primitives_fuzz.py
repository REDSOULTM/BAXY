"""Deterministic property-style fuzzing of the pure primitives that had
edge-case bugs in the audit. `hypothesis` is BLOCKED_NEW_DEP, so we use a
seeded `random` generator to throw thousands of structured-random inputs at each
primitive and assert its invariants. Seeded => reproducible; a failure prints the
offending input.

EJE del norte rector: FIABILIDAD / CALIDAD UX — estos primitivos alimentan la
compactación (anti context-overflow), el texto visible al usuario (sanitize), y
la detección de misión. Sus bugs eran inputs raros que un test puntual no cubre.
"""
from __future__ import annotations

import random
import unittest

from gemma4_agent.agent_compaction import middle_ellipsis
from gemma4_agent.reasoning import sanitize_text
from gemma4_agent.mission_goal import _split_clauses, _fold
from gemma4_agent.voice.corrector import FuzzyCorrector


# Char palette mixing ASCII, unicode, whitespace, punctuation, and the exact
# markup tokens the primitives must handle.
_PALETTE = (
    "abcdefABCDEF 0123456789.,;:!?¡¿\n\t"
    "áéíóúñüÁÉÍÓÚ€漢字😀​́"  # accents, CJK, emoji, ZWSP, combining
    "<>|/"
)
_THINK_FRAGMENTS = [
    "<think>", "</think>", "<|end|>", "<|user|>", "<|assistant|>",
    "razonando", "hola", "respuesta final", "\n\n", "<think>anidado",
]


def _rand_text(rng: random.Random, maxlen: int = 300) -> str:
    n = rng.randint(0, maxlen)
    return "".join(rng.choice(_PALETTE) for _ in range(n))


def _rand_markup(rng: random.Random) -> str:
    """Random concatenation of think/tool markup fragments + filler — exercises
    closed, unclosed, nested and interleaved tags."""
    parts = []
    for _ in range(rng.randint(0, 12)):
        if rng.random() < 0.5:
            parts.append(rng.choice(_THINK_FRAGMENTS))
        else:
            parts.append("".join(rng.choice("abc .") for _ in range(rng.randint(0, 8))))
    return "".join(parts)


class TestMiddleEllipsisProperties(unittest.TestCase):
    """Invariants: output is str, never longer than `limit`, never longer than
    input, and for non-truncating cases returns the input verbatim."""

    def test_fuzz_bounds(self):
        rng = random.Random(1234)
        for _ in range(3000):
            text = _rand_text(rng, maxlen=400)
            limit = rng.randint(0, 500)
            out = middle_ellipsis(text, limit)
            self.assertIsInstance(out, str)
            # Core contract: output never exceeds the limit...
            self.assertLessEqual(len(out), max(0, limit),
                                 f"GREW past limit: limit={limit} in={len(text)} out={len(out)}")
            # ...and never exceeds the input (truncation must shrink or no-op).
            self.assertLessEqual(len(out), len(text),
                                 f"GREW past input: in={len(text)} out={len(out)}")

    def test_fuzz_short_input_is_verbatim(self):
        rng = random.Random(5)
        for _ in range(1000):
            limit = rng.randint(1, 500)
            text = _rand_text(rng, maxlen=limit)  # len <= limit
            if len(text) <= limit:
                self.assertEqual(middle_ellipsis(text, limit), text)

    def test_extremes(self):
        # Hand-picked extreme limits + the empty string.
        for limit in (0, 1, 2, 3, 4, 5, 10, 159, 160, 161):
            out = middle_ellipsis("x" * 1000, limit)
            self.assertLessEqual(len(out), max(0, limit), f"limit={limit}")
        self.assertEqual(middle_ellipsis("", 0), "")
        self.assertEqual(middle_ellipsis("", 100), "")


class TestSanitizeTextProperties(unittest.TestCase):
    """Invariant: the output NEVER contains a `<think>` opening tag nor a
    `<|...|>` control token, no matter how the fragments are arranged."""

    def test_fuzz_no_residual_markup(self):
        rng = random.Random(99)
        for _ in range(4000):
            text = _rand_markup(rng)
            out = sanitize_text(text)
            self.assertIsInstance(out, str)
            self.assertNotIn("<think>", out, f"residual <think> from: {text!r}")
            # No bare control token of the <|word|> form should survive.
            import re
            self.assertIsNone(re.search(r"<\|[a-z_]+\|>", out, re.IGNORECASE),
                              f"residual control token from: {text!r}")

    def test_fuzz_never_raises_on_arbitrary_text(self):
        rng = random.Random(7)
        for _ in range(2000):
            sanitize_text(_rand_text(rng))  # must not raise

    def test_non_str_inputs(self):
        for val in (None, 42, 3.14, ["a"], {"k": "v"}, object()):
            out = sanitize_text(val)
            self.assertIsInstance(out, str)


class TestSplitClausesProperties(unittest.TestCase):
    """Invariants: returns a list of non-empty stripped strings, never raises,
    and an empty/whitespace input yields []."""

    def test_fuzz_shape(self):
        rng = random.Random(2026)
        for _ in range(3000):
            text = _rand_text(rng, maxlen=200)
            out = _split_clauses(text)
            self.assertIsInstance(out, list)
            for clause in out:
                self.assertIsInstance(clause, str)
                self.assertEqual(clause, clause.strip())
                self.assertNotEqual(clause, "")

    def test_empty_inputs(self):
        for empty in ("", "   ", "\n\t", None):
            self.assertEqual(_split_clauses(empty), [])

    def test_fold_idempotent_and_total(self):
        # _fold must be total (never raise) and idempotent on its own output.
        rng = random.Random(3)
        for _ in range(1000):
            t = _rand_text(rng, maxlen=80)
            f = _fold(t)
            self.assertEqual(_fold(f), f, "fold must be idempotent")


class TestCorrectorProperties(unittest.TestCase):
    """The STT fuzzy corrector is on the voice hot-path. Invariants: never
    raises on arbitrary transcripts, always returns a str, NEVER increases the
    token count (it replaces n-grams 1:1 or collapses, never expands), and
    preserves emptiness (empty in -> empty out)."""

    @classmethod
    def setUpClass(cls):
        inv = {
            "verbs": ["abre", "cierra", "reproduce", "busca"],
            "apps": ["chrome", "spotify", "steam", "calculadora", "discord"],
            "music_artists": ["benson boone", "bad bunny"],
            "music_songs": ["beautiful things"],
            "wake_words": ["hey gemma", "oye gemma"],
        }
        cls.corr = FuzzyCorrector(inv)

    def test_fuzz_never_raises_and_no_token_expansion(self):
        rng = random.Random(424242)
        # Build transcripts from real-ish words + noise so the matcher engages.
        words = ["abre", "abr", "chrom", "chrome", "spotofy", "steam", "xyz",
                 "reproduci", "benson", "boone", "hola", "gema", "oye", ""]
        for _ in range(3000):
            k = rng.randint(0, 10)
            transcript = " ".join(rng.choice(words) for _ in range(k))
            out = self.corr.correct(transcript)
            self.assertIsInstance(out, str)
            # Token count must never INCREASE (corrector replaces/collapses).
            self.assertLessEqual(len(out.split()), len(transcript.split()),
                                 f"corrector expanded tokens: {transcript!r} -> {out!r}")

    def test_empty_and_whitespace(self):
        self.assertEqual(self.corr.correct(""), "")
        self.assertEqual(self.corr.correct("   ").strip(), "")

    def test_arbitrary_unicode_does_not_raise(self):
        rng = random.Random(11)
        for _ in range(1000):
            self.corr.correct(_rand_text(rng, maxlen=60))  # must not raise


if __name__ == "__main__":
    unittest.main()
