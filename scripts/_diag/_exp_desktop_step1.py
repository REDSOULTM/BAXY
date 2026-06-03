"""PASO 1 del desktop AISLADO (seguro, SIN SendInput, SIN SwitchDesktop): crear un
escritorio nuevo (CreateDesktop), lanzar Notepad EN ese escritorio, y confirmar que
la ventana queda en el escritorio nuevo (NO en el tuyo/Default donde está VS Code).
Si anda, es la base para correr el SendInput del agente AISLADO de VS Code."""
from __future__ import annotations
import sys, time
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

DESK = "Gemma4Iso"
hdesk = None
hproc = None
try:
    import win32service, win32process, win32con, win32gui
    print("[1] creando escritorio aislado %r..." % DESK, flush=True)
    # GENERIC_ALL para poder enumerar/operar; el desktop vive en WinSta0 (interactiva)
    hdesk = win32service.CreateDesktop(DESK, 0, win32con.GENERIC_ALL, None)
    print(f"    hdesk={hdesk}", flush=True)
    print("[2] lanzando Notepad EN el escritorio aislado...", flush=True)
    si = win32process.STARTUPINFO()
    si.lpDesktop = DESK
    hproc, hthread, pid, tid = win32process.CreateProcess(
        None, "notepad.exe", None, None, 0, 0, None, None, si)
    print(f"    notepad pid={pid}", flush=True)
    time.sleep(2.5)
    # enumerar ventanas DEL escritorio aislado
    iso_wins = []
    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if t and win32gui.IsWindowVisible(h):
            iso_wins.append(t)
        return True
    try:
        win32gui.EnumDesktopWindows(hdesk, cb, None)
    except Exception as e:
        print(f"    (EnumDesktopWindows: {e})", flush=True)
    print(f"[3] ventanas en {DESK!r}: {iso_wins}", flush=True)
    # confirmar que NO está en el escritorio DEFAULT (el tuyo, con VS Code)
    default_wins = []
    def cb2(h, _):
        t = win32gui.GetWindowText(h)
        if t and ("Bloc de notas" in t or "Notepad" in t):
            default_wins.append(t)
        return True
    win32gui.EnumWindows(cb2, None)   # EnumWindows = escritorio actual (Default)
    iso_ok = any("Bloc de notas" in w or "Notepad" in w for w in iso_wins)
    leaked = bool(default_wins)
    print(f"[4] ¿Notepad en el escritorio AISLADO? {iso_ok}", flush=True)
    print(f"    ¿Notepad VISIBLE en tu escritorio (leak)? {leaked} {default_wins}", flush=True)
    if iso_ok and not leaked:
        print("[OK] AISLAMIENTO CONFIRMADO: el Notepad está en el escritorio nuevo, "
              "NO en el tuyo. Base lista para SendInput aislado.", flush=True)
    else:
        print("[!] revisar: aislamiento no confirmado limpio.", flush=True)
finally:
    print("[5] limpiando (matar Notepad de prueba + cerrar escritorio)...", flush=True)
    try:
        if hproc: win32process.TerminateProcess(hproc, 0)
    except Exception as e: print(f"    (kill: {e})", flush=True)
    try:
        if hdesk: win32service.CloseDesktop(hdesk)
    except Exception as e: print(f"    (close desk: {e})", flush=True)
    print("[done]", flush=True)
