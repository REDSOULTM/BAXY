"""EXPERIMENTO SEGURO (sin SendInput, no cierra VS Code): ¿puedo escribir en Notepad
apuntando al CONTROL (UIA ValuePattern.SetValue y/o WM_SETTEXT por HWND)? Eso NO va
al foreground -> seguro. Abre un Notepad NUEVO (trackea su pid), prueba ambos
métodos, lee de vuelta por WM_GETTEXT, reporta, y lo cierra SIN matar otros Notepad."""
from __future__ import annotations
import sys, time, ctypes, subprocess
from ctypes import wintypes
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

u = ctypes.windll.user32
WM_SETTEXT, WM_GETTEXT, WM_GETTEXTLENGTH, WM_CLOSE = 0x000C, 0x000D, 0x000E, 0x0010
u.FindWindowExW.restype = wintypes.HWND
u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]

def _enum_notepad_hwnds():
    out = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        buf = ctypes.create_unicode_buffer(512)
        u.GetWindowTextW(h, buf, 512)
        t = buf.value
        if u.IsWindowVisible(h) and ("Notepad" in t or "Bloc de notas" in t or "Sin t" in t):
            out.append((h, t))
        return True
    u.EnumWindows(cb, 0)
    return out

def _find_edit(hwnd):
    # Win11 Notepad: RichEditD2DPT; clásico: Edit. Buscar hijo editable.
    for cls in ("RichEditD2DPT", "RichEdit50W", "Edit", None):
        child = u.FindWindowExW(hwnd, None, cls, None)
        if child:
            return child, cls
    return None, None

def _get_text(hwnd):
    n = u.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.SendMessageW(hwnd, WM_GETTEXT, n + 1, ctypes.cast(buf, ctypes.c_void_p))
    return buf.value

TEXT = "Gemma4 verificacion 12345"
before = {h for h, _ in _enum_notepad_hwnds()}
proc = None
new_hwnd = None
try:
    print("[1] abriendo Notepad de prueba...", flush=True)
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(2.5)
    # ventana NUEVA (no de las que ya tenías)
    for h, t in _enum_notepad_hwnds():
        if h not in before:
            new_hwnd = h; print(f"[2] ventana nueva: {t!r}", flush=True); break
    if not new_hwnd:
        print("[2] no encontré una ventana nueva (¿Win11 UWP separada?). Abortando seguro.", flush=True)
    else:
        edit, cls = _find_edit(new_hwnd)
        print(f"[3] control editable: class={cls!r} hwnd={edit}", flush=True)
        # MÉTODO A: agente real -> uia_set_value (ValuePattern)
        try:
            import tempfile
            from gemma4_agent.memory_pkg.memory import MemoryStore
            from gemma4_agent.memory_pkg.state import AgentState
            from gemma4_agent.tools_pkg.tools import ToolRegistry
            from pathlib import Path
            tmp = Path(tempfile.mkdtemp())
            reg = ToolRegistry(MemoryStore(tmp/"m.json"), tmp/"c", state=AgentState(tmp/"d"/"s.json"))
            ra = reg.uia_set_value({"query": cls or "edit", "value": TEXT, "window": "Notepad"})
            print(f"[4A] uia_set_value -> ok={ra.get('ok')} method={ra.get('method')} err={str(ra.get('error'))[:50]}", flush=True)
        except Exception as e:
            print(f"[4A] uia_set_value EXC: {e}", flush=True)
        time.sleep(0.4)
        got_a = _get_text(edit) if edit else ""
        print(f"[5A] texto tras UIA: {got_a!r}  -> {'OK' if TEXT in got_a else 'no'}", flush=True)
        # MÉTODO B: WM_SETTEXT directo al control (si UIA no puso)
        if edit and TEXT not in got_a:
            u.SendMessageW(edit, WM_SETTEXT, 0, ctypes.c_wchar_p(TEXT))
            time.sleep(0.3)
            got_b = _get_text(edit)
            print(f"[5B] texto tras WM_SETTEXT: {got_b!r}  -> {'OK' if TEXT in got_b else 'no'}", flush=True)
finally:
    print("[6] cerrando el Notepad de prueba (kill forzado, sin diálogo, sin input)...", flush=True)
    # Matar FORZADO el proceso dueño de la ventana de prueba -> cierra sin diálogo
    # de guardado y SIN input sintético. Solo ESE proceso (su PID), no otros Notepad.
    try:
        if new_hwnd:
            pid = wintypes.DWORD(0)
            u.GetWindowThreadProcessId(new_hwnd, ctypes.byref(pid))
            if pid.value:
                k = ctypes.windll.kernel32
                h = k.OpenProcess(0x0001, False, pid.value)  # PROCESS_TERMINATE
                if h:
                    k.TerminateProcess(h, 0); k.CloseHandle(h)
    except Exception as e:
        print(f"   (cleanup window-pid: {e})", flush=True)
    try:
        if proc and proc.poll() is None: proc.kill()
    except Exception: pass
    print("[done]", flush=True)
