"""Bounded HTTP transport for the loopback llama-server chat endpoint.

Process ownership, endpoint lifecycle and request budgets belong to
``LlmRuntime``.  This adapter owns only the wire concerns: serialize one
payload, acquire the current endpoint and timeout for every attempt, and retry
the closed set of transient loopback failures.
"""

from __future__ import annotations

import contextlib
import http.client
import io
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
LLAMA_SERVER_KEEPALIVE_SECONDS = 5.0
POOL_IDLE_SECONDS = 4.0
POOL_MAX_USES = 90
SLOT_RESTORE_SECONDS = 30.0


def _endpoint_target(endpoint: str, route: str = "/v1/chat/completions") -> tuple[str, int, str]:
    target = urlsplit(endpoint)
    if target.scheme != "http" or target.hostname is None:
        raise ValueError("endpoint HTTP local inválido")
    port = target.port if target.port is not None else 80
    path_prefix = target.path.rstrip("/")
    return target.hostname, port, f"{path_prefix}{route}"


@dataclass(frozen=True)
class SlotState:
    """The saved state of a server slot that a request is evaluated from, whatever that slot evaluated before.

    ``path`` is the file in the server's ``--slot-save-path``; ``prefix`` is the ``/completion`` request that
    evaluates the prompt prefix the state holds, used once to build it.
    """

    path: Path
    prefix: dict[str, Any]


class _PooledConnection:
    def __init__(
        self,
        endpoint: str,
        connection: http.client.HTTPConnection,
        generation: int,
        owner_thread: int,
    ) -> None:
        self.endpoint = endpoint
        self.connection = connection
        self.generation = generation
        self.owner_thread = owner_thread
        self.idle_since = 0.0
        self.uses = 1
        self.slot: int | None = None
        # Pooled requests connect explicitly. Disabling HTTPConnection's
        # implicit reconnect prevents a close/revoke race from opening a new
        # socket after the lease has been invalidated.
        self.connection.auto_open = False
        self._send_lock = threading.Lock()
        self._revoked = False

    def raise_if_revoked(self) -> None:
        with self._send_lock:
            if self._revoked:
                raise ConnectionError("lease HTTP local invalidado")

    def request(
        self,
        path: str,
        request_data: bytes,
        cancellation: ChatCompletionCancellation | None,
    ) -> None:
        """Start a request only while hard invalidation cannot race it."""

        with self._send_lock:
            if self._revoked:
                raise ConnectionError("lease HTTP local invalidado")
            if cancellation is not None:
                cancellation.raise_if_cancelled()
        try:
            self.connection.request(
                "POST",
                path,
                body=request_data,
                headers={"Content-Type": "application/json"},
            )
        except (
            http.client.CannotSendHeader,
            http.client.CannotSendRequest,
            http.client.NotConnected,
        ) as error:
            raise ConnectionError("lease HTTP local desconectado") from error

    def revoke(self) -> None:
        """Prevent reconnect/send and close the currently visible socket."""

        with self._send_lock:
            self._revoked = True
            active_socket = self.connection.sock
        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        try:
            self.connection.close()
        except OSError:
            pass


def _common_prefix_length(first: bytes, second: bytes) -> int:
    length = min(len(first), len(second))
    low, high = 0, length
    while low < high:
        middle = (low + high + 1) // 2
        if first[:middle] == second[:middle]:
            low = middle
        else:
            high = middle - 1
    return low


