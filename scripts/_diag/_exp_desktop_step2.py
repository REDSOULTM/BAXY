"""PASO 2 del desktop AISLADO: correr el `gui_type_into` REAL del agente (clipboard
+ SendInput) en un thread cuyo escritorio es Gemma4Iso. Su SendInput va a ese
escritorio, NO a VS Code (Default). Sin SwitchDesktop (cero disrupción a tu pantalla).
Verifica con la verificación propia del agente (state_changed/UIA) + lee el texto por
UIA desde el mismo thread. SEGURO: aunque el input 'leakeara', va al escritorio
aislado; y arranca con poco texto. Limpia todo al final."""
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
u.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
                             wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
u.SetThreadDesktop.argtypes = [wintypes.HANDLE]
GENERIC_ALL = 0x10000000
DESK = "Gemma4Iso"
TEXT = "Hola Mundo desde Gemma4 aislado"

result = {}

def worker(hdesk):
    # ESTE thread se muda al escritorio aislado ANTES de tocar GUI/agente.
    ok_set = bool(u.SetThreadDesktop(hdesk))
    result["set_thread_desktop"] = ok_set
    # lanzar Notepad EN este escritorio (hereda el desktop del thread creador)
    import win32process
    si = win32process.STARTUPINFO(); si.lpDesktop = DESK
    hp, ht, pid, tid = win32process.CreateProcess(None, "notepad.exe", None, None,
                                                  0, 0, None, None, si)
    result["notepad_pid_launcher"] = pid
    time.sleep(2.5)
    # construir el registry del agente y tipear con el path REAL
    from gemma4_agent.memory_pkg.memory import MemoryStore
    from gemma4_agent.memory_pkg.state import AgentState
    from gemma4_agent.tools_pkg.tools import ToolRegistry
    tmp = Path(tempfile.mkdtemp())
    reg = ToolRegistry(MemoryStore(tmp/"m.json"), tmp/"c", state=AgentState(tmp/"d"/"s.json"))
    r = reg.gui_type_into({"text": TEXT, "window": "Bloc de notas"})
    result["gui_type_into"] = {k: r.get(k) for k in
                               ("ok", "verified", "state_changed", "typed", "method", "error")}
    # leer de vuelta por UIA (TextPattern) desde ESTE thread (mismo escritorio)
    time.sleep(0.5)
    try:
        tree = reg.t_uia({"action": "tree", "window": "Bloc de notas"})
        import json as _j
        blob = _j.dumps(tree, ensure_ascii=False)
        result["uia_has_text"] = TEXT[:20] in blob
        result["uia_excerpt"] = blob[:300]
    except Exception as e:
        result["uia_err"] = str(e)
    # cleanup: matar el Notepad por PID de su ventana
    try:
        for h, t, p in _iso.iso_windows(hdesk):
            if p: _iso.kill_pid(p)
    except Exception as e:
        result["cleanup_err"] = str(e)

if __name__ == "__main__":
    hdesk = u.CreateDesktopW(DESK, None, None, 0, GENERIC_ALL, None)
    print(f"[1] escritorio {DESK!r} hdesk={hdesk}", flush=True)
    t = threading.Thread(target=worker, args=(hdesk,))
    t.start(); t.join(timeout=60)
    print("[2] resultado:", flush=True)
    for k, v in result.items():
        print(f"    {k} = {v}", flush=True)
    # cerrar el escritorio (y matar lo que haya quedado, por PID de ventana)
    try:
        _iso.iso_cleanup(DESK)
    except Exception as e:
        print(f"    (cleanup final: {e})", flush=True)
    gti = result.get("gui_type_into", {})
    print("\n[VEREDICTO] gui_type_into ok=%s verified=%s state_changed=%s | uia_has_text=%s"
          % (gti.get("ok"), gti.get("verified"), gti.get("state_changed"),
             result.get("uia_has_text")), flush=True)
