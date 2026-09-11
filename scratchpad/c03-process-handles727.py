"""Observe native process exit times using the retired phase probe, not acceptance tests."""
from pathlib import Path
import ctypes
from ctypes import wintypes

root = Path(__file__).resolve().parents[1]
source = (root / "scratchpad/c03-dispatch-exit-probe725.py").read_text(encoding="utf-8")
source = source.replace("725", "727")
prototype = root / "artifacts/comprobaciones/C03/astra-test-fidelity726/REJECTED724_test_sidecar_lifecycle.py"
source = source.replace('test_hash = hashlib.sha256(TEST.read_bytes()).hexdigest()',
                        'test_hash = hashlib.sha256(PROTOTYPE.read_bytes()).hexdigest()')
source = source.replace('spec.loader.exec_module(module)',
                        'exec(compile(PROTOTYPE.read_bytes(), str(PROTOTYPE), "exec"), module.__dict__)')
source = source.replace('"test_sha256": test_hash,', '"prototype_sha256": test_hash, "acceptance_tests_unchanged": True,')
source = source.replace('"Popen subclass captures stack only after TimeoutExpired; original test and10/3 deadlines"',
                        '"Retired724 phase probe only. Retain native child handle before trigger; timestamp write and kernel exit separately. Original acceptance files stay restored."')
source = source.replace('hashlib.sha256(TEST.read_bytes()).hexdigest() == test_hash',
                        'hashlib.sha256(PROTOTYPE.read_bytes()).hexdigest() == test_hash')
source = source.replace('        self.descendants = []', '        self.descendants = []\n        self.native = {}\n        self.trigger_ticks = None\n        self.first_wait_recorded = False')
source = source.replace('            owned.append(self)', '''            owned.append(self)
            self.native["launcher"] = open_native(self.pid)
            until = time.monotonic() + 2.0
            while time.monotonic() < until:
                children = psutil.Process(self.pid).children()
                if children:
                    child = children[0]
                    self.native["interpreter"] = open_native(child.pid)
                    break
                time.sleep(0.02)
            self.stdin = ObservedInput(self.stdin, self)
''')
source = source.replace('            return super().wait(timeout=timeout)', '''            code = super().wait(timeout=timeout)
            if self.is_test and not self.first_wait_recorded:
                self.first_wait_recorded = True
                save(OUT / f"attempt{current_attempt}-NATIVE.json", native_state(self, "wait_returned", timeout))
            return code''')
source = source.replace('            self.captured = True', '''            self.captured = True
            self.first_wait_recorded = True
            save(OUT / f"attempt{current_attempt}-NATIVE.json", native_state(self, "deadline", timeout))''')
source = source.replace('        owned.clear()', '''            for native in process.native.values():
                kernel32.CloseHandle(native["handle"])
        owned.clear()''')

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
kernel32.GetProcessTimes.restype = wintypes.BOOL
kernel32.GetSystemTimePreciseAsFileTime.argtypes = [ctypes.POINTER(wintypes.FILETIME)]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.GetPriorityClass.argtypes = [wintypes.HANDLE]
kernel32.GetPriorityClass.restype = wintypes.DWORD


def ticks(value):
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def now_ticks():
    value = wintypes.FILETIME()
    kernel32.GetSystemTimePreciseAsFileTime(ctypes.byref(value))
    return ticks(value)


def open_native(pid):
    handle = kernel32.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return {"pid": pid, "handle": handle}


def native_state(process, stage, timeout):
    records = {}
    for label, value in process.native.items():
        handle = value["handle"]
        signaled = kernel32.WaitForSingleObject(handle, 0) == 0
        creation, exit_time, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                        ctypes.byref(kernel), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        # ExitTime is undefined for a live process, so never report it unless signaled.
        exited = ticks(exit_time) if signaled else None
        records[label] = {"pid": value["pid"], "creation_ticks": ticks(creation), "signaled": signaled,
                          "exit_code": code.value, "exit_ticks": exited,
                          "exit_seconds_after_trigger": (exited - process.trigger_ticks) / 1e7 if exited and process.trigger_ticks else None,
                          "cpu_seconds": (ticks(kernel) + ticks(user)) / 1e7,
                          "priority_class": kernel32.GetPriorityClass(handle)}
    return {"stage": stage, "timeout": timeout, "observed_ticks": now_ticks(),
            "trigger_ticks": process.trigger_ticks, "records": records,
            "observation": "native kernel exit timestamps; retired diagnostic fixture, not acceptance"}


class ObservedInput:
    def __init__(self, stream, process):
        self.stream = stream
        self.process = process

    def write(self, data):
        if data == b'{"type":"crash"}\n':
            self.process.trigger_ticks = now_ticks()
        return self.stream.write(data)

    def __getattr__(self, name):
        return getattr(self.stream, name)


scope = dict(globals(), __file__=__file__, PROTOTYPE=prototype)
exec(compile(source, __file__, "exec"), scope)
