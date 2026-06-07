"""Verifica que 've a X'/'desmutea' ya NO disparen cancel_turn (bug del router).
Mide qué TOOL se ejecuta en vivo. exec mockeado (seguro)."""
import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
_ex = []
ToolRegistry.execute = lambda self,n,a: (_ex.append((n, (a or {}).get("action"))), {"ok":True,"status":"ok","verified":True,"_eval_mock":True})[1]
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
CASES = ["ve a pivigames","desmutea el pc pls","andá a youtube","desmuteá el sonido",
         "para","cancelá eso"]   # los 2 últimos SÍ deben cancelar
for msg in CASES:
    try: agent.history.clear()
    except Exception: pass
    _ex.clear()
    r=agent.run_content(msg); rep=(getattr(r,"content","") or "")
    cancelled = any(n=="session" and act=="cancel_turn" for n,act in _ex)
    print(f"  {'CANCEL' if cancelled else 'action'}: {msg!r:22} exec={_ex} -> {rep[:45]!r}", flush=True)
