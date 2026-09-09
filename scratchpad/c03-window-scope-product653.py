"""Repeat the exact647 product panel after the measured scope instruction652."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
identity_source = r'''
def process_identity653(pid):
    row = {'aumid': None, 'identity_error': None,
           'identity_utc': datetime.now(timezone.utc).isoformat()}
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.GetApplicationUserModelId.argtypes = [w.HANDLE, c.POINTER(w.UINT), w.LPWSTR]
    kernel.GetApplicationUserModelId.restype = w.LONG
    try:
        row['created'] = psutil.Process(pid).create_time()
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            raise OSError(c.get_last_error(), 'OpenProcess')
        try:
            size = w.UINT()
            code = kernel.GetApplicationUserModelId(handle, c.byref(size), None)
            if code == 122 and 0 < size.value <= 1024:
                value = c.create_unicode_buffer(size.value)
                code = kernel.GetApplicationUserModelId(handle, c.byref(size), value)
                if code == 0:
                    row['aumid'] = value.value
                else:
                    row['identity_error'] = f'GetApplicationUserModelId:{code}'
            elif code != 15703:
                row['identity_error'] = f'GetApplicationUserModelId:{code}'
        finally:
            kernel.CloseHandle(handle)
    except (OSError, psutil.Error) as error:
        row['identity_error'] = str(error)
    return row
'''
source = (root/'scratchpad/c03-window-reference-product640.py').read_text(encoding='utf-8')
source = source.replace('window-reference-product640', 'window-scope-product653').replace('window-reference-profile640', 'window-scope-profile653').replace('Shared source638 product', 'Shared source652 product')
old = "exec(compile(prefix,__file__,'exec'))"
assert source.count(old) == 1
source = source.replace(old, '''assert prefix.count('def sample():') == 1
prefix = prefix.replace('def sample():', identity_source + '\\ndef sample():')
assert prefix.count("found.append({'process':") == 1
prefix = prefix.replace("found.append({'process':", "found.append({**process_identity653(pid.value),'process':")
exec(compile(prefix,__file__,'exec'))''')
source = source.replace('No communication authorized.',
    'No communication authorized. Independent HWND snapshots also capture AUMID, creation time and identity errors during each window row, following648; no later process-name-only reconciliation.')
exec(compile(source, __file__, 'exec'))
