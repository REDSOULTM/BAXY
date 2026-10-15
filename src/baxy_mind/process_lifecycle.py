"""Bounded, non-sensitive cleanup primitives for owned child processes."""

from __future__ import annotations

import ctypes
import math
import struct
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from enum import Enum

from .time_budget import remaining_seconds


MAX_PROCESS_REAP_TIMEOUT_SECONDS = 5.0


class ReapStatus(str, Enum):
    """Closed outcomes for one bounded process-reap attempt."""

    ABSENT = "absent"
    REAPED = "reaped"
    TIMED_OUT = "timed_out"
    FAILED = "failed"

    @property
    def complete(self) -> bool:
        return self in {ReapStatus.ABSENT, ReapStatus.REAPED}


class ReapResource(str, Enum):
    """Stable resource names allowed in local cleanup diagnostics."""

    LLM_PROCESS = "llm_process"
    ROUTER_PROCESS = "router_process"
    PLANNER_PROMOTION_THREAD = "planner_promotion_thread"
    REQUEST_DISPATCH_THREAD = "request_dispatch_thread"
    VOICE_ENGINE_SHUTDOWN = "voice_engine_shutdown"


def _bounded_timeout(value: float) -> float:
    """Normalize an internal timeout without permitting an unlimited wait."""

    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(timeout):
        return 0.0
    return max(0.0, min(MAX_PROCESS_REAP_TIMEOUT_SECONDS, timeout))


def _wait_for_process(
    process: subprocess.Popen,
    timeout: float,
) -> ReapStatus:
    try:
        process.wait(timeout=max(0.0, timeout))
        return ReapStatus.REAPED
    except subprocess.TimeoutExpired:
        return ReapStatus.TIMED_OUT
    except (OSError, ValueError):
        return ReapStatus.FAILED


def _kill_process(process: subprocess.Popen) -> bool:
    try:
        if process.poll() is None:
            process.kill()
        return True
    except ProcessLookupError:
        return True
    except (OSError, ValueError):
        return False


def terminate_and_reap_bounded(
    process: subprocess.Popen | None,
    *,
    timeout: float,
    final_wait: float = 0.0,
) -> ReapStatus:
    """Terminate and reap an owned child inside one monotonic total budget.

    ``final_wait`` reserves part of ``timeout`` for a second kill/wait pass.
    This covers delayed OS process teardown without ever turning cleanup into
    an unlimited wait.  The caller receives only a closed status and decides
    whether a stable local diagnostic is appropriate.
    """

    if process is None:
        return ReapStatus.ABSENT

    total = _bounded_timeout(timeout)
    reserved = min(total, _bounded_timeout(final_wait))
    deadline = time.monotonic() + total
    kill_succeeded = _kill_process(process)
    remaining = remaining_seconds(
        deadline,
        total,
        now=time.monotonic(),
    )
    first_budget = min(
        max(0.0, total - reserved),
        max(0.0, remaining - reserved),
    )
    first_status = _wait_for_process(process, first_budget)
    if first_status is ReapStatus.REAPED:
        return first_status

    if (
        reserved > 0.0
        and remaining_seconds(
            deadline,
            total,
            now=time.monotonic(),
        )
        > 0.0
    ):
        kill_succeeded = _kill_process(process) and kill_succeeded
        final_status = _wait_for_process(
            process,
            min(
                reserved,
                remaining_seconds(
                    deadline,
                    total,
                    now=time.monotonic(),
                ),
            ),
        )
        if final_status is ReapStatus.REAPED:
            return final_status
        if final_status is ReapStatus.TIMED_OUT:
            return final_status
        first_status = final_status

    if first_status is ReapStatus.TIMED_OUT:
        return first_status
    return ReapStatus.FAILED if not kill_succeeded else first_status


def report_incomplete_reap(
    resource: ReapResource,
    status: ReapStatus,
) -> None:
    """Write one stable stderr code without PID, path or exception details."""

    if status.complete:
        return
    try:
        sys.stderr.write(
            f"baxy_mind_reap_incomplete:{resource.value}:{status.value}\n"
        )
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change shutdown
        pass


# Encargo I2 (tanda fin2 t4 en redpc: llama-server 12764 sobrevivió a su mente): the mind runs under the runtime's
# venv launcher, whose job lets its children break away silently (JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK), and the App's
# own job allows breakaway, so a llama-server spawned here belongs to no job at all. A mind ended without its
# ``close`` (killed with the App's job, the launcher's, or a crash) left the server running with the model in memory.
# The mind's own kill-on-close job holds what it must never outlive: the job dies with the mind's last handle.
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
# JOBOBJECT_EXTENDED_LIMIT_INFORMATION on x64 (the runtime's only target): 144 bytes, with
# BasicLimitInformation.LimitFlags at offset 16; every other limit stays zero.
_EXTENDED_LIMITS_SIZE = 144
_LIMIT_FLAGS_OFFSET = 16


_owner_job: int | None = None
_owner_job_lock = threading.Lock()


def _kill_on_close_job() -> int | None:
    global _owner_job
    with _owner_job_lock:
        if _owner_job is None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ]
            # Not inheritable (no security attributes): a child holding it would keep its own job alive.
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None
            limits = ctypes.create_string_buffer(_EXTENDED_LIMITS_SIZE)
            struct.pack_into("<I", limits, _LIMIT_FLAGS_OFFSET, _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
            if not kernel32.SetInformationJobObject(
                job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, limits, _EXTENDED_LIMITS_SIZE,
            ):
                kernel32.CloseHandle(job)
                return None
            _owner_job = job
        return _owner_job


def end_with_this_process(process: subprocess.Popen) -> bool:
    """Ties ``process`` to the mind's kill-on-close job: it ends when the mind ends, however the mind ends. False
    off Windows or when the system refuses (the child then lives as before, closed only by ``close``)."""

    if sys.platform != "win32":
        return False
    try:
        job = _kill_on_close_job()
        if job is None:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        return bool(kernel32.AssignProcessToJobObject(job, int(process._handle)))  # noqa: SLF001 - the OS handle
    except (AttributeError, OSError, TypeError, ValueError):
        return False
