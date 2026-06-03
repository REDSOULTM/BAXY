import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent.parent; sys.path.insert(0,str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8",errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
from gemma4_agent.infra.profiles import get_active_profile,apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
apply_profile_to_env(get_active_profile())
get_shared_manager().start(get_active_profile(),wait_health=True,timeout_s=120); print("[boot] OK",flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
disp=[]; _real=ToolRegistry.execute
ToolRegistry.execute=lambda self,n,a:(disp.append((n,(a or {}).get('text') or (a or {}).get('name') or (a or {}).get('action'))) or {"ok":True,"verified":True,"_mock":True})
from gemma4_agent.agent_core.agent import Gemma4Agent
for cmd in ["abrí la calculadora, escribí 5 y abrí el bloc de notas",
            "abrí el bloc de notas y escribí hola"]:
    a=Gemma4Agent(); disp.clear()
    r=a.run_content(cmd)
    print(f"\nQ: {cmd!r}")
    print(f"   dispatch: {disp}")
    print(f"   reply: {(getattr(r,'content','') or '')[:100]!r}")
