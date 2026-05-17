"""NLI service singleton — multilingual zero-shot entailment.

Shared by:
  - capability_classifier (Bug 1): user_input → capability label
  - grounding_gate (Bug 3): reply vs tool_events evidence

The model (mDeBERTa-v3-base-xnli-multilingual) is ~280MB, ~1200ms per
inference on CPU. To stay within voice latency budget (4-5s/turn) we
NEVER call it inline on the hot path; instead:

  - Capability classifier: launched in a background thread parallel to
    the planner. The planner uses its own keyword/embedding decision
    immediately; the NLI result merges later via callback if it arrives
    in time, otherwise it lands in cache for the NEXT similar turn.

  - Grounding gate: scheduled async after the reply is generated; if NLI
    detects contradiction with tool_events, the verdict is logged in the
    lesson store so future similar turns get warned via RAG. The CURRENT
    reply has already been spoken — we cannot block it inline at this
    latency tier.

Both share a single loaded pipeline + LRU cache by sha256(premise + hyp).

The service degrades gracefully: if transformers/the model is unavailable,
classify() returns None (callers must handle None as "unknown").
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

_log = logging.getLogger(__name__)


# Pre-import huggingface_hub at module load (main thread) so that no other
# thread later races us into a half-initialized state. Observed bug:
# faster_whisper.WhisperModel(...) raised "cannot import name 'logging' from
# huggingface_hub" when our background NLI warmup loaded transformers
# concurrently. Forcing the import here, in the main thread, on the same
# thread that imports this module, prevents the race. Safe and cheap (~10ms).
try:
    import huggingface_hub as _hf_hub  # noqa: F401
    from huggingface_hub import logging as _hf_logging  # noqa: F401
except Exception:
    # If huggingface_hub is missing entirely, the NLI service will
    # short-circuit later (degrades to legacy router).
    pass


_MODEL_NAME = os.environ.get(
    "GEMMA4_NLI_MODEL",
    "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
)
_MAX_CACHE = 512


class _NLIService:
    """Thread-safe singleton wrapper around a zero-shot NLI pipeline."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipe: Any = None  # transformers pipeline; lazy-init
        self._load_attempted = False
        self._load_failed = False
        self._cache: OrderedDict[str, dict[str, float]] = OrderedDict()

    # ---------- internal loader ----------

    def _ensure_loaded(self) -> bool:
        """Returns True if the pipeline is ready. Loads on first call."""
        if self._pipe is not None:
            return True
        if self._load_failed:
            return False
        with self._lock:
            if self._pipe is not None:
                return True
            if self._load_failed:
                return False
            self._load_attempted = True
            try:
                # Serialize heavy ML imports across threads. Prevents the
                # "cannot import name 'logging' from huggingface_hub" race
                # with the voice stack (faster_whisper).
                from ._ml_import_lock import ml_imports
                with ml_imports():
                    from transformers import pipeline  # type: ignore
                    _log.info("loading NLI model %s...", _MODEL_NAME)
                    t0 = time.time()
                    self._pipe = pipeline(
                        "zero-shot-classification",
                        model=_MODEL_NAME,
                    )
                _log.info("NLI model loaded in %.1fs", time.time() - t0)
                return True
            except Exception as exc:  # noqa: BLE001 — degrade gracefully
                _log.warning("NLI service unavailable: %s", exc)
                self._load_failed = True
                return False

    def warmup_async(self) -> None:
        """Fire-and-forget background load. Safe to call multiple times."""
        if self._pipe is not None or self._load_failed:
            return
        t = threading.Thread(target=self._ensure_loaded, daemon=True,
                              name="nli-warmup")
        t.start()

    @property
    def ready(self) -> bool:
        return self._pipe is not None

    # ---------- cache ----------

    @staticmethod
    def _cache_key(text: str, labels: tuple[str, ...]) -> str:
        h = hashlib.sha256()
        h.update(text.encode("utf-8", "ignore"))
        h.update(b"\0")
        h.update("|".join(labels).encode("utf-8", "ignore"))
        return h.hexdigest()

    def _cache_get(self, key: str) -> dict[str, float] | None:
        with self._lock:
            v = self._cache.get(key)
            if v is not None:
                # touch (LRU)
                self._cache.move_to_end(key)
            return v

    def _cache_put(self, key: str, value: dict[str, float]) -> None:
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > _MAX_CACHE:
                self._cache.popitem(last=False)

    # ---------- public API ----------

    def classify_sync(
        self,
        text: str,
        labels: list[str],
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, float] | None:
        """Run zero-shot classification synchronously, with optional timeout.

        Returns {label: score} dict (sums ~1.0) or None if unavailable/timeout.
        Uses cache hit fast-path.
        """
        if not text or not labels:
            return None
        labels_t = tuple(labels)
        key = self._cache_key(text, labels_t)
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        if not self._ensure_loaded():
            return None
        if timeout_sec is not None and timeout_sec > 0:
            return self._run_with_timeout(text, list(labels_t), timeout_sec, key)
        return self._run_now(text, list(labels_t), key)

    def classify_async(
        self,
        text: str,
        labels: list[str],
        callback: Callable[[dict[str, float] | None], None] | None = None,
    ) -> None:
        """Fire-and-forget. Result lands in cache; optional callback receives it.

        The callback runs in the worker thread; keep it short and side-effect
        only (logging, telemetry, lesson_store write). Do NOT mutate hot-path
        state from inside it.
        """
        if not text or not labels:
            if callback:
                callback(None)
            return
        labels_t = tuple(labels)
        key = self._cache_key(text, labels_t)
        cached = self._cache_get(key)
        if cached is not None:
            if callback:
                callback(cached)
            return

        def _worker() -> None:
            if not self._ensure_loaded():
                if callback:
                    callback(None)
                return
            result = self._run_now(text, list(labels_t), key)
            if callback:
                callback(result)

        threading.Thread(target=_worker, daemon=True, name="nli-async").start()

    # ---------- internals ----------

    def _run_now(self, text: str, labels: list[str], key: str) -> dict[str, float] | None:
        try:
            t0 = time.time()
            result = self._pipe(text, candidate_labels=labels)  # type: ignore[misc]
            elapsed_ms = (time.time() - t0) * 1000
            _log.debug("NLI %.0fms text=%r top=%r",
                       elapsed_ms, text[:60], result.get("labels", [None])[0])
            scores = {lbl: float(s) for lbl, s in
                      zip(result["labels"], result["scores"])}
            self._cache_put(key, scores)
            return scores
        except Exception as exc:  # noqa: BLE001
            _log.warning("NLI inference failed: %s", exc)
            return None

    def _run_with_timeout(
        self, text: str, labels: list[str], timeout_sec: float, key: str,
    ) -> dict[str, float] | None:
        result: dict[str, Any] = {"value": None}
        done = threading.Event()

        def _t() -> None:
            try:
                result["value"] = self._run_now(text, labels, key)
            finally:
                done.set()

        worker = threading.Thread(target=_t, daemon=True, name="nli-sync-timeout")
        worker.start()
        if not done.wait(timeout=timeout_sec):
            _log.debug("NLI sync timed out after %.2fs", timeout_sec)
            return None
        return result["value"]


_SINGLETON = _NLIService()


def get_nli_service() -> _NLIService:
    return _SINGLETON
