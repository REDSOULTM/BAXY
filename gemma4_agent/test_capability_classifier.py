"""Tests for Bug 1: capability classifier.

Mocks the NLI service for fast unit tests. One gated real-inference test
verifies the Daredevil case actually works end-to-end with mDeBERTa.
"""
from __future__ import annotations

import os
import threading
import unittest
from unittest.mock import MagicMock

from gemma4_agent import capability_classifier as cap_mod
from gemma4_agent.capability_classifier import (
    CAPABILITY_LABELS,
    CAPABILITY_TO_TOOLS,
    CapabilityVerdict,
    augment_subset,
    classify_capability_async,
    classify_capability_cached,
    classify_capability_sync,
    clear_cache,
)


def _scores_only(top: str, top_score: float = 0.9,
                  second: str | None = None, second_score: float = 0.0) -> dict:
    """Build a labels/scores dict like NLI pipeline returns, normalized."""
    scores: dict[str, float] = {}
    for lbl in CAPABILITY_LABELS:
        scores[lbl] = 0.01
    scores[top] = top_score
    if second:
        scores[second] = second_score
    return scores


class TestTaxonomy(unittest.TestCase):

    def test_labels_are_unique(self):
        self.assertEqual(len(set(CAPABILITY_LABELS)), len(CAPABILITY_LABELS))

    def test_every_label_has_a_bucket(self):
        for lbl in CAPABILITY_LABELS:
            self.assertIn(lbl, CAPABILITY_TO_TOOLS,
                          f"label {lbl!r} missing from CAPABILITY_TO_TOOLS")

    def test_audiovisual_bucket_contains_media(self):
        self.assertIn("media", CAPABILITY_TO_TOOLS["consumir contenido audiovisual"])


class TestBuildVerdict(unittest.TestCase):

    def setUp(self):
        clear_cache()

    def test_high_confidence_returns_bucket(self):
        scores = _scores_only("consumir contenido audiovisual", 0.95)
        v = cap_mod._build_verdict(scores)
        self.assertEqual(v.top_label, "consumir contenido audiovisual")
        self.assertIn("media", v.bucket)
        self.assertFalse(v.ambiguous)

    def test_below_threshold_returns_empty_bucket(self):
        # Top score 0.3 is below the 0.45 threshold.
        scores = {lbl: 0.1 for lbl in CAPABILITY_LABELS}
        scores["consumir contenido audiovisual"] = 0.3
        v = cap_mod._build_verdict(scores)
        self.assertLess(v.confidence, 0.45)
        # Bucket NOT populated when below threshold.
        self.assertEqual(v.bucket, frozenset())

    def test_ambiguous_top_two_close(self):
        scores = _scores_only(
            "consumir contenido audiovisual", 0.55,
            second="navegar la web o buscar información", second_score=0.50,
        )
        v = cap_mod._build_verdict(scores)
        self.assertTrue(v.ambiguous)
        # Both buckets in result
        self.assertIn("media", v.bucket)
        self.assertIn("web", v.bucket)


class TestCache(unittest.TestCase):

    def setUp(self):
        clear_cache()

    def test_cache_miss_returns_none(self):
        self.assertIsNone(classify_capability_cached("nunca antes visto"))

    def test_cache_hit(self):
        # Manually inject a verdict
        v = CapabilityVerdict(top_label="x", confidence=0.9,
                               bucket=frozenset({"media"}))
        cap_mod._cache_put("hola mundo", v)
        out = classify_capability_cached("hola mundo")
        self.assertIs(out, v)

    def test_cache_normalizes_case(self):
        v = CapabilityVerdict(top_label="x", confidence=0.9,
                               bucket=frozenset({"media"}))
        cap_mod._cache_put("Hola Mundo", v)
        # Lookup with different case still hits.
        self.assertIs(classify_capability_cached("HOLA mundo"), v)


