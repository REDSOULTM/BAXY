"""PASO 6: verificación DEFINITIVA del tipeo aislado. Con el escritorio aislado
activo: enfoca el Notepad, el agente tipea, luego Ctrl+A + Ctrl+C por SendInput
CRUDO in-process (garantizado al Notepad aislado, NO a VS Code), y leo el clipboard
(compartido en la window-station). Reintenta hasta 3x si el foco falla. Si el
clipboard == el texto -> CONFIRMADO que el agente tipea en apps reales, aislado."""
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
for fn, res, args in [("CreateDesktopW", wintypes.HANDLE, [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]),
                      ("OpenInputDesktop", wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD])]:
    getattr(u, fn).restype = res; getattr(u, fn).argtypes = args
u.SetThreadDesktop.argtypes = [wintypes.HANDLE]; u.SwitchDesktop.argtypes = [wintypes.HANDLE]
GENERIC_ALL = 0x10000000
DESK = "Gemma4Iso"
TEXT = "GEMMA4 PRUEBA AISLADA 98765 hola mundo"

# --- SendInput crudo para combos de teclas (Ctrl+A, Ctrl+C) ---
PUL = ctypes.POINTER(ctypes.c_ulong)
class KBD(ctypes.Structure):
    _fields_=[("wVk",ctypes.c_ushort),("wScan",ctypes.c_ushort),("dwFlags",ctypes.c_ulong),("time",ctypes.c_ulong),("dwExtraInfo",PUL)]
class _IU(ctypes.Union): _fields_=[("ki",KBD)]
class INP(ctypes.Structure): _fields_=[("type",ctypes.c_ulong),("u",_IU)]
KEYUP=0x0002; VK_CTRL=0x11
def _ev(vk,up):
    return INP(1,_IU(ki=KBD(vk,0,KEYUP if up else 0,0,None)))
def combo(vk):
    arr=(INP*4)(_ev(VK_CTRL,False),_ev(vk,False),_ev(vk,True),_ev(VK_CTRL,True))
    u.SendInput(4,arr,ctypes.sizeof(INP))

def read_clip():
    try:
        import win32clipboard as w
        w.OpenClipboard()
        try: return w.GetClipboardData(w.CF_UNICODETEXT) or ""
        finally: w.CloseClipboard()
    except Exception as e: return f"<err {e}>"

result={}
hDefault=u.OpenInputDesktop(0,False,GENERIC_ALL)
def _wd():
    time.sleep(35)
    try: u.SwitchDesktop(hDefault)
    except Exception: pass

def worker(hiso):
    switched=False
    try:
        u.SetThreadDesktop(hiso)
        import win32process, win32gui
        from gemma4_agent.memory_pkg.memory import MemoryStore
        from gemma4_agent.memory_pkg.state import AgentState
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        tmp=Path(tempfile.mkdtemp())
        reg=ToolRegistry(MemoryStore(tmp/"m.json"),tmp/"c",state=AgentState(tmp/"d"/"s.json"))
        for attempt in range(1,4):
            si=win32process.STARTUPINFO(); si.lpDesktop=DESK
            win32process.CreateProcess(None,"notepad.exe",None,None,0,0,None,None,si)
            time.sleep(3.0)                       # dejar que Notepad RENDERICE en Iso
            if not switched:
                u.SwitchDesktop(hiso); switched=True
            time.sleep(1.5)                       # settle como foreground
            r=reg.gui_type_into({"text":TEXT,"window":"Bloc de notas"})
            result[f"try{attempt}"]={k:r.get(k) for k in ("ok","verified","method","error")}
            if r.get("ok"):
                time.sleep(0.6)
                # vaciar clipboard, luego copiar del Notepad por SendInput crudo
                try:
                    import win32clipboard as w
                    w.OpenClipboard(); w.EmptyClipboard(); w.SetClipboardText("___nada___"); w.CloseClipboard()
                except Exception: pass
                combo(0x41); time.sleep(0.3)      # Ctrl+A
                combo(0x43); time.sleep(0.5)      # Ctrl+C
                clip=read_clip()
                result["clipboard"]=clip[:90]
                result["CONFIRMED"]=(TEXT in clip)
                if result["CONFIRMED"]: break
            # limpiar Notepad de este intento y reintentar
            try:
                for h,t,p in _iso.iso_windows(hiso):
                    if p: _iso.kill_pid(p)
            except Exception: pass
            time.sleep(0.5)
    except Exception as e:
        result["worker_err"]=repr(e)
    finally:
        try:
            for h,t,p in _iso.iso_windows(hiso):
                if p: _iso.kill_pid(p)
        except Exception: pass
        if switched:
            try: u.SwitchDesktop(hDefault)
            except Exception: pass

if __name__=="__main__":
    threading.Thread(target=_wd,daemon=True).start()
    hiso=u.CreateDesktopW(DESK,None,None,0,GENERIC_ALL,None)
    t=threading.Thread(target=worker,args=(hiso,)); t.start(); t.join(timeout=33)
    try: u.SwitchDesktop(hDefault)
    except Exception: pass
    print("[resultado]",flush=True)
    for k,v in result.items(): print(f"   {k} = {v}",flush=True)
    try: _iso.iso_cleanup(DESK)
    except Exception as e: print(f"   (cleanup: {e})",flush=True)
    print(f"\n[VEREDICTO] CONFIRMADO = {result.get('CONFIRMED')}",flush=True)
