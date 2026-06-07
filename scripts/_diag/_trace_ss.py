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
# trazar el repair + describe + detect
_lar = A.Gemma4Agent._llm_action_reply
A.Gemma4Agent._llm_action_reply = lambda self,ut,did,fb,target_lang=None: (print(f"    REPAIR ut={ut!r} target={target_lang} did={did!r}",flush=True), _lar(self,ut,did,fb,target_lang))[1]
_dl=A._detect_lang
A._detect_lang=lambda t:(lambda r:(print(f"    detect({t[:25]!r})={r}",flush=True),r)[1])(_dl(t))
# trazar el screen_description path
_sdr=A.Gemma4Agent._screen_description_reply
def _sdrw(self,ev):
    r=_sdr(self,ev); 
    if r: print(f"    SCREEN_DESC OVERRIDE -> {r[:40]!r}",flush=True)
    return r
A.Gemma4Agent._screen_description_reply=_sdrw
agent = A.Gemma4Agent(); agent.run_content("hola")
print("\n=== take a screenshot ===",flush=True)
r=agent.run_content("take a screenshot")
print(f"  REPLY: {(getattr(r,'content','') or '')!r}",flush=True)