class ChatCompletionConnectionPool:
    """Bounded, exclusive HTTP/1.1 connections for one LLM runtime.

    With ``server_slots`` the pool also owns the server's slots, one per
    connection: every lease carries one slot, sent as ``id_slot``, so a request
    lands where its prompt prefix is still cached. Tandas 05e/06 (2026-09-24):
    left to the server, the tool selector — the fourth of four requests a model
    turn starts together on three slots — waited ~0.8 s for a connection and
    then took the slot the progress notice had just left, reusing 3 of its
    ~2.6k prompt tokens in all 46 turns. The last slot is therefore kept for
    tool-selection requests; the others take, among the free remaining slots,
    the one whose previous request shares the longest prefix with theirs.
    """

    def __init__(
        self,
        *,
        max_connections: int = 3,
        server_slots: bool = False,
        idle_seconds: float = POOL_IDLE_SECONDS,
        max_uses: int = POOL_MAX_USES,
    ) -> None:
        if max_connections < 1 or (server_slots and max_connections < 2):
            raise ValueError("cantidad de conexiones HTTP inválida")
        self._server_slots = server_slots
        self._busy_slots: set[int] = set()
        self._slot_requests = [b""] * max_connections
        # Release order, not clock time: Windows' clock ticks every ~16 ms.
        self._slot_released = [0] * max_connections
        self._releases = 0
        # A slot whose response was abandoned (cancelled, failed) may still be
        # decoding on the server until it notices; a pinned request would wait.
        self._slot_abandoned = [False] * max_connections
        # The saved state (``SlotState.path``) each slot was put back in after its last request.
        self._slot_holds: list[Path | None] = [None] * max_connections
        # States the server refused to build (no ``--slot-save-path``, a save it cannot write).
        self._refused_states: set[Path] = set()
        self._maximum = max_connections
        self._idle_seconds = min(
            max(0.0, idle_seconds),
            LLAMA_SERVER_KEEPALIVE_SECONDS,
        )
        self._max_uses = max(1, max_uses)
        self._condition = threading.Condition()
        self._idle: list[_PooledConnection] = []
        self._active: dict[int, _PooledConnection] = {}
        self._total = 0
        self._generation = 0
        self._closed = False

    def _free_slot(self, reserved: bool, request_data: bytes) -> int | None:
        """The slot this request may take now, or None while its slots are busy."""

        last = self._maximum - 1
        free = [
            slot
            for slot in ((last,) if reserved else range(last))
            if slot not in self._busy_slots
        ]
        if not free:
            return None
        return max(
            free,
            key=lambda slot: (
                not self._slot_abandoned[slot],
                _common_prefix_length(request_data, self._slot_requests[slot]),
                -self._slot_released[slot],
            ),
        )

    def acquire(
        self,
        endpoint: str,
        timeout: float,
        *,
        cancellation: ChatCompletionCancellation | None = None,
        require_fresh: bool = False,
        reserved: bool = False,
        request_data: bytes = b"",
    ) -> _PooledConnection:
        """Lease one connection exclusively, preferring the current thread.

        With server slots the lease also owns one slot (``entry.slot``): the
        reserved one for ``reserved`` requests, otherwise a shared one chosen by
        the prefix of ``request_data``.
        """

        hostname, port, _ = _endpoint_target(endpoint)
        owner_thread = threading.get_ident()
        maximum_wait = max(0.0, float(timeout))
        deadline = time.monotonic() + maximum_wait
        if cancellation is not None:
            cancellation._register_wait_condition(self._condition)
        try:
            with self._condition:
                while True:
                    if cancellation is not None:
                        cancellation.raise_if_cancelled()
                    if self._closed:
                        raise RuntimeError("pool HTTP local cerrado")
                    now = time.monotonic()
                    retained: list[_PooledConnection] = []
                    for entry in self._idle:
                        expired = now - entry.idle_since >= self._idle_seconds
                        if (
                            expired
                            or entry.endpoint != endpoint
                            or entry.generation != self._generation
                            or entry.uses >= self._max_uses
                        ):
                            entry.connection.close()
                            self._total -= 1
                        else:
                            retained.append(entry)
                    self._idle = retained

                    if require_fresh and self._idle:
                        discarded = self._idle
                        self._idle = []
                        self._total -= len(discarded)
                        for entry in discarded:
                            entry.connection.close()

                    slot = (
                        self._free_slot(reserved, request_data)
                        if self._server_slots
                        else None
                    )
                    if self._server_slots and slot is None:
                        remaining = deadline - now
                        if remaining <= 0.0:
                            raise TimeoutError(
                                "se agotó la espera del pool HTTP local"
                            )
                        self._condition.wait(timeout=remaining)
                        continue

                    preferred_index = None
                    if not require_fresh:
                        preferred_index = next(
                            (
                                index
                                for index in range(
                                    len(self._idle) - 1,
                                    -1,
                                    -1,
                                )
                                if (
                                    self._idle[index].owner_thread
                                    == owner_thread
                                )
                            ),
                            None,
                        )
                        if preferred_index is None and self._idle:
                            preferred_index = len(self._idle) - 1
                    if preferred_index is not None:
                        entry = self._idle.pop(preferred_index)
                        entry.owner_thread = owner_thread
                        entry.uses += 1
                        return self._lease(entry, slot, request_data)

                    if self._total < self._maximum:
                        connection = http.client.HTTPConnection(
                            hostname,
                            port,
                            timeout=maximum_wait,
                        )
                        entry = _PooledConnection(
                            endpoint,
                            connection,
                            self._generation,
                            owner_thread,
                        )
                        self._total += 1
                        return self._lease(entry, slot, request_data)

                    remaining = deadline - now
                    if remaining <= 0.0:
                        raise TimeoutError(
                            "se agotó la espera del pool HTTP local"
                        )
                    self._condition.wait(timeout=remaining)
        finally:
            if cancellation is not None:
                cancellation._unregister_wait_condition(self._condition)

    def _lease(
        self,
        entry: _PooledConnection,
        slot: int | None,
        request_data: bytes,
    ) -> _PooledConnection:
        entry.slot = slot
        if slot is not None:
            self._busy_slots.add(slot)
            self._slot_requests[slot] = request_data
        self._active[id(entry)] = entry
        return entry

    def retire_generation(self) -> None:
        """Drain potentially stale sockets without aborting valid responses."""

        with self._condition:
            self._generation += 1
            idle = self._idle
            self._idle = []
            self._total -= len(idle)
            self._condition.notify_all()
        for entry in idle:
            entry.connection.close()

    def refuse_slot_state(self, path: Path) -> None:
        with self._condition:
            self._refused_states.add(path)

    def refuses_slot_state(self, path: Path) -> bool:
        with self._condition:
            return path in self._refused_states

    def take_slot_hold(self, slot: int) -> Path | None:
        """The saved state the leased ``slot`` holds, forgotten now that a request will use the slot."""

        with self._condition:
            held, self._slot_holds[slot] = self._slot_holds[slot], None
            return held

    def release(
        self,
        entry: _PooledConnection,
        *,
        reusable: bool,
        holds: Path | None = None,
    ) -> None:
        """Return a complete response connection or invalidate it; ``holds`` is the state its slot was put in."""

        close_connection = False
        with self._condition:
            if self._active.pop(id(entry), None) is None:
                return
            if entry.slot is not None:
                current = reusable and not self._closed and entry.generation == self._generation
                self._slot_holds[entry.slot] = holds if current else None
                self._busy_slots.discard(entry.slot)
                self._releases += 1
                self._slot_released[entry.slot] = self._releases
                self._slot_abandoned[entry.slot] = not reusable
                entry.slot = None
                # Waiters may want different slots: wake them all.
                self._condition.notify_all()
            reusable = (
                reusable
                and not self._closed
                and entry.generation == self._generation
                and entry.connection.sock is not None
                and entry.uses < self._max_uses
            )
            if reusable:
                entry.idle_since = time.monotonic()
                self._idle.append(entry)
            else:
                self._total -= 1
                close_connection = True
            self._condition.notify()
        if close_connection:
            entry.connection.close()

    def invalidate(self) -> None:
        """Close every connection without preventing a later server restart."""

        with self._condition:
            self._generation += 1
            idle = self._idle
            self._idle = []
            active = list(self._active.values())
            self._total -= len(idle)
            # A replaced server starts with empty slots.
            self._slot_holds = [None] * len(self._slot_holds)
            self._refused_states = set()
            for entry in [*idle, *active]:
                entry.revoke()
            self._condition.notify_all()

    def close(self) -> None:
        """Close idle and active sockets and reject future acquisitions."""

        with self._condition:
            if self._closed:
                return
            self._closed = True
        self.invalidate()


