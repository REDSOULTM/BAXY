"""De-risk: ¿cu(goal) produce un plan útil para nav/acción IN-APP? (open_chat para
canal de Discord, open_url para web, etc.). Mockea PlanExecutor.execute -> captura el
plan que el planner del 4B arma. Sin ejecución física."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from gemma4_agent.computer_use_pkg import computer_use as cu
from gemma4_agent.agent_core.agent import Gemma4Agent

plans = []
cu.PlanExecutor.execute = lambda self, plan, *a, **k: (plans.append(plan) or
    {"ok": True, "verified": True, "steps": [{"op": p.get("op"), "arg": p.get("arg")} for p in (plan or [])]})

a = Gemma4Agent()
GOALS = [
    "andá al canal general en Discord", "entrá al canal de música en Discord",
    "abrí el canal general de Discord", "ve a la playlist de rock en Spotify",
    "andá a youtube en el navegador",
]
for g in GOALS:
    plans.clear()
    try:
        res = a.tools.t_computer_use({"goal": g})
    except Exception as e:
        print(f"  {g!r:46} -> EXC {type(e).__name__}: {e}"); continue
    ops = [(p.get("op"), str(p.get("arg"))[:28]) for pl in plans for p in (pl or [])]
    print(f"  {g!r:46} -> plan={ops}", flush=True)
print("[done]")
