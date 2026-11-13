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


def installed_memory_mb() -> int | None:
    """VRAM5: the RAM installed in the PC, as its firmware says it (GetPhysicallyInstalledSystemMemory, KiB: «the amount
    of RAM that is physically installed», learn.microsoft.com sysinfoapi), or None when unread. Not ullTotalPhys, which
    is what Windows can use: less by what the hardware and an integrated GPU reserve."""
    kib = ctypes.c_ulonglong(0)
    try:
        ok = ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kib))
    except (AttributeError, OSError):
        return None
    return kib.value // 1024 if ok and kib.value else None


def free_memory_mb() -> int | None:
    """The PC's RAM free now (ullAvailPhys), or None when unread."""
    status = _status()
    return None if status is None else status.ullAvailPhys // (1024 * 1024)


class _CounterValue(ctypes.Structure):
    _fields_ = [("CStatus", ctypes.c_ulong), ("largeValue", ctypes.c_longlong)]


class _CounterItem(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _CounterValue)]


_PDH_MORE_DATA = 0x800007D2
_PDH_FMT_LARGE = 0x00000400
_PDH_VALID = (0x00000000, 0x00000001)  # PDH_CSTATUS_VALID_DATA, PDH_CSTATUS_NEW_DATA


def gpu_shared_mb(pid: int) -> int | None:
    r"""VRAM5 (AUD1 F9): the PC's RAM a process holds as video memory, «GPU Process Memory(pid_<pid>_…)\Shared Usage»,
    summed over its adapters: what Windows (WDDM) gives a process when the card's own memory does not hold what it asks.
    The same counter set the App reads for the dedicated memory (WindowsModelResourceReader). None when unread."""
    try:
        pdh = ctypes.windll.pdh
    except (AttributeError, OSError):
        return None
    query, counter = ctypes.c_void_p(), ctypes.c_void_p()
    if pdh.PdhOpenQueryW(None, None, ctypes.byref(query)) != 0:
        return None
    try:
        if (pdh.PdhAddEnglishCounterW(query, r"\GPU Process Memory(*)\Shared Usage", None, ctypes.byref(counter)) != 0
                or pdh.PdhCollectQueryData(query) != 0):
            return None
        size, count = ctypes.c_ulong(0), ctypes.c_ulong(0)
        if pdh.PdhGetFormattedCounterArrayW(counter, _PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count),
                                            None) & 0xFFFFFFFF != _PDH_MORE_DATA or not size.value:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if pdh.PdhGetFormattedCounterArrayW(counter, _PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count),
                                            buffer) != 0:
            return None
        items = ctypes.cast(buffer, ctypes.POINTER(_CounterItem))
        prefix = f"pid_{pid}_"
        held = [items[i].FmtValue.largeValue for i in range(count.value)
                if (items[i].szName or "").startswith(prefix) and items[i].FmtValue.CStatus in _PDH_VALID]
        return sum(held) // (1024 * 1024) if held else None
    finally:
        pdh.PdhCloseQuery(query)
