"""Characterization tests for the loopback llama-server HTTP adapter."""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from baxy_mind.llm_transport import (
    ChatCompletionCancellation,
    ChatCompletionCancelled,
    ChatCompletionConnectionPool,
    post_chat_completion,
)


def _response(payload: object) -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


def _http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "http://127.0.0.1:39000/v1/chat/completions",
        status,
        "test",
        {},
        None,
    )


def _connection_with_response(response: object) -> MagicMock:
    connection = MagicMock()
    connection.sock = MagicMock()
    connection.getresponse.return_value = response
    return connection


def test_transport_reacquires_endpoint_and_timeout_for_each_attempt() -> None:
    endpoints = iter(
        [
            "http://127.0.0.1:39001",
            "http://127.0.0.1:39002",
        ]
    )
    timeouts = iter([0.4, 0.2, 0.1])
    endpoint_calls = 0
    timeout_calls = 0

    def endpoint_for_attempt() -> str:
        nonlocal endpoint_calls
        endpoint_calls += 1
        return next(endpoints)

    def timeout_for_attempt() -> float:
        nonlocal timeout_calls
        timeout_calls += 1
        return next(timeouts)

    with patch(
        "baxy_mind.llm_transport.urllib.request.urlopen",
        side_effect=[_http_error(503), _response({"choices": []})],
    ) as open_url:
        result = post_chat_completion(
            {"messages": [{"role": "user", "content": "hola"}]},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=timeout_for_attempt,
        )

    assert result == {"choices": []}
    assert endpoint_calls == 2
    assert timeout_calls == 3
    assert [call.args[0].full_url for call in open_url.call_args_list] == [
        "http://127.0.0.1:39001/v1/chat/completions",
        "http://127.0.0.1:39002/v1/chat/completions",
    ]
    assert [call.kwargs["timeout"] for call in open_url.call_args_list] == [
        0.4,
        0.2,
    ]
    assert (
        open_url.call_args_list[0].args[0].data
        == open_url.call_args_list[1].args[0].data
    )


def test_transport_rejects_a_success_that_finishes_after_its_budget() -> None:
    timeout_for_attempt = MagicMock(
        side_effect=[0.04, TimeoutError("request budget expired")]
    )

    with (
        patch(
            "baxy_mind.llm_transport.urllib.request.urlopen",
            return_value=_response({"choices": []}),
        ) as open_url,
        pytest.raises(TimeoutError, match="budget expired"),
    ):
        post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=timeout_for_attempt,
        )

    open_url.assert_called_once()
    assert timeout_for_attempt.call_count == 2


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transport_retries_only_the_closed_http_status_set(status: int) -> None:
    with patch(
        "baxy_mind.llm_transport.urllib.request.urlopen",
        side_effect=[_http_error(status), _response({"ok": True})],
    ) as open_url:
        result = post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
        )

    assert result == {"ok": True}
    assert open_url.call_count == 2


@pytest.mark.parametrize("status", [200, 400, 401, 404, 409, 501])
def test_transport_does_not_retry_other_http_statuses(status: int) -> None:
    error = _http_error(status)
    with (
        patch(
            "baxy_mind.llm_transport.urllib.request.urlopen",
            side_effect=error,
        ) as open_url,
        pytest.raises(urllib.error.HTTPError) as raised,
    ):
        post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
        )

    assert raised.value is error
    assert open_url.call_count == 1


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("direct timeout"),
        ConnectionError("direct connection failure"),
        urllib.error.URLError(TimeoutError("wrapped timeout")),
        urllib.error.URLError(ConnectionError("wrapped connection failure")),
    ],
)
def test_transport_retries_only_transient_connection_failures(
    failure: Exception,
) -> None:
    with patch(
        "baxy_mind.llm_transport.urllib.request.urlopen",
        side_effect=[failure, _response({"ok": True})],
    ) as open_url:
        result = post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
        )

    assert result == {"ok": True}
    assert open_url.call_count == 2


