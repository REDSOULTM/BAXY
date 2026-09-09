from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import __main__ as sidecar
from baxy_mind import protocol


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 1.0),
        (5, 5.0),
        (20, 20.0),
        (45, 45.0),
        (55, 55.0),
        (60, 60.0),
        (120, 120.0),
        (180, 120.0),
        ("invalid", 3.25),
    ],
)
def test_message_composition_budget_preserves_the_certified_cpu_window(
    raw: object,
    expected: float,
) -> None:
    assert sidecar._message_composition_budget(raw) == expected


def _exercise_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    messages: list[dict[str, Any] | BaseException | None],
    *,
    with_llm: bool,
    voice_status_error: bool = False,
    voice_shutdown_error: bool = False,
    llm_close_error: bool = False,
    router_close_error: bool = False,
    serialize_replies: bool = False,
) -> dict[str, Any]:
    cleanup: list[str] = []
    replies: list[dict[str, Any]] = []
    voice_instances: list[object] = []
    reply_written = threading.Event()

    class FakeLlmRuntime:
        @staticmethod
        def start_warmup() -> None:
            return None

        @staticmethod
        def begin_request(*_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def end_request() -> None:
            return None

        @staticmethod
        def close() -> None:
            cleanup.append("llm.close")
            if llm_close_error:
                raise RuntimeError("sensitive llm cleanup detail")

    class FakeRouter:
        @staticmethod
        def close() -> None:
            cleanup.append("router.close")
            if router_close_error:
                raise RuntimeError("sensitive router cleanup detail")

    class FakeVoiceEngine:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            voice_instances.append(self)

        @staticmethod
        def status() -> dict[str, object]:
            if voice_status_error:
                raise RuntimeError("voice status handler failed")
            return {"state": "idle"}

        @staticmethod
        def shutdown() -> None:
            cleanup.append("voice.shutdown")
            if voice_shutdown_error:
                raise RuntimeError("voice shutdown failed")

    monkeypatch.setattr(sidecar, "LlmRuntime", FakeLlmRuntime)
    monkeypatch.setattr(sidecar, "VoiceEngine", FakeVoiceEngine)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    def capture_reply(reply: dict[str, Any]) -> None:
        replies.append(reply)
        if reply.get("type") != "hello":
            reply_written.set()

    monkeypatch.setattr(sidecar, "_write", capture_reply)
    if with_llm:
        monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    else:
        monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)

    pending = iter(messages)
    read_count = 0

    def read_message() -> dict[str, Any] | None:
        nonlocal read_count
        if serialize_replies and read_count > 0:
            assert reply_written.wait(timeout=1.0)
            reply_written.clear()
        read_count += 1
        item = next(pending, None)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)
    result: int | None = None
    raised: BaseException | None = None
    try:
        result = sidecar.main()
    except BaseException as error:
        raised = error
    return {
        "cleanup": cleanup,
        "raised": raised,
        "replies": replies,
        "result": result,
        "voice_instances": len(voice_instances),
    }


def test_dispatch_crash_exits_while_redirected_stdin_remains_open() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    script = """
import os
import sys
import threading
import time
from baxy_mind import __main__ as sidecar
from baxy_mind import protocol

receiver_entered = threading.Event()
bounded_reader = protocol._BoundedFileDescriptorLineReader

def observed_reader(descriptor):
    def observed_os_read(descriptor, limit):
        receiver_entered.set()
        return os.read(descriptor, limit)

    return bounded_reader(
        descriptor,
        read=observed_os_read,
    )

def crash_dispatch(
    lifecycle,
    *,
    read_message,
    write_message,
    request_finished,
):
    write_message({"type": "hello", "protocol": "test"})
    if not receiver_entered.wait(timeout=2.0):
        raise RuntimeError("receiver_did_not_enter")
    time.sleep(0.1)
    raise RuntimeError("forced_dispatch_crash")

protocol._BoundedFileDescriptorLineReader = observed_reader
sidecar._run_sidecar = crash_dispatch
sys.exit(sidecar.main())
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_root)
    started_at = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    try:
        return_code = process.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3.0)
        pytest.fail("sidecar did not exit after its dispatcher failed")
    finally:
        if process.stdin is not None:
            process.stdin.close()

    stdout = process.stdout.read() if process.stdout is not None else b""
    stderr = process.stderr.read() if process.stderr is not None else b""

    assert return_code == 1
    assert time.monotonic() - started_at < 3.0
    assert b'"type":"hello"' in stdout
    assert b"forced_dispatch_crash" in stderr
    assert b"_enter_buffered_busy" not in stderr


def test_cold_voice_dsp_responds_while_redirected_stdin_remains_open() -> None:
    """Native SciPy initialization must not race a blocking Windows pipe read."""
    source_root = Path(__file__).resolve().parents[1] / "src"
    script = """
import sys
from baxy_mind import __main__ as sidecar
from baxy_mind.voice_aec import _resample
import numpy as np

def probe_dispatch(lifecycle, *, read_message, write_message, request_finished):
    write_message({"type": "hello", "protocol": "test"})
    assert read_message()["type"] == "probe"
    # This is intentionally the first DSP request in a fresh process. Require
    # SciPy itself so a missing dependency cannot pass through interpolation.
    from scipy.signal import resample_poly
    assert callable(resample_poly)
    audio = _resample(np.zeros(1536, dtype=np.int16), 48000)
    assert audio.shape == (512,)
    write_message({"type": "probe.done"})
    return 0

