"""VERIFICACIÓN FÍSICA INTEGRAL del computer-use (PC del user, libre). Corre comandos
REALES (run_content, sin mocks) en el escritorio normal, saca screenshot de cada uno
para que Claude los LEA y confirme. Casos SEGUROS: tipeo enfoca-primero SIN Enter,
abrir apps, media. NADA de Enter/Ctrl+W/instalar. Cierra las apps de prueba al final."""
from __future__ import annotations
import os, sys, time, subprocess, ctypes
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)

import win32gui, win32process
from PIL import ImageGrab
from gemma4_agent.agent_core.agent import Gemma4Agent

DIR = Path("scripts/_diag/_battery"); DIR.mkdir(exist_ok=True)
def notepads():
    out=set()
    def cb(h,_):
        t=win32gui.GetWindowText(h)
        if "Bloc de notas" in t or "Notepad" in t or "Calculadora" in t or "Calculator" in t:
            out.add(win32process.GetWindowThreadProcessId(h)[1])
        return True
    win32gui.EnumWindows(cb,None); return out

def kill_pid(pid):
    k=ctypes.windll.kernel32; h=k.OpenProcess(0x0001,False,pid)
    if h: k.TerminateProcess(h,0); k.CloseHandle(h)

before = notepads()
agent = Gemma4Agent()

def vol():
    try:
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        # leer volumen maestro por pycaw (read-only)
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        dev=AudioUtilities.GetSpeakers(); iface=dev.Activate(IAudioEndpointVolume._iid_,CLSCTX_ALL,None)
        v=cast(iface,POINTER(IAudioEndpointVolume))
        return round(v.GetMasterVolumeLevelScalar()*100)
    except Exception as e:
        return f"?({e})"

TESTS = [
    ("type_notepad",  "escribí HOLA MUNDO GEMMA 11111 en el bloc de notas", "abrir notepad"),
    ("calc_open",     "abrí la calculadora", None),
    ("type_calc",     "escribí 123 en la calculadora", None),
    ("chain_open_type","abrí el bloc de notas y escribí CADENA GEMMA 22222", None),
    ("screenshot",    "sacá un screenshot", None),
    ("volume",        "bajá el volumen", "vol"),
    ("query",         "qué hora es", None),
]
results=[]
# asegurar Notepad abierto para el 1er test
subprocess.Popen(["notepad.exe"]); time.sleep(2.5)
for tid, cmd, note in TESTS:
    v0 = vol() if note=="vol" else None
    reply = agent.run_content(cmd)
    rep = (getattr(reply,"content","") or "").strip()
    time.sleep(0.8)
    shot = DIR / f"{tid}.png"
    try: ImageGrab.grab().save(shot)
    except Exception as e: shot=f"err {e}"
    v1 = vol() if note=="vol" else None
    results.append((tid, cmd, rep[:80], str(shot), (v0,v1) if note=="vol" else None))
    print(f"[{tid}] reply={rep[:70]!r}" + (f" vol {v0}->{v1}" if note=="vol" else ""), flush=True)

print("\n=== RESUMEN ===", flush=True)
for tid,cmd,rep,shot,vol_ in results:
    print(f"  {tid}: {cmd!r}\n      reply={rep!r} shot={Path(shot).name if 'err' not in shot else shot}"
          + (f" VOL {vol_}" if vol_ else ""), flush=True)

# cleanup: cerrar SOLO las apps que abrí (PIDs nuevos)
time.sleep(0.5)
for pid in (notepads() - before):
    try: kill_pid(pid); print(f"[cleanup] cerré pid {pid}", flush=True)
    except Exception: pass
print("[done]", flush=True)