def test_transport_does_not_retry_non_transient_url_failure() -> None:
    error = urllib.error.URLError(ValueError("invalid local request"))
    with (
        patch(
            "baxy_mind.llm_transport.urllib.request.urlopen",
            side_effect=error,
        ) as open_url,
        pytest.raises(urllib.error.URLError) as raised,
    ):
        post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
        )

    assert raised.value is error
    assert open_url.call_count == 1


def test_transport_never_retries_a_runtime_lifecycle_failure() -> None:
    closed = RuntimeError("llama-server runtime is closed")
    endpoint_for_attempt = MagicMock(side_effect=closed)
    timeout_for_attempt = MagicMock()

    with (
        patch("baxy_mind.llm_transport.urllib.request.urlopen") as open_url,
        pytest.raises(RuntimeError) as raised,
    ):
        post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=timeout_for_attempt,
        )

    assert raised.value is closed
    endpoint_for_attempt.assert_called_once_with()
    timeout_for_attempt.assert_not_called()
    open_url.assert_not_called()


@pytest.mark.parametrize("max_attempts", [0, 3, -1])
def test_transport_rejects_an_unbounded_attempt_count_before_io(
    max_attempts: int,
) -> None:
    endpoint_for_attempt = MagicMock()
    timeout_for_attempt = MagicMock()
    with pytest.raises(ValueError, match="intentos HTTP"):
        post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=timeout_for_attempt,
            max_attempts=max_attempts,
        )

    endpoint_for_attempt.assert_not_called()
    timeout_for_attempt.assert_not_called()


def test_transport_serializes_once_before_acquiring_runtime_state() -> None:
    endpoint_for_attempt = MagicMock()
    timeout_for_attempt = MagicMock()

    with pytest.raises(TypeError):
        post_chat_completion(
            {"notJson": object()},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=timeout_for_attempt,
        )

    endpoint_for_attempt.assert_not_called()
    timeout_for_attempt.assert_not_called()


def test_transport_does_not_retry_a_malformed_success_body() -> None:
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b"{"

    with (
        patch(
            "baxy_mind.llm_transport.urllib.request.urlopen",
            return_value=response,
        ) as open_url,
        pytest.raises(json.JSONDecodeError),
    ):
        post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
        )

    assert open_url.call_count == 1


def test_cancellable_transport_closes_socket_and_never_retries() -> None:
    cancellation = ChatCompletionCancellation()
    request_started = threading.Event()
    socket_closed = threading.Event()
    fake_socket = MagicMock()

    class BlockingConnection:
        sock = fake_socket

        def connect(self) -> None:
            return None

        def request(self, *_args: object, **_kwargs: object) -> None:
            request_started.set()

        def getresponse(self) -> None:
            assert socket_closed.wait(timeout=1.0)
            raise ConnectionAbortedError("socket closed by cancellation")

        def close(self) -> None:
            socket_closed.set()

    endpoint_for_attempt = MagicMock(
        return_value="http://127.0.0.1:39000"
    )
    timeout_for_attempt = MagicMock(return_value=1.0)
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            return_value=BlockingConnection(),
        ) as connection_type,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=timeout_for_attempt,
            cancellation=cancellation,
        )
        assert request_started.wait(timeout=1.0)
        cancellation.cancel()
        with pytest.raises(ChatCompletionCancelled):
            future.result(timeout=1.0)

    connection_type.assert_called_once_with(
        "127.0.0.1",
        39000,
        timeout=1.0,
    )
    fake_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)
    endpoint_for_attempt.assert_called_once_with()
    timeout_for_attempt.assert_called_once_with()


def test_cancelled_transport_stops_before_runtime_or_io() -> None:
    cancellation = ChatCompletionCancellation()
    cancellation.cancel()
    endpoint_for_attempt = MagicMock()
    timeout_for_attempt = MagicMock()

    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection"
        ) as connection_type,
        pytest.raises(ChatCompletionCancelled),
    ):
        post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=timeout_for_attempt,
            cancellation=cancellation,
        )

    endpoint_for_attempt.assert_not_called()
    timeout_for_attempt.assert_not_called()
    connection_type.assert_not_called()


