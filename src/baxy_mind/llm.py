"""LLM de conversación/tools: Qwen3-4B Q4_K_M vía llama-server (ADR-0005).

llama-server corre como subproceso del sidecar en 127.0.0.1 (puerto efímero).
El Job Object kill-on-close del shell mata el árbol completo al cerrar.
Fallback CPU por construcción: BAXY_MIND_NGL=0.

Config por entorno:
- BAXY_MIND_LLM_GGUF: ruta del GGUF (obligatoria para levantar el LLM).
- BAXY_MIND_LLAMA_SERVER: ruta de llama-server.exe.
- BAXY_MIND_NGL: capas en GPU (default 99; 0 = CPU puro).
- BAXY_MIND_CTX: contexto por ranura (default 10240, máximo 12288). El decisor en
  contexto lleva el catálogo entero (~6 k tokens) en su ranura; medido con
  Qwen3.5-4B Q4_K_M, 3 ranuras × 12 288 en la app: 3 876–3 908 MiB de pico del
  servidor (goal v3, meta ≤ 3,8 GB); con 10 240 por ranura baja ≈ 128 MiB (M61,
  2026-09-29). Otro modelo necesita su propia medición física.
- BAXY_MIND_LLM_INVALID_JSON_DIR: diagnóstico local opt-in; conserva sólo la
  respuesta inválida sanitizada y metadatos de terminación, nunca el prompt.
"""

from __future__ import annotations

import contextlib
from collections import OrderedDict
import json
import math
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable
from . import llm_startup
from .cpu_prose_adapter import CpuProseAdapter
from .decider_adapter import DeciderAdapter
from .llm_transport import ChatCompletionCancellation, ChatCompletionConnectionPool, SlotState, post_chat_completion
from .process_lifecycle import (
    end_with_this_process,
    ReapResource,
    ReapStatus,
    report_incomplete_reap,
    terminate_and_reap_bounded,
)
from .time_budget import remaining_seconds
from .llm_settings import (
    _batch_sizes_from_env, _context_size_from_env, _kv_cache_type_from_env, _kv_offload_from_env,
    _loopback_endpoint_from_env, _own_decider_state_dir, _request_timeout_from_env, DEFAULT_KV_CACHE_TYPE_V,
    GPU_SERVER_SLOTS, LLM_HEALTH_POLL_INTERVAL_SECONDS, LLM_HEALTH_POLL_TIMEOUT_SECONDS,
    VALIDATED_CLASSIFIER_REUSE_CAPACITY,
)
from .llm_grammar import _compact_structured_grammar, _grammar_safe_payload
from .llm_audit import _capture_invalid_schema_response, _capture_model_call_timing
from .native_selection import (
    _native_prose_without_call, _native_selection_description, _native_selection_may_continue,
    NATIVE_SELECTION_CALL_TOKENS, NATIVE_SELECTION_PROSE_TOKENS, NATIVE_TOOL_POLICY_PROMPT,
)
from .dialogue_history import _bounded_history, _normalized_dialogue_text
from .reply_budget import _decode_rate_of, _DECODE_RATE_WEIGHT
from .argument_payload import DirectArgumentExtraction
from .llm_chat import ChatMixin, _PreparedChat
from .llm_request_checks import RequestChecksMixin
from .llm_decider import DeciderMixin
from .llm_clarify import ClarifyMixin
from .llm_plans import PlanArgumentsMixin
from .llm_compose import ComposeMixin


LLM_PROCESS_CLOSE_TIMEOUT_SECONDS = 0.25
LLM_PROCESS_FINAL_REAP_TIMEOUT_SECONDS = 0.1
LLM_WARMUP_CLOSE_TIMEOUT_SECONDS = 0.5


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]




