"""Utilidades de escritorio AISLADO (CreateDesktop) — robustas, ctypes.
- iso_cleanup(name): mata los procesos de las ventanas del escritorio `name` (por
  PID real de la ventana, no el handle del launcher) y cierra el escritorio.
- Reusable por los pasos siguientes. Ejecutado directo -> limpia 'Gemma4Iso'.
"""
from __future__ import annotations
import sys, ctypes
from ctypes import wintypes
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

u = ctypes.windll.user32
k = ctypes.windll.kernel32
u.OpenDesktopW.restype = wintypes.HANDLE
u.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
GENERIC_ALL = 0x10000000
PROCESS_TERMINATE = 0x0001
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _win_pid(hwnd):
    pid = wintypes.DWORD(0)
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def iso_windows(hdesk):
    out = []
    def cb(h, _):
        buf = ctypes.create_unicode_buffer(512)
        u.GetWindowTextW(h, buf, 512)
        out.append((h, buf.value, _win_pid(h)))
        return True
    u.EnumDesktopWindows(hdesk, WNDENUMPROC(cb), 0)
    return out


def kill_pid(pid):
    if not pid:
        return False
    h = k.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not h:
        return False
    ok = bool(k.TerminateProcess(h, 0))
    k.CloseHandle(h)
    return ok


def iso_cleanup(name="Gemma4Iso"):
    hdesk = u.OpenDesktopW(name, 0, False, GENERIC_ALL)
    if not hdesk:
        print(f"[cleanup] no existe el escritorio {name!r} (nada que limpiar)", flush=True)
        return
    wins = iso_windows(hdesk)
    print(f"[cleanup] ventanas en {name!r}: {[(w[1], w[2]) for w in wins if w[1]]}", flush=True)
    killed = set()
    for h, title, pid in wins:
        if pid and pid not in killed:
            ok = kill_pid(pid)
            killed.add(pid)
            print(f"   kill pid={pid} ({title!r}) -> {ok}", flush=True)
    import time; time.sleep(0.5)
    ok = bool(u.CloseDesktop(hdesk))
    print(f"[cleanup] CloseDesktop({name!r}) -> {ok}", flush=True)


if __name__ == "__main__":
    iso_cleanup(sys.argv[1] if len(sys.argv) > 1 else "Gemma4Iso")
