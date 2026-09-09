"""Bounded HTTP transport for the loopback llama-server chat endpoint.

Process ownership, endpoint lifecycle and request budgets belong to
``LlmRuntime``.  This adapter owns only the wire concerns: serialize one
payload, acquire the current endpoint and timeout for every attempt, and retry
the closed set of transient loopback failures.
"""

from __future__ import annotations

import http.client
import io
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit


RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
LLAMA_SERVER_KEEPALIVE_SECONDS = 5.0
POOL_IDLE_SECONDS = 4.0
POOL_MAX_USES = 90


def _endpoint_target(endpoint: str) -> tuple[str, int, str]:
    target = urlsplit(endpoint)
    if target.scheme != "http" or target.hostname is None:
        raise ValueError("endpoint HTTP local inválido")
    port = target.port if target.port is not None else 80
    path_prefix = target.path.rstrip("/")
    return target.hostname, port, f"{path_prefix}/v1/chat/completions"


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


class ChatCompletionConnectionPool:
    """Bounded, exclusive HTTP/1.1 connections for one LLM runtime."""

    def __init__(
        self,
        *,
        max_connections: int = 3,
        idle_seconds: float = POOL_IDLE_SECONDS,
        max_uses: int = POOL_MAX_USES,
    ) -> None:
        if max_connections < 1:
            raise ValueError("cantidad de conexiones HTTP inválida")
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

    def acquire(
        self,
        endpoint: str,
        timeout: float,
        *,
        cancellation: ChatCompletionCancellation | None = None,
        require_fresh: bool = False,
    ) -> _PooledConnection:
        """Lease one connection exclusively, preferring the current thread."""

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
                        self._active[id(entry)] = entry
                        return entry

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
                        self._active[id(entry)] = entry
                        return entry

                    remaining = deadline - now
                    if remaining <= 0.0:
                        raise TimeoutError(
                            "se agotó la espera del pool HTTP local"
                        )
                    self._condition.wait(timeout=remaining)
        finally:
            if cancellation is not None:
                cancellation._unregister_wait_condition(self._condition)

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

    def release(
        self,
        entry: _PooledConnection,
        *,
        reusable: bool,
    ) -> None:
        """Return a complete response connection or invalidate it."""

        close_connection = False
        with self._condition:
            if self._active.pop(id(entry), None) is None:
                return
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
) -> tuple[bytes, bool]:
    """Complete one response on an exclusively owned HTTP connection."""

    _, _, path = _endpoint_target(endpoint)
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


def _post_pooled(
    connection_pool: ChatCompletionConnectionPool,
    endpoint: str,
    request_data: bytes,
    timeout: float,
    cancellation: ChatCompletionCancellation | None,
    *,
    require_fresh: bool,
) -> dict[str, Any]:
    """Lease one exclusive connection and return it only after valid JSON."""

    started = time.monotonic()
    entry = connection_pool.acquire(
        endpoint,
        timeout,
        cancellation=cancellation,
        require_fresh=require_fresh,
    )
    response_reusable = False
    valid_response = False
    cancellation_attached = False
    try:
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
        connection_pool.release(
            entry,
            reusable=(
                valid_response
                and response_reusable
                and cancellation_allows_reuse
            ),
        )


def post_chat_completion(
    payload: dict[str, Any],
    *,
    endpoint_for_attempt: Callable[[], str],
    timeout_for_attempt: Callable[[], float],
    max_attempts: int = 2,
    cancellation: ChatCompletionCancellation | None = None,
    connection_pool: ChatCompletionConnectionPool | None = None,
) -> dict[str, Any]:
    """Post one local chat request with an explicitly bounded retry.

    The endpoint and timeout callbacks run before every wire attempt.  This is
    intentional: the runtime can replace a dead owned process between attempts
    and every retry remains inside the caller's current monotonic budget.
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
                    request_data,
                    timeout,
                    cancellation,
                    require_fresh=attempt > 0,
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