sidecar._run_sidecar = probe_dispatch
sys.exit(sidecar.main())
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_root)
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    try:
        assert process.stdin is not None
        process.stdin.write(b'{"type":"probe"}\n')
        process.stdin.flush()
        # Keep stdin open: communicate() would send EOF and hide the deadlock.
        return_code = process.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3.0)
        pytest.fail("cold voice DSP stalled with the protocol input still open")
    finally:
        if process.stdin is not None:
            process.stdin.close()
    stdout = process.stdout.read() if process.stdout is not None else b""
    stderr = process.stderr.read() if process.stderr is not None else b""
    assert return_code == 0, stderr.decode("utf-8", errors="replace")
    assert b'"type":"probe.done"' in stdout
    assert not stderr


def test_eof_closes_only_the_constructed_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = _exercise_sidecar(
        monkeypatch,
        [None],
        with_llm=False,
    )

    assert observed["result"] == 0
    assert observed["raised"] is None
    assert observed["voice_instances"] == 0
    assert observed["cleanup"] == ["router.close"]


def test_protocol_violation_closes_constructed_resources_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = _exercise_sidecar(
        monkeypatch,
        [protocol.ProtocolViolation("malformed_json", "fixture")],
        with_llm=True,
    )

    assert observed["result"] == 65
    assert observed["raised"] is None
    assert observed["voice_instances"] == 0
    assert observed["cleanup"] == ["llm.close", "router.close"]
    assert observed["replies"][-1]["code"] == "malformed_json"


def test_protocol_violation_keeps_exit_65_when_cleanup_also_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observed = _exercise_sidecar(
        monkeypatch,
        [protocol.ProtocolViolation("malformed_json", "fixture")],
        with_llm=True,
        llm_close_error=True,
    )

    captured = capsys.readouterr()
    assert observed["result"] == 65
    assert observed["raised"] is None
    assert observed["cleanup"] == ["llm.close", "router.close"]
    assert (
        captured.err
        == "baxy_mind_cleanup_failure:RuntimeError\n"
    )
    assert "sensitive" not in captured.err


def test_handler_exception_closes_all_resources_once_in_safe_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = _exercise_sidecar(
        monkeypatch,
        [{"type": "voice.status", "id": "voice-1"}, None],
        with_llm=True,
        voice_status_error=True,
    )

    assert observed["result"] == 0
    assert observed["raised"] is None
    assert observed["cleanup"] == [
        "voice.shutdown",
        "llm.close",
        "router.close",
    ]
    assert observed["replies"][-1]["code"] == "request_failed"


def test_lifecycle_close_is_directly_idempotent_and_joins_owned_worker() -> None:
    events: list[str] = []
    planner_stop = threading.Event()

    class Evidence:
        def stop(self, timeout: float) -> bool:
            events.append(f"evidence.stop:{timeout}")
            return True

    class Voice:
        @staticmethod
        def shutdown() -> None:
            events.append("voice.shutdown")

    class Llm:
        @staticmethod
        def close() -> None:
            events.append("llm.close")

    class Router:
        @staticmethod
        def close() -> None:
            events.append("router.close")

    planner = threading.Thread(
        target=planner_stop.wait,
        name="fixture-planner-promotion",
        daemon=True,
    )
    planner.start()
    lifecycle = sidecar._SidecarLifecycle()
    lifecycle.own_voice_engine(Voice())
    lifecycle.own_llm(Llm())
    lifecycle.own_turn_evidence(Evidence())
    lifecycle.own_planner_promotion(planner, planner_stop)
    lifecycle.own_router(Router())

    lifecycle.close()
    lifecycle.close()

    assert not planner.is_alive()
    assert events == [
        "evidence.stop:0.0",
        "voice.shutdown",
        "llm.close",
        f"evidence.stop:{sidecar.BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS}",
        "router.close",
    ]


def test_rejected_lazy_voice_candidate_is_closed_outside_ownership_lock() -> None:
    lifecycle = sidecar._SidecarLifecycle()
    constructor_entered = threading.Event()
    finish_constructor = threading.Event()
    shutdown_calls: list[bool] = []
    ownership_errors: list[BaseException] = []

    class Voice:
        def __init__(self) -> None:
            constructor_entered.set()
            assert finish_constructor.wait(timeout=1.0)

        def shutdown(self) -> None:
            lock_was_free = lifecycle._ownership_lock.acquire(
                blocking=False
            )
            shutdown_calls.append(lock_was_free)
            if lock_was_free:
                lifecycle._ownership_lock.release()

    def construct_and_claim() -> None:
        candidate = Voice()
        try:
            lifecycle.own_voice_engine(candidate)
        except BaseException as error:
            ownership_errors.append(error)

    worker = threading.Thread(
        target=construct_and_claim,
        name="fixture-lazy-voice-owner",
    )
    worker.start()
    try:
        assert constructor_entered.wait(timeout=1.0)
        lifecycle.close()
    finally:
        finish_constructor.set()
        worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert shutdown_calls == [True]
    assert len(ownership_errors) == 1
    assert isinstance(ownership_errors[0], RuntimeError)
    assert str(ownership_errors[0]) == "sidecar lifecycle is already closed"


