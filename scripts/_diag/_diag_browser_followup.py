"""DIAGNÓSTICO (no fix): por qué el LLM elige app en vez de browser en el follow-up
'abrelo en el navegador'. Captura subset ofrecido (orden) + tool_call emitido."""
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
# capturar el subset que el router ofrece por turno
import gemma4_agent.routing.planner as P
_orig_sel = P.select_tool_names
def _sel(content, plan, **kw):
    s = _orig_sel(content, plan, **kw)
    txt = content if isinstance(content, str) else "?"
    print(f"  SUBSET para {txt!r:30}: {s}", flush=True)
    return s
P.select_tool_names = _sel
import gemma4_agent.agent_core.agent as A
A.select_tool_names = _sel  # por si lo importó directo
from gemma4_agent.tools_pkg.tools import ToolRegistry
_ex = []
def _exec(self, n, a):
    _ex.append((n, (a or {}).get("action")))
    if n == "app" and (a or {}).get("action") == "open":
        return {"ok": False, "status": "needs_user", "note": "not installed", "_eval_mock": True}
    return {"ok": True, "status": "dispatched", "_eval_mock": True}
ToolRegistry.execute = _exec
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
agent.history.clear()
agent.run_content("abre pivigames")
print("--- turno 2: abrelo en el navegador ---", flush=True)
_ex.clear()
r = agent.run_content("abrelo en el navegador")
print(f"  TOOL EMITIDA: {_ex}", flush=True)
print(f"  reply: {(getattr(r,'content','') or '')[:50]!r}", flush=True)