def test_cancellable_transport_never_reconnects_after_last_pre_send_check() -> None:
    before_request = threading.Event()
    continue_request = threading.Event()

    class GatedCancellation(ChatCompletionCancellation):
        def __init__(self) -> None:
            super().__init__()
            self._checks = 0

        def raise_if_cancelled(self) -> None:
            super().raise_if_cancelled()
            self._checks += 1
            if self._checks == 3:
                before_request.set()
                assert continue_request.wait(timeout=1.0)

    class Connection:
        def __init__(self) -> None:
            self.sock = None
            self.auto_open = True
            self.connect_calls = 0
            self.sent = False

        def connect(self) -> None:
            self.connect_calls += 1
            self.sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            if self.sock is None:
                if self.auto_open:
                    self.connect()
                else:
                    raise http.client.NotConnected()
            self.sent = True

        def close(self) -> None:
            self.sock = None

    cancellation = GatedCancellation()
    connection = Connection()
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            return_value=connection,
        ),
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
            max_attempts=1,
            cancellation=cancellation,
        )
        assert before_request.wait(timeout=1.0)
        cancellation.cancel()
        continue_request.set()
        with pytest.raises(ChatCompletionCancelled):
            future.result(timeout=1.0)

    assert connection.connect_calls == 1
    assert connection.sent is False


def test_pool_reuses_one_connection_without_cross_request_content() -> None:
    pool = ChatCompletionConnectionPool(max_connections=3)
    requests: list[dict[str, object]] = []

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def __init__(self, marker: str) -> None:
            self._marker = marker

        def read(self) -> bytes:
            return json.dumps({"marker": self._marker}).encode("utf-8")

        def close(self) -> None:
            return None

    class Connection:
        def __init__(self) -> None:
            self.sock = MagicMock()
            self._marker = ""

        def request(
            self,
            _method: str,
            _path: str,
            *,
            body: bytes,
            headers: dict[str, str],
        ) -> None:
            assert headers == {"Content-Type": "application/json"}
            payload = json.loads(body.decode("utf-8"))
            requests.append(payload)
            self._marker = str(payload["marker"])

        def getresponse(self) -> Response:
            return Response(self._marker)

        def close(self) -> None:
            self.sock = None

    connection = Connection()
    with patch(
        "baxy_mind.llm_transport.http.client.HTTPConnection",
        return_value=connection,
    ) as connection_type:
        first = post_chat_completion(
            {"marker": "first"},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
            connection_pool=pool,
        )
        second = post_chat_completion(
            {"marker": "second"},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
            connection_pool=pool,
        )

    pool.close()
    assert first == {"marker": "first"}
    assert second == {"marker": "second"}
    assert requests == [{"marker": "first"}, {"marker": "second"}]
    connection_type.assert_called_once_with(
        "127.0.0.1",
        39000,
        timeout=1.0,
    )


def test_pool_discards_connection_after_malformed_json_response() -> None:
    pool = ChatCompletionConnectionPool(max_connections=3)

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def close(self) -> None:
            return None

    class Connection:
        def __init__(self, body: bytes) -> None:
            self.sock = MagicMock()
            self._body = body

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> Response:
            return Response(self._body)

        def close(self) -> None:
            self.sock = None

    malformed = Connection(b"{")
    replacement = Connection(b'{"ok":true}')
    with patch(
        "baxy_mind.llm_transport.http.client.HTTPConnection",
        side_effect=[malformed, replacement],
    ) as connection_type:
        with pytest.raises(json.JSONDecodeError):
            post_chat_completion(
                {"messages": []},
                endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
                timeout_for_attempt=lambda: 1.0,
                connection_pool=pool,
            )
        recovered = post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
            connection_pool=pool,
        )

    pool.close()
    assert recovered == {"ok": True}
    assert connection_type.call_count == 2
    assert malformed.sock is None