class TestAugmentSubset(unittest.TestCase):

    def setUp(self):
        clear_cache()

    def test_empty_input_returns_unchanged(self):
        subset, tel = augment_subset("", ["safety"])
        self.assertEqual(subset, ["safety"])
        self.assertIsNone(tel["source"])

    def test_cache_hit_augments_subset(self):
        v = CapabilityVerdict(
            top_label="consumir contenido audiovisual",
            confidence=0.9,
            bucket=frozenset({"media", "browser"}),
        )
        cap_mod._cache_put("quiero ver daredevil born again", v)
        subset, tel = augment_subset("quiero ver daredevil born again", ["safety"])
        self.assertIn("media", subset)
        self.assertIn("browser", subset)
        self.assertIn("safety", subset)
        self.assertEqual(tel["source"], "cache")
        self.assertEqual(set(tel["added_tools"]), {"media", "browser"})

    def test_cache_hit_below_threshold_no_change(self):
        v = CapabilityVerdict(
            top_label="?",
            confidence=0.2,
            bucket=frozenset({"media"}),
        )
        cap_mod._cache_put("foo bar", v)
        subset, tel = augment_subset("foo bar", ["safety"])
        # Below threshold: no augmentation
        self.assertEqual(subset, ["safety"])

    def test_no_duplicate_tools(self):
        v = CapabilityVerdict(
            top_label="consumir contenido audiovisual",
            confidence=0.9,
            bucket=frozenset({"media", "browser"}),
        )
        cap_mod._cache_put("test", v)
        subset, tel = augment_subset("test", ["safety", "media"])
        self.assertEqual(subset.count("media"), 1)


class TestSyncWithMockedNLI(unittest.TestCase):

    def setUp(self):
        clear_cache()
        from gemma4_agent import nli_service as nli_mod
        self._original_pipe = nli_mod._SINGLETON._pipe
        self._original_failed = nli_mod._SINGLETON._load_failed
        nli_mod._SINGLETON._load_failed = False

    def tearDown(self):
        from gemma4_agent import nli_service as nli_mod
        nli_mod._SINGLETON._pipe = self._original_pipe
        nli_mod._SINGLETON._load_failed = self._original_failed

    def test_sync_daredevil_routes_to_audiovisual(self):
        from gemma4_agent import nli_service as nli_mod
        # Mock pipeline output
        nli_mod._SINGLETON._pipe = MagicMock(return_value={
            "labels": list(CAPABILITY_LABELS),
            "scores": [
                0.92 if lbl == "consumir contenido audiovisual" else 0.01
                for lbl in CAPABILITY_LABELS
            ],
        })
        verdict = classify_capability_sync("quiero ver daredevil born again",
                                            timeout_sec=5.0)
        self.assertIsNotNone(verdict)
        self.assertTrue(verdict.available)
        self.assertEqual(verdict.top_label, "consumir contenido audiovisual")
        self.assertIn("media", verdict.bucket)

    def test_sync_unavailable_returns_unavailable_verdict(self):
        from gemma4_agent import nli_service as nli_mod
        nli_mod._SINGLETON._pipe = None
        nli_mod._SINGLETON._load_failed = True
        v = classify_capability_sync("anything", timeout_sec=0.1)
        self.assertIsNotNone(v)
        self.assertFalse(v.available)


class TestAsyncCallback(unittest.TestCase):

    def setUp(self):
        clear_cache()

    def test_async_warms_cache(self):
        from gemma4_agent import nli_service as nli_mod
        nli_mod._SINGLETON._load_failed = False
        nli_mod._SINGLETON._pipe = MagicMock(return_value={
            "labels": list(CAPABILITY_LABELS),
            "scores": [
                0.88 if lbl == "consumir contenido audiovisual" else 0.01
                for lbl in CAPABILITY_LABELS
            ],
        })
        evt = threading.Event()
        captured = []
        classify_capability_async("quiero mirar la nueva serie de marvel",
                                   callback=lambda v: (captured.append(v), evt.set()))
        evt.wait(timeout=2.0)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].top_label, "consumir contenido audiovisual")
        # Cache must now have it
        c = classify_capability_cached("quiero mirar la nueva serie de marvel")
        self.assertIsNotNone(c)


@unittest.skipUnless(os.environ.get("GEMMA4_RUN_NLI_TESTS") == "1",
                     "real NLI inference; set GEMMA4_RUN_NLI_TESTS=1")
class TestRealInferenceDaredevil(unittest.TestCase):

    def test_daredevil_real(self):
        clear_cache()
        v = classify_capability_sync("quiero ver daredevil born again",
                                      timeout_sec=15.0)
        self.assertIsNotNone(v)
        self.assertTrue(v.available)
        self.assertEqual(v.top_label, "consumir contenido audiovisual")
        self.assertIn("media", v.bucket)

    def test_ponme_musica_routes_to_audiovisual(self):
        clear_cache()
        # "Ponme música" is unambiguously audiovisual consumption.
        v = classify_capability_sync("ponme musica de los beatles",
                                      timeout_sec=15.0)
        self.assertIsNotNone(v)
        self.assertTrue(v.available)
        self.assertEqual(v.top_label, "consumir contenido audiovisual")
        self.assertIn("media", v.bucket)


if __name__ == "__main__":
    unittest.main()
