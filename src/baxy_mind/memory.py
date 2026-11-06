"""What Windows says of the PC's memory (GlobalMemoryStatusEx), for what a native load needs and for why one failed."""
from __future__ import annotations

import ctypes


class _MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _status() -> _MemoryStatus | None:
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    try:
        return status if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
    except (AttributeError, OSError):
        return None


def commit_available_mb() -> int | None:
    """The memory this process can still commit (ullAvailPageFile), or None when unread."""
    status = _status()
    return None if status is None else status.ullAvailPageFile // (1024 * 1024)


def free_memory_mb() -> int | None:
    """The PC's RAM free now (ullAvailPhys), or None when unread."""
    status = _status()
    return None if status is None else status.ullAvailPhys // (1024 * 1024)
