"""PASO 5: prueba DEFINITIVA y VISUAL. Con el escritorio aislado activo, el agente
tipea en el Notepad y SACA UN SCREENSHOT del escritorio aislado (lo guarda a un path
fijo). Vuelve a tu escritorio. Después YO leo el PNG -> si veo el texto en el Notepad,
queda 100% confirmado que el agente tipea en apps reales (aislado de VS Code)."""
from __future__ import annotations
import sys, time, ctypes, threading, tempfile, shutil
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
TEXT = "GEMMA4 PRUEBA AISLADA 98765 hola mundo"
PROOF = Path("scripts/_diag/_iso_proof.png").resolve()

result = {}
hDefault = u.OpenInputDesktop(0, False, GENERIC_ALL)

def _watchdog():
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
        time.sleep(2.0)
        u.SwitchDesktop(hiso); switched = True
        time.sleep(0.8)
        from gemma4_agent.memory_pkg.memory import MemoryStore
        from gemma4_agent.memory_pkg.state import AgentState
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        tmp = Path(tempfile.mkdtemp())
        reg = ToolRegistry(MemoryStore(tmp/"m.json"), tmp/"c", state=AgentState(tmp/"d"/"s.json"))
        r = reg.gui_type_into({"text": TEXT, "window": "Bloc de notas"})
        result["gui_type_into"] = {k: r.get(k) for k in ("ok","verified","state_changed","method")}
        time.sleep(0.6)
        shot = reg.gui_screenshot({})
        sp = shot.get("image_path") if isinstance(shot, dict) else None
        result["shot_path"] = sp
        if sp and Path(sp).exists():
            shutil.copy(sp, PROOF)
            result["proof"] = str(PROOF)
        # OCR automatico (ademas del screenshot que leere yo)
        try:
            oc = reg.execute("vision", {"action": "ocr", "image_path": str(PROOF)})
            txt = (oc.get("text") or "") if isinstance(oc, dict) else ""
            result["ocr_has_text"] = "98765" in txt or "GEMMA4" in txt.upper()
            result["ocr_excerpt"] = txt[:120].replace("\n", " ")
        except Exception as e:
            result["ocr_err"] = str(e)
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
    print(f"\n[PROOF PNG] {PROOF}", flush=True)
