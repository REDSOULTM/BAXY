import sys, os, json, time
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
CASES = [("en","open spotify"),("en","close chrome"),("en","take a screenshot"),("en","mute the sound"),
 ("en","play some music"),("en","minimize this window"),
 ("pt","abre o spotify"),("pt","fecha o chrome"),("pt","tira um print"),("pt","reproduz música"),
 ("fr","ouvre spotify"),("fr","ferme chrome"),("fr","mets le volume à 30"),("fr","coupe le son"),
 ("de","öffne spotify"),("de","schließe chrome"),("de","mach einen screenshot"),
 ("it","apri spotify"),("it","chiudi chrome"),("it","imposta il volume a 30"),("it","fai uno screenshot"),
 ("es","abrí spotify"),("es","cerrá chrome"),("es","subí el volumen")]
out=open("scripts/_diag/_lang_replies.jsonl","w",encoding="utf-8")
for lang,msg in CASES:
    try: agent.history.clear()
    except Exception: pass
    t0=time.time(); r=agent.run_content(msg); dt=time.time()-t0
    rep=(getattr(r,"content","") or "")
    out.write(json.dumps({"expected":lang,"msg":msg,"reply":rep,"dt":round(dt,2)},ensure_ascii=False)+"\n")
    print(f"  [{lang}] {dt:4.1f}s {msg!r} -> {rep[:50]!r}", flush=True)
out.close()