def test_pool_discards_a_cancelled_connection_before_next_request() -> None:
    pool = ChatCompletionConnectionPool(max_connections=3)
    cancellation = ChatCompletionCancellation()
    request_started = threading.Event()
    socket_closed = threading.Event()
    cancelled_socket = MagicMock()

    class BlockingConnection:
        sock = cancelled_socket

        def request(self, *_args: object, **_kwargs: object) -> None:
            request_started.set()

        def getresponse(self) -> None:
            assert socket_closed.wait(timeout=1.0)
            raise ConnectionAbortedError("cancelled")

        def close(self) -> None:
            socket_closed.set()

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def read(self) -> bytes:
            return b'{"ok":true}'

        def close(self) -> None:
            return None

    class ReplacementConnection:
        sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            self.sock = None

    endpoint_for_attempt = MagicMock(
        return_value="http://127.0.0.1:39000"
    )
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            side_effect=[BlockingConnection(), ReplacementConnection()],
        ) as connection_type,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=lambda: 1.0,
            cancellation=cancellation,
            connection_pool=pool,
        )
        assert request_started.wait(timeout=1.0)
        cancellation.cancel()
        with pytest.raises(ChatCompletionCancelled):
            future.result(timeout=1.0)
        recovered = post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=lambda: 1.0,
            connection_pool=pool,
        )

    pool.close()
    assert recovered == {"ok": True}
    assert connection_type.call_count == 2
    assert endpoint_for_attempt.call_count == 2
    cancelled_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)


def test_pool_cancellation_interrupts_wait_for_an_exclusive_lease() -> None:
    waiter_registered = threading.Event()

    class ObservableCancellation(ChatCompletionCancellation):
        def _register_wait_condition(
            self,
            condition: threading.Condition,
        ) -> None:
            super()._register_wait_condition(condition)
            waiter_registered.set()

    cancellation = ObservableCancellation()
    pool = ChatCompletionConnectionPool(max_connections=1)
    occupied_connection = MagicMock()
    occupied_connection.sock = MagicMock()
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            return_value=occupied_connection,
        ) as connection_type,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        occupied = pool.acquire("http://127.0.0.1:39000", 1.0)
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
            max_attempts=1,
            cancellation=cancellation,
            connection_pool=pool,
        )
        assert waiter_registered.wait(timeout=1.0)
        time.sleep(0.02)
        assert future.done() is False
        started = time.monotonic()
        cancellation.cancel()
        with pytest.raises(ChatCompletionCancelled):
            future.result(timeout=0.2)
        cancellation_latency = time.monotonic() - started
        pool.release(occupied, reusable=False)

    pool.close()
    assert cancellation_latency < 0.2
    connection_type.assert_called_once_with(
        "127.0.0.1",
        39000,
        timeout=1.0,
    )


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionResetError("stale keep-alive socket"),
        http.client.RemoteDisconnected("remote closed keep-alive socket"),
        http.client.ResponseNotReady("stale HTTP response state"),
    ],
)
def test_pool_discards_connection_error_then_retries_on_a_fresh_socket(
    failure: BaseException,
) -> None:
    pool = ChatCompletionConnectionPool(max_connections=3)
    failed_socket = MagicMock()

    class FailedConnection:
        sock = failed_socket

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> None:
            raise failure

        def close(self) -> None:
            self.sock = None

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def read(self) -> bytes:
            return b'{"ok":true}'

        def close(self) -> None:
            return None

    class RecoveredConnection:
        sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            self.sock = None

    endpoint_for_attempt = MagicMock(
        return_value="http://127.0.0.1:39000"
    )
    timeout_for_attempt = MagicMock(return_value=1.0)
    with patch(
        "baxy_mind.llm_transport.http.client.HTTPConnection",
        side_effect=[FailedConnection(), RecoveredConnection()],
    ) as connection_type:
        result = post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=timeout_for_attempt,
            connection_pool=pool,
        )

    pool.close()
    assert result == {"ok": True}
    assert connection_type.call_count == 2
    assert endpoint_for_attempt.call_count == 2
    assert timeout_for_attempt.call_count == 3


