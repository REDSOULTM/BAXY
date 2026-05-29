"""In-process event bus that the agent publishes to and the FastAPI server
subscribes to. Decouples agent threads from the WS broadcast loop.

Contract: events are plain dicts that match the WS payload union in the UI's
`types.ts`. The bus does not validate — that's the caller's responsibility —
because the agent module is the source of truth for what those payloads mean.

Threading: the agent runs in one or more sync threads. Each WS connection on
the server side gets its own subscriber (a bounded queue). Publish is sync
and non-blocking: if a subscriber's queue is full, the oldest message is
dropped to keep the producer from stalling. That's the right tradeoff for a
UI bus — better to lose a stale metric than to deadlock the agent.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

# bounded so a stalled WS connection can't grow memory without limit
_MAX_QUEUE = 256

# synchronous listener: called inline on every publish. used by the log
# recorder so every event gets written to disk before the WS broadcast
# fan-out runs. listeners MUST be fast (under 1ms) and exception-safe;
# anything slow goes through subscribe() + its own consumer thread.
EventListener = Callable[[dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[queue.Queue[dict[str, Any]]] = set()
        self._listeners: list[EventListener] = []

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=_MAX_QUEUE)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def add_listener(self, fn: EventListener) -> None:
        """Register a synchronous callback fired on every publish, in order
        of registration, BEFORE the WS fan-out. Exceptions are swallowed."""
        with self._lock:
            if fn not in self._listeners:
                self._listeners.append(fn)

    def remove_listener(self, fn: EventListener) -> None:
        with self._lock:
            try:
                self._listeners.remove(fn)
            except ValueError:
                pass

    def publish(self, event: dict[str, Any]) -> None:
        """Fan-out to all live subscribers. Drops oldest on overflow so a
        stuck subscriber never blocks the publisher. Sync listeners (logs,
        metrics) run before the WS queue fan-out."""
        with self._lock:
            listeners = list(self._listeners)
            targets = list(self._subscribers)
        for fn in listeners:
            try:
                fn(event)
            except Exception as exc:
                logger.debug("event bus listener raised: %s", exc)
        for q in targets:
            try:
                q.put_nowait(event)
            except queue.Full:
                # drop the oldest queued event for this subscriber so newer
                # state stays fresh. swallowing the resulting queue.Empty
                # handles the race where another thread drained it first.
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(event)
                except queue.Full:
                    logger.debug("event bus subscriber still full after drop; skipping")

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)


# module-level singleton — both agent and server import from here so they share
# the same instance without having to pass it through call chains.
BUS = EventBus()
