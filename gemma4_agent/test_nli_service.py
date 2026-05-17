"""Tests for the NLI service.

The model loads ~14s and inference is ~1200ms on CPU — too slow for most CI.
Tests cover the wiring (cache, timeout, fallback when model unavailable);
the ONE real-inference test is gated behind GEMMA4_RUN_NLI_TESTS=1.
"""
from __future__ import annotations

import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.nli_service import _NLIService, get_nli_service


class TestNLIServiceCache(unittest.TestCase):

    def test_cache_hit_returns_without_loading(self):
        svc = _NLIService()
        labels = ["a", "b"]
        key = svc._cache_key("hola", tuple(labels))
        svc._cache_put(key, {"a": 0.8, "b": 0.2})
        # Even without loading the pipe, cache hit returns.
        result = svc.classify_sync("hola", labels)
        self.assertEqual(result, {"a": 0.8, "b": 0.2})

    def test_cache_key_stable(self):
        svc = _NLIService()
        k1 = svc._cache_key("foo", ("x", "y"))
        k2 = svc._cache_key("foo", ("x", "y"))
        k3 = svc._cache_key("foo", ("y", "x"))  # order matters
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)

    def test_cache_lru_eviction(self):
        svc = _NLIService()
        # Smaller cap for test simulation: insert >> _MAX_CACHE
        from gemma4_agent import nli_service as mod
        with patch.object(mod, "_MAX_CACHE", 3):
            for i in range(5):
                svc._cache_put(f"k{i}", {"x": float(i)})
            # Should retain only the last 3.
            self.assertEqual(len(svc._cache), 3)
            self.assertNotIn("k0", svc._cache)
            self.assertIn("k4", svc._cache)


class TestNLIServiceGracefulDegrade(unittest.TestCase):
    """If the model fails to load, classify must return None instead of raising."""

    def test_classify_returns_none_when_load_fails(self):
        svc = _NLIService()
        # Force load_failed without trying the real load
        svc._load_failed = True
        out = svc.classify_sync("anything", ["a", "b"])
        self.assertIsNone(out)

    def test_empty_inputs_return_none(self):
        svc = _NLIService()
        self.assertIsNone(svc.classify_sync("", ["a"]))
        self.assertIsNone(svc.classify_sync("hi", []))

    def test_async_with_empty_calls_callback_none(self):
        svc = _NLIService()
        received = []
        svc.classify_async("", ["a"], callback=received.append)
        # Callback runs synchronously when input is invalid.
        self.assertEqual(received, [None])


class TestNLIServiceTimeout(unittest.TestCase):

    def test_sync_timeout_returns_none_on_slow_run(self):
        svc = _NLIService()
        # Mock the pipe to sleep longer than timeout
        slow_pipe = MagicMock(side_effect=lambda *a, **kw: (time.sleep(2.0)
                                                              or {"labels": ["a"], "scores": [1.0]}))
        svc._pipe = slow_pipe
        out = svc.classify_sync("foo", ["a", "b"], timeout_sec=0.2)
        self.assertIsNone(out)

    def test_sync_no_timeout_runs(self):
        svc = _NLIService()
        fast_pipe = MagicMock(return_value={"labels": ["a", "b"],
                                              "scores": [0.9, 0.1]})
        svc._pipe = fast_pipe
        out = svc.classify_sync("foo", ["a", "b"])
        self.assertEqual(out, {"a": 0.9, "b": 0.1})


class TestNLIServiceAsync(unittest.TestCase):

    def test_async_callback_receives_result(self):
        svc = _NLIService()
        fast_pipe = MagicMock(return_value={"labels": ["x"], "scores": [1.0]})
        svc._pipe = fast_pipe

        evt = threading.Event()
        captured = []

        def cb(result):
            captured.append(result)
            evt.set()

        svc.classify_async("foo", ["x", "y"], callback=cb)
        ok = evt.wait(timeout=2.0)
        self.assertTrue(ok, "async callback should fire within 2s")
        self.assertEqual(captured, [{"x": 1.0}])


class TestNLIServiceSingleton(unittest.TestCase):

    def test_get_nli_service_returns_singleton(self):
        a = get_nli_service()
        b = get_nli_service()
        self.assertIs(a, b)


@unittest.skipUnless(os.environ.get("GEMMA4_RUN_NLI_TESTS") == "1",
                     "set GEMMA4_RUN_NLI_TESTS=1 to run real-inference NLI test")
class TestNLIServiceRealInference(unittest.TestCase):
    """Single integration test that actually loads mDeBERTa. Skipped by default."""

    def test_daredevil_classifies_as_audiovisual(self):
        svc = get_nli_service()
        labels = [
            "consumir contenido audiovisual",
            "gestionar agenda",
            "consultar memoria personal",
            "navegar web",
        ]
        scores = svc.classify_sync("quiero ver daredevil born again", labels,
                                    timeout_sec=15.0)
        self.assertIsNotNone(scores)
        top = max(scores.items(), key=lambda kv: kv[1])
        self.assertEqual(top[0], "consumir contenido audiovisual")
        self.assertGreater(top[1], 0.6)


if __name__ == "__main__":
    unittest.main()
