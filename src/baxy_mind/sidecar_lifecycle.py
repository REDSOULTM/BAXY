"""The sidecar's owned resources (voice engine, model, router, dispatch and promotion threads), each released once
and in dependency order.
"""

from __future__ import annotations

import sys
import threading
from typing import Any, Callable

from .process_lifecycle import ReapResource, ReapStatus, report_incomplete_reap


BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS = 0.15
BACKGROUND_WORKER_ABORT_JOIN_SECONDS = 0.25


class _SidecarLifecycle:
    """Own sidecar resources and release each one once in dependency order."""

    def __init__(self) -> None:
        self._ownership_lock = threading.Lock()
        self._voice_engine: Any | None = None
        self._voice_cancel_pending = False
        self._llm: Any | None = None
        self._planner_promotion_thread: threading.Thread | None = None
        self._planner_promotion_stop: threading.Event | None = None
        self._dispatch_thread: threading.Thread | None = None
        self._router: Any | None = None
        self._closed = False

    def _claim(
        self,
        current: Any | None,
        resource: Any,
        name: str,
    ) -> Any:
        if self._closed:
            raise RuntimeError("sidecar lifecycle is already closed")
        if current is not None:
            raise RuntimeError(f"{name} already has an owner")
        return resource

    def own_voice_engine(self, voice_engine: Any) -> Any:
        ownership_error: RuntimeError | None = None
        cleanup_rejected_candidate = False
        apply_pending_cancel = False
        with self._ownership_lock:
            try:
                self._voice_engine = self._claim(
                    self._voice_engine,
                    voice_engine,
                    "voice engine",
                )
            except RuntimeError as error:
                ownership_error = error
                cleanup_rejected_candidate = self._voice_engine is not voice_engine
            else:
                apply_pending_cancel = self._voice_cancel_pending
                self._voice_cancel_pending = False
        if ownership_error is not None:
            if cleanup_rejected_candidate:
                try:
                    voice_engine.shutdown()
                except BaseException as cleanup_error:
                    _report_secondary_cleanup_failure(cleanup_error)
            raise ownership_error
        if apply_pending_cancel:
            try:
                voice_engine.cancel_speech()
            except Exception as cancel_error:  # noqa: BLE001 - retry by barrier
                _report_deferred_voice_cancel_failure(cancel_error)
        return voice_engine

    def own_llm(self, llm: Any) -> Any:
        with self._ownership_lock:
            self._llm = self._claim(self._llm, llm, "LLM runtime")
        return llm

    def own_planner_promotion(
        self,
        thread: threading.Thread,
        stop_event: threading.Event,
    ) -> threading.Thread:
        with self._ownership_lock:
            self._planner_promotion_thread = self._claim(
                self._planner_promotion_thread,
                thread,
                "planner promotion thread",
            )
            self._planner_promotion_stop = self._claim(
                self._planner_promotion_stop,
                stop_event,
                "planner promotion stop event",
            )
        return thread

    def own_dispatch_thread(
        self,
        thread: threading.Thread,
    ) -> threading.Thread:
        with self._ownership_lock:
            self._dispatch_thread = self._claim(
                self._dispatch_thread,
                thread,
                "request dispatch thread",
            )
        return thread

    def own_router(self, router: Any) -> Any:
        with self._ownership_lock:
            self._router = self._claim(
                self._router,
                router,
                "intent router",
            )
        return router

    def request_voice_cancel(
        self,
        *,
        defer_if_unowned: bool,
    ) -> bool:
        """Cancel owned TTS or record one intent for lazy voice ownership."""

        with self._ownership_lock:
            if self._closed:
                return False
            voice_engine = self._voice_engine
            if voice_engine is None and defer_if_unowned:
                self._voice_cancel_pending = True
                return True
        if voice_engine is None:
            return False
        voice_engine.cancel_speech()
        return True

    def close(self) -> None:
        with self._ownership_lock:
            if self._closed:
                return
            self._closed = True
            self._voice_cancel_pending = False

        cleanup_errors: list[BaseException] = []

        def attempt(callback: Callable[[], Any]) -> tuple[bool, Any]:
            try:
                return True, callback()
            except BaseException as error:  # noqa: BLE001 - finish teardown
                cleanup_errors.append(error)
                return False, None

        def observed_reap_status(
            attempt_succeeded: bool,
            resource_stopped: bool,
        ) -> ReapStatus:
            if resource_stopped:
                return ReapStatus.REAPED
            return ReapStatus.TIMED_OUT if attempt_succeeded else ReapStatus.FAILED

        if self._planner_promotion_stop is not None:
            self._planner_promotion_stop.set()

        voice_shutdown_errors: list[BaseException] = []
        voice_shutdown_thread: threading.Thread | None = None
        voice_shutdown_error_collected = False
        voice_shutdown_started = False
        voice_stopped = True
        voice_reap_status = ReapStatus.ABSENT
        voice_engine = self._voice_engine

        def shutdown_voice() -> None:
            try:
                voice_engine.shutdown()
            except BaseException as error:  # noqa: BLE001 - relay to owner
                voice_shutdown_errors.append(error)

        def collect_voice_shutdown_error() -> None:
            nonlocal voice_shutdown_error_collected, voice_reap_status
            if (
                voice_shutdown_error_collected
                or not voice_stopped
                or not voice_shutdown_errors
            ):
                return
            voice_shutdown_error_collected = True
            voice_reap_status = ReapStatus.FAILED
            cleanup_errors.append(voice_shutdown_errors[0])

        if voice_engine is not None:
            voice_shutdown_thread = threading.Thread(
                target=shutdown_voice,
                name="baxy-voice-shutdown",
                daemon=True,
            )
            ok, _ = attempt(voice_shutdown_thread.start)
            voice_shutdown_started = ok
            if ok:
                ok, _ = attempt(
                    lambda: voice_shutdown_thread.join(
                        timeout=BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS,
                    )
                )
                voice_stopped = not voice_shutdown_thread.is_alive()
                voice_reap_status = observed_reap_status(
                    ok,
                    voice_stopped,
                )
                collect_voice_shutdown_error()
            else:
                voice_stopped = False
                voice_reap_status = ReapStatus.FAILED
        if self._llm is not None:
            attempt(self._llm.close)

        planner_stopped = True
        planner_reap_status = ReapStatus.ABSENT
        planner_thread = self._planner_promotion_thread
        if (
            planner_thread is not None
            and planner_thread is not threading.current_thread()
            and planner_thread.is_alive()
        ):
            ok, _ = attempt(
                lambda: planner_thread.join(
                    timeout=BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            )
            planner_stopped = not planner_thread.is_alive()
            planner_reap_status = observed_reap_status(
                ok,
                planner_stopped,
            )
        elif planner_thread is not None:
            planner_stopped = not planner_thread.is_alive()
            planner_reap_status = (
                ReapStatus.REAPED if planner_stopped else ReapStatus.TIMED_OUT
            )

        dispatch_stopped = True
        dispatch_reap_status = ReapStatus.ABSENT
        dispatch_thread = self._dispatch_thread
        if (
            dispatch_thread is not None
            and dispatch_thread is not threading.current_thread()
            and dispatch_thread.is_alive()
        ):
            ok, _ = attempt(
                lambda: dispatch_thread.join(
                    timeout=BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            )
            dispatch_stopped = not dispatch_thread.is_alive()
            dispatch_reap_status = observed_reap_status(
                ok,
                dispatch_stopped,
            )
        elif dispatch_thread is not None:
            dispatch_stopped = not dispatch_thread.is_alive()
            dispatch_reap_status = (
                ReapStatus.REAPED if dispatch_stopped else ReapStatus.TIMED_OUT
            )

        # Normal shutdown remains graceful when the optional workers observed
        # their stop signals. If a worker is still inside model/encoder I/O,
        # abort the transport without waiting for its serialized request lock.
        if self._router is not None and (
            not planner_stopped or not dispatch_stopped
        ):
            request_close = getattr(self._router, "request_close", None)
            if callable(request_close):
                attempt(request_close)
            if (
                planner_thread is not None
                and planner_thread is not threading.current_thread()
                and planner_thread.is_alive()
            ):
                ok, _ = attempt(
                    lambda: planner_thread.join(
                        timeout=BACKGROUND_WORKER_ABORT_JOIN_SECONDS,
                    )
                )
                planner_stopped = not planner_thread.is_alive()
                planner_reap_status = observed_reap_status(
                    ok,
                    planner_stopped,
                )
            if (
                dispatch_thread is not None
                and dispatch_thread is not threading.current_thread()
                and dispatch_thread.is_alive()
            ):
                ok, _ = attempt(
                    lambda: dispatch_thread.join(
                        timeout=BACKGROUND_WORKER_ABORT_JOIN_SECONDS,
                    )
                )
                dispatch_stopped = not dispatch_thread.is_alive()
                dispatch_reap_status = observed_reap_status(
                    ok,
                    dispatch_stopped,
                )

        if (
            voice_shutdown_thread is not None
            and voice_shutdown_started
            and voice_shutdown_thread.is_alive()
        ):
            ok, _ = attempt(
                lambda: voice_shutdown_thread.join(
                    timeout=BACKGROUND_WORKER_ABORT_JOIN_SECONDS,
                )
            )
            voice_stopped = not voice_shutdown_thread.is_alive()
            voice_reap_status = observed_reap_status(
                ok,
                voice_stopped,
            )
            collect_voice_shutdown_error()

        if self._router is not None:
            attempt(self._router.close)

        if (
            planner_thread is not None
            and planner_thread is not threading.current_thread()
        ):
            planner_stopped = not planner_thread.is_alive()
            if planner_stopped:
                planner_reap_status = ReapStatus.REAPED
        if (
            dispatch_thread is not None
            and dispatch_thread is not threading.current_thread()
        ):
            dispatch_stopped = not dispatch_thread.is_alive()
            if dispatch_stopped:
                dispatch_reap_status = ReapStatus.REAPED
        if voice_shutdown_thread is not None and voice_shutdown_started:
            voice_stopped = not voice_shutdown_thread.is_alive()
            if voice_stopped and voice_reap_status is not ReapStatus.FAILED:
                voice_reap_status = ReapStatus.REAPED
            collect_voice_shutdown_error()

        report_incomplete_reap(
            ReapResource.PLANNER_PROMOTION_THREAD,
            planner_reap_status,
        )
        report_incomplete_reap(
            ReapResource.REQUEST_DISPATCH_THREAD,
            dispatch_reap_status,
        )
        report_incomplete_reap(
            ReapResource.VOICE_ENGINE_SHUTDOWN,
            voice_reap_status,
        )

        if cleanup_errors:
            raise cleanup_errors[0]


def _report_secondary_cleanup_failure(error: BaseException) -> None:
    """Emit only a stable local type; stdout remains reserved for JSONL."""

    try:
        sys.stderr.write(f"baxy_mind_cleanup_failure:{type(error).__name__}\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change shutdown
        pass


def _report_deferred_voice_cancel_failure(error: BaseException) -> None:
    """Report a failed lazy cancel intent without leaking request content."""

    try:
        sys.stderr.write(
            f"baxy_mind_deferred_voice_cancel_failure:{type(error).__name__}\n"
        )
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change control flow
        pass
