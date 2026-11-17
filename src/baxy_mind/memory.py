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


def _gpu_counter(path: str) -> dict[str, int] | None:
    """Every instance of a «GPU …» counter of Windows (PDH) and its value in bytes; None when unread."""
    try:
        pdh = ctypes.windll.pdh
    except (AttributeError, OSError):
        return None
    query, counter = ctypes.c_void_p(), ctypes.c_void_p()
    if pdh.PdhOpenQueryW(None, None, ctypes.byref(query)) != 0:
        return None
    try:
        if (pdh.PdhAddEnglishCounterW(query, path, None, ctypes.byref(counter)) != 0
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
        return {items[i].szName or "": items[i].FmtValue.largeValue for i in range(count.value)
                if items[i].FmtValue.CStatus in _PDH_VALID}
    finally:
        pdh.PdhCloseQuery(query)


def gpu_shared_mb(pid: int) -> int | None:
    r"""VRAM5 (AUD1 F9): the PC's RAM a process holds as video memory, «GPU Process Memory(pid_<pid>_…)\Shared Usage»,
    summed over its adapters: what Windows (WDDM) gives a process when the card's own memory does not hold what it asks.
    The same counter set the App reads for the dedicated memory (WindowsModelResourceReader). None when unread."""
    values = _gpu_counter(r"\GPU Process Memory(*)\Shared Usage")
    held = [value for name, value in (values or {}).items() if name.startswith(f"pid_{pid}_")]
    return sum(held) // (1024 * 1024) if held else None


class _Guid(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


def _guid(text: str) -> _Guid:
    digits = text.replace("-", "")
    guid = _Guid(int(digits[0:8], 16), int(digits[8:12], 16), int(digits[12:16], 16))
    for i in range(8):
        guid.Data4[i] = int(digits[16 + 2 * i:18 + 2 * i], 16)
    return guid


class _AdapterDesc1(ctypes.Structure):
    _fields_ = [("Description", ctypes.c_wchar * 128), ("VendorId", ctypes.c_uint), ("DeviceId", ctypes.c_uint),
                ("SubSysId", ctypes.c_uint), ("Revision", ctypes.c_uint), ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t), ("SharedSystemMemory", ctypes.c_size_t),
                ("LuidLowPart", ctypes.c_uint32), ("LuidHighPart", ctypes.c_int32), ("Flags", ctypes.c_uint)]


_IID_FACTORY1 = "770aae78-f26f-4dba-a829-253c83d1b387"  # IDXGIFactory1 (dxgi.h)
_DXGI_SOFTWARE = 0x2  # DXGI_ADAPTER_FLAG_SOFTWARE


def _method(obj: ctypes.c_void_p, index: int, *types: type) -> ctypes._CFuncPtr:
    """The COM method at ``index`` of ``obj``'s table (IUnknown 0-2, IDXGIObject 3-6, then the interface's own)."""
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(table[index])


def _adapters() -> list[tuple[str, int, str]] | None:
    """Every hardware adapter DXGI lists: its description, its dedicated memory in bytes («the number of bytes of
    dedicated video memory that are not shared with the CPU», DXGI_ADAPTER_DESC1) and its LUID as the GPU counters
    name it (luid_0x<high>_0x<low>); None when unread."""
    try:
        create = ctypes.windll.dxgi.CreateDXGIFactory1
    except (AttributeError, OSError):
        return None
    factory = ctypes.c_void_p()
    if create(ctypes.byref(_guid(_IID_FACTORY1)), ctypes.byref(factory)) != 0 or not factory:
        return None
    found: list[tuple[str, int, str]] = []
    try:
        index = 0
        while True:
            adapter = ctypes.c_void_p()
            # IDXGIFactory1::EnumAdapters1 (12); DXGI_ERROR_NOT_FOUND past the last one
            if _method(factory, 12, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(factory, index, ctypes.byref(adapter)) != 0:
                break
            try:
                desc = _AdapterDesc1()
                # IDXGIAdapter1::GetDesc1 (10)
                if _method(adapter, 10, ctypes.POINTER(_AdapterDesc1))(adapter, ctypes.byref(desc)) == 0 and not desc.Flags & _DXGI_SOFTWARE:
                    found.append((desc.Description, desc.DedicatedVideoMemory,
                                  f"luid_0x{desc.LuidHighPart & 0xFFFFFFFF:08X}_0x{desc.LuidLowPart:08X}".lower()))
            finally:
                _method(adapter, 2)(adapter)  # Release
            index += 1
    finally:
        _method(factory, 2)(factory)
    return found


def card_room_mb(description: str) -> int | None:
    r"""VELX2: the memory of the graphics card named ``description`` that no process holds now, MiB: its dedicated
    memory (DXGI) less what every process holds on it, «GPU Adapter Memory(luid_…)\Dedicated Usage». Not what CUDA calls
    free on Windows: that is the budget Windows gives the asking process less its own use, blind to every other process
    (DXGI_QUERY_VIDEO_MEMORY_INFO «Budget: … the OS-provided video memory budget … that the application should target»,
    learn.microsoft.com, read 2026-11-16; on the PC's RTX 4060 Ti 15,341 − 106 = 15,235, the same with 3 GB held by
    another process; on a GTX 1650 of 4 GB with the desktop on the integrated GPU 3,292 against 3,900 nvidia-smi
    gives). The largest of the adapters of that name that Windows counts; None when unread or none matches."""
    try:
        adapters = _adapters()
        used = _gpu_counter(r"\GPU Adapter Memory(*)\Dedicated Usage")
    except OSError:
        return None  # a Windows without DXGI or the GPU counters: not known, as before
    if not adapters or used is None:
        return None
    rooms = []
    for name, dedicated, luid in adapters:
        held = [value for instance, value in used.items() if instance.lower().startswith(luid + "_")]
        if name.strip() == description.strip() and held:
            rooms.append(max(0, dedicated - sum(held)) // (1024 * 1024))
    return max(rooms) if rooms else None


def gpu_dedicated_mb(pid: int) -> int | None:
    r"""VELX2: the card's own memory a process holds, «GPU Process Memory(pid_<pid>_…)\Dedicated Usage», summed over its
    adapters; None when unread."""
    values = _gpu_counter(r"\GPU Process Memory(*)\Dedicated Usage")
    held = [value for name, value in (values or {}).items() if name.startswith(f"pid_{pid}_")]
    return sum(held) // (1024 * 1024) if held else None
