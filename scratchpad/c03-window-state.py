"""Lee el estado real de ventanas del escritorio: quién tiene el primer plano y qué es visible.

El verificador de `app.open` exige ventana visible y primer plano; si el escritorio no concede ninguno
de los dos, la operación falla aunque la app esté abierta. Antes de culpar al producto de una
regresión hay que mirar el escritorio, y eso es lo que hace este script.

Uso:
    python scratchpad/c03-window-state.py [nombre-proceso ...]
"""
from __future__ import annotations

import ctypes
import sys

import psutil

user32 = ctypes.windll.user32


def title(handle: int) -> str:
    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value


def main(argv: list[str]) -> int:
    foreground = user32.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
    owner = None
    try:
        owner = psutil.Process(pid.value).name() if pid.value else None
    except psutil.Error:
        owner = "?"
    print(f"foreground handle={foreground} pid={pid.value} process={owner} "
          f"title={title(foreground)!r}")
    print(f"LogonUI running (locked session): "
          f"{any(p.info['name'] == 'LogonUI.exe' for p in psutil.process_iter(['name']))}")

    wanted = {name.lower() for name in argv[1:]} or {"steam", "discord", "chrome", "mspaint"}
    handles: dict[int, list[int]] = {}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def collect(handle, _):
        process_id = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        handles.setdefault(process_id.value, []).append(handle)
        return True

    user32.EnumWindows(collect, 0)
    for process in psutil.process_iter(["pid", "name"]):
        name = (process.info["name"] or "").lower()
        if not any(want in name for want in wanted):
            continue
        for handle in handles.get(process.info["pid"], []):
            visible = bool(user32.IsWindowVisible(handle))
            iconic = bool(user32.IsIconic(handle))
            if not visible and not iconic:
                continue
            print(f"  {process.info['name']:20} pid{process.info['pid']:<7} handle={handle} "
                  f"visible={visible} minimized={iconic} foreground={handle == foreground} "
                  f"title={title(handle)!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