class LlmRuntime(ChatMixin, RequestChecksMixin, DeciderMixin, ClarifyMixin, PlanArgumentsMixin, ComposeMixin):
    def __init__(self) -> None:
        endpoint = _loopback_endpoint_from_env()
        gguf = os.environ.get("BAXY_MIND_LLM_GGUF")
        server = os.environ.get("BAXY_MIND_LLAMA_SERVER")
        if endpoint is None:
            if not gguf or not Path(gguf).is_file():
                raise FileNotFoundError(f"GGUF no encontrado: {gguf}")
            if not server or not Path(server).is_file():
                raise FileNotFoundError(f"llama-server no encontrado: {server}")
        self._request_timeout = _request_timeout_from_env()
        self._request_total_deadline: float | None = None
        self._request_total_maximum_timeout: float | None = None
        self._request_deadline: float | None = None
        self._request_maximum_timeout: float | None = None
        self._request_attempt = 0
        self._request_identity = ""
        self._semantic_effect_cache: dict[
            str,
            tuple[str, str | None],
        ] = {}
        self._response_language_cache: dict[str, str] = {}
        self._rejected_reply_cache: dict[tuple[object, ...], str] = {}
        self._validated_classifier_reuse_enabled = endpoint is None
        self._validated_classifier_reuse_lock = threading.Lock()
        self._semantic_effect_reuse_cache: OrderedDict[
            str,
            tuple[str, str | None],
        ] = OrderedDict()
        self._response_language_reuse_cache: OrderedDict[
            str,
            str,
        ] = OrderedDict()
        self._effect_count_reuse_cache: OrderedDict[
            str,
            str,
        ] = OrderedDict()
        self._operation_compatibility_reuse_cache: OrderedDict[
            str,
            bool,
        ] = OrderedDict()
        self._completion_cancellation_state = threading.local()
        self._deferred_language_work: (
            tuple[
                str,
                ChatCompletionCancellation,
                Any,
            ]
            | None
        ) = None
        self._deferred_count_work: (
            tuple[
                str,
                ChatCompletionCancellation,
                Any,
            ]
            | None
        ) = None
        self._speculative_chat_handoff: _PreparedChat | None = None
        # M117: the contextual decision started with the turn (``prepare_decision``), keyed by its whole payload.
        self._prepared_decision: tuple[str, ChatCompletionCancellation, Future] | None = None
        self._direct_argument_handoff: (
            tuple[
                str,
                float,
                DirectArgumentExtraction,
            ]
            | None
        ) = None
        self._gguf = gguf
        self._server = server
        self._endpoint = endpoint
        self._cpu_prose_adapter = CpuProseAdapter.from_environment(gguf)
        self._decider_adapter = DeciderAdapter.from_environment(gguf)
        if self._cpu_prose_adapter is not None and self._decider_adapter is not None:
            # Both would be the server's adapter 0; each role turns only its own on.
            raise ValueError("cpu_prose_adapter_and_decider_adapter_exclusive")
        # AUTO can abstain; the previously rejected REQUIRED policy could not.
        # Native selection preserves scope that the separate type classifier
        # erased in C03. Downstream catalog, argument and invocation checks own
        # execution. The existing override retains the JSON comparison path.
        native_policy_override = os.environ.get("BAXY_MIND_NATIVE_TOOL_POLICY")
        if native_policy_override is None:
            self._native_tool_policy_enabled = True
        elif native_policy_override.strip() in {"1", "true", "yes"}:
            self._native_tool_policy_enabled = True
        elif native_policy_override.strip() in {"0", "false", "no"}:
            self._native_tool_policy_enabled = False
        else:
            raise ValueError("BAXY_MIND_NATIVE_TOOL_POLICY inválido")
        self._parallel_turn_verification = (
            endpoint is None and os.environ.get("BAXY_MIND_NGL", "99").strip() != "0"
        )
        self._speculative_count_after_guard = self._parallel_turn_verification
        self._speculative_knowledge_enabled = self._parallel_turn_verification
        self._external_ready = False
        self._port: int | None = None
        self._process: subprocess.Popen | None = None
        self._startup_lock = threading.Lock()
        self._warmup_lock = threading.Lock()
        self._warmup_thread: threading.Thread | None = None
        self._warmup_ready = threading.Event()
        self._warmup_done = threading.Event()
        self._close_event = threading.Event()
        self._lifecycle_lock = threading.Lock()
        self._http_connection_pool = ChatCompletionConnectionPool(
            max_connections=GPU_SERVER_SLOTS,
            server_slots=self._parallel_turn_verification,
        )

    def _server_command(self) -> list[str]:
        """Build the bounded local inference profile used by the sidecar.

        Quantized KV cache plus Flash Attention preserve the current 4K conversational
        window per slot while reducing cache pressure. The GPU profile uses
        three continuously batched slots so the primary policy, independent
        semantic verifier and independent language detector can run together;
        the HTTP pool assigns them (``id_slot``) and keeps one for the selector.
        CPU fallback defaults to one slot; a bounded experiment may retain two
        or three alternating prompt prefixes without granting parallel policy
        authority.
        """

        gpu_layers = os.environ.get("BAXY_MIND_NGL", "99").strip()
        cpu_only = gpu_layers == "0"
        kv_offload = _kv_offload_from_env() and not cpu_only
        kv_cache_type = _kv_cache_type_from_env()
        parallel = (
            GPU_SERVER_SLOTS if getattr(self, "_parallel_turn_verification", False) else 1
        )
        context_size = _context_size_from_env()
        batch_size, ubatch_size = _batch_sizes_from_env()
        command = [
            str(self._server),
            "-m",
            str(self._gguf),
            "--host",
            "127.0.0.1",
            "--port",
            str(self._port),
            "-ngl",
            gpu_layers,
            "-c",
            str(context_size * parallel),
            "-b",
            str(batch_size),
            "-ub",
            str(ubatch_size),
            # The measured quantized V cache requires Flash Attention in llama.cpp.
            # CPU fallback still has no GPU compute/offload because -dev none
            # and the three explicit no-offload flags below are authoritative.
            "-fa",
            "on",
            "-ctk",
            kv_cache_type,
            "-ctv",
            (
                _kv_cache_type_from_env(os.environ["BAXY_MIND_KV_CACHE_TYPE_V"])
                if "BAXY_MIND_KV_CACHE_TYPE_V" in os.environ
                else kv_cache_type if "BAXY_MIND_KV_CACHE_TYPE" in os.environ else DEFAULT_KV_CACHE_TYPE_V
            ),
            "-np",
            str(parallel),
            "--jinja",
            "--reasoning",
            "off",
            "--reasoning-budget",
            "0",
            # The backend's optional host prompt cache otherwise grows up to
            # 8 GiB. Recompute evicted prefixes within the same active context.
            "--cache-ram",
            "0",
        ]
        if not cpu_only:
            # GPU weights need not retain resident pages of the mapped GGUF.
            # Measured with the same context and replies in C03 runs 423/424.
            command.append("--no-mmap")
        if parallel > 1:
            command.append("--cont-batching")
        for adapter in (getattr(self, "_cpu_prose_adapter", None), getattr(self, "_decider_adapter", None)):
            if adapter is not None:
                command.extend(adapter.server_arguments())
        state_dir = getattr(self, "_decider_state_dir", None)
        if state_dir is not None:
            # Estabilización A: the decider's slot starts every decision from its saved catalog state.
            command.extend(["--slot-save-path", str(state_dir)])
        if not kv_offload:
            command.append("--no-kv-offload")
        if cpu_only:
            # ``-ngl 0`` alone still initializes CUDA buffers in the pinned
            # WDDM build. These supported llama.cpp flags keep compute and
            # model/KV/operator offload on CPU; the CUDA-linked executable may
            # still reserve a small WDDM allocation, measured separately.
            command.extend(
                [
                    "-dev",
                    "none",
                    "--no-op-offload",
                    "--no-mmproj-offload",
                ]
            )
        return command

    def _ensure_started(self) -> None:
        self._raise_if_closed()
        deadline = getattr(self, "_request_deadline", None)
        if deadline is None:
            acquired = self._startup_lock.acquire()
        else:
            acquired = self._startup_lock.acquire(
                timeout=self._remaining_request_timeout()
            )
        if not acquired:
            raise TimeoutError("se agotó el presupuesto mientras iniciaba el LLM")
        try:
            self._raise_if_closed()
            self._ensure_started_locked()
        finally:
            self._startup_lock.release()

    def _ensure_started_locked(self) -> None:
        lifecycle_lock = self._lifecycle_lock_for()
        with lifecycle_lock:
            self._raise_if_closed()
            owned_process = self._process
            if owned_process is not None and owned_process.poll() is None:
                self._warmup_ready.set()
                return
        # An internally owned process must be checked before treating a
        # populated endpoint as an externally managed server.  Otherwise a
        # llama-server that exits after warmup leaves a permanently dead port
        # which every retry reuses.
        if owned_process is not None:
            # A dead child is a transient transport fault, not a permanent
            # runtime shutdown. Keep this teardown separate from ``close`` so
            # a later request can legitimately retry startup.
            self._stop_owned_process()
        self._raise_if_closed()
        if self._endpoint is not None:
            if not self._external_ready:
                deadline = getattr(self, "_request_deadline", None)
                timeout = (
                    420.0 if deadline is None else self._remaining_request_timeout()
                )
                self._wait_ready(timeout)
            with lifecycle_lock:
                self._raise_if_closed()
                self._external_ready = True
                self._warmup_ready.set()
            return
        # r22: a model that cannot fit in the free VRAM fails now with its
        # cause instead of being launched to die while warming up.
        llm_startup.require_vram_for(
            getattr(self, "_gguf", None),
            cpu_only=os.environ.get("BAXY_MIND_NGL", "99").strip() == "0",
        )
        port = _free_port()
        with lifecycle_lock:
            self._raise_if_closed()
            self._port = port
            if getattr(self, "_parallel_turn_verification", False) and getattr(self, "_decider_state_dir", None) is None:
                self._decider_state_dir, self._decider_state_lock = _own_decider_state_dir()
            command = self._server_command()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            # Encargo I2: the server never outlives this mind, even one killed without close.
            end_with_this_process(process)
        except Exception:
            with lifecycle_lock:
                if self._process is None and self._port == port:
                    self._port = None
            raise
        with lifecycle_lock:
            # Child creation itself stays outside the lifecycle lock so a
            # blocked OS spawn cannot block ``close``. Publication is atomic:
            # a child that finishes spawning after close is killed locally and
            # never becomes the runtime's active server.
            if self._is_closed():
                publish_process = False
            else:
                self._port = port
                self._process = process
                self._endpoint = f"http://127.0.0.1:{port}"
                # The server's own startup lines, kept only until it is ready.
                self._server_stderr = llm_startup.StderrTail(process.stderr)
                publish_process = True
        if not publish_process:
            try:
                self._terminate_process(process)
            finally:
                raise RuntimeError("llama-server runtime is closed")
        deadline = getattr(self, "_request_deadline", None)
        startup_timeout = (
            420.0 if deadline is None else self._remaining_request_timeout()
        )
        try:
            self._wait_ready(startup_timeout)
            with lifecycle_lock:
                self._raise_if_closed()
                self._external_ready = True
                self._warmup_ready.set()
        except Exception:
            self._stop_owned_process()
            raise

    def start_warmup(self) -> None:
        """Load the local model once in the background, without blocking hello."""

        with self._warmup_lock:
            if self._is_closed():
                self._warmup_done.set()
                return
            if self._warmup_thread is not None and self._warmup_thread.is_alive():
                return
            if self._warmup_ready.is_set():
                self._warmup_done.set()
                return
            self._warmup_done.clear()

            def warmup() -> None:
                try:
                    self._ensure_started()
                    self._startup_failure = None
                except Exception as error:  # noqa: BLE001 - kept as its cause
                    # A real request may retry; startup must remain fail-closed.
                    # The cause stays for the catalog reply (r22: it was lost).
                    self._startup_failure = llm_startup.failure_of(error)
                    return
                finally:
                    # Completion and readiness are separate signals. A failed
                    # process wakes the catalog handshake immediately instead
                    # of looking indistinguishable from a slow cold start.
                    self._warmup_done.set()

            self._warmup_thread = threading.Thread(
                target=warmup,
                name="baxy-llm-warmup",
                daemon=True,
            )
            self._warmup_thread.start()

    def startup_failure(self) -> llm_startup.LlmStartupFailure | None:
        """Why the last warmup failed, or None while none failed."""

        return getattr(self, "_startup_failure", None)

    def wait_warmup(self, timeout: float) -> bool:
        if self._warmup_ready.is_set():
            return True
        self._warmup_done.wait(timeout=self._normalize_request_budget(timeout))
        return self._warmup_ready.is_set()

    def _wait_ready(self, timeout: float = 420.0) -> None:
        process = self._process
        endpoint = self._endpoint
        if endpoint is None:
            raise RuntimeError("llama-server no fue iniciado")
        maximum_timeout = self._normalize_request_budget(timeout)
        deadline = time.monotonic() + maximum_timeout

        def current_remaining() -> float:
            local_remaining = remaining_seconds(
                deadline,
                maximum_timeout,
                now=time.monotonic(),
            )
            request_remaining = self._request_remaining_seconds()
            return (
                local_remaining
                if request_remaining is None
                else min(local_remaining, request_remaining)
            )

        while True:
            remaining = current_remaining()
            if remaining <= 0.0:
                break
            self._raise_if_closed()
            if process is not None and process.poll() is not None:
                stderr_tail = getattr(self, "_server_stderr", None)
                raise llm_startup.exit_failure(
                    process.returncode,
                    stderr_tail.tail() if stderr_tail is not None else (),
                )
            healthy = False
            try:
                with urllib.request.urlopen(
                    f"{endpoint}/health",
                    timeout=min(LLM_HEALTH_POLL_TIMEOUT_SECONDS, remaining),
                ) as response:
                    healthy = response.status == 200 and current_remaining() > 0.0
            except Exception:
                remaining = current_remaining()
                if remaining <= 0.0:
                    break
                close_event = getattr(self, "_close_event", None)
                pause = min(LLM_HEALTH_POLL_INTERVAL_SECONDS, remaining)
                if close_event is not None:
                    close_event.wait(timeout=pause)
                else:
                    time.sleep(pause)
            if healthy:
                stderr_tail = getattr(self, "_server_stderr", None)
                if stderr_tail is not None:
                    stderr_tail.stop_recording()
                for adapter in (getattr(self, "_cpu_prose_adapter", None), getattr(self, "_decider_adapter", None)):
                    if adapter is not None:
                        adapter.initialize(endpoint, current_remaining())
                return
        raise TimeoutError("llama-server no quedó listo")

    def _lifecycle_lock_for(self) -> threading.Lock:
        lifecycle_lock = getattr(self, "_lifecycle_lock", None)
        if lifecycle_lock is None:
            # Some boundary tests construct only the fields they exercise.
            # Production instances always initialize this lock in ``__init__``.
            lifecycle_lock = threading.Lock()
            self._lifecycle_lock = lifecycle_lock
        return lifecycle_lock

    def _is_closed(self) -> bool:
        close_event = getattr(self, "_close_event", None)
        return close_event is not None and close_event.is_set()

    def _raise_if_closed(self) -> None:
        if self._is_closed():
            raise RuntimeError("llama-server runtime is closed")

    def _detach_owned_process_locked(self) -> subprocess.Popen | None:
        process = getattr(self, "_process", None)
        self._process = None
        self._port = None
        self._clear_validated_classifier_reuse()
        if getattr(self, "_external_ready", False):
            self._external_ready = False
        if hasattr(self, "_warmup_ready"):
            self._warmup_ready.clear()
        if process is not None:
            self._endpoint = None
        return process

    def _clear_validated_classifier_reuse(self) -> None:
        """Forget model-derived values when the owned model process changes."""

        lock = getattr(self, "_validated_classifier_reuse_lock", None)
        if lock is None:
            return
        with lock:
            semantic_cache = getattr(
                self,
                "_semantic_effect_reuse_cache",
                None,
            )
            language_cache = getattr(
                self,
                "_response_language_reuse_cache",
                None,
            )
            count_cache = getattr(
                self,
                "_effect_count_reuse_cache",
                None,
            )
            compatibility_cache = getattr(
                self,
                "_operation_compatibility_reuse_cache",
                None,
            )
            if semantic_cache is not None:
                semantic_cache.clear()
            if language_cache is not None:
                language_cache.clear()
            if count_cache is not None:
                count_cache.clear()
            if compatibility_cache is not None:
                compatibility_cache.clear()

    def _validated_classifier_reuse_get(
        self,
        cache_name: str,
        text: str,
    ) -> object | None:
        if not getattr(
            self,
            "_validated_classifier_reuse_enabled",
            False,
        ):
            return None
        lock = getattr(self, "_validated_classifier_reuse_lock", None)
        cache = getattr(self, cache_name, None)
        if lock is None or cache is None:
            return None
        if not cache:
            # The first request through a fresh model process must not acquire
            # a lock or perturb the certified P/G/L launch schedule.
            return None
        with lock:
            value = cache.get(text)
            if value is not None:
                cache.move_to_end(text)
            return value

    def _validated_classifier_reuse_put(
        self,
        cache_name: str,
        text: str,
        value: object,
    ) -> None:
        if not getattr(
            self,
            "_validated_classifier_reuse_enabled",
            False,
        ):
            return
        lock = getattr(self, "_validated_classifier_reuse_lock", None)
        cache = getattr(self, cache_name, None)
        if lock is None or cache is None:
            return
        with lock:
            cache[text] = value
            cache.move_to_end(text)
            while len(cache) > VALIDATED_CLASSIFIER_REUSE_CAPACITY:
                cache.popitem(last=False)

    @staticmethod
    def _terminate_process(
        process: subprocess.Popen | None,
    ) -> ReapStatus:
        status = terminate_and_reap_bounded(
            process,
            timeout=LLM_PROCESS_CLOSE_TIMEOUT_SECONDS,
            final_wait=LLM_PROCESS_FINAL_REAP_TIMEOUT_SECONDS,
        )
        report_incomplete_reap(ReapResource.LLM_PROCESS, status)
        return status

    def _stop_owned_process(self) -> None:
        """Retire one child without permanently closing the runtime."""

        connection_pool = getattr(self, "_http_connection_pool", None)
        if connection_pool is not None:
            connection_pool.invalidate()
        with self._lifecycle_lock_for():
            process = self._detach_owned_process_locked()
        self._terminate_process(process)
        # Revisión A H1: the next server's slots start without the decider's adapter, and it clears a restored slot
        # when the decision brings the adapter: the first decision would be evaluated whole, from another state.
        # Its states are built again on it.
        state_dir = getattr(self, "_decider_state_dir", None)
        if state_dir is not None:
            for saved in Path(state_dir).glob("decider-*.bin"):
                with contextlib.suppress(OSError):
                    saved.unlink(missing_ok=True)

    def close(self) -> None:
        """Cancel startup and retire the owned child within a short bound."""

        self._retire_deferred_language_work()
        self._retire_deferred_count_work()
        self._retire_prepared_decision()
        self._retire_decider_warmup()
        with self._lifecycle_lock_for():
            close_event = getattr(self, "_close_event", None)
            if close_event is None:
                close_event = threading.Event()
                self._close_event = close_event
            close_event.set()
            process = self._detach_owned_process_locked()
            if hasattr(self, "_warmup_done"):
                self._warmup_done.set()

        connection_pool = getattr(self, "_http_connection_pool", None)
        if connection_pool is not None:
            connection_pool.close()
        self._terminate_process(process)
        warmup_thread = getattr(self, "_warmup_thread", None)
        if (
            warmup_thread is not None
            and warmup_thread is not threading.current_thread()
            and warmup_thread.is_alive()
        ):
            warmup_thread.join(timeout=LLM_WARMUP_CLOSE_TIMEOUT_SECONDS)

        # Defensive second pass for partially initialized instances; the
        # lifecycle lock already makes a post-close production spawn impossible.
        self._stop_owned_process()
        state_dir = getattr(self, "_decider_state_dir", None)
        self._decider_state_dir = None
        lock = getattr(self, "_decider_state_lock", None)
        self._decider_state_lock = None
        if lock is not None:
            lock.close()
        if state_dir is not None:
            shutil.rmtree(state_dir, ignore_errors=True)

    @staticmethod
    def _normalize_request_budget(timeout: float) -> float:
        try:
            budget = float(timeout)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, budget) if math.isfinite(budget) else 0.0

    def _request_remaining_seconds(self) -> float | None:
        deadline = getattr(self, "_request_deadline", None)
        maximum_timeout = getattr(self, "_request_maximum_timeout", None)
        if deadline is None or maximum_timeout is None:
            return None
        return remaining_seconds(
            deadline,
            maximum_timeout,
            now=time.monotonic(),
        )

    def _remaining_request_timeout(self) -> float:
        remaining = self._request_remaining_seconds()
        if remaining is None:
            raise RuntimeError("no hay un presupuesto local activo")
        if remaining <= 0.0:
            raise TimeoutError("se agotó el presupuesto local del LLM")
        return remaining

    def _retire_deferred_language_work(self) -> None:
        work = getattr(self, "_deferred_language_work", None)
        self._deferred_language_work = None
        if work is None:
            return
        _, cancellation, future = work
        cancellation.cancel()
        future.cancel()

    def _retire_prepared_chat(self) -> None:
        """Close a prepared reply nobody consumed, releasing its server slot."""

        prepared = getattr(self, "_speculative_chat_handoff", None)
        self._speculative_chat_handoff = None
        if prepared is not None:
            prepared.retire()

    def _retire_decider_warmup(self) -> None:
        """Cancel the decider's catalog warmup (``warm_decider``) that is still reading."""

        cancellation = getattr(self, "_decider_warmup", None)
        self._decider_warmup = None
        if cancellation is not None:
            cancellation.cancel()

    def _retire_prepared_decision(self) -> None:
        """Close a contextual decision prepared for a turn that no longer reads it."""

        prepared = getattr(self, "_prepared_decision", None)
        self._prepared_decision = None
        if prepared is not None:
            _, cancellation, future = prepared
            cancellation.cancel()
            future.cancel()

    def _retire_deferred_count_work(self) -> None:
        """Cancel a speculative V that no longer has a valid consumer."""

        work = getattr(self, "_deferred_count_work", None)
        self._deferred_count_work = None
        if work is None:
            return
        _, cancellation, future = work
        cancellation.cancel()
        future.cancel()

    def consume_deferred_response_language(
        self,
        text: str,
    ) -> tuple[bool, str | None]:
        """Consume the exact L future after the outer turn gates choose chat.

        The boolean distinguishes "there was no deferred inference" from "the
        one deferred inference failed".  A valid result is reused exactly;
        failure remains eligible for the original authoritative retry.
        """

        work = getattr(self, "_deferred_language_work", None)
        if work is None:
            return False, None
        deferred_text, _, future = work
        if deferred_text != text:
            self._retire_deferred_language_work()
            return False, None
        self._deferred_language_work = None
        try:
            result = future.result()
        except Exception:
            return True, None
        if result not in {"es", "en", "mixed"}:
            return True, None
        language = str(result)
        cache = getattr(self, "_response_language_cache", None)
        if cache is not None:
            cache[text] = language
        return True, language

    def retire_deferred_response_language(self, text: str) -> None:
        """Cancel an unused L only after the outer turn result is final."""

        work = getattr(self, "_deferred_language_work", None)
        if work is None:
            return
        if work[0] != text:
            self._retire_deferred_language_work()
            return
        self._retire_deferred_language_work()

    def begin_request(
        self,
        timeout: float,
        *,
        attempt: int = 0,
        identity: str = "",
    ) -> None:
        # `identity` es sólo diagnóstico: permite que una traza atribuya cada
        # POST al turno que lo originó en vez de adivinarlo por proximidad
        # temporal, que mezcla trabajo especulativo, cancelado y de otros
        # turnos. No influye en ninguna decisión ni en el prompt.
        self._request_identity = str(identity)[:128]
        self._retire_deferred_language_work()
        self._retire_deferred_count_work()
        maximum_timeout = self._normalize_request_budget(timeout)
        deadline = time.monotonic() + maximum_timeout
        self._request_total_deadline = deadline
        self._request_total_maximum_timeout = maximum_timeout
        self._request_deadline = deadline
        self._request_maximum_timeout = maximum_timeout
        self._request_attempt = max(0, int(attempt))
        self._semantic_effect_cache = {}
        self._response_language_cache = {}
        self._rejected_reply_cache = {}
        self._speculative_count_after_guard = bool(
            getattr(self, "_parallel_turn_verification", False)
        )
        self._retire_prepared_chat()
        self._retire_prepared_decision()

    def begin_request_attempt(self, timeout: float, *, attempt: int) -> None:
        """Cap one logical attempt inside the existing total request budget."""

        request_attempt = max(0, int(attempt))
        if request_attempt > 0:
            # G and L classify the unchanged request text, independently from
            # P. Reusing only completed values avoids paying both again when
            # the structured primary response alone needs a logical retry.
            semantic_effect_cache = dict(getattr(self, "_semantic_effect_cache", {}))
            response_language_cache = dict(
                getattr(self, "_response_language_cache", {})
            )
            # A greedy reply the contracts rejected is the same draft again when the retried decision asks
            # for it with the same inputs (``chat``).
            rejected_reply_cache = dict(getattr(self, "_rejected_reply_cache", {}))
        else:
            semantic_effect_cache = {}
            response_language_cache = {}
            rejected_reply_cache = {}
        self._retire_deferred_language_work()
        self._retire_deferred_count_work()
        total_deadline = getattr(self, "_request_total_deadline", None)
        total_maximum_timeout = getattr(
            self,
            "_request_total_maximum_timeout",
            None,
        )
        if total_deadline is None or total_maximum_timeout is None:
            raise RuntimeError("no hay un presupuesto total activo")
        now = time.monotonic()
        total_remaining = remaining_seconds(
            total_deadline,
            total_maximum_timeout,
            now=now,
        )
        if total_remaining <= 0.0:
            raise TimeoutError("se agotó el presupuesto total del LLM")
        maximum_timeout = min(
            self._normalize_request_budget(timeout),
            total_remaining,
        )
        self._request_deadline = min(
            total_deadline,
            now + maximum_timeout,
        )
        self._request_maximum_timeout = maximum_timeout
        self._request_attempt = request_attempt
        self._semantic_effect_cache = semantic_effect_cache
        self._response_language_cache = response_language_cache
        self._rejected_reply_cache = rejected_reply_cache
        self._speculative_count_after_guard = (
            bool(getattr(self, "_parallel_turn_verification", False))
            and request_attempt == 0
        )
        self._retire_prepared_chat()
        self._retire_prepared_decision()

    def end_request(self) -> None:
        self._retire_deferred_language_work()
        self._retire_deferred_count_work()
        self._request_total_deadline = None
        self._request_total_maximum_timeout = None
        self._request_deadline = None
        self._request_maximum_timeout = None
        self._request_attempt = 0
        self._semantic_effect_cache = {}
        self._response_language_cache = {}
        self._rejected_reply_cache = {}
        self._speculative_count_after_guard = bool(
            getattr(self, "_parallel_turn_verification", False)
        )
        self._retire_prepared_chat()
        self._retire_prepared_decision()

    def _effective_request_timeout(self, requested: float | None = None) -> float:
        request_timeout = getattr(self, "_request_timeout", 19.0)
        try:
            request_timeout = float(request_timeout)
        except (TypeError, ValueError):
            request_timeout = 0.0
        if not math.isfinite(request_timeout):
            request_timeout = 0.0
        requested_timeout = (
            55.0 if requested is None else self._normalize_request_budget(requested)
        )
        timeout = min(
            _request_timeout_from_env(),
            max(0.0, request_timeout),
            requested_timeout,
        )
        deadline = getattr(self, "_request_deadline", None)
        if deadline is not None:
            timeout = min(timeout, self._remaining_request_timeout())
        if timeout <= 0.0:
            raise TimeoutError("se agotó el presupuesto local del LLM")
        return timeout

    def _post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: ChatCompletionCancellation | None = None,
        reserved_slot: bool = False,
        slot_state: SlotState | None = None,
    ) -> dict[str, Any]:
        """Call the local inference endpoint with an explicitly bounded retry."""

        # Qwen3.5's native template accepts only the first system message.
        # The role builders supply a prefix of identity, task and language
        # instructions. Serialize that prefix together without moving or
        # changing any dialogue, or mutating a payload retained for retries.
        if getattr(self, "_cpu_prose_adapter", None) is not None:
            payload = {"lora": [{"id": 0, "scale": 0.0}], **payload}
        # Ronda 20 P5 (v3-27): no bound the server's grammar refuses goes on the wire (grammar_safe_schema).
        payload = _grammar_safe_payload(payload)
        # Ronda 24 (r23 t2-c02#3, curl on the product's server: [system, user, system] → HTTP 400 «System message must
        # be at the beginning»): an instruction a builder adds after the dialogue began (a length note, a repair) is
        # served with the prefix too, in its order; the dialogue keeps its order and roles.
        messages = payload.get("messages", [])
        system_prefix = [message["content"] for message in messages if message.get("role") == "system"]
        late_system = any(
            message.get("role") == "system" and any(item.get("role") != "system" for item in messages[:index])
            for index, message in enumerate(messages)
        )
        if len(system_prefix) > 1 or late_system:
            payload = {
                **payload,
                "messages": [
                    {"role": "system", "content": "\n\n".join(system_prefix)},
                    *(message for message in messages if message.get("role") != "system"),
                ],
            }

        def endpoint_for_attempt() -> str:
            self._ensure_started()
            endpoint = self._endpoint
            if endpoint is None:
                raise RuntimeError("llama-server no está disponible")
            return endpoint

        started = time.monotonic()
        response: object = None
        failure: BaseException | None = None
        try:
            response = post_chat_completion(
                payload,
                endpoint_for_attempt=endpoint_for_attempt,
                timeout_for_attempt=lambda: self._effective_request_timeout(timeout),
                max_attempts=max_attempts,
                cancellation=cancellation,
                connection_pool=getattr(
                    self,
                    "_http_connection_pool",
                    None,
                ),
                # The contextual decider keeps its own server slot, so its long
                # fixed prompt stays cached and it never queues behind the turn's
                # speculative work. M52 (2026-09-28): the native selector's catalogue
                # probe no longer shares it: each probe evicted the decider's cached
                # catalogue and the next decision re-read ≈ 6 100 tokens (3,5 s; 12 %
                # of DEV-A decisions).
                reserved_slot=reserved_slot,
                slot_state=slot_state,
            )
            return response  # type: ignore[return-value]
        except BaseException as error:
            failure = error
            raise
        finally:
            elapsed = time.monotonic() - started
            _capture_model_call_timing(
                payload,
                request_identity=str(getattr(self, "_request_identity", "")),
                elapsed_ms=elapsed * 1000.0,
                response=response,
                error=failure,
            )
            measured = _decode_rate_of(response, elapsed)
            if measured is not None:
                previous = getattr(self, "_measured_decode_rate", None)
                weight = _DECODE_RATE_WEIGHT
                self._measured_decode_rate = (
                    measured if previous is None else previous * (1 - weight) + measured * weight
                )

    def _post_schema_object(
        self,
        payload: dict[str, Any],
        label: str,
    ) -> dict[str, Any]:
        """Decode a constrained response, retrying one malformed object."""

        last_error: Exception | None = None
        base_seed = payload.get("seed", 0)
        if not isinstance(base_seed, int) or isinstance(base_seed, bool):
            base_seed = 0
        logical_attempt = max(0, int(getattr(self, "_request_attempt", 0)))
        for attempt in range(2):
            current = dict(payload)
            compact_grammar = _compact_structured_grammar(current)
            if compact_grammar is not None:
                # Keep the full JSON schema in the internal payload so recovery
                # can narrow it safely; replace it only in the wire copy.
                current.pop("response_format", None)
                current["grammar"] = compact_grammar
            # The first logical attempt stays greedy/reproducible. A full
            # turn retry uses a small, deterministic sampling profile so it
            # does not repeat exactly the same invalid constrained decode.
            # The closed JSON schema and all downstream validators remain
            # unchanged, so this adds diversity without adding authority.
            current["temperature"] = 0.0 if logical_attempt == 0 else 0.1
            current["seed"] = base_seed + (logical_attempt * 1_009) + attempt
            cancellation_state = getattr(
                self,
                "_completion_cancellation_state",
                None,
            )
            cancellation = (
                getattr(cancellation_state, "current", None)
                if cancellation_state is not None
                else None
            )
            response = (
                self._post(current)
                if cancellation is None
                else self._post(
                    current,
                    cancellation=cancellation,
                )
            )
            content = ""
            finish_reason = None
            try:
                choices = response["choices"]
                if not isinstance(choices, list) or not choices:
                    raise ValueError("respuesta sin choices")
                choice = choices[0]
                if not isinstance(choice, dict):
                    raise TypeError("choice no es objeto")
                message = choice["message"]
                if not isinstance(message, dict):
                    raise TypeError("message no es objeto")
                raw_content = message.get("content")
                if raw_content is not None and not isinstance(raw_content, str):
                    raise TypeError("content no es texto")
                content = raw_content or ""
                raw_finish_reason = choice.get("finish_reason")
                finish_reason = (
                    raw_finish_reason if isinstance(raw_finish_reason, str) else None
                )
                result = json.loads(content)
            except (
                json.JSONDecodeError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ) as error:
                _capture_invalid_schema_response(
                    label,
                    attempt,
                    content,
                    finish_reason,
                )
                last_error = error
                continue
            if isinstance(result, dict):
                return result
            last_error = ValueError(f"{label} no devolvió un objeto")
        raise ValueError(
            f"{label} devolvió JSON inválido tras dos intentos"
        ) from last_error

    @property
    def native_tool_policy_enabled(self) -> bool:
        """Whether this attested model uses its measured native tool contract."""

        return bool(getattr(self, "_native_tool_policy_enabled", False))

    def _post_native_tool_selection(
        self,
        text: str,
        operation_names: list[str],
        contracts_by_operation: dict[str, dict[str, Any]],
        prior_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Select leaf tools without granting any execution authority."""

        if not operation_names:
            raise ValueError("la selección nativa requiere candidatos")
        prior_messages = _bounded_history(prior_messages)
        if (
            prior_messages
            and prior_messages[-1].get("role") == "user"
            and _normalized_dialogue_text(prior_messages[-1].get("content"))
            == _normalized_dialogue_text(text)
        ):
            prior_messages.pop()
        mapping = {
            "baxy_" + operation.replace(".", "__"): operation
            for operation in operation_names
        }
        if len(mapping) != len(operation_names):
            raise ValueError("nombres nativos de operación ambiguos")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": wire_name,
                    "description": _native_selection_description(
                        operation,
                        contracts_by_operation[operation]["description"],
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
            }
            for wire_name, operation in mapping.items()
        ]
        payload = {
            "messages": [
                {"role": "system", "content": NATIVE_TOOL_POLICY_PROMPT},
                # Preserve the source roles of the bounded dialogue. Quoting
                # old requests inside the current user message revived effects
                # already completed in earlier turns (product360).
                *prior_messages,
                {"role": "user", "content": text},
            ],
            "tools": tools,
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "temperature": 0.0,
            "seed": 0,
            "max_tokens": NATIVE_SELECTION_PROSE_TOKENS,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = self._post(payload)
        if _native_selection_may_continue(response, tuple(mapping)):
            # Only a reply that may have begun a call earns the full budget;
            # prose without a call selected nothing at any length.
            response = self._post(
                {**payload, "max_tokens": NATIVE_SELECTION_CALL_TOKENS}
            )
        try:
            choices = response["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("respuesta nativa sin una choice")
            message = choices[0]["message"]
            if not isinstance(message, dict):
                raise TypeError("mensaje nativo inválido")
            calls = message.get("tool_calls")
            if choices[0].get("finish_reason") == "length" and (
                calls or not _native_prose_without_call(message.get("content"), tuple(mapping))
            ):
                # Uso real 2026-09-23 «Cuéntame un poco sobre el modelo de
                # aprendizaje transformer», «qué son exactamente las liebres de
                # mar»: the selector began answering in prose, ran out of tokens,
                # and the truncation failed both turn attempts, which ended in a
                # pointless recovery question. Only a cut call is incomplete; prose
                # with no call selected nothing, whatever its length.
                raise ValueError("selección nativa truncada")
            if calls is None or calls == []:
                operations = []
            elif not isinstance(calls, list) or len(calls) > 8:
                raise ValueError("invalid native operation count")
            else:
                operations = []
                for call in calls:
                    if not isinstance(call, dict):
                        raise TypeError("invalid native call")
                    function = call.get("function")
                    if not isinstance(function, dict):
                        raise TypeError("invalid native function")
                    operation = mapping.get(function.get("name"))
                    if operation is None:
                        raise ValueError("native operation outside shortlist")
                    arguments = function.get("arguments", "{}")
                    if not isinstance(arguments, str) or json.loads(arguments) != {}:
                        raise ValueError("native selection included arguments")
                    operations.append(operation)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("respuesta nativa de operaciones inválida") from error
        return {
            "mode": (
                "conversation"
                if not operations
                else "action"
                if len(operations) == 1
                else "plan"
            ),
            "question": "",
            "conversation_kind": "knowledge" if not operations else "",
            "effect_operations": operations,
            # A non-conversational result never exposes this field. If a veto
            # changes presentation, independent language detection replaces it.
            "response_language": "es",
        }

    def _run_with_completion_cancellation(
        self,
        cancellation: ChatCompletionCancellation,
        callback: Callable[[], Any],
    ) -> Any:
        """Run ``callback`` with its completions closable by ``cancellation``."""

        cancellation_state = getattr(self, "_completion_cancellation_state", None)
        if cancellation_state is None:
            cancellation_state = threading.local()
            self._completion_cancellation_state = cancellation_state
        prior_cancellation = getattr(cancellation_state, "current", None)
        cancellation_state.current = cancellation
        try:
            return callback()
        finally:
            if prior_cancellation is None:
                try:
                    del cancellation_state.current
                except AttributeError:
                    pass
            else:
                cancellation_state.current = prior_cancellation
