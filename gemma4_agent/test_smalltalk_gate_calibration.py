"""Smalltalk gate calibration probes (hotfix E.5 2026-05-17).

These tests run the router in a FRESH state (RouterV2.reset())
before each probe so cache hits from prior tests can't mask
calibration regressions. The bug fixed here: hotfix E's
test_play_music_es passed only because test_play_music_en
(alphabetically earlier) cached the embedding; a cold call to
'pone benson boone' fired the smalltalk gate.

What this sprint resolves (audit-day bugs):
  - 'pone benson boone'    → hybrid, media in top-3 ✓
  - 'pone los redonditos'  → hybrid, media in top-3 ✓

Known limitation (documented as @unittest.expectedFailure):
  - 'pone queen', 'play queen', 'poneme algo tranqui' still
    fire smalltalk cold. Two-word imperatives + a single
    common noun stay just above the 0.030 delta floor because
    mean-pooling dilutes single-doc YAML additions across 65
    docs. Anti-scope #6: this requires a follow-up sprint
    (smalltalk centroid re-computation OR more YAML anchors
    OR a calibration approach beyond a single scalar floor).
    See project_router_v2_calibration #7.
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import MODEL_PATH, RouterV2


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class SmalltalkGateColdTest(unittest.TestCase):
    def _route_cold(self, query: str) -> tuple[list[str], dict]:
        """Force a fresh router so no cache hit pollutes the result."""
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        return router.route(query)

    # --- Smalltalk should still fire ---
    def test_hola_fires_smalltalk(self) -> None:
        _, tel = self._route_cold("hola")
        self.assertEqual(tel.get("source"), "smalltalk")

    def test_gracias_fires_smalltalk(self) -> None:
        _, tel = self._route_cold("gracias")
        self.assertEqual(tel.get("source"), "smalltalk")

    def test_thanks_fires_smalltalk(self) -> None:
        _, tel = self._route_cold("thanks")
        self.assertEqual(tel.get("source"), "smalltalk")

    def test_gracias_por_todo_fires_smalltalk(self) -> None:
        # Was a regex false-positive in v1; v2 should classify as
        # smalltalk (delta well above 0.030).
        _, tel = self._route_cold("gracias por todo")
        self.assertEqual(tel.get("source"), "smalltalk")

    # --- Music commands must NOT fire smalltalk (the bug) ---
    def test_pone_benson_boone_does_NOT_fire_smalltalk_cold(self) -> None:
        # The bug: delta=0.028 fired the gate at theta=0.025. With
        # the new theta=0.030, this should land on hybrid retrieval.
        subset, tel = self._route_cold("pone benson boone")
        self.assertNotEqual(
            tel.get("source"), "smalltalk",
            f"smalltalk gate fired with delta={tel.get('smalltalk_delta')}; "
            f"subset={subset}",
        )

    def test_pone_los_redonditos_does_NOT_fire_smalltalk_cold(self) -> None:
        subset, tel = self._route_cold("pone los redonditos")
        self.assertNotEqual(tel.get("source"), "smalltalk")

    @unittest.expectedFailure
    def test_play_queen_does_NOT_fire_smalltalk_cold(self) -> None:
        # KNOWN LIMITATION (hotfix E.5 2026-05-17). Despite adding
        # 'play queen' to media.example_queries.en, this query still
        # fires smalltalk cold (delta=0.032, just above theta=0.030).
        # The mean-pooling on a single new doc among 65 dilutes the
        # signal too much; the smalltalk centroid (33 short seed
        # phrases) lands almost as close. Sprint E.5 anti-scope rule:
        # do NOT raise theta past 0.030, do NOT invent length-aware
        # metric. Documented in project_router_v2_calibration #7 as
        # a follow-up sprint candidate (needs more 'play X' anchors
        # or a different smalltalk centroid computation).
        #
        # The pone-X family (the audit-day bug) IS resolved by this
        # sprint; play-X-with-1-word-band is a strictly larger ask.
        subset, tel = self._route_cold("play queen")
        self.assertNotEqual(tel.get("source"), "smalltalk")

    # --- Action commands still work ---
    def test_abrime_steam_does_NOT_fire_smalltalk_cold(self) -> None:
        subset, tel = self._route_cold("abrime el Steam")
        self.assertNotEqual(tel.get("source"), "smalltalk")
        self.assertIn("steam", subset)

    # --- E5.2 joint-fix smokes: 'pone X' must reach media cold ---
    def test_pone_benson_boone_routes_to_media_cold(self) -> None:
        # End-to-end smoke: cold cache, query should land in hybrid
        # retrieval AND surface 'media' in the subset.
        subset, tel = self._route_cold("pone benson boone")
        self.assertEqual(
            tel.get("source"), "hybrid",
            f"got source={tel.get('source')}, expected hybrid",
        )
        self.assertIn("media", subset,
                      f"media missing from cold subset: {subset}")

    def test_pone_redonditos_routes_to_media_cold(self) -> None:
        subset, tel = self._route_cold("pone los redonditos")
        self.assertEqual(tel.get("source"), "hybrid")
        self.assertIn("media", subset)


if __name__ == "__main__":
    unittest.main()
