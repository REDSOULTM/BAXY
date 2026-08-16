import hashlib
import io
import json
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import baxy_mind.router as router_module
import baxy_mind.router_worker as router_worker_module
from baxy_mind.router import (
    DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_INTERACTIVE_ENCODER_TIMEOUT_SECONDS,
    MODEL_NAME,
    MODEL_REVISION,
    IntentRouter,
    ProcessIntentRouter,
    RequestBudgetEncoder,
    SemanticEncoder,
    _encoder_snapshot_identity,
    _load_frozen_pool,
    _verified_encoder_snapshot,
)
from baxy_mind.planner import PlannerCatalog


class _FakePipe:
    def __init__(self):
        self.payload = ""

    def write(self, value):
        self.payload += value

    @staticmethod
    def flush():
        return None


class _FakeProcess:
    def __init__(self):
        self.stdin = _FakePipe()
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout):
        del timeout
        self.returncode = 0
        return 0


def process_router(*, ready=True):
    router = ProcessIntentRouter.__new__(ProcessIntentRouter)
    router._process = _FakeProcess()
    router._responses = queue.Queue()
    router._lock = threading.Lock()
    router._is_ready = ready
    router._failed = False
    router._failure = ""
    router._next_request_id = 1
    router._closed = threading.Event()
    return router


