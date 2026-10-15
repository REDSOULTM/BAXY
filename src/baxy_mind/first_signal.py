"""Conditional first signal: estimate, formulate, correct.

The owner's hard bar is three seconds of dead silence. A turn that will
finish inside the budget stays quiet until the real reply. A turn that
will miss it gets one formulated in-progress sentence that never claims a
result, worded only once the request is still pending near that bar.
When verification denies, the person reads the correction.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


SILENCE_BUDGET_SECONDS = 3.0
# First hito after last visible output: strictly over 3 s, before a 1 s
# pulse would next tick at 4 s.
# Emit before the primary model work: that call alone was measured at ~2.5 s
# wall on this tree's model path, already next to the silence bar.
EARLY_SIGNAL_THRESHOLD_SECONDS = 1.5
# Tanda-06b (2026-09-24): worded as each model-path request began, the notice was
# a fourth decode beside the selector, the guard G and the prepared reply on a
# GPU that is compute-bound, so every one of them decoded slower for a sentence
# a turn that ends in time never needs. It is worded only when the request is
# still pending this long after it arrived: its own call took ~1 s under that
# load (median of the tanda's notices), so it still lands inside the budget.
NOTICE_AFTER_SECONDS = SILENCE_BUDGET_SECONDS - 1.0
PATH_RECOGNIZER = "explicit_effects"
PATH_CLOSED_CONVERSATION = "explicit_conversation"
PATH_MODEL = "model"
KIND_EARLY = "early"

_PATH_COST_SECONDS = {
    PATH_RECOGNIZER: 0.07,
    PATH_CLOSED_CONVERSATION: 0.9,
    PATH_MODEL: 2.5,
}
_EXTRA_STEP_SECONDS = 2.0
_SNIPPET_CHARS = 42
def estimate_turn_seconds(path: str, step_count: int = 1) -> float:
    """Two-line cost: known path plus extra compound steps."""

    cost = _PATH_COST_SECONDS.get(str(path or ""), _PATH_COST_SECONDS[PATH_MODEL])
    extra = max(0, int(step_count) - 1)
    return cost + extra * _EXTRA_STEP_SECONDS


def should_emit_early(path: str, step_count: int = 1) -> bool:
    """True only when the chosen path is predicted to breach the silence budget."""

    return estimate_turn_seconds(path, step_count) >= EARLY_SIGNAL_THRESHOLD_SECONDS




def turn_signal_payload(
    request_id: object,
    text: str,
    *,
    kind: str = KIND_EARLY,
) -> dict[str, object]:
    """Sidecar event. Same request id, different type so it cannot complete the turn."""

    return {
        "type": "turn.signal",
        "id": request_id,
        "kind": kind,
        "text": text,
        "asserted_result": False,
    }


class PendingTurnSignal:
    """The in-progress notice channel of one request, open until its result is written.

    The notice may start only once the request has been pending ``notice_after``
    seconds. Closing the channel (the request's result was written) retires a
    notice that has not started, cancels one being worded through the callbacks
    registered with ``on_close``, and drops any signal written after it.
    """

    def __init__(
        self,
        write: Callable[[dict[str, Any]], Any],
        *,
        notice_after: float = NOTICE_AFTER_SECONDS,
    ) -> None:
        self._write = write
        self._notice_at = time.monotonic() + max(0.0, float(notice_after))
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._on_close: list[Callable[[], Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        if not self._closed.is_set():
            self._write(payload)

    def notice_due(self) -> bool:
        """Wait until the notice may start: True if the request is still pending then."""

        # A timed wait may wake a clock tick early on Windows: wait out the rest.
        while (remaining := self._notice_at - time.monotonic()) > 0.0:
            if self._closed.wait(remaining):
                return False
        return not self._closed.is_set()

    def on_close(self, callback: Callable[[], Any]) -> None:
        with self._lock:
            if not self._closed.is_set():
                self._on_close.append(callback)
                return
        callback()

    def close(self) -> None:
        with self._lock:
            self._closed.set()
            callbacks, self._on_close = self._on_close, []
        for callback in callbacks:
            callback()
