"""Cross-component lock to serialize heavy ML library imports.

Why this exists:

  Multiple components in the agent need to import `huggingface_hub` (and
  its transitive deps like `transformers`, `tokenizers`, `safetensors`):

    - voice/stt.py            -> faster_whisper -> huggingface_hub
    - nli_service.py          -> transformers   -> huggingface_hub
    - ops_tools / embedders   -> sentence_transformers -> huggingface_hub

  Python's import system has a per-module lock, but the components above
  run on DIFFERENT threads (voice worker, NLI worker, planner async).
  Observed failure: thread A imports `huggingface_hub` (partially), thread B
  observes the half-built module and raises
  "cannot import name 'logging' from huggingface_hub".

  This lock serializes the FIRST heavy import in each component. Once
  Python's module cache is warm, subsequent imports are O(1) lookups and
  no longer contend.

Usage:
    from gemma4_agent._ml_import_lock import ml_imports
    with ml_imports():
        import huggingface_hub
        from faster_whisper import WhisperModel
        # ... other heavy imports

The lock is a plain threading.Lock at module scope. Process-local.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager


_LOCK = threading.Lock()


@contextmanager
def ml_imports():
    """Context manager that serializes heavy ML library imports across
    threads. Holding it during `import x` blocks; releasing once the
    import line returns is enough because Python caches the module."""
    _LOCK.acquire()
    try:
        yield
    finally:
        _LOCK.release()