def test_lifecycle_aborts_router_before_final_join_when_worker_is_stuck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    release_worker = threading.Event()
    worker = threading.Thread(
        target=release_worker.wait,
        name="fixture-stuck-evidence",
        daemon=True,
    )
    worker.start()

    class Evidence:
        @staticmethod
        def stop(timeout: float) -> bool:
            events.append(f"evidence.stop:{timeout}")
            worker.join(timeout=timeout)
            return not worker.is_alive()

    class Router:
        @staticmethod
        def request_close() -> None:
            events.append("router.request_close")
            release_worker.set()

        @staticmethod
        def close() -> None:
            assert not worker.is_alive()
            events.append("router.close")

    monkeypatch.setattr(
        sidecar,
        "BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS",
        0.02,
    )
    lifecycle = sidecar._SidecarLifecycle()
    lifecycle.own_turn_evidence(Evidence())
    lifecycle.own_router(Router())

    started_at = time.monotonic()
    lifecycle.close()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.3
    assert not worker.is_alive()
    assert events == [
        "evidence.stop:0.0",
        "evidence.stop:0.02",
        "router.request_close",
        f"evidence.stop:{sidecar.BACKGROUND_WORKER_ABORT_JOIN_SECONDS}",
        "router.close",
    ]


def test_lifecycle_reports_workers_that_survive_bounded_abort(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence_timeouts: list[float] = []
    router_events: list[str] = []
    release_worker = threading.Event()
    planner_stop = threading.Event()
    planner = threading.Thread(
        target=release_worker.wait,
        name="private-planner-worker-detail",
        daemon=True,
    )
    dispatch = threading.Thread(
        target=release_worker.wait,
        name="private-dispatch-worker-detail",
        daemon=True,
    )
    planner.start()
    dispatch.start()

    class Evidence:
        @staticmethod
        def stop(timeout: float) -> bool:
            evidence_timeouts.append(timeout)
            return False

    class Router:
        @staticmethod
        def request_close() -> None:
            router_events.append("request_close")

        @staticmethod
        def close() -> None:
            router_events.append("close")

    monkeypatch.setattr(
        sidecar,
        "BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        sidecar,
        "BACKGROUND_WORKER_ABORT_JOIN_SECONDS",
        0.01,
    )
    lifecycle = sidecar._SidecarLifecycle()
    lifecycle.own_turn_evidence(Evidence())
    lifecycle.own_planner_promotion(planner, planner_stop)
    lifecycle.own_dispatch_thread(dispatch)
    lifecycle.own_router(Router())

    try:
        started_at = time.monotonic()
        lifecycle.close()
        elapsed = time.monotonic() - started_at
        captured = capsys.readouterr()
    finally:
        release_worker.set()
        planner.join(timeout=1.0)
        dispatch.join(timeout=1.0)

    assert elapsed < 0.2
    assert evidence_timeouts == [0.0, 0.01, 0.01, 0.0]
    assert router_events == ["request_close", "close"]
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "baxy_mind_reap_incomplete:turn_evidence_thread:timed_out",
        "baxy_mind_reap_incomplete:planner_promotion_thread:timed_out",
        "baxy_mind_reap_incomplete:request_dispatch_thread:timed_out",
    ]
    assert "private" not in captured.err


@pytest.mark.parametrize(
    "tail",
    [
        None,
        {"type": "shutdown", "id": "shutdown-1"},
    ],
    ids=["eof", "shutdown"],
)
def test_catalog_background_workers_stop_before_router_on_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tail: dict[str, Any] | None,
) -> None:
    from baxy_mind import turn_evidence as evidence_module

    corpus = tmp_path / "turn-evidence.jsonl"
    corpus.write_text("", encoding="utf-8")
    encode_started = threading.Event()
    service_instances: list[evidence_module.TurnEvidenceService] = []
    router_instances: list[object] = []
    encoder_timeouts: list[float] = []
    calls_after_close: list[str] = []
    cleanup: list[str] = []
    replies: list[dict[str, Any]] = []

    class FakeRouter:
        def __init__(self) -> None:
            self.closed = False
            router_instances.append(self)

        def try_ready(self, _timeout: float = 0.0) -> bool:
            if self.closed:
                calls_after_close.append("try_ready")
            return not self.closed

        def encode(
            self,
            _texts: object,
            *,
            timeout: float,
            prefix: str = "query",
        ):
            if self.closed:
                calls_after_close.append("encode.start")
            encoder_timeouts.append(timeout)
            encode_started.set()
            time.sleep(0.05)
            if self.closed:
                calls_after_close.append("encode.finish")
            return [[1.0]]

        def request_close(self) -> None:
            cleanup.append("router.request_close")
            self.closed = True

        def close(self) -> None:
            service = service_instances[0]
            if service._thread is not None and service._thread.is_alive():
                calls_after_close.append("evidence.worker_alive")
            self.closed = True
            cleanup.append("router.close")

    def evidence_factory() -> evidence_module.TurnEvidenceService:
        service = evidence_module.TurnEvidenceService(corpus)
        service_instances.append(service)
        return service

    fake_index = SimpleNamespace(
        count=1,
        dimensions=1,
        encoder_identity="fixture-encoder",
        report=SimpleNamespace(source_sha256="a" * 64),
    )

    def build_index(
        _cls: object,
        _path: Path,
        encoder: Any,
        *,
        is_cancelled: Any = None,
    ):
        del is_cancelled
        encoder(["fixture corpus"])
        return fake_index

    tools = [
        {
            "function": {
                "canonical_name": "app.open",
            }
        }
    ]
    monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setattr(sidecar, "TurnEvidenceService", evidence_factory)
    monkeypatch.setattr(sidecar, "configure_tools", lambda _value: tools)
    monkeypatch.setattr(
        sidecar,
        "configure_application_catalog",
        lambda _value: (),
    )
    monkeypatch.setattr(
        sidecar,
        "_create_planner_resources",
        lambda *_args, **_kwargs: (object(), object()),
    )
    monkeypatch.setattr(sidecar, "_write", replies.append)
    monkeypatch.setattr(
        evidence_module,
        "load_abstention_policy",
        lambda _path=None: None,
    )
    monkeypatch.setattr(
        evidence_module.TurnEvidenceIndex,
        "from_corpus",
        classmethod(build_index),
    )
    read_count = 0

    def read_message() -> dict[str, Any] | None:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return {
                "type": "catalog.configure",
                "id": "catalog-1",
                "capabilities": [],
                "applicationCatalog": [],
            }
        assert encode_started.wait(timeout=1.0)
        return tail

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)

    result = sidecar.main()

    assert result == 0
    assert len(router_instances) == 1
    assert len(service_instances) == 1
    assert service_instances[0].state == "stopped"
    assert service_instances[0]._thread is not None
    assert not service_instances[0]._thread.is_alive()
    assert not any(
        thread.name == "baxy-planner-e5-promotion" and thread.is_alive()
        for thread in threading.enumerate()
    )
    assert encoder_timeouts == [sidecar.BACKGROUND_ENCODER_TIMEOUT_SECONDS]
    assert calls_after_close == []
    assert cleanup == ["router.close"]
    if tail is not None:
        assert replies[-1] == {
            "type": "shutdown.ack",
            "id": "shutdown-1",
        }


