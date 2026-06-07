import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")
# 1) probar _guess_lang en los inputs que fallan
from gemma4_agent.safety_pkg.reply_validator import _guess_lang
print("=== _guess_lang de inputs que leakean ===", flush=True)
for t in ["close chrome","set volume to 30","take a screenshot","play music","schließe chrome","imposta il volume a 30","mets le volume à 30"]:
    print(f"  {t!r} -> {_guess_lang(t)!r}", flush=True)
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
ToolRegistry.execute = lambda self,n,a: {"ok":True,"status":"dispatched","verified":None,"_eval_mock":True}
from gemma4_agent.agent_core.agent import Gemma4Agent
# trazar si el repair se dispara
_lar = Gemma4Agent._llm_action_reply
Gemma4Agent._llm_action_reply = lambda self,ut,did,fb: (print(f"  REPAIR FIRED: ut={ut!r} did={did!r}",flush=True), _lar(self,ut,did,fb))[1]
agent = Gemma4Agent(); agent.run_content("hola")
for msg in ["close chrome","take a screenshot","play music"]:
    try: agent.history.clear()
    except Exception: pass
    print(f"\n=== {msg!r} ===", flush=True)
    r=agent.run_content(msg)
    print(f"  REPLY: {(getattr(r,'content','') or '')!r}", flush=True)
