import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
ToolRegistry.execute = lambda self,n,a: {"ok":True,"status":"dispatched","verified":None,"_eval_mock":True}
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
# capturar los _msgs del summary pass interceptando client.chat
orig = agent.client.chat
calls=[]
def spy(msgs, **kw):
    calls.append(msgs)
    return orig(msgs, **kw)
agent.client.chat = spy
agent.history.clear()
agent.run_content("close chrome")
# el último call es el summary pass; imprimir su system
for i,msgs in enumerate(calls):
    sysm = next((m for m in msgs if m.get("role")=="system"), None)
    sc = (sysm.get("content","") if sysm else "")[:200]
    print(f"--- call {i}: system[:200] = {sc!r}", flush=True)
