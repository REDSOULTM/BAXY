"""Read-only OS API probe on this disposable process, without changing product source."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import time


class Counters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('page_fault_count', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'peak_working_set', 'working_set', 'peak_paged_pool', 'paged_pool',
            'peak_nonpaged_pool', 'nonpaged_pool', 'pagefile_usage', 'peak_pagefile_usage',
            'private_commit', 'private_working_set',
        )
    ] + [('shared_commit', ctypes.c_ulonglong)]


kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = wintypes.HANDLE
kernel.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
kernel.K32GetProcessMemoryInfo.restype = wintypes.BOOL
handle = kernel.GetCurrentProcess()


def observe():
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    started = time.perf_counter()
    if not kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'working_set_bytes': counters.working_set,
            'private_working_set_bytes': counters.private_working_set,
            'private_commit_bytes': counters.private_commit,
            'shared_commit_bytes': counters.shared_commit,
            'api_milliseconds': (time.perf_counter() - started) * 1000}


before = observe()
allocation = bytearray(8 * 2**20)
for offset in range(0, len(allocation), 4096):
    allocation[offset] = 1
after = observe()
result = {'utc': datetime.now(timezone.utc).isoformat(), 'api': 'K32GetProcessMemoryInfo/PROCESS_MEMORY_COUNTERS_EX2',
          'scope': 'Disposable observer process only; no product acceptance or survey credit.',
          'structure_bytes': ctypes.sizeof(Counters), 'temporary_allocation_bytes': len(allocation),
          'before': before, 'after': after,
          'private_resident_delta_bytes': after['private_working_set_bytes'] - before['private_working_set_bytes']}
assert 0 < before['private_working_set_bytes'] <= before['working_set_bytes']
assert 0 < after['private_working_set_bytes'] <= after['working_set_bytes']
assert result['private_resident_delta_bytes'] >= 7 * 2**20
path = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03/PROCESS_REPAIR796/PRIVATE_WORKING_SET_PROBE.json'
assert not path.exists()
path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