class ProcessIntentRouterReadinessTests(unittest.TestCase):
    def test_cold_worker_can_be_observed_without_blocking_or_failing(self):
        router = process_router(ready=False)

        self.assertFalse(router.try_ready())
        router._responses.put({"type": "ready"})
        self.assertTrue(router.try_ready())
        self.assertTrue(router.try_ready())
        self.assertFalse(router._failed)

    def test_invalid_ready_message_permanently_retires_channel(self):
        router = process_router(ready=False)
        router._responses.put({"type": "ready", "unexpected": True})

        self.assertFalse(router.try_ready(0.1))
        self.assertTrue(router._failed)
        self.assertTrue(router._closed.is_set())
        self.assertTrue(router._process.killed)

        router._responses.put({"type": "ready"})
        self.assertFalse(router.try_ready(0.1))
        self.assertEqual(router._responses.qsize(), 1)

    def test_readiness_probe_does_not_wait_past_busy_channel(self):
        router = process_router(ready=False)
        router._lock.acquire()
        try:
            before = router_module.time.monotonic()
            self.assertFalse(router.try_ready(0.01))
            elapsed = router_module.time.monotonic() - before
        finally:
            router._lock.release()

        self.assertLess(elapsed, 0.1)
        self.assertFalse(router._failed)

    def test_readiness_probe_rejects_nonfinite_timeouts_before_locking(self):
        router = process_router()

        for timeout in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(timeout=timeout):
                self.assertFalse(router.try_ready(timeout))

    def test_encode_uses_strictly_monotonic_request_ids(self):
        router = process_router()
        router._responses.put(
            {"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]}
        )
        first = router.encode(["uno"], timeout=1.0)
        router._responses.put(
            {"type": "encode.result", "id": 2, "rows": [[0.0, 1.0]]}
        )
        second = router.encode(("dos",), timeout=1.0)

        np.testing.assert_array_equal(first, [[1.0, 0.0]])
        np.testing.assert_array_equal(second, [[0.0, 1.0]])
        requests = [
            json.loads(line)
            for line in router._process.stdin.payload.splitlines()
        ]
        self.assertEqual([request["id"] for request in requests], [1, 2])
        self.assertEqual(
            [request["type"] for request in requests],
            ["encode", "encode"],
        )

    def test_timeout_retires_channel_and_late_reply_is_never_reused(self):
        router = process_router()

        with self.assertRaises(TimeoutError):
            router.encode(["uno"], timeout=0.01)

        self.assertTrue(router._failed)
        self.assertEqual(router._failure, "timeout")
        self.assertTrue(router._closed.is_set())
        self.assertTrue(router._process.killed)
        router._responses.put(
            {"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]}
        )

        self.assertIsNone(router.try_encode(["dos"], timeout=0.1))
        self.assertEqual(router._responses.qsize(), 1)

    def test_mismatched_reply_retires_channel_and_expected_reply_stays_stale(self):
        router = process_router()
        router._responses.put(
            {"type": "encode.result", "id": 99, "rows": [[1.0, 0.0]]}
        )

        with self.assertRaisesRegex(RuntimeError, "mismatched"):
            router.encode(["uno"], timeout=1.0)

        router._responses.put(
            {"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]}
        )
        self.assertIsNone(router.try_encode(["dos"], timeout=0.1))
        self.assertEqual(router._responses.qsize(), 1)
        self.assertTrue(router._process.killed)

    def test_error_or_invalid_embedding_response_fails_closed(self):
        for response in (
            {"type": "error", "id": 1, "code": "request_failed"},
            {"type": "encode.result", "id": 1, "rows": [[float("nan")]]},
            {"type": "encode.result", "id": 1, "rows": []},
        ):
            with self.subTest(response=response):
                router = process_router()
                router._responses.put(response)
                self.assertIsNone(router.try_encode(["uno"], timeout=1.0))
                self.assertTrue(router._failed)
                self.assertTrue(router._closed.is_set())

    def test_try_encode_never_raises_and_default_encode_timeout_is_finite(self):
        router = process_router()

        self.assertGreater(DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS, 0.0)
        self.assertIsNone(router.try_encode([], timeout=float("inf")))
        self.assertFalse(router._failed)

    def test_close_aborts_encode_holding_request_lock_within_total_budget(self):
        router = process_router()
        encode_finished = threading.Event()
        encode_error: list[BaseException] = []

        def encode() -> None:
            try:
                router.encode(["bloqueado"], timeout=120.0)
            except BaseException as error:  # noqa: BLE001 - thread assertion
                encode_error.append(error)
            finally:
                encode_finished.set()

        worker = threading.Thread(target=encode, daemon=True)
        worker.start()
        deadline = time.monotonic() + 1.0
        while not router._process.stdin.payload and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(router._process.stdin.payload)

        started_at = time.monotonic()
        router.close(timeout=0.2)
        elapsed = time.monotonic() - started_at

        self.assertTrue(encode_finished.wait(timeout=0.5))
        worker.join(timeout=0.5)
        self.assertLess(elapsed, 0.4)
        self.assertFalse(worker.is_alive())
        self.assertTrue(router._closed.is_set())
        self.assertTrue(router._process.killed)
        self.assertEqual(len(encode_error), 1)
        self.assertIsInstance(encode_error[0], RuntimeError)

    def test_close_observes_persistent_process_reap_timeout(self):
        class StubbornProcess(_FakeProcess):
            def __init__(self):
                super().__init__()
                self.kill_calls = 0
                self.wait_timeouts = []

            @staticmethod
            def poll():
                return None

            def kill(self):
                self.kill_calls += 1

            def wait(self, timeout):
                self.wait_timeouts.append(timeout)
                raise subprocess.TimeoutExpired(
                    "private-router-command",
                    timeout,
                    output="private stdout",
                    stderr="private stderr",
                )

        router = process_router()
        process = StubbornProcess()
        router._process = process
        diagnostic = io.StringIO()

        with patch(
            "baxy_mind.process_lifecycle.sys.stderr",
            diagnostic,
        ), patch(
            "baxy_mind.router.time.monotonic",
            return_value=133_604.703,
        ):
            started_at = time.perf_counter()
            router.close(timeout=0.04)
            elapsed = time.perf_counter() - started_at

        self.assertLess(elapsed, 0.2)
        self.assertGreaterEqual(process.kill_calls, 2)
        self.assertGreaterEqual(len(process.wait_timeouts), 3)
        self.assertTrue(
            all(0.0 <= timeout <= 0.04 for timeout in process.wait_timeouts)
        )
        self.assertEqual(
            diagnostic.getvalue(),
            "baxy_mind_reap_incomplete:router_process:timed_out\n",
        )
        self.assertNotIn("private", diagnostic.getvalue())

    def test_close_keeps_graceful_shutdown_when_no_encode_is_active(self):
        router = process_router()

        router.close(timeout=0.2)

        requests = [
            json.loads(line)
            for line in router._process.stdin.payload.splitlines()
        ]
        self.assertEqual(
            requests,
            [{"type": "shutdown", "id": 1}],
        )
        self.assertTrue(router._closed.is_set())
        self.assertFalse(router._process.killed)
        self.assertEqual(router._process.returncode, 0)

    def test_close_atomically_blocks_launcher_publication_after_empty_snapshot(self):
        entered_spawn = threading.Event()
        release_spawn = threading.Event()
        close_left_lifecycle = threading.Event()
        allow_close_to_continue = threading.Event()
        process = _FakeProcess()

        def blocked_spawn(*_args, **_kwargs):
            entered_spawn.set()
            release_spawn.wait(timeout=2.0)
            return process

        class CloseExitGateLock:
            def __init__(self):
                self._lock = threading.Lock()
                self._gated_close = False

            def __enter__(self):
                self._lock.acquire()
                return self

            def __exit__(self, _type, _value, _traceback):
                self._lock.release()
                if (
                    threading.current_thread().name == "router-close-race"
                    and not self._gated_close
                ):
                    self._gated_close = True
                    close_left_lifecycle.set()
                    allow_close_to_continue.wait(timeout=2.0)

        with patch.dict(
            router_module.os.environ,
            {"BAXY_MIND_ROUTER_START_DELAY": "0"},
        ), patch(
            "baxy_mind.router.subprocess.Popen",
            side_effect=blocked_spawn,
        ):
            router = ProcessIntentRouter()
            self.assertTrue(entered_spawn.wait(timeout=1.0))
            router._lifecycle_lock = CloseExitGateLock()
            close_errors: list[BaseException] = []

            def close_router() -> None:
                try:
                    router.close(timeout=0.5)
                except BaseException as error:  # noqa: BLE001 - thread assertion
                    close_errors.append(error)

            closer = threading.Thread(
                target=close_router,
                name="router-close-race",
                daemon=True,
            )
            closer.start()
            self.assertTrue(close_left_lifecycle.wait(timeout=1.0))
            self.assertTrue(router._closed.is_set())
            self.assertFalse(router._is_ready)
            release_spawn.set()
            router._launcher.join(timeout=1.0)
            allow_close_to_continue.set()
            closer.join(timeout=1.0)

        self.assertFalse(closer.is_alive())
        self.assertFalse(router._launcher.is_alive())
        self.assertIsNone(router._process)
        self.assertTrue(process.killed)
        self.assertEqual(close_errors, [])

    def test_readiness_cannot_be_republished_after_abortive_close(self):
        router = process_router(ready=False)
        receive_started = threading.Event()
        release_response = threading.Event()
        results: list[bool] = []

        def delayed_ready(_timeout: float | None = None) -> dict:
            receive_started.set()
            release_response.wait(timeout=2.0)
            return {"type": "ready"}

        router._receive = delayed_ready
        observer = threading.Thread(
            target=lambda: results.append(router.try_ready(1.0)),
            daemon=True,
        )
        observer.start()
        self.assertTrue(receive_started.wait(timeout=1.0))

        router.request_close()
        release_response.set()
        observer.join(timeout=1.0)

        self.assertFalse(observer.is_alive())
        self.assertEqual(results, [False])
        self.assertTrue(router._closed.is_set())
        self.assertFalse(router._is_ready)

    def test_production_worker_cannot_route_any_phrase(self):
        router = ProcessIntentRouter.__new__(ProcessIntentRouter)

        for unseen in (
            "zarpifica el estado de mi equipo",
            "please frobnicate this",
            "任意の新しい表現",
        ):
            with self.assertRaisesRegex(RuntimeError, "encoder-only"):
                router.route(unseen)

    def test_worker_echoes_request_ids_and_rejects_unbound_requests(self):
        class FakeSemanticEncoder:
            @staticmethod
            def encode(texts):
                return np.asarray(
                    [[float(index), 1.0] for index, _ in enumerate(texts, 1)],
                    dtype=np.float32,
                )

        requests = "\n".join(
            (
                json.dumps({"type": "encode", "id": 7, "texts": ["uno"]}),
                json.dumps({"type": "encode", "id": 8, "texts": ["dos"]}),
                json.dumps({"type": "encode", "texts": ["sin id"]}),
                json.dumps({"type": "shutdown", "id": 9}),
            )
        )
        output = io.StringIO()
        with (
            patch.object(
                router_worker_module,
                "SemanticEncoder",
                FakeSemanticEncoder,
            ),
            patch.object(router_worker_module.sys, "stdin", io.StringIO(requests)),
            patch.object(router_worker_module.sys, "stdout", output),
        ):
            result = router_worker_module.main()

        messages = [
            json.loads(line) for line in output.getvalue().splitlines()
        ]
        self.assertEqual(result, 0)
        self.assertEqual(messages[0], {"type": "ready"})
        self.assertEqual(messages[1]["id"], 7)
        self.assertEqual(messages[2]["id"], 8)
        self.assertEqual(
            messages[3],
            {
                "type": "error",
                "id": None,
                "code": "invalid_request",
            },
        )


class RequestBudgetEncoderTests(unittest.TestCase):
    def test_readiness_is_observed_without_encoding(self):
        class ReadyTransport:
            def __init__(self):
                self.timeouts = []

            def try_ready(self, timeout):
                self.timeouts.append(timeout)
                return True

        transport = ReadyTransport()
        encoder = RequestBudgetEncoder(transport)

        self.assertTrue(encoder.try_ready(0.125))
        self.assertEqual(transport.timeouts, [0.125])

    def test_reuses_exact_rows_across_overlapping_batches_within_request(self):
        class CountingTransport:
            def __init__(self):
                self.calls = []

            def encode(self, texts, *, timeout):
                self.calls.append((tuple(texts), timeout))
                return np.asarray(
                    [
                        {
                            "alpha": (1.0, 10.0),
                            "beta": (2.0, 20.0),
                            "gamma": (3.0, 30.0),
                        }[text]
                        for text in texts
                    ],
                    dtype=np.float32,
                )

        transport = CountingTransport()
        encoder = RequestBudgetEncoder(transport)

        encoder.begin_request(1.0)
        first = encoder(["alpha", "beta", "alpha"])
        overlapping = encoder(["beta", "gamma"])
        cached = encoder(["gamma", "alpha"])
        encoder.end_request()

        encoder.begin_request(1.0)
        next_request = encoder(["beta"])
        encoder.end_request()

        np.testing.assert_array_equal(
            first,
            np.asarray(
                [(1.0, 10.0), (2.0, 20.0), (1.0, 10.0)],
                dtype=np.float32,
            ),
        )
        np.testing.assert_array_equal(
            overlapping,
            np.asarray([(2.0, 20.0), (3.0, 30.0)], dtype=np.float32),
        )
        np.testing.assert_array_equal(
            cached,
            np.asarray([(3.0, 30.0), (1.0, 10.0)], dtype=np.float32),
        )
        np.testing.assert_array_equal(
            next_request,
            np.asarray([(2.0, 20.0)], dtype=np.float32),
        )
        self.assertEqual(
            [texts for texts, _timeout in transport.calls],
            [
                ("alpha", "beta"),
                ("gamma",),
                ("beta",),
            ],
        )

    def test_blocked_interactive_encoder_falls_back_to_lexical_quickly(self):
        class BlockingAfterOfflineBuild:
            def __init__(self):
                self.timeouts = []

            def encode(self, texts, *, timeout):
                self.timeouts.append(timeout)
                if timeout < DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS:
                    time.sleep(timeout)
                    raise TimeoutError("blocked encoder")
                return np.ones((len(texts), 2), dtype=np.float32)

        transport = BlockingAfterOfflineBuild()
        encoder = RequestBudgetEncoder(transport)
        catalog = PlannerCatalog(
            [
                {
                    "function": {
                        "canonical_name": "system.time",
                        "description": "Read the current time.",
                        "risk": "read_only",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                            "additionalProperties": False,
                        },
                    }
                }
            ],
            encoder=encoder,
        )

        with patch(
            "baxy_mind.router.time.monotonic",
            return_value=133_604.703,
        ):
            encoder.begin_request(0.04)
            started = time.perf_counter()
            try:
                shortlist = catalog.shortlist("read the current time")
            finally:
                encoder.end_request()
            elapsed = time.perf_counter() - started

        self.assertEqual(
            tuple(tool.name for tool in shortlist),
            ("system.time",),
        )
        interactive_timeouts = [
            timeout
            for timeout in transport.timeouts
            if timeout < DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS
        ]
        self.assertTrue(interactive_timeouts)
        self.assertLessEqual(
            max(interactive_timeouts),
            min(DEFAULT_INTERACTIVE_ENCODER_TIMEOUT_SECONDS, 0.04),
        )
        self.assertLess(elapsed, 0.25)
        self.assertTrue(
            all(
                timeout == DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS
                for timeout in transport.timeouts[:2]
            )
        )


class _FakeEncoder:
    def __init__(self):
        self.batch_lengths = []

    def encode(self, texts, **_kwargs):
        self.batch_lengths.append(len(texts))
        rows = {
            "query: time": [1.0, 0.0],
            "query: hello": [0.0, 1.0],
            "query: ambiguous": [0.707, 0.707],
            "query: what is on the screen right now": [1.0, 0.0],
        }
        return np.asarray([rows[text] for text in texts], dtype=float)


def fake_router():
    router = IntentRouter.__new__(IntentRouter)
    router._model = _FakeEncoder()
    router._class_names = ["system.time", "ABSTAIN__conversation"]
    router._class_of_row = [0, 1]
    router._pool = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=float)
    router._rows_by_class = {0: [0], 1: [1]}
    return router


class IntentRouterBatchTests(unittest.TestCase):
    def test_snapshot_manifest_is_portable_and_content_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "model.safetensors").write_bytes(b"weights")
            nested = snapshot / "nested"
            nested.mkdir()
            (nested / "config.json").write_bytes(b'{"value":1}\n')
            (snapshot / "README.md").write_bytes(b"readme")

            identity = _encoder_snapshot_identity(
                snapshot,
                model="fixture/model",
                revision="a" * 40,
            )
            weights_sha256 = hashlib.sha256(b"weights").hexdigest()
            config_sha256 = hashlib.sha256(b'{"value":1}\n').hexdigest()
            readme_sha256 = hashlib.sha256(b"readme").hexdigest()
            manifest = (
                "model=fixture/model\n"
                f"revision={'a' * 40}\n"
                f"README.md\t6\t{readme_sha256}\n"
                f"model.safetensors\t7\t{weights_sha256}\n"
                f"nested/config.json\t12\t{config_sha256}\n"
            )

            self.assertEqual(
                identity.manifest_sha256,
                hashlib.sha256(manifest.encode("utf-8")).hexdigest(),
            )
            self.assertEqual(identity.file_count, 3)
            self.assertEqual(identity.weights_sha256, weights_sha256)

    def test_snapshot_resolution_is_exact_local_memoized_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            weights = snapshot / "model.safetensors"
            weights.write_bytes(b"fixture weights")
            expected = _encoder_snapshot_identity(snapshot)
            _verified_encoder_snapshot.cache_clear()
            with (
                patch(
                    "huggingface_hub.snapshot_download",
                    return_value=str(snapshot),
                ) as download,
                patch.object(
                    router_module,
                    "MODEL_SNAPSHOT_MANIFEST_SHA256",
                    expected.manifest_sha256,
                ),
                patch.object(
                    router_module,
                    "MODEL_SNAPSHOT_FILE_COUNT",
                    expected.file_count,
                ),
                patch.object(
                    router_module,
                    "MODEL_WEIGHTS_SHA256",
                    expected.weights_sha256,
                ),
            ):
                first = router_module.verified_encoder_snapshot_identity()
                second = router_module.verified_encoder_snapshot_identity()

            self.assertEqual(first, second)
            download.assert_called_once_with(
                repo_id=MODEL_NAME,
                revision=MODEL_REVISION,
                local_files_only=True,
            )

            weights.write_bytes(b"changed")
            _verified_encoder_snapshot.cache_clear()
            with (
                patch(
                    "huggingface_hub.snapshot_download",
                    return_value=str(snapshot),
                ),
                patch.object(
                    router_module,
                    "MODEL_SNAPSHOT_MANIFEST_SHA256",
                    expected.manifest_sha256,
                ),
                patch.object(
                    router_module,
                    "MODEL_SNAPSHOT_FILE_COUNT",
                    expected.file_count,
                ),
                patch.object(
                    router_module,
                    "MODEL_WEIGHTS_SHA256",
                    expected.weights_sha256,
                ),
                self.assertRaises(RuntimeError),
            ):
                router_module.verified_encoder_snapshot_identity()
            _verified_encoder_snapshot.cache_clear()

    def test_intent_router_loads_only_the_pinned_local_revision(self):
        calls = []

        class FakeSentenceTransformer:
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))

            def encode(self, texts, **_kwargs):
                return np.ones((len(texts), 2), dtype=np.float32)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bank = root / "bank.jsonl"
            bank.write_text(
                '{"label":"ABSTAIN__conversation","text":"hello"}\n',
                encoding="utf-8",
            )
            with (
                patch.object(
                    router_module,
                    "verified_encoder_snapshot_identity",
                    return_value={"manifest_sha256": "fixture"},
                ),
                patch.dict(
                    sys.modules,
                    {
                        "sentence_transformers": SimpleNamespace(
                            SentenceTransformer=FakeSentenceTransformer
                        )
                    },
                ),
            ):
                IntentRouter(
                    bank_path=bank,
                    pool_path=root / "missing.npy",
                    pool_metadata_path=root / "missing.json",
                )

        self.assertEqual(
            calls,
            [
                (
                    (MODEL_NAME,),
                    {
                        "device": "cpu",
                        "revision": MODEL_REVISION,
                        "local_files_only": True,
                    },
                )
            ],
        )

    def test_frozen_pool_loads_only_for_the_exact_bank(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bank = root / "bank.jsonl"
            pool_path = root / "pool.npy"
            metadata_path = root / "pool.json"
            bank.write_text('{"label":"time","text":"what time is it"}\n', encoding="utf-8")
            expected = np.asarray([[1.0, 0.0]], dtype=np.float32)
            np.save(pool_path, expected, allow_pickle=False)
            metadata_path.write_text(
                json.dumps(
                    {
                        "schema": "baxy-intent-pool-v1",
                        "model": MODEL_NAME,
                        "bank_sha256": hashlib.sha256(bank.read_bytes()).hexdigest(),
                        "pool_sha256": hashlib.sha256(pool_path.read_bytes()).hexdigest(),
                        "rows": 1,
                        "dimensions": 2,
                    }
                ),
                encoding="utf-8",
            )

            loaded = _load_frozen_pool(
                bank,
                pool_path,
                metadata_path,
                expected_rows=1,
            )
            np.testing.assert_array_equal(loaded, expected)

            bank.write_text('{"label":"time","text":"changed"}\n', encoding="utf-8")
            self.assertIsNone(
                _load_frozen_pool(
                    bank,
                    pool_path,
                    metadata_path,
                    expected_rows=1,
                )
            )

    def test_route_many_preserves_single_route_decisions_in_bounded_batches(self):
        router = fake_router()

        decisions = router.route_many(
            ("time", "hello", "ambiguous"),
            batch_size=2,
        )

        self.assertEqual(router._model.batch_lengths, [2, 1])
        self.assertEqual(decisions[0].kind, "operation")
        self.assertEqual(decisions[0].operation, "system.time")
        self.assertEqual(decisions[1].kind, "conversation")
        self.assertEqual(decisions[2].kind, "conversation")

    def test_route_many_rejects_invalid_batch_size_and_accepts_empty_input(self):
        router = fake_router()

        self.assertEqual(router.route_many(()), [])
        with self.assertRaises(ValueError):
            router.route_many(("time",), batch_size=0)

    def test_offline_router_decision_depends_only_on_semantic_pool(self):
        router = fake_router()

        decision = router.route("what is on the screen right now")

        self.assertEqual(decision.kind, "operation")
        self.assertEqual(decision.operation, "system.time")
        self.assertEqual(decision.winner_pool, "system.time")

    def test_semantic_encoder_has_no_routing_api(self):
        self.assertNotIn("route", SemanticEncoder.__dict__)


if __name__ == "__main__":
    unittest.main()