def test_pool_retry_drains_multiple_stale_idle_connections() -> None:
    pool = ChatCompletionConnectionPool(max_connections=3)

    class StaleConnection:
        def __init__(self) -> None:
            self.sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> None:
            raise ConnectionResetError("stale keep-alive socket")

        def close(self) -> None:
            self.sock = None

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def read(self) -> bytes:
            return b'{"ok":true}'

        def close(self) -> None:
            return None

    class ReplacementConnection:
        sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            self.sock = None

    stale_connections = [StaleConnection() for _ in range(3)]
    replacement = ReplacementConnection()
    endpoint = "http://127.0.0.1:39000"
    with patch(
        "baxy_mind.llm_transport.http.client.HTTPConnection",
        side_effect=[*stale_connections, replacement],
    ) as connection_type:
        leases = [pool.acquire(endpoint, 1.0) for _ in range(3)]
        for lease in leases:
            pool.release(lease, reusable=True)
        result = post_chat_completion(
            {"messages": []},
            endpoint_for_attempt=lambda: endpoint,
            timeout_for_attempt=lambda: 1.0,
            connection_pool=pool,
        )

    pool.close()
    assert result == {"ok": True}
    assert connection_type.call_count == 4
    assert all(connection.sock is None for connection in stale_connections)


def test_pool_close_revokes_lease_before_it_can_connect_or_send() -> None:
    acquired = threading.Event()
    continue_after_close = threading.Event()

    class BlockingAcquirePool(ChatCompletionConnectionPool):
        def acquire(
            self,
            endpoint: str,
            timeout: float,
            **kwargs: object,
        ) -> object:
            entry = super().acquire(endpoint, timeout, **kwargs)
            acquired.set()
            assert continue_after_close.wait(timeout=1.0)
            return entry

    class Connection:
        def __init__(self) -> None:
            self.sock = None
            self.connect_calls = 0
            self.request_calls = 0

        def connect(self) -> None:
            self.connect_calls += 1
            self.sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            self.request_calls += 1

        def close(self) -> None:
            self.sock = None

    pool = BlockingAcquirePool(max_connections=1)
    connection = Connection()
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            return_value=connection,
        ),
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 1.0,
            max_attempts=1,
            connection_pool=pool,
        )
        assert acquired.wait(timeout=1.0)
        pool.close()
        continue_after_close.set()
        with pytest.raises(ConnectionError):
            future.result(timeout=1.0)

    assert connection.connect_calls == 0
    assert connection.request_calls == 0


def test_pool_close_interrupts_a_blocked_request_without_waiting_for_timeout() -> None:
    request_started = threading.Event()
    request_interrupted = threading.Event()
    active_socket = MagicMock()
    active_socket.shutdown.side_effect = (
        lambda _operation: request_interrupted.set()
    )

    class Connection:
        def __init__(self) -> None:
            self.sock = active_socket

        def request(self, *_args: object, **_kwargs: object) -> None:
            request_started.set()
            assert request_interrupted.wait(timeout=1.0)
            raise ConnectionAbortedError("socket revoked")

        def close(self) -> None:
            self.sock = None

    pool = ChatCompletionConnectionPool(max_connections=1)
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            return_value=Connection(),
        ),
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 2.0,
            max_attempts=1,
            connection_pool=pool,
        )
        assert request_started.wait(timeout=1.0)
        started = time.monotonic()
        pool.close()
        close_latency = time.monotonic() - started
        with pytest.raises(ConnectionError):
            future.result(timeout=1.0)

    assert close_latency < 0.2
    active_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)


def test_pool_never_publishes_response_revoked_during_body_read() -> None:
    read_started = threading.Event()
    release_read = threading.Event()

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def read(self) -> bytes:
            read_started.set()
            assert release_read.wait(timeout=1.0)
            return b'{"ok":true}'

        def close(self) -> None:
            return None

    class Connection:
        def __init__(self) -> None:
            self.sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            self.sock = None

    pool = ChatCompletionConnectionPool(max_connections=1)
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            return_value=Connection(),
        ),
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
            timeout_for_attempt=lambda: 2.0,
            max_attempts=1,
            connection_pool=pool,
        )
        assert read_started.wait(timeout=1.0)
        pool.close()
        release_read.set()
        with pytest.raises(ConnectionError):
            future.result(timeout=1.0)


