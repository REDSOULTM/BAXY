"""Wake-word detector orchestrator (Sprint R2 2026-05-18).

Public surface:
  - WakeDetector — composes openWakeWord (preferred) and Vosk
    (fallback) backends behind a single API.

Backend selection:
  - Default ("auto"): try openWakeWord first; on load failure,
    fall back to Vosk.
  - GEMMA4_WAKE_BACKEND env var: "oww" (force openWakeWord, no
    fallback), "vosk" (skip openWakeWord entirely), or "auto"
    (default).

The Vosk implementation lives in wake_vosk.py (VoskWakeDetector,
verbatim from the pre-R2 wake.py). The openWakeWord backend is
in wake_oww.py. This file re-exports the Vosk module-level
helpers + constants so existing imports keep working without
churn (controller.py, bench.py, server.py, test_wake_match.py,
test_wake_debounce.py all touch them by name).
"""
from __future__ import annotations

import logging
import os
from typing import Literal

import numpy as np

# Re-export the Vosk-side constants + helpers verbatim so external
# importers (controller, bench, server, tests) keep working.
from .wake_vosk import (  # noqa: F401  (re-exported intentionally)
    VOSK_MODEL_NAME,
    VOSK_MODEL_URL,
    VOSK_MODEL_DIR,
    WAKE_VOCAB,
    WAKE_DEBOUNCE_S,
    WAKE_MIN_CONFIDENCE,
    WakeCallback,
    model_exists,
    download_model,
    match_wake_phrase,
    VoskWakeDetector,
)

logger = logging.getLogger(__name__)


BackendName = Literal["auto", "oww", "vosk"]


class WakeDetector:
    """Composes openWakeWord (preferred) and Vosk (fallback)
    backends behind the same public API as the pre-R2
    VoskWakeDetector.

    Usage (unchanged for callers):
        det = WakeDetector(on_wake=lambda phrase, ts, tail, conf: ...)
        if det.load():
            det.feed(chunk)

    The `backend` argument (default "auto") controls which engines
    are tried. Env var GEMMA4_WAKE_BACKEND overrides the argument
    so the operator can force a backend in production without
    code changes.
    """

    def __init__(
        self,
        on_wake: WakeCallback,
        backend: BackendName = "vosk",
    ) -> None:
        # Sprint R2 default = "vosk". The audit
        # (scripts/wake_backend_audit.py) showed that pre-trained
        # openWakeWord models ("hey_jarvis") yield 0 fires on the
        # operator's "hey gemma" audio. Until a custom "hey gemma"
        # model exists (see docs/architecture/wake_custom_training_path.md),
        # Vosk stays the only useful default.
        #
        # Operators who want to benchmark openWakeWord against
        # alternate audio can set GEMMA4_WAKE_BACKEND=auto or oww.
        env_override = os.environ.get("GEMMA4_WAKE_BACKEND")
        if env_override in ("auto", "oww", "vosk"):
            backend = env_override  # type: ignore[assignment]
        self._backend_name: BackendName = backend
        # _active must be set BEFORE _on_wake because the
        # _on_wake setter forwards to it.
        self._active: VoskWakeDetector | object | None = None
        self._active_kind: str = "none"
        self._on_wake = on_wake
        self.last_error: str | None = None

    # --- public API (preserves old WakeDetector surface) ----------

    def load(self) -> bool:
        if self._backend_name in ("auto", "oww"):
            try:
                from .wake_oww import OpenWakeWordDetector  # lazy import
                oww = OpenWakeWordDetector(on_wake=self._on_wake)
                if oww.load():
                    self._active = oww
                    self._active_kind = "oww"
                    self.last_error = None
                    logger.info("WakeDetector backend: openWakeWord")
                    return True
                else:
                    logger.warning(
                        "openWakeWord load failed (%s); falling back to Vosk",
                        oww.last_error,
                    )
            except Exception as exc:
                logger.warning("openWakeWord init failed: %s", exc)

        if self._backend_name == "oww":
            # User explicitly asked for oww only; no fallback.
            self.last_error = "openWakeWord requested but failed to load"
            return False

        # Vosk fallback (also the path for backend="vosk").
        vosk = VoskWakeDetector(on_wake=self._on_wake)
        if vosk.load():
            self._active = vosk
            self._active_kind = "vosk"
            self.last_error = None
            logger.info("WakeDetector backend: Vosk")
            return True
        self.last_error = vosk.last_error
        return False

    def feed(self, chunk: np.ndarray) -> None:
        if self._active is None:
            return
        self._active.feed(chunk)

    def is_loaded(self) -> bool:
        if self._active is None:
            return False
        return self._active.is_loaded()

    def reset(self) -> None:
        if self._active is not None:
            self._active.reset()

    def unload(self) -> None:
        if self._active is not None:
            self._active.unload()

    # --- introspection helpers (NOT part of the pre-R2 API) ------

    @property
    def backend(self) -> str:
        """Which backend is actually active. "oww", "vosk", or
        "none" if .load() hasn't been called or failed."""
        return self._active_kind

    # --- legacy attribute shims ----------------------------------
    # Some call-sites (test_gx_features.py, testaudio_analysis.py)
    # mutate Vosk internals directly via attributes like `_rec`,
    # `_loaded`, `_on_wake`, `_last_fire_at`,
    # `_samples_since_last_result`. The orchestrator forwards those
    # reads/writes to a lazily-instantiated Vosk backend so the
    # external code keeps working without changes.

    def _ensure_vosk_active(self) -> None:
        """Lazy-init a VoskWakeDetector when a caller pokes private
        Vosk attributes before .load() runs (test fixtures do this
        to bypass model loading)."""
        if self._active is None:
            self._active = VoskWakeDetector(on_wake=self.__dict__.get(
                "_on_wake_value", lambda *a, **kw: None,
            ))
            self._active_kind = "vosk"

    @property
    def _on_wake(self):  # type: ignore[override]
        return self.__dict__.get("_on_wake_value")

    @_on_wake.setter
    def _on_wake(self, value):
        self.__dict__["_on_wake_value"] = value
        if self._active is not None:
            try:
                self._active._on_wake = value  # type: ignore[attr-defined]
            except Exception:
                pass

    @property
    def _rec(self):
        if self._active is None:
            return None
        return getattr(self._active, "_rec", None)

    @_rec.setter
    def _rec(self, value):
        self._ensure_vosk_active()
        try:
            self._active._rec = value  # type: ignore[attr-defined]
        except Exception:
            pass

    @property
    def _loaded(self) -> bool:
        if self._active is None:
            return False
        return getattr(self._active, "_loaded", False)

    @_loaded.setter
    def _loaded(self, value: bool) -> None:
        self._ensure_vosk_active()
        try:
            self._active._loaded = bool(value)  # type: ignore[attr-defined]
        except Exception:
            pass

    @property
    def _last_fire_at(self) -> float:
        if self._active is None:
            return 0.0
        return getattr(self._active, "_last_fire_at", 0.0)

    @_last_fire_at.setter
    def _last_fire_at(self, value: float) -> None:
        self._ensure_vosk_active()
        try:
            self._active._last_fire_at = float(value)  # type: ignore[attr-defined]
        except Exception:
            pass

    @property
    def _samples_since_last_result(self) -> int:
        if self._active is None:
            return 0
        return getattr(self._active, "_samples_since_last_result", 0)

    @_samples_since_last_result.setter
    def _samples_since_last_result(self, value: int) -> None:
        self._ensure_vosk_active()
        try:
            self._active._samples_since_last_result = int(value)  # type: ignore[attr-defined]
        except Exception:
            pass
