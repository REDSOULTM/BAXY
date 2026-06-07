"""MEDIR el ENCADENAMIENTO actual (Etapa 2): comandos multi-paso / meta pasan por
run_content REAL (router+4B+multi-intent split + app-action), ejecución física
MOCKEADA. Captura la SECUENCIA de tools despachadas + planes de cu, para ver qué
encadena bien y dónde rompe (dependencia, back-reference, decomposición implícita)."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.computer_use_pkg import computer_use as cu
from gemma4_agent.agent_core.agent import Gemma4Agent

cap = {"disp": [], "plans": []}
_real = ToolRegistry.execute
ToolRegistry.execute = lambda self,n,a: (cap["disp"].append((n, dict(a or {}))) or
    (_real(self,n,a) if n=="computer_use" else {"ok":True,"status":"ok","_mock":True}))
cu.PlanExecutor.execute = lambda self,plan,*a,**k: (cap["plans"].append(plan) or
    {"ok":True,"verified":True,"steps":[{"op":p.get("op"),"arg":p.get("arg")} for p in (plan or [])]})
# simular apps abiertas para que el OS-check de act_in_app deje pasar
_OPEN={"notepad","bloc","bloque","notas","word","spotify","discord","vlc","chrome","navegador","youtube","calculadora"}
Gemma4Agent._window_title_in_text = lambda self,t: ("App - "+t) if (
    {w for w in __import__("re").findall(r"\w+",(t or "").lower()) if len(w)>=4} & _OPEN) else None

def run(msg):
    a=Gemma4Agent(); cap["disp"].clear(); cap["plans"].clear()
    r=a.run_content(msg)
    return list(cap["disp"]), list(cap["plans"]), (getattr(r,"content","") or "").strip()

CHAINS = [
    "instalá VLC y abrilo",                             # package -> app (back-ref) DONE
    "descargá Spotify y abrilo",                        # download -> open
    "instalá el chrome, esperá y abrilo",              # 3 pasos con wait
    "abrí el bloc de notas y cerralo",                  # open -> CLOSE (dependent close?)
    "abrí la calculadora y abrí el bloc de notas",      # 2 opens independientes
    "abrí el word, escribí hola y guardá",              # 3 pasos in-app
    "abrí Discord y escribí hola",                      # app -> type in-app (false-success?)
    "abrí steam e instalá doom",                        # app -> install in-app
    "abrí el explorador y andá a descargas",            # app -> nav in-app
    "poné una alarma a las 8 y bajá el volumen",        # 2 indep (no computer-use)
]
for c in CHAINS:
    disp, plans, rep = run(c)
    chain = " → ".join(n for n,_ in disp) or "(nada)"
    ops = [f"{p.get('op')}({str(p.get('arg'))[:18]})" for pl in plans for p in (pl or [])]
    print("\n" + "="*78)
    print(f"Q: {c!r}")
    print(f"   CADENA: {chain}")
    if ops: print(f"   cu_plan: {ops}")
    print(f"   reply: {rep[:90]!r}")
