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
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.computer_use_pkg import computer_use as cu
from gemma4_agent.agent_core.agent import Gemma4Agent
plans = []
ToolRegistry.execute = (lambda real: (lambda self,n,a: real(self,n,a) if n=="computer_use" else {"ok":True,"_mock":True}))(ToolRegistry.execute)
cu.PlanExecutor.execute = lambda self,plan,*a,**k: (plans.append(plan) or {"ok":True,"verified":True,"steps":[{"op":p.get("op"),"arg":p.get("arg")} for p in plan]})
Gemma4Agent._window_title_in_text = lambda self,t: ("App - "+t) if t else None
for u in ["escribí sigue en claude code", "en claude code escribí quién eres",
          "escribí hola mundo en el bloc de notas", "andá a Claude Code y escribí continuá"]:
    plans.clear(); Gemma4Agent().run_content(u)
    pl = plans[0] if plans else []
    print(f"\nQ {u!r}")
    for p in pl: print(f"   {p.get('op')}({p.get('arg')!r})")