def test_normal_shutdown_closes_all_resources_once_in_safe_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = _exercise_sidecar(
        monkeypatch,
        [
            {"type": "voice.status", "id": "voice-1"},
            {"type": "shutdown", "id": "shutdown-1"},
        ],
        with_llm=True,
        serialize_replies=True,
    )

    assert observed["result"] == 0
    assert observed["raised"] is None
    assert observed["cleanup"] == [
        "voice.shutdown",
        "llm.close",
        "router.close",
    ]
    assert observed["replies"][-1] == {
        "type": "shutdown.ack",
        "id": "shutdown-1",
    }


def test_cleanup_failure_does_not_hide_the_primary_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = RuntimeError("primary read failure")
    observed = _exercise_sidecar(
        monkeypatch,
        [
            {"type": "voice.status", "id": "voice-1"},
            primary,
        ],
        with_llm=True,
        voice_shutdown_error=True,
    )

    assert observed["result"] is None
    assert observed["raised"] is primary
    assert observed["cleanup"] == [
        "voice.shutdown",
        "llm.close",
        "router.close",
    ]


def test_failed_llm_scope_entry_finishes_the_attempt_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope_events: list[str] = []
    finished: list[dict[str, Any]] = []

    class FakeLlmRuntime:
        @staticmethod
        def start_warmup() -> None:
            return None

        @staticmethod
        def begin_request(*_args: object, **_kwargs: object) -> None:
            scope_events.append("llm.begin")
            raise RuntimeError("fixture begin failure")

        @staticmethod
        def end_request() -> None:
            scope_events.append("llm.end")

        @staticmethod
        def narrate(*_args: object, **_kwargs: object) -> str:
            raise AssertionError("handler ran after failed scope entry")

        @staticmethod
        def close() -> None:
            return None

    class FakeRouter:
        @staticmethod
        def close() -> None:
            return None

    monkeypatch.setattr(sidecar, "LlmRuntime", FakeLlmRuntime)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    message = {
        "type": "narrate",
        "id": "scope-llm",
        "userText": "fixture",
        "operation": "system.time",
        "outcome": {},
    }
    pending = iter([message])
    lifecycle = sidecar._SidecarLifecycle()

    try:
        with pytest.raises(RuntimeError, match="fixture begin failure"):
            sidecar._run_sidecar(
                lifecycle,
                read_message=lambda: next(pending, None),
                write_message=lambda _message: None,
                request_finished=finished.append,
            )
    finally:
        lifecycle.close()

    assert scope_events == ["llm.begin", "llm.end"]
    assert finished == [message]


def test_failed_encoder_scope_entry_closes_both_attempted_scopes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope_events: list[str] = []
    finished: list[dict[str, Any]] = []
    encoders: list[object] = []

    class FakeLlmRuntime:
        @staticmethod
        def start_warmup() -> None:
            return None

        @staticmethod
        def begin_request(*_args: object, **_kwargs: object) -> None:
            scope_events.append("llm.begin")

        @staticmethod
        def end_request() -> None:
            scope_events.append("llm.end")

        @staticmethod
        def close() -> None:
            return None

    class FakeRouter:
        @staticmethod
        def close() -> None:
            return None

    class FakeEncoder:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            encoders.append(self)

        @staticmethod
        def begin_request(_budget: float) -> None:
            scope_events.append("encoder.begin")
            raise RuntimeError("fixture encoder begin failure")

        @staticmethod
        def end_request() -> None:
            scope_events.append("encoder.end")

    monkeypatch.setattr(sidecar, "LlmRuntime", FakeLlmRuntime)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setattr(sidecar, "RequestBudgetEncoder", FakeEncoder)
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    message = {
        "type": "turn.decide",
        "id": "scope-encoder",
        "text": "fixture",
    }
    pending = iter([message])
    lifecycle = sidecar._SidecarLifecycle()

    try:
        with pytest.raises(
            RuntimeError,
            match="fixture encoder begin failure",
        ):
            sidecar._run_sidecar(
                lifecycle,
                read_message=lambda: next(pending, None),
                write_message=lambda _message: None,
                request_finished=finished.append,
            )
    finally:
        lifecycle.close()

    assert len(encoders) == 2
    assert scope_events == [
        "llm.begin",
        "encoder.begin",
        "encoder.end",
        "llm.end",
    ]
    assert finished == [message]


