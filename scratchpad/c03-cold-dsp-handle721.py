"""Probe the HANDLE hypothesis privately; do not replace the product reader."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "scratchpad/c03-cold-dsp-probe719.py").read_text(encoding="utf-8")
source = source.replace("719", "721")
source = source.replace('("original", "deferred_warmup_only"):', '("deferred_warmup_only", "deferred_with_readfile"):')
source = source.replace('if profile == "deferred_warmup_only":', 'if profile.startswith("deferred_"):')
source = source.replace('["original", "deferred_warmup_only"]', '["deferred_warmup_only", "deferred_with_readfile"]')
source = source.replace('"Replace prepare_resampler only in the private child process, no source edits"',
                        '"Both profiles defer warmup; second changes only the private reader syscall to ReadFile"')
native = '''
import ctypes
from ctypes import wintypes
import msvcrt
from baxy_mind import protocol
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
read_file = kernel32.ReadFile
read_file.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                      ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
read_file.restype = wintypes.BOOL
def native_read(descriptor, limit):
    buffer = ctypes.create_string_buffer(limit)
    count = wintypes.DWORD()
    if not read_file(msvcrt.get_osfhandle(descriptor), buffer, limit, ctypes.byref(count), None):
        error = ctypes.get_last_error()
        if error == 109:
            return b""
        raise ctypes.WinError(error)
    return buffer.raw[:count.value]
protocol._BoundedFileDescriptorLineReader.__init__.__kwdefaults__["read"] = native_read
'''
marker = '        tag = profile + ("-crash" if expected_code else "-dsp")'
insert = '''        if profile == "deferred_with_readfile":
            script = script.replace("receiver_entered = threading.Event()", NATIVE + "\\nreceiver_entered = threading.Event()") if expected_code else script.replace("def probe_dispatch(", NATIVE + "\\ndef probe_dispatch(")
            script = script.replace("return os.read(descriptor, limit)", "return native_read(descriptor, limit)")
'''
assert source.count(marker) == 1
source = source.replace(marker, insert + marker)
# Persist timeout evidence before disposal; close the owned parent's write end only
# after that evidence, so a blocked native shutdown cannot consume the diagnostic.
marker = '            for pid, created in reversed(descendants):'
replacement = '''            write(OUT / (tag + "-DEADLINE.json"), {"elapsed": elapsed, "deadline": deadline,
                "timed_out": True, "stack_exit_code": stack_exit,
                "owned_descendants": descendants})
            if process.stdin is not None:
                process.stdin.close()
            for pid, created in reversed(descendants):'''
source = source.replace(marker, replacement)
source = source.replace('except psutil.NoSuchProcess:', 'except (psutil.NoSuchProcess, psutil.TimeoutExpired):')
exec(compile(source, __file__, "exec"), {"__file__": __file__, "NATIVE": native})
