"""The protocol's inbound side: the reader of stdin, the bounded serial lane that keeps model and catalog work one at
a time, and the writer that makes a shutdown acknowledgement terminal.
"""

from __future__ import annotations

import os
import queue
import stat
import sys
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any, Callable

from . import protocol


SERIAL_PENDING_REQUEST_LIMIT = 16
_BLOCKING_REQUEST_TYPES = frozenset(
    {
        "arguments",
        "catalog.configure",
        "computer.use.step",
        "message.compose",
        "narrate",
        "plan",
        "plan.ground",
        "turn.decide",
        "voice.speak",
        "voice.start",
        "voice.status",
        "voice.stop",
    }
)
_VOICE_MUTATION_REQUEST_TYPES = frozenset(
    {
        "voice.speak",
        "voice.start",
        "voice.stop",
    }
)


@dataclass(frozen=True)
class _ReadFailure:
    error: BaseException


@dataclass(frozen=True)
class _InboundMessage:
    message: dict[str, Any] | None


@dataclass(frozen=True)
class _DispatchFinished:
    result: int | None = None
    error: BaseException | None = None


class _AcknowledgedVoiceCancel(dict[str, Any]):
    """Internal replay marker that cannot be forged by a JSON object."""


class _LaneSubmission(str, Enum):
    """Closed outcomes for one bounded serial-lane admission."""

    ACCEPTED = "accepted"
    CLOSED = "closed"
    FULL = "full"


class _TerminalProtocolWriter:
    """Serialize replies and make a shutdown acknowledgement terminal."""

    def __init__(self, write_message: Callable[[dict], None]) -> None:
        self._write_message = write_message
        self._lock = threading.Lock()
        self._hello_written = threading.Event()
        self._terminal = False

    def write(self, message: dict) -> bool:
        with self._lock:
            if self._terminal:
                return False
            self._write_message(message)
            if message.get("type") == "hello":
                self._hello_written.set()
            if message.get("type") == "shutdown.ack":
                self._terminal = True
            return True

    def write_terminal(self, message: dict) -> bool:
        with self._lock:
            if self._terminal:
                return False
            self._write_message(message)
            self._terminal = True
            return True

    def wait_until_hello(self, timeout: float) -> bool:
        return self._hello_written.wait(timeout=max(0.0, timeout))


class _SerialRequestLane:
    """Keep model/catalog work serial while exposing its scheduling state."""

    def __init__(
        self,
        pending_limit: int | None = None,
    ) -> None:
        pending_limit = (
            SERIAL_PENDING_REQUEST_LIMIT if pending_limit is None else pending_limit
        )
        if pending_limit < 1:
            raise ValueError("pending_limit must be positive")
        self._condition = threading.Condition()
        self._pending: deque[dict[str, Any] | _ReadFailure] = deque()
        self._active: dict[str, Any] | None = None
        self._pending_limit = pending_limit
        self._normal_pending = 0
        self._blocking_work = 0
        self._voice_mutations = 0
        self._voice_mutation_sequence = 0
        self._replayed_voice_mutation_sequence = 0
        self._closed = False

    @staticmethod
    def _kind(message: dict[str, Any] | None) -> str:
        return str(message.get("type")) if message is not None else ""

    def submit(
        self,
        message: dict[str, Any] | _ReadFailure,
        *,
        reserved: bool = False,
    ) -> _LaneSubmission:
        with self._condition:
            if self._closed:
                return _LaneSubmission.CLOSED
            if (
                isinstance(message, dict)
                and not isinstance(message, _AcknowledgedVoiceCancel)
                and not reserved
                and self._normal_pending >= self._pending_limit
            ):
                return _LaneSubmission.FULL
            self._pending.append(message)
            if isinstance(message, dict) and not isinstance(
                message, _AcknowledgedVoiceCancel
            ):
                self._normal_pending += 1
                kind = self._kind(message)
                if kind in _BLOCKING_REQUEST_TYPES:
                    self._blocking_work += 1
                if kind in _VOICE_MUTATION_REQUEST_TYPES:
                    self._voice_mutations += 1
                    self._voice_mutation_sequence += 1
            self._condition.notify()
            return _LaneSubmission.ACCEPTED

    def voice_cancel_snapshot(self) -> tuple[bool, int | None]:
        """Capture urgency and the last prior voice mutation atomically."""

        with self._condition:
            replay_token = (
                self._voice_mutation_sequence if self._voice_mutations > 0 else None
            )
            return self._blocking_work > 0, replay_token

    def schedule_voice_cancel_replay(self, replay_token: int) -> bool:
        """Append one silent barrier for a pre-cancel mutation snapshot."""

        with self._condition:
            if self._closed or replay_token <= self._replayed_voice_mutation_sequence:
                return False
            self._pending.append(_AcknowledgedVoiceCancel({"type": "voice.cancel"}))
            self._replayed_voice_mutation_sequence = replay_token
            self._condition.notify()
            return True

    def close(self, *, drop_pending: bool) -> None:
        with self._condition:
            self._closed = True
            if drop_pending:
                self._pending.clear()
                self._normal_pending = 0
                active_kind = self._kind(self._active)
                self._blocking_work = int(active_kind in _BLOCKING_REQUEST_TYPES)
                self._voice_mutations = int(
                    active_kind in _VOICE_MUTATION_REQUEST_TYPES
                )
            self._condition.notify_all()

    def read_message(self) -> dict[str, Any] | None:
        with self._condition:
            while not self._pending and not self._closed:
                self._condition.wait()
            if not self._pending:
                return None
            item = self._pending.popleft()
            if isinstance(item, _ReadFailure):
                raise item.error
            if not isinstance(item, _AcknowledgedVoiceCancel):
                self._normal_pending -= 1
            self._active = item
            return item

    def finish(self, message: dict[str, Any]) -> None:
        with self._condition:
            if self._active is message:
                kind = self._kind(message)
                if kind in _BLOCKING_REQUEST_TYPES:
                    self._blocking_work -= 1
                if kind in _VOICE_MUTATION_REQUEST_TYPES:
                    self._voice_mutations -= 1
                self._active = None
            self._condition.notify_all()

    def has_blocking_work(self) -> bool:
        with self._condition:
            return self._blocking_work > 0


def _receive_protocol_messages(
    events: queue.Queue[_InboundMessage | _ReadFailure | _DispatchFinished],
    read_message: Callable[[], dict[str, Any] | None],
) -> None:
    """Read the one owned stdin stream without executing request handlers."""

    while True:
        try:
            message = read_message()
        except BaseException as error:  # noqa: BLE001 - relay to owner thread
            events.put(_ReadFailure(error))
            return
        events.put(_InboundMessage(message))
        if message is None or (message and str(message.get("type")) == "shutdown"):
            return


def _open_protocol_reader() -> Callable[[], dict[str, Any] | None]:
    """Own one incremental raw-stdin reader for the receiver lifetime."""

    descriptor = sys.stdin.fileno()
    if os.name == "nt" and stat.S_ISFIFO(os.fstat(descriptor).st_mode):
        # A synchronous pipe read can stall cold native DSP loading on Windows.
        # Python 3.12 supports nonblocking pipes; the bounded reader waits only
        # when no bytes are available, leaving EOF and real errors distinct.
        os.set_blocking(descriptor, False)
    stream = protocol._BoundedFileDescriptorLineReader(descriptor)
    return partial(protocol.read_message, stream)