def test_shutdown_ack_interrupts_heavy_work_and_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    narrate_started = threading.Event()
    release_narrate = threading.Event()
    llm_closed = threading.Event()
    replies: list[dict[str, Any]] = []
    request_scopes: list[str] = []

    class FakeLlmRuntime:
        @staticmethod
        def start_warmup() -> None:
            return None

        @staticmethod
        def begin_request(*_args: object, **_kwargs: object) -> None:
            request_scopes.append("begin")

        @staticmethod
        def end_request() -> None:
            request_scopes.append("end")

        @staticmethod
        def narrate(*_args: object, **_kwargs: object) -> str:
            narrate_started.set()
            assert release_narrate.wait(timeout=2.0)
            return "late reply"

        @staticmethod
        def close() -> None:
            assert replies[-1] == {
                "type": "shutdown.ack",
                "id": "shutdown-fast",
            }
            llm_closed.set()
            release_narrate.set()

    class FakeRouter:
        @staticmethod
        def request_close() -> None:
            release_narrate.set()

        @staticmethod
        def close() -> None:
            return None

    monkeypatch.setattr(sidecar, "LlmRuntime", FakeLlmRuntime)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setattr(sidecar, "_write", replies.append)
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    read_count = 0

    def read_message() -> dict[str, Any]:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return {
                "type": "narrate",
                "id": "narrate-blocked",
                "userText": "fixture",
                "operation": "system.time",
                "outcome": {},
            }
        assert narrate_started.wait(timeout=1.0)
        return {"type": "shutdown", "id": "shutdown-fast"}

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)

    started_at = time.monotonic()
    result = sidecar.main()
    elapsed = time.monotonic() - started_at

    assert result == 0
    assert elapsed < 1.0
    assert llm_closed.is_set()
    assert request_scopes == ["begin", "end"]
    assert [reply["type"] for reply in replies] == [
        "hello",
        "shutdown.ack",
    ]


def test_voice_cancel_bypasses_llm_work_without_mutating_its_request_scope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    voice_ready = threading.Event()
    narrate_started = threading.Event()
    narrate_finished = threading.Event()
    release_narrate = threading.Event()
    cancel_observed = threading.Event()
    voice_events: list[str] = []
    replies: list[dict[str, Any]] = []
    request_scopes: list[str] = []

    class FakeLlmRuntime:
        @staticmethod
        def start_warmup() -> None:
            return None

        @staticmethod
        def begin_request(*_args: object, **_kwargs: object) -> None:
            request_scopes.append("begin")

        @staticmethod
        def end_request() -> None:
            request_scopes.append("end")

        @staticmethod
        def narrate(*_args: object, **_kwargs: object) -> str:
            narrate_started.set()
            assert release_narrate.wait(timeout=2.0)
            narrate_finished.set()
            return "done"

        @staticmethod
        def close() -> None:
            release_narrate.set()

    class FakeRouter:
        @staticmethod
        def close() -> None:
            return None

    class FakeVoiceEngine:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def status() -> dict[str, object]:
            voice_ready.set()
            return {"state": "idle"}

        @staticmethod
        def cancel_speech() -> None:
            voice_events.append("cancel")
            if len(voice_events) == 1:
                assert narrate_started.is_set()
                assert not narrate_finished.is_set()
                release_narrate.set()
            else:
                assert voice_events[-2] == "speak"
            cancel_observed.set()
            if len(voice_events) > 1:
                raise RuntimeError("private replay failure")

        @staticmethod
        def speak(_text: str) -> bool:
            voice_events.append("speak")
            return True

        @staticmethod
        def shutdown() -> None:
            return None

    monkeypatch.setattr(sidecar, "LlmRuntime", FakeLlmRuntime)
    monkeypatch.setattr(sidecar, "VoiceEngine", FakeVoiceEngine)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setattr(sidecar, "_write", replies.append)
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    read_count = 0

    def read_message() -> dict[str, Any] | None:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return {"type": "voice.status", "id": "voice-status"}
        if read_count == 2:
            assert voice_ready.wait(timeout=1.0)
            return {
                "type": "narrate",
                "id": "narrate-active",
                "userText": "fixture",
                "operation": "system.time",
                "outcome": {},
            }
        if read_count == 3:
            assert narrate_started.wait(timeout=1.0)
            return {
                "type": "voice.speak",
                "id": "speak-before-cancel",
                "text": "fixture",
            }
        if read_count == 4:
            return {"type": "voice.cancel", "id": "cancel-fast"}
        assert cancel_observed.wait(timeout=1.0)
        return None

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)

    result = sidecar.main()

    assert result == 0
    assert cancel_observed.is_set()
    assert request_scopes == [
        "begin",
        "end",
        "begin",
        "end",
        "begin",
        "end",
    ]
    assert voice_events == ["cancel", "speak", "cancel"]
    reply_types = [reply["type"] for reply in replies]
    assert reply_types.count("voice.cancelled") == 1
    assert not any(
        reply.get("id") == "cancel-fast"
        and reply.get("type") == "error"
        for reply in replies
    )
    assert reply_types.index("voice.cancelled") < reply_types.index(
        "narrate.result"
    )
    captured = capsys.readouterr()
    assert (
        captured.err
        == "baxy_mind_control_replay_failure:RuntimeError\n"
    )
    assert "private" not in captured.err


