"""Tests for router_v2 — semantic-first tool routing (Sprint 8a).

Skips all the integration tests if the e5-small ONNX model isn't on
disk yet (cold checkout / first user clone). Runs the env-flag tests
unconditionally because they don't need the model.

Some assertions are deliberately loose because Sprint 8a ships with
the short legacy TOOL_DESCRIPTIONS. Sprint 8b is going to enrich each
description with `purpose + example_queries`, at which point BM25 has
much more material and these assertions can tighten. The tests here
pin the shape of the public contract (pipeline source labels,
telemetry keys, fallback behaviour, top-K cap) rather than which
exact tool wins top-1 for a given query.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.router_v2 import (
    CACHE_THETA,
    FALLBACK_THETA,
    MODEL_PATH,
    TOOL_DESCRIPTIONS_YAML,
    RouterV2,
    SMALLTALK_DELTA_THETA,
    TOP_K,
    is_enabled,
    is_shadow,
    route_v2,
)


_HAS_MODEL = MODEL_PATH.exists()


class EnvFlagsTest(unittest.TestCase):
    """The env-gating helpers must work whether or not the model is on disk."""

    def test_is_enabled_default_matches_model_presence(self) -> None:
        """Hotfix E 2026-05-17: is_enabled() now defaults ON when the
        e5-small model is on disk. Without an explicit env var, the
        result tracks MODEL_PATH.exists() AND singleton availability.
        """
        old_v2 = os.environ.pop("GEMMA4_ROUTER_V2", None)
        old_v1_only = os.environ.pop("GEMMA4_ROUTER_V1_ONLY", None)
        try:
            if MODEL_PATH.exists():
                self.assertTrue(is_enabled(),
                                "v2 should default ON when model present")
            else:
                self.assertFalse(is_enabled(),
                                 "v2 should default OFF when model absent")
        finally:
            if old_v2 is not None:
                os.environ["GEMMA4_ROUTER_V2"] = old_v2
            if old_v1_only is not None:
                os.environ["GEMMA4_ROUTER_V1_ONLY"] = old_v1_only

    def test_is_enabled_v1_only_flag_forces_off(self) -> None:
        old_v1_only = os.environ.get("GEMMA4_ROUTER_V1_ONLY")
        os.environ["GEMMA4_ROUTER_V1_ONLY"] = "1"
        try:
            self.assertFalse(is_enabled())
        finally:
            if old_v1_only is None:
                os.environ.pop("GEMMA4_ROUTER_V1_ONLY", None)
            else:
                os.environ["GEMMA4_ROUTER_V1_ONLY"] = old_v1_only

    def test_is_enabled_explicit_off_overrides_default(self) -> None:
        old_v2 = os.environ.get("GEMMA4_ROUTER_V2")
        old_v1_only = os.environ.pop("GEMMA4_ROUTER_V1_ONLY", None)
        os.environ["GEMMA4_ROUTER_V2"] = "0"
        try:
            self.assertFalse(is_enabled())
        finally:
            if old_v2 is None:
                os.environ.pop("GEMMA4_ROUTER_V2", None)
            else:
                os.environ["GEMMA4_ROUTER_V2"] = old_v2
            if old_v1_only is not None:
                os.environ["GEMMA4_ROUTER_V1_ONLY"] = old_v1_only

    def test_is_shadow_default_when_model_present(self) -> None:
        """Without an explicit env, shadow defaults to ON if model
        is on disk. Skip when the model isn't there (CI machines).

        Hotfix E 2026-05-17: shadow is now ON by default whenever
        MODEL_PATH exists. Operator can disable with
        GEMMA4_ROUTER_V2_SHADOW=0.
        """
        old = os.environ.pop("GEMMA4_ROUTER_V2_SHADOW", None)
        try:
            if MODEL_PATH.exists():
                self.assertTrue(is_shadow(),
                                "shadow should default ON when model present")
            else:
                self.assertFalse(is_shadow(),
                                 "shadow should default OFF when model absent")
        finally:
            if old is not None:
                os.environ["GEMMA4_ROUTER_V2_SHADOW"] = old

    def test_is_shadow_explicit_off_overrides_default(self) -> None:
        old = os.environ.get("GEMMA4_ROUTER_V2_SHADOW")
        os.environ["GEMMA4_ROUTER_V2_SHADOW"] = "0"
        try:
            self.assertFalse(is_shadow())
        finally:
            if old is None:
                os.environ.pop("GEMMA4_ROUTER_V2_SHADOW", None)
            else:
                os.environ["GEMMA4_ROUTER_V2_SHADOW"] = old

    def test_is_shadow_true_when_env_set(self) -> None:
        prev = os.environ.get("GEMMA4_ROUTER_V2_SHADOW")
        os.environ["GEMMA4_ROUTER_V2_SHADOW"] = "1"
        try:
            self.assertTrue(is_shadow())
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_ROUTER_V2_SHADOW", None)
            else:
                os.environ["GEMMA4_ROUTER_V2_SHADOW"] = prev


class ConstantsSanityTest(unittest.TestCase):
    """Thresholds chosen with care — pin the values so a future commit
    can't silently move them without showing up in a diff."""

    def test_cache_theta_band(self) -> None:
        # Cache is for "the user said almost exactly the same thing
        # twice"; anything below 0.85 risks false positives.
        self.assertGreaterEqual(CACHE_THETA, 0.85)
        self.assertLessEqual(CACHE_THETA, 0.95)

    def test_smalltalk_delta_theta_band(self) -> None:
        # Delta between centroid similarities, calibrated in 8a.2.
        # Outside this band the gate fires too often or never.
        self.assertGreaterEqual(SMALLTALK_DELTA_THETA, 0.01)
        self.assertLessEqual(SMALLTALK_DELTA_THETA, 0.10)

    def test_fallback_theta_matches_rrf_scale(self) -> None:
        # With k=60 over ~65 docs the top-1 RRF max is ~2/61 ≈ 0.033;
        # the fallback threshold must live in that band.
        self.assertGreaterEqual(FALLBACK_THETA, 0.01)
        self.assertLessEqual(FALLBACK_THETA, 0.05)

    def test_top_k_is_reasonable(self) -> None:
        self.assertGreaterEqual(TOP_K, 8)
        self.assertLessEqual(TOP_K, 32)