def test_pool_retries_when_revoked_between_send_and_response() -> None:
    response_waiting = threading.Event()
    continue_response = threading.Event()

    class RevokedConnection:
        def __init__(self) -> None:
            self.sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> None:
            response_waiting.set()
            assert continue_response.wait(timeout=1.0)
            raise http.client.ResponseNotReady()

        def close(self) -> None:
            self.sock = None

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def read(self) -> bytes:
            return b'{"ok":true}'

        def close(self) -> None:
            return None

    class ReplacementConnection:
        sock = MagicMock()

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            self.sock = None

    pool = ChatCompletionConnectionPool(max_connections=1)
    endpoint_for_attempt = MagicMock(
        return_value="http://127.0.0.1:39000"
    )
    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            side_effect=[RevokedConnection(), ReplacementConnection()],
        ) as connection_type,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        future = executor.submit(
            post_chat_completion,
            {"messages": []},
            endpoint_for_attempt=endpoint_for_attempt,
            timeout_for_attempt=lambda: 2.0,
            connection_pool=pool,
        )
        assert response_waiting.wait(timeout=1.0)
        pool.invalidate()
        continue_response.set()
        result = future.result(timeout=1.0)

    pool.close()
    assert result == {"ok": True}
    assert connection_type.call_count == 2
    assert endpoint_for_attempt.call_count == 2


def test_pool_bounds_concurrency_to_three_exclusive_connections() -> None:
    pool = ChatCompletionConnectionPool(max_connections=3)
    release_responses = threading.Event()
    three_started = threading.Event()
    state_lock = threading.Lock()
    state = {"active": 0, "maximum": 0}
    created: list[object] = []

    class Response:
        status = 200
        reason = "OK"
        headers: dict[str, str] = {}
        will_close = False

        def __init__(self, connection: Connection, marker: str) -> None:
            self._connection = connection
            self._marker = marker

        def read(self) -> bytes:
            assert release_responses.wait(timeout=2.0)
            with state_lock:
                state["active"] -= 1
                self._connection.in_use = False
            return json.dumps({"marker": self._marker}).encode("utf-8")

        def close(self) -> None:
            return None

    class Connection:
        def __init__(self) -> None:
            self.sock = MagicMock()
            self.in_use = False
            self.marker = ""

        def request(
            self,
            _method: str,
            _path: str,
            *,
            body: bytes,
            headers: dict[str, str],
        ) -> None:
            del headers
            with state_lock:
                assert self.in_use is False
                self.in_use = True
                state["active"] += 1
                state["maximum"] = max(
                    state["maximum"],
                    state["active"],
                )
                if state["active"] == 3:
                    three_started.set()
            self.marker = str(json.loads(body.decode("utf-8"))["marker"])

        def getresponse(self) -> Response:
            return Response(self, self.marker)

        def close(self) -> None:
            self.sock = None

    def connection_factory(
        _host: str,
        _port: int,
        *,
        timeout: float,
    ) -> Connection:
        del timeout
        connection = Connection()
        created.append(connection)
        return connection

    with (
        patch(
            "baxy_mind.llm_transport.http.client.HTTPConnection",
            side_effect=connection_factory,
        ),
        ThreadPoolExecutor(max_workers=6) as executor,
    ):
        futures = [
            executor.submit(
                post_chat_completion,
                {"marker": str(index)},
                endpoint_for_attempt=lambda: "http://127.0.0.1:39000",
                timeout_for_attempt=lambda: 3.0,
                connection_pool=pool,
            )
            for index in range(6)
        ]
        assert three_started.wait(timeout=1.0)
        assert len(created) == 3
        release_responses.set()
        results = [future.result(timeout=3.0) for future in futures]

    pool.close()
    assert state["maximum"] == 3
    assert state["active"] == 0
    assert len(created) == 3
    assert sorted(result["marker"] for result in results) == [
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