def test_serial_shutdown_ack_is_terminal_for_voice_cleanup_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies: list[dict[str, Any]] = []

    class FakeRouter:
        @staticmethod
        def close() -> None:
            return None

    class FakeVoiceEngine:
        def __init__(
            self,
            _on_transcript: object,
            on_event: Any,
            **_kwargs: object,
        ) -> None:
            self._on_event = on_event

        @staticmethod
        def status() -> dict[str, object]:
            return {"state": "idle"}

        def shutdown(self) -> None:
            self._on_event(
                {
                    "event": "state",
                    "mode": "off",
                }
            )

    monkeypatch.setattr(sidecar, "VoiceEngine", FakeVoiceEngine)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)
    pending = iter(
        [
            {"type": "voice.status", "id": "status-serial"},
            {"type": "shutdown", "id": "shutdown-serial"},
        ]
    )
    lifecycle = sidecar._SidecarLifecycle()
    writer = sidecar._TerminalProtocolWriter(replies.append)

    try:
        result = sidecar._run_sidecar(
            lifecycle,
            read_message=lambda: next(pending, None),
            write_message=writer.write,
        )
    finally:
        lifecycle.close()

    assert result == 0
    assert [reply["type"] for reply in replies] == [
        "hello",
        "voice.status.result",
        "shutdown.ack",
    ]
    assert replies[-1]["id"] == "shutdown-serial"


def test_voice_cancel_replays_when_speak_finishes_during_fast_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    voice_ready = threading.Event()
    speak_started = threading.Event()
    release_speak = threading.Event()
    cancel_observed = threading.Event()
    speak_result_written = threading.Event()
    replies: list[dict[str, Any]] = []
    cancel_calls = 0
    spoke_after_cancel = False

    class FakeRouter:
        @staticmethod
        def close() -> None:
            return None

    class FakeVoiceEngine:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def status() -> dict[str, object]:
            voice_ready.set()
            return {"state": "idle"}

        @staticmethod
        def speak(_text: str) -> bool:
            nonlocal spoke_after_cancel
            speak_started.set()
            assert release_speak.wait(timeout=2.0)
            spoke_after_cancel = cancel_observed.is_set()
            return True

        @staticmethod
        def cancel_speech() -> None:
            nonlocal cancel_calls
            cancel_calls += 1
            cancel_observed.set()
            release_speak.set()
            if cancel_calls == 1:
                assert speak_result_written.wait(timeout=1.0)
                time.sleep(0.05)

        @staticmethod
        def shutdown() -> None:
            release_speak.set()

    monkeypatch.setattr(sidecar, "VoiceEngine", FakeVoiceEngine)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)

    def capture_reply(reply: dict[str, Any]) -> None:
        replies.append(reply)
        if reply.get("type") == "voice.speak.result":
            speak_result_written.set()

    monkeypatch.setattr(sidecar, "_write", capture_reply)
    monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)
    read_count = 0

    def read_message() -> dict[str, Any] | None:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return {"type": "voice.status", "id": "voice-ready"}
        if read_count == 2:
            assert voice_ready.wait(timeout=1.0)
            return {
                "type": "voice.speak",
                "id": "sapi-blocked",
                "text": "fixture",
            }
        if read_count == 3:
            assert speak_started.wait(timeout=1.0)
            return {"type": "voice.cancel", "id": "cancel-sapi"}
        assert cancel_observed.wait(timeout=1.0)
        return None

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)

    started_at = time.monotonic()
    result = sidecar.main()
    elapsed = time.monotonic() - started_at

    assert result == 0
    assert elapsed < 1.0
    assert cancel_calls == 2
    assert spoke_after_cancel
    reply_types = [reply["type"] for reply in replies]
    assert reply_types.count("voice.cancelled") == 1
    assert reply_types.count("voice.speak.result") == 1


