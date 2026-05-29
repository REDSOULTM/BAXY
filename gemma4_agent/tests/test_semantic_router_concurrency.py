"""The semantic-router model load must be thread-safe: the warmup daemon thread
and the first user turn both call _ensure_loaded concurrently. Without a lock
they double-load the SentenceTransformer and can mis-count attempts toward
_RETRY_MAX_ATTEMPTS, falsely tripping permanently_disabled.

We stub SentenceTransformer (slow load) so no real model/GPU is needed."""
from __future__ import annotations

import sys
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from gemma4_agent.routing import semantic_router as sr



@dataclass
class _LoadCounter:
    loads: int = 0
    lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self):
        self.lock = threading.Lock()


class _StubST:
    """Stand-in for SentenceTransformer with a deliberately slow __init__ so
    concurrent callers overlap inside the load window."""

    counter: _LoadCounter = _LoadCounter()

    def __init__(self, name):
        with _StubST.counter.lock:
            _StubST.counter.loads += 1
        time.sleep(0.15)  # widen the race window

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        import numpy as np
        n = len(texts) if hasattr(texts, "__len__") else 1
        return np.ones((n, 384), dtype="float32") / (384 ** 0.5)


class TestEnsureLoadedConcurrency(unittest.TestCase):
    def setUp(self):
        # Fresh state for each test.
        sr._STATE = sr._State()
        _StubST.counter = _LoadCounter()
        # Inject a fake sentence_transformers module exposing SentenceTransformer.
        self._fake_mod = types.ModuleType("sentence_transformers")
        self._fake_mod.SentenceTransformer = _StubST  # type: ignore[attr-defined]
        self._saved = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = self._fake_mod

    def tearDown(self):
        if self._saved is not None:
            sys.modules["sentence_transformers"] = self._saved
        else:
            sys.modules.pop("sentence_transformers", None)
        sr._STATE = sr._State()

    def test_concurrent_load_happens_once(self):
        results = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(sr._ensure_loaded) for _ in range(8)]
            results = [f.result() for f in futs]
        self.assertTrue(all(results), "every concurrent caller must succeed")
        self.assertEqual(_StubST.counter.loads, 1,
                         "model must load exactly once under contention")
        self.assertFalse(sr._STATE.permanently_disabled)
        self.assertLessEqual(sr._STATE.attempt_count, 1,
                             "concurrent callers must not inflate attempt_count")

    def test_fast_path_after_load_takes_no_lock(self):
        # Prime the load, then a subsequent call must return True immediately.
        self.assertTrue(sr._ensure_loaded())
        loads_after_prime = _StubST.counter.loads
        self.assertTrue(sr._ensure_loaded())
        self.assertEqual(_StubST.counter.loads, loads_after_prime,
                         "second call must not reload")


if __name__ == "__main__":
    unittest.main()
