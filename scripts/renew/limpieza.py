"""What a bench starts dies with it (PC-Q, 2026-10-25).

A bench killed from outside (its python ended with TerminateProcess, a closed console) runs no finally: the
llama-servers it had started stayed alive, two pairs of them on 2026-10-25, holding the GPU's VRAM and the judge's port
for the next run. A process handed to die_with_this_process goes into a Windows job that kills what it holds when its
last handle closes; the handle is this process's and is never closed by hand, so the job ends when this process ends,
however it ends (the App does the same for the mind: WindowsKillOnCloseJob in LocalJsonlSidecarProcess.cs).
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Any

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _BasicLimits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


_JOBS: list[int] = []  # open until this process ends: closing one kills what it holds


def die_with_this_process(process: Any) -> bool:
    """Whether `process` (a subprocess.Popen) now ends when this process ends. False off Windows, for a process that
    already exited, or when Windows refused (the bench goes on as before, its finally still closes it)."""
    if sys.platform != "win32" or process is None or process.poll() is not None:
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return False
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not (kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits),
                                             ctypes.sizeof(limits))
            and kernel32.AssignProcessToJobObject(job, int(process._handle))):
        kernel32.CloseHandle(job)
        return False
    _JOBS.append(job)
    return True
