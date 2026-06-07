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
ToolRegistry.execute = lambda self,n,a: (print(f"  TOOL: {n} {a}", flush=True), {"ok":True,"status":"dispatched","verified":None,"_eval_mock":True})[1]
from gemma4_agent.agent_core.agent import Gemma4Agent
_lar = Gemma4Agent._llm_action_reply
Gemma4Agent._llm_action_reply = lambda self,ut,did,fb: (print(f"  HELPER: did={did!r}",flush=True), _lar(self,ut,did,fb))[1]
agent = Gemma4Agent(); agent.run_content("hola")
for msg in ["close chrome","set volume to 30","mute the sound"]:
    try: agent.history.clear()
    except Exception: pass
    print(f"\n=== {msg!r} ===", flush=True)
    r=agent.run_content(msg)
    print(f"  REPLY: {(getattr(r,'content','') or '')!r}", flush=True)
