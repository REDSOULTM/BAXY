"""Pins the _rank tiebreaks that disambiguate score-ties.

2026-05-20 live probe batch 9: with everything tied on score, the resolver
launched the wrong target:
  - "Edge"  -> "MicrosoftEdgeBCHost" (a helper process) instead of the
    browser, because "edge" is a substring of both (score 75 tie).
  - "Chrome" -> "YouTube" / "southpark" (PWA shortcuts whose launch is
    Chrome.exe → launch-stem score 100) instead of "Google Chrome".
Tiebreaks added: name-match-presence first (the query must appear in the
NAME, not just the launch stem), then name length closest to the query.
Uses synthetic candidates so the test is deterministic across machines.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools_pkg.app_resolver import AppResolver, AppCandidate


def _rank(query, cands):
    return AppResolver()._rank(query, cands, limit=5)


class TestRankTiebreaks(unittest.TestCase):

    def test_edge_prefers_browser_over_helper(self):
        cands = [
            AppCandidate("MicrosoftEdgeBCHost", "shortcut", "MicrosoftEdgeBCHost.exe", "file"),
            AppCandidate("MicrosoftEdgeDevTools", "shortcut", "MicrosoftEdgeDevTools.exe", "file"),
            AppCandidate("Microsoft Edge", "shortcut", "msedge.exe", "file"),
        ]
        top = _rank("Edge", cands)[0]
        self.assertEqual(top.name, "Microsoft Edge")

    def test_chrome_prefers_named_app_over_pwa_shortcut(self):
        # PWAs launch via Chrome.exe (launch-stem matches), but the user who
        # says "Chrome" wants the app NAMED Chrome.
        cands = [
            AppCandidate("YouTube", "shortcut", "Chrome.exe", "file"),
            AppCandidate("southpark", "shortcut", "Chrome.exe", "file"),
            AppCandidate("Google Chrome", "shortcut", "Chrome.exe", "file"),
        ]
        top = _rank("Chrome", cands)[0]
        self.assertEqual(top.name, "Google Chrome")

    def test_exact_name_still_wins(self):
        cands = [
            AppCandidate("Discord Helper", "shortcut", "DiscordHelper.exe", "file"),
            AppCandidate("Discord", "shortcut", "Discord.exe", "file"),
        ]
        self.assertEqual(_rank("Discord", cands)[0].name, "Discord")


if __name__ == "__main__":
    unittest.main()