class DisabledPathTest(unittest.TestCase):
    """route_v2 must return ([], …disabled…) cleanly when the model is
    absent, without raising. Verified by patching MODEL_PATH so the
    test runs even on hosts that have the model."""

    def test_route_v2_returns_disabled_when_model_missing(self) -> None:
        # We can't unset the existing module-level MODEL_PATH cheaply,
        # but we can construct a fresh RouterV2 with a router whose
        # _load_failed sticky flag is set.
        RouterV2.reset()
        router = RouterV2.get()
        # Simulate sticky failure WITHOUT relying on FS state.
        router._load_failed = True
        router._load_error = "test-injected: model missing"
        subset, telemetry = router.route("hola")
        self.assertEqual(subset, [])
        self.assertEqual(telemetry["source"], "disabled")
        self.assertIn("error", telemetry)
        # Clean up for the next class so we get a fresh singleton.
        RouterV2.reset()


@unittest.skipUnless(_HAS_MODEL, "e5-small ONNX model not installed")
class RouterV2BasicTest(unittest.TestCase):
    """Integration-flavour tests with the real model + tool index loaded."""

    @classmethod
    def setUpClass(cls) -> None:
        RouterV2.reset()
        cls.router = RouterV2.get()
        ok = cls.router._ensure_loaded()
        if not ok:
            raise unittest.SkipTest(
                f"router_v2 failed to load: {cls.router._load_error}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        RouterV2.reset()

    def test_is_available(self) -> None:
        self.assertTrue(self.router.is_available())

    def test_smalltalk_gate_es(self) -> None:
        subset, telemetry = self.router.route("hola, como estas?")
        self.assertEqual(subset, [])
        self.assertEqual(telemetry["source"], "smalltalk")
        self.assertIn("smalltalk_delta", telemetry)

    def test_smalltalk_gate_en(self) -> None:
        subset, telemetry = self.router.route("thank you very much")
        self.assertEqual(subset, [])
        self.assertEqual(telemetry["source"], "smalltalk")

    def test_steam_routes_to_steam(self) -> None:
        subset, telemetry = self.router.route("abrime el Steam")
        self.assertEqual(telemetry["source"], "hybrid")
        # Proper-noun "Steam" appears in the tool name; BM25 should
        # pin this even with the short legacy descriptions.
        self.assertIn("steam", subset)

    def test_power_point_surfaces_office_in_topk(self) -> None:
        # The bug that motivated Sprint 8: 'power point' must reach
        # office. Loose because Sprint 8b will materially improve
        # this. We just need `office` to BE in top-K, not top-1.
        subset, telemetry = self.router.route("Puedes hacerme un power point sobre IA?")
        self.assertEqual(telemetry["source"], "hybrid")
        self.assertIn("office", subset, f"got: {subset}")

    def test_hybrid_returns_at_most_top_k(self) -> None:
        # Subset cap. With the popular-fallback branch we can add up
        # to len(popular)=9 extras, so the true upper bound is
        # TOP_K + 9.
        subset, _ = self.router.route("hacer cualquier cosa que no encaje")
        self.assertLessEqual(len(subset), TOP_K + 9)

    def test_telemetry_carries_elapsed_ms(self) -> None:
        _, telemetry = self.router.route("hola")
        self.assertIn("elapsed_ms", telemetry)
        self.assertIsInstance(telemetry["elapsed_ms"], float)

    def test_telemetry_carries_source(self) -> None:
        _, telemetry = self.router.route("borra el archivo de mi escritorio")
        self.assertIn(telemetry["source"], {"hybrid", "smalltalk", "cache"})

    def test_warm_latency_under_budget(self) -> None:
        # Cold-load already happened in setUpClass; this checks the
        # steady-state hot path.
        self.router.route("warmup query that varies")
        subset, telemetry = self.router.route("abrime el navegador")
        # Generous budget — quantized e5-small + bm25 over 65 docs
        # should land < 100 ms even on CPU. Anything > 300 ms means
        # something regressed.
        self.assertLess(
            telemetry["elapsed_ms"], 300.0,
            f"warm route took {telemetry['elapsed_ms']:.1f} ms",
        )

    def test_cache_hit_on_exact_repeat(self) -> None:
        # Sufficiently distinctive query so the first call doesn't hit
        # the smalltalk gate and the second call hits the cache.
        q = "investiga cuándo salió la primera GameBoy en Argentina"
        s1, t1 = self.router.route(q)
        s2, t2 = self.router.route(q)
        self.assertEqual(s1, s2)
        # The second call MUST be a cache hit (same vector → cosine == 1).
        self.assertEqual(t2["source"], "cache")

    def test_top1_for_known_brand_query(self) -> None:
        # "Steam" is the most discriminative known-good case for BM25.
        # We have to make sure THIS call goes through the hybrid path,
        # not cache — earlier tests may have already routed "abrime el
        # Steam", so we use a slightly different phrasing to force a
        # cache miss (the cosine of two distinct queries against the
        # same intent stays under CACHE_THETA=0.88).
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        _, telemetry = router.route("quiero abrir Steam ahora")
        self.assertEqual(telemetry.get("source"), "hybrid")
        self.assertIn(telemetry.get("bm25_top1"), {"steam"})


@unittest.skipUnless(_HAS_MODEL, "e5-small ONNX model not installed")
class RouterV2EdgeCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        RouterV2.reset()
        cls.router = RouterV2.get()
        if not cls.router._ensure_loaded():
            raise unittest.SkipTest(cls.router._load_error)

    @classmethod
    def tearDownClass(cls) -> None:
        RouterV2.reset()

    def test_empty_query_is_handled(self) -> None:
        subset, telemetry = self.router.route("")
        self.assertEqual(subset, [])
        self.assertEqual(telemetry["source"], "empty_query")

    def test_whitespace_query_is_handled(self) -> None:
        subset, telemetry = self.router.route("   ")
        self.assertEqual(subset, [])
        self.assertEqual(telemetry["source"], "empty_query")

    def test_module_entry_point_works(self) -> None:
        # route_v2 = RouterV2.get().route — exposed module-level.
        subset, telemetry = route_v2("hola")
        self.assertIsInstance(subset, list)
        self.assertIsInstance(telemetry, dict)
        self.assertIn("source", telemetry)


class ToolDescriptionsYamlTest(unittest.TestCase):
    """Structural tests for tool_descriptions.yaml (Sprint 8b).

    These don't need the ONNX model — they just parse the file and
    cross-check it against COMPOUND_TOOL_SCHEMAS. Cheap to run on every
    CI loop and catches the most common mistake (forgetting to add a
    new tool's entry when COMPOUND_TOOL_SCHEMAS grows)."""

    @classmethod
    def setUpClass(cls) -> None:
        import yaml
        with open(TOOL_DESCRIPTIONS_YAML, encoding="utf-8") as fh:
            cls.entries = yaml.safe_load(fh) or []

    def test_yaml_has_65_entries(self) -> None:
        self.assertEqual(len(self.entries), 65,
                         f"expected 65 tools, got {len(self.entries)}")

    def test_yaml_entries_have_required_fields(self) -> None:
        for e in self.entries:
            with self.subTest(name=e.get("name")):
                self.assertIn("name", e)
                self.assertIn("purpose", e)
                self.assertIn("example_queries", e)
                self.assertIsInstance(e["example_queries"], dict)
                self.assertIn("es", e["example_queries"])
                self.assertIn("en", e["example_queries"])
                self.assertGreaterEqual(len(e["example_queries"]["es"]), 4,
                                        f"{e['name']}: <4 ES queries")
                self.assertGreaterEqual(len(e["example_queries"]["en"]), 4,
                                        f"{e['name']}: <4 EN queries")

    def test_yaml_names_match_compound_tools(self) -> None:
        from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS
        yaml_names = {e["name"] for e in self.entries}
        tool_names = {s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS}
        missing = tool_names - yaml_names
        extra = yaml_names - tool_names
        self.assertFalse(missing, f"YAML missing: {sorted(missing)}")
        self.assertFalse(extra, f"YAML extras (not in COMPOUND): {sorted(extra)}")


@unittest.skipUnless(_HAS_MODEL, "e5-small ONNX model not installed")
class EnrichedRoutingTest(unittest.TestCase):
    """End-to-end routing tests that exercise the YAML-enriched index.

    These were not possible in Sprint 8a (descriptions were too short
    for BM25 to discriminate). With 8b's example_queries the router
    actually catches power-point/office and coloquial play commands."""

    @classmethod
    def setUpClass(cls) -> None:
        RouterV2.reset()
        cls.router = RouterV2.get()
        if not cls.router._ensure_loaded():
            raise unittest.SkipTest(cls.router._load_error)

    @classmethod
    def tearDownClass(cls) -> None:
        RouterV2.reset()

    def test_power_point_routes_to_office(self) -> None:
        # The motivating bug for Sprint 8: 'power point' must surface
        # `office` in the top-K subset. With the 8b ES queries
        # ("hazme un power point sobre los planetas") BM25 has direct
        # lexical material to hit, so this should now reliably make it.
        RouterV2.reset()
        r = RouterV2.get()
        if not r._ensure_loaded():
            self.skipTest(r._load_error)
        subset, telemetry = r.route("Puedes hacerme un power point sobre IA?")
        self.assertEqual(telemetry["source"], "hybrid")
        self.assertIn("office", subset, f"office missing from {subset}")

    def test_coloquial_play_routes_to_media_or_browser(self) -> None:
        # Rioplatense imperative "pone Daredevil en netflix" — must
        # land on media (the streaming-deeplink tool). browser is an
        # acceptable secondary because the legacy phrasing
        # "abri netflix" is in the browser docs.
        RouterV2.reset()
        r = RouterV2.get()
        if not r._ensure_loaded():
            self.skipTest(r._load_error)
        subset, telemetry = r.route("pone Daredevil en netflix")
        self.assertEqual(telemetry["source"], "hybrid")
        self.assertTrue(
            "media" in subset or "browser" in subset,
            f"neither media nor browser surfaced: {subset}",
        )


if __name__ == "__main__":
    unittest.main()