class ChatCompletionCancelled(Exception):
    """Raised when a speculative local inference is deliberately abandoned."""


class ChatCompletionCancellation:
    """Own the one live socket used by a cancellable completion request."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._connection: http.client.HTTPConnection | None = None
        self._wait_conditions: set[threading.Condition] = set()

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ChatCompletionCancelled("inferencia especulativa cancelada")

    def attach(self, connection: http.client.HTTPConnection) -> None:
        with self._lock:
            if self._cancelled:
                raise ChatCompletionCancelled(
                    "inferencia especulativa cancelada"
                )
            self._connection = connection

    def detach(self, connection: http.client.HTTPConnection) -> bool:
        with self._lock:
            if self._connection is connection:
                self._connection = None
            return not self._cancelled

    def _register_wait_condition(
        self,
        condition: threading.Condition,
    ) -> None:
        with self._lock:
            if self._cancelled:
                raise ChatCompletionCancelled(
                    "inferencia especulativa cancelada"
                )
            self._wait_conditions.add(condition)

    def _unregister_wait_condition(
        self,
        condition: threading.Condition,
    ) -> None:
        with self._lock:
            self._wait_conditions.discard(condition)

    def cancel(self) -> None:
        """Signal cancellation and make the active loopback socket observable."""

        with self._lock:
            self._cancelled = True
            connection = self._connection
            self._connection = None
            wait_conditions = tuple(self._wait_conditions)
        for condition in wait_conditions:
            with condition:
                condition.notify_all()
        if connection is not None:
            active_socket = connection.sock
        else:
            active_socket = None
        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def _post_on_connection(
    connection: http.client.HTTPConnection,
    endpoint: str,
    request_data: bytes,
    cancellation: ChatCompletionCancellation | None,
    pooled_entry: _PooledConnection | None = None,
    route: str = "/v1/chat/completions",
) -> tuple[bytes, bool]:
    """Complete one response on an exclusively owned HTTP connection."""

    _, _, path = _endpoint_target(endpoint, route)
    try:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if connection.sock is None:
            if pooled_entry is not None:
                pooled_entry.raise_if_revoked()
            # Connect explicitly so cancellation owns the concrete socket before
            # waiting for llama-server's non-streaming response.
            connection.connect()
        if pooled_entry is not None:
            pooled_entry.raise_if_revoked()
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if pooled_entry is None:
            connection.request(
                "POST",
                path,
                body=request_data,
                headers={"Content-Type": "application/json"},
            )
        else:
            pooled_entry.request(path, request_data, cancellation)
        response = connection.getresponse()
        try:
            response_data = response.read()
            status = response.status
            reason = response.reason
            headers = response.headers
            reusable = not response.will_close
        finally:
            response.close()
        if pooled_entry is not None:
            pooled_entry.raise_if_revoked()
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if not 200 <= status < 300:
            raise urllib.error.HTTPError(
                f"{endpoint}{path}",
                status,
                reason,
                headers,
                io.BytesIO(response_data),
            )
        return response_data, reusable
    except Exception as error:
        if cancellation is not None and cancellation.cancelled:
            raise ChatCompletionCancelled(
                "inferencia especulativa cancelada"
            ) from error
        if pooled_entry is not None:
            try:
                pooled_entry.raise_if_revoked()
            except ConnectionError as revoked:
                # HTTPConnection can surface state errors such as
                # ResponseNotReady when hard invalidation wins between send
                # and response acquisition. Keep the established transient
                # retry contract instead of leaking an internal state error.
                raise revoked from error
        raise


def _post_cancellable(
    endpoint: str,
    request_data: bytes,
    timeout: float,
    cancellation: ChatCompletionCancellation,
) -> bytes:
    """Post through a disposable socket that another thread can close."""

    hostname, port, _ = _endpoint_target(endpoint)
    connection = http.client.HTTPConnection(
        hostname,
        port,
        timeout=timeout,
    )
    # Connection is explicit so a cancellation between the final check and
    # ``request`` cannot silently auto-open a replacement socket.
    connection.auto_open = False
    cancellation.attach(connection)
    try:
        response_data, _ = _post_on_connection(
            connection,
            endpoint,
            request_data,
            cancellation,
        )
        return response_data
    finally:
        cancellation.detach(connection)
        connection.close()


def _restore_slot_state(
    connection_pool: ChatCompletionConnectionPool,
    entry: _PooledConnection,
    endpoint: str,
    state: SlotState,
    cancellation: ChatCompletionCancellation | None,
) -> bool:
    """Put the leased slot in ``state``: built and saved the first time, restored every later time.

    Estabilización A (r31-m1): with the server's own prompt cache, a hybrid model resumes from the last context
    checkpoint that fits, and where that checkpoint lies depends on the length of the slot's previous request. The
    same request then evaluated 161 or 216 tokens and the decider's first word flipped on a 0.004-0.17 nat tie.
    A refused restore drops the file, and that request is evaluated whole (another state, so possibly another
    reply); the next one builds the state again. A refused build means this server cannot keep the state: its
    requests go without one, as before the state existed.
    """

    def post(route: str, body: dict[str, Any]) -> None:
        _post_on_connection(
            entry.connection,
            endpoint,
            json.dumps(body).encode("utf-8"),
            cancellation,
            entry,
            route=route,
        )

    action = f"/slots/{entry.slot}?action="
    saved = state.path.is_file()
    try:
        if saved:
            post(action + "restore", {"filename": state.path.name})
        else:
            post("/completion", {**state.prefix, "id_slot": entry.slot})
            post(action + "save", {"filename": state.path.name})
    except urllib.error.HTTPError as error:
        error.close()
        if saved:
            # A file the server cannot read (a save cut short) is built again by the next request.
            with contextlib.suppress(OSError):
                state.path.unlink(missing_ok=True)
        else:
            connection_pool.refuse_slot_state(state.path)
        return False
    return True


def _restore_and_release(
    connection_pool: ChatCompletionConnectionPool,
    entry: _PooledConnection,
    endpoint: str,
    state: SlotState,
) -> None:
    """Once the reply is handed over, put its slot back in ``state`` so the next request finds it there.

    The restore reads the whole saved prefix (≈110 ms measured for the decider's 6 777 tokens); done here it is off
    the turn's path, and a request that arrives first waits for the slot as it would for the restore.
    """

    restored = False
    try:
        entry.connection.timeout = SLOT_RESTORE_SECONDS
        if entry.connection.sock is not None:
            entry.connection.sock.settimeout(SLOT_RESTORE_SECONDS)
        restored = _restore_slot_state(connection_pool, entry, endpoint, state, None)
    except Exception:  # noqa: BLE001 - the next request restores the slot itself
        restored = False
    finally:
        connection_pool.release(entry, reusable=restored, holds=state.path if restored else None)


def prepare_slot_state(
    connection_pool: ChatCompletionConnectionPool,
    endpoint: str,
    state: SlotState,
    *,
    timeout: float,
    cancellation: ChatCompletionCancellation | None = None,
) -> None:
    """Put the reserved slot in ``state`` with no request after it (the decider's warmup)."""

    entry = connection_pool.acquire(endpoint, timeout, cancellation=cancellation, reserved=True)
    held = connection_pool.take_slot_hold(entry.slot) if entry.slot is not None else None
    ready = held == state.path
    try:
        if not ready and entry.slot is not None and not connection_pool.refuses_slot_state(state.path):
            entry.connection.timeout = timeout
            if cancellation is not None:
                cancellation.attach(entry.connection)
            try:
                ready = _restore_slot_state(connection_pool, entry, endpoint, state, cancellation)
            finally:
                if cancellation is not None:
                    ready = cancellation.detach(entry.connection) and ready
    finally:
        connection_pool.release(entry, reusable=ready, holds=state.path if ready else None)


def _post_pooled(
    connection_pool: ChatCompletionConnectionPool,
    endpoint: str,
    payload: dict[str, Any],
    request_data: bytes,
    timeout: float,
    cancellation: ChatCompletionCancellation | None,
    *,
    require_fresh: bool,
    reserved_slot: bool,
    slot_state: SlotState | None = None,
) -> dict[str, Any]:
    """Lease one exclusive connection and return it only after valid JSON."""

    started = time.monotonic()
    entry = connection_pool.acquire(
        endpoint,
        timeout,
        cancellation=cancellation,
        require_fresh=require_fresh,
        reserved=reserved_slot,
        request_data=request_data,
    )
    response_reusable = False
    valid_response = False
    cancellation_attached = False
    if slot_state is not None and connection_pool.refuses_slot_state(slot_state.path):
        slot_state = None
    try:
        if entry.slot is not None:
            request_data = json.dumps({**payload, "id_slot": entry.slot}).encode("utf-8")
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0.0:
            raise TimeoutError("se agotó la espera del pool HTTP local")
        entry.raise_if_revoked()
        entry.connection.timeout = remaining
        active_socket = entry.connection.sock
        if active_socket is not None:
            try:
                active_socket.settimeout(remaining)
            except OSError as error:
                raise ConnectionError(
                    "la conexión HTTP persistente dejó de estar disponible"
                ) from error
        if cancellation is not None:
            cancellation.attach(entry.connection)
            cancellation_attached = True
        held = connection_pool.take_slot_hold(entry.slot) if entry.slot is not None else None
        if slot_state is not None and entry.slot is not None and held != slot_state.path:
            _restore_slot_state(connection_pool, entry, endpoint, slot_state, cancellation)
        response_data, response_reusable = _post_on_connection(
            entry.connection,
            endpoint,
            request_data,
            cancellation,
            entry,
        )
        result = json.loads(response_data.decode("utf-8"))
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        # This lock acquisition is the publication linearization point:
        # a hard invalidation that wins first rejects the completed body.
        entry.raise_if_revoked()
        valid_response = True
        return result
    except (
        TimeoutError,
        ConnectionError,
        urllib.error.HTTPError,
        http.client.HTTPException,
    ):
        # One stale socket can mean the server retired an entire keep-alive
        # generation. Drain idle siblings and let in-flight valid responses
        # finish before their old generation is closed on release.
        connection_pool.retire_generation()
        raise
    finally:
        cancellation_allows_reuse = True
        if cancellation is not None and cancellation_attached:
            cancellation_allows_reuse = cancellation.detach(entry.connection)
        reusable = valid_response and response_reusable and cancellation_allows_reuse
        if (
            reusable
            and slot_state is not None
            and entry.slot is not None
            and not connection_pool.refuses_slot_state(slot_state.path)
        ):
            threading.Thread(
                target=_restore_and_release,
                args=(connection_pool, entry, endpoint, slot_state),
                name="baxy-slot-restore",
                daemon=True,
            ).start()
        else:
            connection_pool.release(entry, reusable=reusable)


def post_chat_completion(
    payload: dict[str, Any],
    *,
    endpoint_for_attempt: Callable[[], str],
    timeout_for_attempt: Callable[[], float],
    max_attempts: int = 2,
    cancellation: ChatCompletionCancellation | None = None,
    connection_pool: ChatCompletionConnectionPool | None = None,
    reserved_slot: bool = False,
    slot_state: SlotState | None = None,
) -> dict[str, Any]:
    """Post one local chat request with an explicitly bounded retry.

    The endpoint and timeout callbacks run before every wire attempt.  This is
    intentional: the runtime can replace a dead owned process between attempts
    and every retry remains inside the caller's current monotonic budget.
    ``reserved_slot`` asks a slot-owning pool for its reserved server slot;
    ``slot_state`` is the saved state that slot is put in first (``_restore_slot_state``).
    """

    if max_attempts not in {1, 2}:
        raise ValueError("cantidad de intentos HTTP inválida")

    request_data = json.dumps(payload).encode("utf-8")
    for attempt in range(max_attempts):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        endpoint = endpoint_for_attempt()
        try:
            timeout = timeout_for_attempt()
            if connection_pool is not None:
                result = _post_pooled(
                    connection_pool,
                    endpoint,
                    payload,
                    request_data,
                    timeout,
                    cancellation,
                    require_fresh=attempt > 0,
                    reserved_slot=reserved_slot,
                    slot_state=slot_state,
                )
            elif cancellation is None:
                request = urllib.request.Request(
                    f"{endpoint}/v1/chat/completions",
                    data=request_data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(
                    request,
                    timeout=timeout,
                ) as response:
                    response_data = response.read()
            else:
                response_data = _post_cancellable(
                    endpoint,
                    request_data,
                    timeout,
                    cancellation,
                )
            if connection_pool is None:
                result = json.loads(response_data.decode("utf-8"))
        except urllib.error.HTTPError as error:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            if attempt + 1 < max_attempts and error.code in RETRYABLE_HTTP_STATUSES:
                error.close()
                continue
            raise
        except (
            TimeoutError,
            ConnectionError,
            urllib.error.URLError,
            http.client.HTTPException,
        ) as error:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            reason = error.reason if isinstance(error, urllib.error.URLError) else error
            if attempt + 1 < max_attempts and isinstance(
                reason,
                (TimeoutError, ConnectionError, http.client.HTTPException),
            ):
                continue
            raise
        # Socket timeouts bound individual blocking operations, not the whole
        # response. Re-read the runtime's monotonic budget before publishing a
        # successful inference so a slow/trickling body cannot become late state.
        timeout_for_attempt()
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        return result
    raise RuntimeError("reintento HTTP local inalcanzable")
