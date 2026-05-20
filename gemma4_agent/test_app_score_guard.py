"""Pins the first-character guard in tools._score that stops short
near-anagram app names from fuzzy-matching.

2026-05-20 live probe batch 8: "abre Teams" opened STEAM. _score("Teams",
"Steam") was ~40 (difflib ratio ~0.8) because the two are near-anagrams.
A real typo keeps the first letter ("spotfy"->"spotify"); a different
first letter on a short single-token query is a different app. The guard
only applies to short single-token queries, so multi-word / longer fuzzy
tolerance is unchanged.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools import _score


class TestScoreFirstCharGuard(unittest.TestCase):

    def test_near_anagram_does_not_match(self):
        # The bug: Teams resolved to Steam.
        self.assertEqual(_score("Teams", "Steam"), 0)
        self.assertEqual(_score("Steam", "Teams"), 0)

    def test_exact_and_substring_unaffected(self):
        self.assertEqual(_score("steam", "Steam"), 100)
        self.assertEqual(_score("teams", "Microsoft Teams"), 75)  # substring
        self.assertEqual(_score("edge", "Microsoft Edge"), 75)

    def test_real_typos_still_match(self):
        # Same first letter, genuine typo → must still score > 0.
        for q, c in [("spotfy", "Spotify"), ("calculadra", "Calculadora"),
                     ("discrod", "Discord"), ("notpad", "Notepad")]:
            self.assertGreater(_score(q, c), 0, f"{q} vs {c}")

    def test_longer_query_keeps_fuzzy_tolerance(self):
        # Multi-word voice mishears must still fuzzy-match (guard is scoped
        # to short single-token queries only).
        self.assertGreater(_score("saint rose", "Saints Row"), 0)


if __name__ == "__main__":
    unittest.main()