def test_voice_cancel_is_deferred_until_lazy_voice_ownership(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    constructor_entered = threading.Event()
    cancel_acknowledged = threading.Event()
    replies: list[dict[str, Any]] = []
    cancel_calls = 0
    spoke_after_deferred_cancel = False

    class FakeRouter:
        @staticmethod
        def close() -> None:
            return None

    class FakeVoiceEngine:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            constructor_entered.set()
            assert cancel_acknowledged.wait(timeout=1.0)

        @staticmethod
        def speak(_text: str) -> bool:
            nonlocal spoke_after_deferred_cancel
            spoke_after_deferred_cancel = cancel_calls == 1
            return True

        @staticmethod
        def cancel_speech() -> None:
            nonlocal cancel_calls
            cancel_calls += 1
            if cancel_calls == 1:
                raise RuntimeError("private deferred cancel failure")

        @staticmethod
        def shutdown() -> None:
            return None

    monkeypatch.setattr(sidecar, "VoiceEngine", FakeVoiceEngine)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)

    def capture_reply(reply: dict[str, Any]) -> None:
        replies.append(reply)
        if reply.get("type") == "voice.cancelled":
            cancel_acknowledged.set()

    monkeypatch.setattr(sidecar, "_write", capture_reply)
    monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)
    read_count = 0

    def read_message() -> dict[str, Any] | None:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return {
                "type": "voice.speak",
                "id": "lazy-speak",
                "text": "fixture",
            }
        if read_count == 2:
            assert constructor_entered.wait(timeout=1.0)
            return {"type": "voice.cancel", "id": "lazy-cancel"}
        assert cancel_acknowledged.wait(timeout=1.0)
        return None

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)

    result = sidecar.main()

    assert result == 0
    assert cancel_calls == 2
    assert spoke_after_deferred_cancel
    assert sum(
        reply.get("id") == "lazy-cancel"
        and reply.get("type") == "voice.cancelled"
        for reply in replies
    ) == 1
    assert sum(
        reply.get("id") == "lazy-speak"
        and reply.get("type") == "voice.speak.result"
        for reply in replies
    ) == 1
    captured = capsys.readouterr()
    assert (
        captured.err
        == "baxy_mind_deferred_voice_cancel_failure:RuntimeError\n"
    )
    assert "private" not in captured.err


def test_fast_shutdown_does_not_wait_for_voice_start_lifecycle_lock(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lifecycle_lock = threading.Lock()
    start_entered = threading.Event()
    release_start = threading.Event()
    shutdown_finished = threading.Event()
    replies: list[dict[str, Any]] = []

    class FakeRouter:
        @staticmethod
        def request_close() -> None:
            return None

        @staticmethod
        def close() -> None:
            return None

    class FakeVoiceEngine:
        def __init__(
            self,
            _on_transcript: object,
            on_event: Any,
            **_kwargs: object,
        ) -> None:
            self._on_event = on_event

        @property
        def mode(self) -> str:
            return "direct"

        def start(self, _mode: str) -> bool:
            with lifecycle_lock:
                start_entered.set()
                assert release_start.wait(timeout=2.0)
            return True

        @staticmethod
        def status() -> dict[str, object]:
            return {"state": "idle"}

        def shutdown(self) -> None:
            with lifecycle_lock:
                self._on_event({"event": "state", "mode": "off"})
            shutdown_finished.set()

    monkeypatch.setattr(sidecar, "VoiceEngine", FakeVoiceEngine)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setattr(sidecar, "_write", replies.append)
    monkeypatch.setattr(
        sidecar,
        "BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        sidecar,
        "BACKGROUND_WORKER_ABORT_JOIN_SECONDS",
        0.01,
    )
    monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)
    read_count = 0

    def read_message() -> dict[str, Any]:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return {
                "type": "voice.start",
                "id": "voice-start-blocked",
                "mode": "direct",
            }
        assert start_entered.wait(timeout=1.0)
        return {"type": "shutdown", "id": "shutdown-during-start"}

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)

    started_at = time.monotonic()
    result = sidecar.main()
    elapsed = time.monotonic() - started_at
    captured = capsys.readouterr()

    assert result == 0
    assert elapsed < 0.3
    assert [reply["type"] for reply in replies] == [
        "hello",
        "shutdown.ack",
    ]
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "baxy_mind_reap_incomplete:request_dispatch_thread:timed_out",
        "baxy_mind_reap_incomplete:voice_engine_shutdown:timed_out",
    ]

    release_start.set()
    assert shutdown_finished.wait(timeout=1.0)
    assert [reply["type"] for reply in replies] == [
        "hello",
        "shutdown.ack",
    ]


def test_serial_lane_bounds_backlog_and_reserves_control_barriers() -> None:
    lane = sidecar._SerialRequestLane(pending_limit=2)
    active = {"type": "voice.speak", "id": "active"}
    pending = {"type": "voice.start", "id": "pending"}

    assert (
        lane.submit(active)
        is sidecar._LaneSubmission.ACCEPTED
    )
    assert lane.read_message() is active
    assert (
        lane.submit(pending)
        is sidecar._LaneSubmission.ACCEPTED
    )
    assert (
        lane.submit({"type": "narrate", "id": "queued"})
        is sidecar._LaneSubmission.ACCEPTED
    )
    assert (
        lane.submit({"type": "plan", "id": "overflow"})
        is sidecar._LaneSubmission.FULL
    )
    blocking_work, replay_token = lane.voice_cancel_snapshot()
    assert blocking_work
    assert replay_token is not None
    assert lane.schedule_voice_cancel_replay(replay_token)
    assert not lane.schedule_voice_cancel_replay(replay_token)
    assert (
        lane.submit(
            {"type": "shutdown", "id": "reserved"},
            reserved=True,
        )
        is sidecar._LaneSubmission.ACCEPTED
    )
    assert len(lane._pending) == 4

    original_kind = lane._kind
    lane._kind = lambda _message: (_ for _ in ()).throw(
        AssertionError("hot-path queue scan")
    )
    try:
        assert lane.has_blocking_work()
    finally:
        lane._kind = original_kind

    failure_lane = sidecar._SerialRequestLane(pending_limit=1)
    accepted = {"type": "narrate", "id": "accepted-before-failure"}
    violation = protocol.ProtocolViolation("malformed_json", "fixture")
    assert (
        failure_lane.submit(accepted)
        is sidecar._LaneSubmission.ACCEPTED
    )
    assert (
        failure_lane.submit({"type": "plan", "id": "overflow"})
        is sidecar._LaneSubmission.FULL
    )
    assert (
        failure_lane.submit(sidecar._ReadFailure(violation))
        is sidecar._LaneSubmission.ACCEPTED
    )
    failure_lane.close(drop_pending=False)
    assert failure_lane.read_message() is accepted
    failure_lane.finish(accepted)
    with pytest.raises(protocol.ProtocolViolation) as captured:
        failure_lane.read_message()
    assert captured.value is violation


