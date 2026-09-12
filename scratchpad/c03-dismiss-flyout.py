"""Cierra un flyout del sistema que se queda con el primer plano, con ESC, y comprueba el resultado.

Por qué existe: REPAIR1031 falló entera porque «Configuración rápida» (ShellHost.exe) tenía el primer
plano y no lo cede, así que `SetForegroundWindow` no puede traer la ventana del destino y `app.open`
devuelve verification_failed aunque la app esté abierta. Esto restablece el escritorio antes de medir
otra vez; no toca ninguna app del usuario ni cierra nada suyo.

Uso:
    python scratchpad/c03-dismiss-flyout.py
"""
from __future__ import annotations

import ctypes
import time

import psutil

user32 = ctypes.windll.user32
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


def foreground() -> tuple[int, str]:
    handle = user32.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    name = "?"
    if pid.value:
        try:
            name = psutil.Process(pid.value).name()
        except psutil.Error:
            pass
    return handle, name


def main() -> int:
    handle, name = foreground()
    print(f"before: handle={handle} process={name}")
    for attempt in range(3):
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.6)
        new_handle, new_name = foreground()
        if new_handle != handle or new_name.lower() != name.lower():
            print(f"after {attempt + 1} ESC: handle={new_handle} process={new_name}")
            return 0
    handle, name = foreground()
    print(f"unchanged: handle={handle} process={name}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
