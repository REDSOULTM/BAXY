"""Regression test for the huggingface_hub thread-import race.

Bug observed in production (2026-05-16 19:13):
  STT init failed with:
    "cannot import name 'logging' from 'huggingface_hub'"
  Root cause: NLI service (transformers) was loading in a background
  thread while the voice stack (faster_whisper) tried to import
  huggingface_hub on the main thread, observing a half-initialized module.

Fix: serialize heavy ML imports across threads via a module-level lock
in `_ml_import_lock.py`.
"""
from __future__ import annotations

import threading
import unittest
from unittest.mock import patch


class TestMLImportLock(unittest.TestCase):

    def test_lock_serializes_concurrent_acquire(self):
        """Two threads entering ml_imports() must NOT overlap."""
        from gemma4_agent._ml_import_lock import ml_imports

        in_use = []  # tracks active count
        max_overlap = [0]
        evt = threading.Event()
        gate = threading.Event()

        def worker():
            with ml_imports():
                in_use.append(1)
                max_overlap[0] = max(max_overlap[0], sum(in_use))
                # Hold the lock briefly so the OTHER thread is forced to wait.
                evt.wait(timeout=0.5)
                in_use.pop()
            gate.set()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        evt.set()
        t1.join(timeout=5)
        t2.join(timeout=5)
        # Both ran, but never simultaneously.
        self.assertEqual(max_overlap[0], 1,
                          "ml_imports lock must prevent concurrent entry")

    def test_lock_is_reentrant_safe_via_context_manager(self):
        """Using the context manager is safe to call from one thread."""
        from gemma4_agent._ml_import_lock import ml_imports
        with ml_imports():
            self.assertTrue(True)
        # Second entry must also succeed (lock was released).
        with ml_imports():
            self.assertTrue(True)


class TestNLIUsesLock(unittest.TestCase):
    """NLI service's loader path must hit ml_imports()."""

    def test_nli_loader_calls_ml_imports(self):
        import inspect
        from gemma4_agent import nli_service
        src = inspect.getsource(nli_service._NLIService._ensure_loaded)
        self.assertIn("ml_imports", src,
                      "_ensure_loaded must wrap transformers import in ml_imports")


class TestSTTUsesLock(unittest.TestCase):

    def test_stt_load_calls_ml_imports(self):
        import inspect
        from gemma4_agent.voice import stt
        # The STT loader (StreamingSTT.load) must use ml_imports around
        # faster_whisper + huggingface_hub imports.
        src = inspect.getsource(stt)
        self.assertIn("ml_imports", src,
                      "stt.py must wrap faster_whisper import in ml_imports")
        self.assertIn("from faster_whisper import WhisperModel", src)


if __name__ == "__main__":
    unittest.main()
