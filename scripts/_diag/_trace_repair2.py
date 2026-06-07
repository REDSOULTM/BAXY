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
import gemma4_agent.agent_core.agent as A
# trazar _detect_lang y el repair
_dl = A._detect_lang
A._detect_lang = lambda t: (lambda r: (print(f"    detect_lang({t[:30]!r})={r}",flush=True), r)[1])(_dl(t))
_lar = A.Gemma4Agent._llm_action_reply
A.Gemma4Agent._llm_action_reply = lambda self,ut,did,fb: (print(f"    REPAIR FIRED ut={ut!r} did={did!r}",flush=True), _lar(self,ut,did,fb))[1]
# trazar si _finalize_turn se alcanza
_ft = A.Gemma4Agent._finalize_turn
def _ftw(self,*a,**k):
    print("    _finalize_turn REACHED",flush=True)
    return _ft(self,*a,**k)
A.Gemma4Agent._finalize_turn = _ftw
agent = A.Gemma4Agent(); agent.run_content("hola")
for msg in ["take a screenshot","chiudi chrome"]:
    try: agent.history.clear()
    except Exception: pass
    print(f"\n=== {msg!r} ===", flush=True)
    r=agent.run_content(msg)
    print(f"  REPLY: {(getattr(r,'content','') or '')!r}", flush=True)
