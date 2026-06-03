"""Deterministic camera event watchers for later L2 use."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CameraEvent:
    kind: str
    timestamp_s: float
    detail: str = ""


class FacePresenceWatcher:
    """Emit enter/leave events from face counts with glitch-tolerant debounce.

    MediaPipe drops a frame here and there, so a noisy presence stream looks
    like ``present, present, absent, present, present``. The earlier debounce
    reset its candidate on every contrary frame, so a single dropped frame
    restarted the timer and the event could never fire. Here the candidate
    survives brief contrary blips: the timer only restarts when the contrary
    state itself persists past ``glitch_tolerance_s``.
    """

    def __init__(self, debounce_s: float = 0.75, glitch_tolerance_s: float = 0.2) -> None:
        if debounce_s < 0:
            raise ValueError("debounce_s must be >= 0")
        if glitch_tolerance_s < 0:
            raise ValueError("glitch_tolerance_s must be >= 0")
        self.debounce_s = float(debounce_s)
        self.glitch_tolerance_s = float(glitch_tolerance_s)
        self._present = False
        self._candidate: bool | None = None
        self._candidate_since: float | None = None
        self._last_contrary_since: float | None = None
        self._last_t: float | None = None

    def update(self, face_count: int, timestamp_s: float) -> CameraEvent | None:
        # Guard against non-monotonic timestamps (perf_counter is monotonic, but
        # callers may feed replayed/test streams). A backward jump is ignored.
        if self._last_t is not None and timestamp_s < self._last_t:
            return None
        self._last_t = timestamp_s
        now_present = face_count > 0

        if now_present == self._present:
            # Frame agrees with the committed state. This may be a glitch that
            # interrupts an in-flight transition; tolerate it briefly instead of
            # discarding the candidate outright.
            if self._candidate is not None:
                if self._last_contrary_since is None:
                    self._last_contrary_since = timestamp_s
                elif timestamp_s - self._last_contrary_since > self.glitch_tolerance_s:
                    # The contrary (= committed) state held long enough that the
                    # transition is no longer credible; abandon the candidate.
                    self._candidate = None
                    self._candidate_since = None
                    self._last_contrary_since = None
            return None

        # Frame supports a transition away from the committed state.
        self._last_contrary_since = None
        if self._candidate != now_present:
            self._candidate = now_present
            self._candidate_since = timestamp_s
            return None
        if self._candidate_since is not None and timestamp_s - self._candidate_since >= self.debounce_s:
            self._present = now_present
            self._candidate = None
            self._candidate_since = None
            return CameraEvent("face_entered" if now_present else "face_left", timestamp_s)
        return None

