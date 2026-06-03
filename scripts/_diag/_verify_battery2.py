"""Verificación física AMPLIA #2: generaliza a Word (editor distinto) + cadena de
3 pasos. Comandos REALES, screenshots para LEER. Tipeo enfoca-primero sin Enter,
opens. Cierra apps de prueba por PID al final."""
from __future__ import annotations
import os, sys, time, ctypes
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
apply_profile_to_env(get_active_profile())
get_shared_manager().start(get_active_profile(), wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
import win32gui, win32process
from PIL import ImageGrab
from gemma4_agent.agent_core.agent import Gemma4Agent
DIR = Path("scripts/_diag/_battery"); DIR.mkdir(exist_ok=True)
TARGET = ("Word","Document","Calcul","Bloc de notas","Notepad","Sin t")
def tracked():
    out=set()
    def cb(h,_):
        t=win32gui.GetWindowText(h)
        if any(k in t for k in TARGET): out.add(win32process.GetWindowThreadProcessId(h)[1])
        return True
    win32gui.EnumWindows(cb,None); return out
before=tracked()
agent=Gemma4Agent()
TESTS=[
    ("word_type", "abrí el Word y escribí GEMMA WORD 33333", 6.0),
    ("chain3",    "abrí la calculadora, escribí 5 y abrí el bloc de notas", 4.0),
]
for tid,cmd,wait in TESTS:
    r=agent.run_content(cmd)
    rep=(getattr(r,"content","") or "").strip()
    time.sleep(wait)
    ImageGrab.grab().save(str((DIR/f"{tid}.png").resolve()))
    print(f"[{tid}] {cmd!r}\n       reply={rep[:90]!r}", flush=True)
# cleanup: cerrar lo que abrí (PIDs nuevos) por PID de ventana
time.sleep(0.5)
for pid in (tracked()-before):
    try:
        k=ctypes.windll.kernel32; h=k.OpenProcess(0x0001,False,pid)
        if h: k.TerminateProcess(h,0); k.CloseHandle(h); print(f"[cleanup] cerré pid {pid}",flush=True)
    except Exception: pass
print("[done]", flush=True)
