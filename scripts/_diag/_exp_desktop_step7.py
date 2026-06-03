"""PASO 7 (final, limpio): un intento, settle generoso. Verifica por el TÍTULO de la
ventana del Notepad (Win11 pone la 1ra línea del doc ahí -> GetWindowText lo lee,
fiable, sin screenshot/UIA). Confirma que el agente tipea en la app aislada."""
from __future__ import annotations
import sys, time, ctypes, threading, tempfile
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0, ".")
sys.path.insert(0, str(Path("scripts/_diag").resolve()))
import _desktop_iso as _iso
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
u = ctypes.windll.user32
u.CreateDesktopW.restype = wintypes.HANDLE
u.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
u.OpenInputDesktop.restype = wintypes.HANDLE
u.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
u.SetThreadDesktop.argtypes = [wintypes.HANDLE]; u.SwitchDesktop.argtypes = [wintypes.HANDLE]
GENERIC_ALL = 0x10000000; DESK = "Gemma4Iso"
TEXT = "Gemma verifica aislado 98765"
result = {}
hDefault = u.OpenInputDesktop(0, False, GENERIC_ALL)
def _wd():
    time.sleep(30)
    try: u.SwitchDesktop(hDefault)
    except Exception: pass
def worker(hiso):
    switched = False
    try:
        u.SetThreadDesktop(hiso)
        import win32process
        si = win32process.STARTUPINFO(); si.lpDesktop = DESK
        win32process.CreateProcess(None, "notepad.exe", None, None, 0, 0, None, None, si)
        time.sleep(4.0)
        u.SwitchDesktop(hiso); switched = True
        time.sleep(2.5)
        from gemma4_agent.memory_pkg.memory import MemoryStore
        from gemma4_agent.memory_pkg.state import AgentState
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        tmp = Path(tempfile.mkdtemp())
        reg = ToolRegistry(MemoryStore(tmp/"m.json"), tmp/"c", state=AgentState(tmp/"d"/"s.json"))
        r = reg.gui_type_into({"text": TEXT, "window": "Bloc de notas"})
        result["gui_type_into"] = {k: r.get(k) for k in ("ok","verified","method","error")}
        time.sleep(0.8)
        # leer el TÍTULO de la ventana del Notepad aislado (= contenido del doc)
        titles = [t for h, t, p in _iso.iso_windows(hiso) if "Bloc de notas" in t or "Notepad" in t]
        result["notepad_title"] = titles[0] if titles else "(no encontrada)"
        ttl = (titles[0] if titles else "")
        result["CONFIRMED_98765"] = "98765" in ttl
        result["CONFIRMED_partial"] = any(w in ttl for w in ("verifica", "aislado", "Gemma"))
        try:
            for h, t, p in _iso.iso_windows(hiso):
                if p: _iso.kill_pid(p)
        except Exception: pass
    except Exception as e:
        result["worker_err"] = repr(e)
    finally:
        if switched:
            try: u.SwitchDesktop(hDefault)
            except Exception: pass
if __name__ == "__main__":
    threading.Thread(target=_wd, daemon=True).start()
    hiso = u.CreateDesktopW(DESK, None, None, 0, GENERIC_ALL, None)
    t = threading.Thread(target=worker, args=(hiso,)); t.start(); t.join(timeout=28)
    try: u.SwitchDesktop(hDefault)
    except Exception: pass
    print("[resultado]", flush=True)
    for k, v in result.items(): print(f"   {k} = {v}", flush=True)
    try: _iso.iso_cleanup(DESK)
    except Exception as e: print(f"   (cleanup: {e})", flush=True)
    print(f"\n[VEREDICTO] texto en la app aislada: 98765={result.get('CONFIRMED_98765')} "
          f"parcial={result.get('CONFIRMED_partial')}", flush=True)
