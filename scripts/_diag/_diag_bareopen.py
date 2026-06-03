import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent.parent; sys.path.insert(0,str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8",errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
from gemma4_agent.infra.profiles import get_active_profile,apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof=get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof,wait_health=True,timeout_s=120); print("[boot] OK",flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
disp=[]; _real=ToolRegistry.execute
ToolRegistry.execute=lambda self,n,a:(disp.append(n) or {"ok":True,"_mock":True})
from gemma4_agent.agent_core.agent import Gemma4Agent
# router subset también
import json
for cmd in ["abrí la calculadora","abrí spotify","abrí el bloc de notas","abrí discord","abrí la calc"]:
    routes=[]
    for _ in range(3):
        a=Gemma4Agent(); disp.clear(); a.run_content(cmd); routes.append(",".join(disp) or "NADA")
    print(f"  {cmd!r:28} -> {routes}",flush=True)