def test_bounded_control_plane_rejects_overload_once_and_keeps_controls_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    narrate_started = threading.Event()
    release_narrate = threading.Event()
    voice_ready = threading.Event()
    cancel_observed = threading.Event()
    replies: list[dict[str, Any]] = []
    request_scopes: list[str] = []
    narrate_calls: list[str] = []

    class FakeLlmRuntime:
        @staticmethod
        def start_warmup() -> None:
            return None

        @staticmethod
        def begin_request(*_args: object, **_kwargs: object) -> None:
            request_scopes.append("begin")

        @staticmethod
        def end_request() -> None:
            request_scopes.append("end")

        @staticmethod
        def narrate(
            user_text: str,
            *_args: object,
            **_kwargs: object,
        ) -> str:
            narrate_calls.append(user_text)
            narrate_started.set()
            assert release_narrate.wait(timeout=2.0)
            return "late"

        @staticmethod
        def close() -> None:
            release_narrate.set()

    class FakeRouter:
        @staticmethod
        def request_close() -> None:
            release_narrate.set()

        @staticmethod
        def close() -> None:
            release_narrate.set()

    class FakeVoiceEngine:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def status() -> dict[str, object]:
            voice_ready.set()
            return {"state": "idle"}

        @staticmethod
        def cancel_speech() -> None:
            cancel_observed.set()

        @staticmethod
        def shutdown() -> None:
            return None

    monkeypatch.setattr(sidecar, "LlmRuntime", FakeLlmRuntime)
    monkeypatch.setattr(sidecar, "VoiceEngine", FakeVoiceEngine)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setattr(sidecar, "_write", replies.append)
    monkeypatch.setattr(sidecar, "SERIAL_PENDING_REQUEST_LIMIT", 2)
    monkeypatch.setattr(sidecar, "CONTROL_EVENT_QUEUE_LIMIT", 2)
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    queue_instances: list[Any] = []
    original_queue = sidecar.queue.Queue

    class RecordingQueue(original_queue):
        def __init__(self, maxsize: int = 0) -> None:
            super().__init__(maxsize=maxsize)
            self.high_water = 0
            queue_instances.append(self)

        def put(self, item: object, *args: object, **kwargs: object) -> None:
            super().put(item, *args, **kwargs)
            self.high_water = max(self.high_water, self.qsize())

    monkeypatch.setattr(sidecar.queue, "Queue", RecordingQueue)

    overflow_ids = [f"overflow-{index}" for index in range(24)]
    messages = [
        {"type": "voice.status", "id": "voice-ready"},
        {
            "type": "narrate",
            "id": "narrate-active",
            "userText": "active",
            "operation": "system.time",
            "outcome": {},
        },
        *[
            {
                "type": "narrate",
                "id": request_id,
                "userText": request_id,
                "operation": "system.time",
                "outcome": {},
            }
            for request_id in overflow_ids
        ],
        {"type": "voice.cancel", "id": "cancel-overload"},
        {"type": "shutdown", "id": "shutdown-overload"},
    ]
    pending = iter(messages)
    read_count = 0

    def read_message() -> dict[str, Any]:
        nonlocal read_count
        if read_count == 1:
            assert voice_ready.wait(timeout=1.0)
        elif read_count == 2:
            assert narrate_started.wait(timeout=1.0)
        read_count += 1
        return next(pending)

    monkeypatch.setattr(sidecar, "_open_protocol_reader", lambda: read_message)

    result = sidecar.main()

    assert result == 0
    assert len(queue_instances) == 1
    assert queue_instances[0].maxsize == 2
    assert 0 < queue_instances[0].high_water <= 2
    assert cancel_observed.is_set()
    assert narrate_calls == ["active"]
    assert request_scopes == ["begin", "end", "begin", "end"]
    assert replies[-1] == {
        "type": "shutdown.ack",
        "id": "shutdown-overload",
    }
    assert sum(
        reply.get("id") == "cancel-overload"
        and reply.get("type") == "voice.cancelled"
        for reply in replies
    ) == 1

    overflow_replies = {
        str(reply.get("id")): reply
        for reply in replies
        if reply.get("id") in overflow_ids
    }
    accepted_ids = set(overflow_ids[:2])
    assert sum(
        reply.get("id") in overflow_ids
        for reply in replies
    ) == len(overflow_ids) - len(accepted_ids)
    assert set(overflow_replies) == set(overflow_ids) - accepted_ids
    assert all(
        reply == {
            "type": "error",
            "id": request_id,
            "code": "request_failed",
            "message": "request_runtime_failure",
        }
        for request_id, reply in overflow_replies.items()
    )
