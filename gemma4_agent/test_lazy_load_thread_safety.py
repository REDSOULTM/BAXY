"""Lazy model loaders must be thread-safe: the warmup daemon thread and the
first user turn call them concurrently. Each loader uses double-checked locking
so the load body runs at most once even under contention.

Pure concurrency test — no real models. We monkeypatch the load body to count
invocations and widen the race window with a tiny sleep."""
from __future__ import annotations

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from gemma4_agent import abstain_head, reranker, tool_head


def _hammer(fn, n=8):
    with ThreadPoolExecutor(max_workers=n) as ex:
        return [f.result() for f in [ex.submit(fn) for _ in range(n)]]


class TestLazyLoadThreadSafety(unittest.TestCase):
    def test_abstain_head_loads_body_once(self):
        abstain_head._MODEL = None
        abstain_head._LOAD_TRIED = False
        calls = {"n": 0}
        orig = abstain_head._load_model_locked

        def counting():
            calls["n"] += 1
            time.sleep(0.05)
            return orig()

        abstain_head._load_model_locked = counting
        try:
            _hammer(abstain_head.load_model)
        finally:
            abstain_head._load_model_locked = orig
            abstain_head._MODEL = None
            abstain_head._LOAD_TRIED = False
        self.assertEqual(calls["n"], 1, "load body must run once under contention")

    def test_tool_head_loads_body_once(self):
        tool_head._HEAD = None
        tool_head._TRIED = False
        calls = {"n": 0}
        orig = tool_head._load_locked

        def counting():
            calls["n"] += 1
            time.sleep(0.05)
            return orig()

        tool_head._load_locked = counting
        try:
            _hammer(tool_head.load)
        finally:
            tool_head._load_locked = orig
            tool_head._HEAD = None
            tool_head._TRIED = False
        self.assertEqual(calls["n"], 1)

    def test_reranker_loads_model_once(self):
        # reranker has no separate _locked fn; assert the CrossEncoder import
        # path runs once by stubbing sentence_transformers.
        import sys
        import types
        reranker._S = reranker._State()
        loads = {"n": 0}

        class _StubCE:
            def __init__(self, *a, **k):
                loads["n"] += 1
                time.sleep(0.05)

            def predict(self, pairs, show_progress_bar=False):
                return [0.0] * len(pairs)

        fake = types.ModuleType("sentence_transformers")
        fake.CrossEncoder = _StubCE  # type: ignore[attr-defined]
        saved = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = fake
        # Force-enable in case env disabled it.
        import os
        prev = os.environ.get("GEMMA4_RERANKER")
        os.environ["GEMMA4_RERANKER"] = "1"
        try:
            _hammer(reranker._load)
        finally:
            if saved is not None:
                sys.modules["sentence_transformers"] = saved
            else:
                sys.modules.pop("sentence_transformers", None)
            if prev is None:
                os.environ.pop("GEMMA4_RERANKER", None)
            else:
                os.environ["GEMMA4_RERANKER"] = prev
            reranker._S = reranker._State()
        self.assertEqual(loads["n"], 1, "CrossEncoder must load once under contention")


if __name__ == "__main__":
    unittest.main()
