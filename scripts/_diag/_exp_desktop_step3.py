"""PASO 3 del desktop AISLADO: con SwitchDesktop (el escritorio aislado pasa a ser
el ACTIVO durante el test -> SendInput/UIA/screenshot funcionan normal ahí; VS Code
queda en Default, NO recibe el input). Corre el `gui_type_into` REAL del agente en
el Notepad aislado y verifica (state_changed + UIA-read). WATCHDOG: vuelve a tu
escritorio a los 20s pase lo que pase. SEGURO: el SendInput va al escritorio activo
(aislado), no a VS Code (Default)."""
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
TEXT = "Hola Mundo desde Gemma4"

result = {}
hDefault = u.OpenInputDesktop(0, False, GENERIC_ALL)   # tu escritorio actual

def _watchdog():
    time.sleep(20)
    try: u.SwitchDesktop(hDefault)   # vuelve SIEMPRE, pase lo que pase
    except Exception: pass

def worker(hiso):
    switched = False
    try:
        u.SetThreadDesktop(hiso)
        import win32process
        si = win32process.STARTUPINFO(); si.lpDesktop = DESK
        win32process.CreateProcess(None, "notepad.exe", None, None, 0, 0, None, None, si)
        time.sleep(2.0)
        u.SwitchDesktop(hiso); switched = True   # AHORA el aislado es el activo
        time.sleep(0.8)
        from gemma4_agent.memory_pkg.memory import MemoryStore
        from gemma4_agent.memory_pkg.state import AgentState
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        tmp = Path(tempfile.mkdtemp())
        reg = ToolRegistry(MemoryStore(tmp/"m.json"), tmp/"c", state=AgentState(tmp/"d"/"s.json"))
        r = reg.gui_type_into({"text": TEXT, "window": "Bloc de notas"})
        result["gui_type_into"] = {k: r.get(k) for k in
                                   ("ok","verified","state_changed","typed","method","error")}
        time.sleep(0.4)
        try:
            tree = reg.t_uia({"action": "tree", "window": "Bloc de notas"})
            import json as _j; blob = _j.dumps(tree, ensure_ascii=False)
            result["uia_has_text"] = TEXT[:15] in blob
            result["uia_root"] = (tree.get("root") or {}).get("name", "")[:60]
        except Exception as e:
            result["uia_err"] = str(e)
        # cleanup notepad
        try:
            for h,t,p in _iso.iso_windows(hiso):
                if p: _iso.kill_pid(p)
        except Exception: pass
    finally:
        if switched:
            try: u.SwitchDesktop(hDefault)   # volver a TU escritorio
            except Exception: pass

if __name__ == "__main__":
    threading.Thread(target=_watchdog, daemon=True).start()
    hiso = u.CreateDesktopW(DESK, None, None, 0, GENERIC_ALL, None)
    t = threading.Thread(target=worker, args=(hiso,)); t.start(); t.join(timeout=30)
    try: u.SwitchDesktop(hDefault)   # garantía extra
    except Exception: pass
    print("[resultado]", flush=True)
    for k,v in result.items(): print(f"   {k} = {v}", flush=True)
    try: _iso.iso_cleanup(DESK)
    except Exception as e: print(f"   (cleanup: {e})", flush=True)
    gti = result.get("gui_type_into", {})
    verdict = "TIPEÓ Y VERIFICÓ" if (gti.get("ok") and (gti.get("state_changed") or result.get("uia_has_text"))) else "no confirmado"
    print(f"\n[VEREDICTO] {verdict} | ok={gti.get('ok')} state_changed={gti.get('state_changed')} uia_has_text={result.get('uia_has_text')}", flush=True)
