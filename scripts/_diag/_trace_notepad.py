import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
_orig = ToolRegistry.execute
def _traced(self, n, a):
    print(f"  TOOL EXEC: {n} {a}", flush=True)
    return {"ok": True, "status": "dispatched", "verified": None, "_eval_mock": True}
ToolRegistry.execute = _traced
# trazar extract_app_open
from gemma4_agent.routing import command_splitter as cs
_orig_eao = cs.extract_app_open
def _eao(t):
    r = _orig_eao(t); print(f"  extract_app_open({t!r}) = {r!r}", flush=True); return r
cs.extract_app_open = _eao
# trazar mi helper
from gemma4_agent.agent_core.agent import Gemma4Agent
_orig_lar = Gemma4Agent._llm_action_reply
def _lar(self, ut, did, fallback):
    print(f"  _llm_action_reply CALLED: did={did!r}", flush=True)
    r = _orig_lar(self, ut, did, fallback); print(f"  _llm_action_reply -> {r!r}", flush=True); return r
Gemma4Agent._llm_action_reply = _lar
agent = Gemma4Agent(); agent.run_content("hola")
print("\n=== run 'open notepad' ===", flush=True)
r = agent.run_content("open notepad")
print(f"FINAL REPLY: {(getattr(r,'content','') or '')!r}", flush=True)
