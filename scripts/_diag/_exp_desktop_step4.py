"""PASO 4: verificación DEFINITIVA del tipeo aislado vía PORTAPAPELES. Con el
escritorio aislado activo (SwitchDesktop): el agente tipea en el Notepad, luego
Ctrl+A + Ctrl+C (en el Notepad aislado, seguro), y leo el clipboard (compartido).
Si el clipboard == el texto -> el agente REALMENTE tipeó en la app. Vuelve a tu
escritorio (watchdog 30s)."""
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
u.OpenInputDesktop.restype = wintypes.HANDLE
u.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
u.SetThreadDesktop.argtypes = [wintypes.HANDLE]
u.SwitchDesktop.argtypes = [wintypes.HANDLE]
GENERIC_ALL = 0x10000000
DESK = "Gemma4Iso"
TEXT = "Hola Mundo desde Gemma4 aislado 98765"

result = {}
hDefault = u.OpenInputDesktop(0, False, GENERIC_ALL)

def _watchdog():
    time.sleep(30)
    try: u.SwitchDesktop(hDefault)
    except Exception: pass

def _read_clipboard():
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return data or ""
    except Exception as e:
        return f"<clip err {e}>"

def worker(hiso):
    switched = False
    try:
        u.SetThreadDesktop(hiso)
        import win32process
        si = win32process.STARTUPINFO(); si.lpDesktop = DESK
        win32process.CreateProcess(None, "notepad.exe", None, None, 0, 0, None, None, si)
        time.sleep(2.0)
        u.SwitchDesktop(hiso); switched = True
        time.sleep(0.8)
        from gemma4_agent.memory_pkg.memory import MemoryStore
        from gemma4_agent.memory_pkg.state import AgentState
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        tmp = Path(tempfile.mkdtemp())
        reg = ToolRegistry(MemoryStore(tmp/"m.json"), tmp/"c", state=AgentState(tmp/"d"/"s.json"))
        # vaciar clipboard para no leer un residuo viejo
        try:
            import win32clipboard
            win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText("___nada___"); win32clipboard.CloseClipboard()
        except Exception: pass
        r = reg.gui_type_into({"text": TEXT, "window": "Bloc de notas"})
        result["gui_type_into"] = {k: r.get(k) for k in ("ok","verified","state_changed","method","error")}
        time.sleep(0.5)
        # select-all + copy EN EL NOTEPAD AISLADO (input va al escritorio activo=aislado)
        reg.execute("gui", {"action": "keypress", "keys": "ctrl+a"}); time.sleep(0.25)
        reg.execute("gui", {"action": "keypress", "keys": "ctrl+c"}); time.sleep(0.4)
        clip = _read_clipboard()
        result["clipboard"] = clip[:80]
        result["typed_confirmed"] = (TEXT in clip)
        try:
            for h,t,p in _iso.iso_windows(hiso):
                if p: _iso.kill_pid(p)
        except Exception: pass
    except Exception as e:
        result["worker_err"] = repr(e)
    finally:
        if switched:
            try: u.SwitchDesktop(hDefault)
            except Exception: pass

if __name__ == "__main__":
    threading.Thread(target=_watchdog, daemon=True).start()
    hiso = u.CreateDesktopW(DESK, None, None, 0, GENERIC_ALL, None)
    t = threading.Thread(target=worker, args=(hiso,)); t.start(); t.join(timeout=28)
    try: u.SwitchDesktop(hDefault)
    except Exception: pass
    print("[resultado]", flush=True)
    for k,v in result.items(): print(f"   {k} = {v}", flush=True)
    try: _iso.iso_cleanup(DESK)
    except Exception as e: print(f"   (cleanup: {e})", flush=True)
    print(f"\n[VEREDICTO] tipeo confirmado por clipboard = {result.get('typed_confirmed')}", flush=True)
