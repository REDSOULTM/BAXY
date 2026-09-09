"""Check whether process-name counts omit a second packaged application host."""
from pathlib import Path
from datetime import datetime, timezone
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
home = Path(os.environ['LOCALAPPDATA'])/'BAXY'
private = home/'C03-package-scope648-private'
out = root/'artifacts/comprobaciones/C03/astra-package-scope648'
private.mkdir(exist_ok=False); out.mkdir(exist_ok=False)
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
snapshots = {name: json.loads((home/f'C03-context-product647-private/windows-{name}.json').read_text(encoding='utf-8')) for name in ['before', 'after']}
write(out/'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Read current OS AUMID for PIDs already captured in647 native snapshots. Validate that process name and creation time are compatible with each snapshot. Determine whether counting only WhatsApp.Root.exe omitted a second process belonging to the same package. Current metadata is not a contemporaneous647 identity capture; retain that limitation. No window creation, activation, messaging, inference or source changes.',
    'snapshot_hashes': {key: sha(home/f'C03-context-product647-private/windows-{key}.json') for key in snapshots},
    'documentation': 'https://learn.microsoft.com/en-us/windows/win32/api/appmodel/nf-appmodel-getapplicationusermodelid'})
k = c.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
k.CloseHandle.argtypes = [w.HANDLE]
k.GetApplicationUserModelId.argtypes = [w.HANDLE, c.POINTER(w.UINT), w.LPWSTR]
k.GetApplicationUserModelId.restype = w.LONG
observations = []
for pid in sorted({r['pid'] for s in snapshots.values() for r in s['windows']}):
    row = {'pid': pid, 'aumid': None, 'error': None}
    try:
        process = psutil.Process(pid)
        row.update(process=process.name(), created=process.create_time())
        row['compatible_snapshots'] = [key for key, snapshot in snapshots.items()
            if row['created'] <= datetime.fromisoformat(snapshot['utc']).timestamp()
            and any(r['pid'] == pid and r['process'] == row['process'] for r in snapshot['windows'])]
        handle = k.OpenProcess(0x1000, False, pid)
        if not handle: raise OSError(c.get_last_error(), 'OpenProcess')
        try:
            length = w.UINT(); first = k.GetApplicationUserModelId(handle, c.byref(length), None)
            row['first_result'] = first
            if first == 122 and 0 < length.value <= 1024:
                buffer = c.create_unicode_buffer(length.value)
                second = k.GetApplicationUserModelId(handle, c.byref(length), buffer)
                row['second_result'] = second
                if second == 0: row['aumid'] = buffer.value
                else: row['error'] = f'GetApplicationUserModelId:{second}'
            elif first != 15703: row['error'] = f'GetApplicationUserModelId:{first}'
        finally: k.CloseHandle(handle)
    except (psutil.Error, OSError) as error:
        row['error'] = str(error)
    observations.append(row)
write(private/'process-identities.json', observations)
target = '5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App'
matches = [r for r in observations if r['aumid'] == target]
counts = {key: sum(1 for window in snapshot['windows']
    if any(r['pid'] == window['pid'] and key in r['compatible_snapshots'] for r in matches))
    for key, snapshot in snapshots.items()}
result = {'aumid': target, 'matched_processes': [{k: r[k] for k in ['process', 'compatible_snapshots']} for r in matches],
    'matching_snapshot_window_counts': counts, 'source_changed': False,
    'errors': sum(bool(r['error']) for r in observations),
    'identity_capture_is_later_than647': True,
    'private_sha256': sha(private/'process-identities.json')}
write(out/'RESULT.json', result)
print(json.dumps(result, ensure_ascii=False))
