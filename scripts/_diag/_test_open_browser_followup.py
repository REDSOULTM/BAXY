"""Reproduce el bug del screenshot: 'abre pivigames' (no instalado) -> 'abrelo en
el navegador' DEBE abrir en browser, no app(search). Mide la cadena de 2 turnos."""
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
# app.open de algo no instalado -> needs_user (como en prod); browser/web -> ok
def _exec(self, n, a):
    _ex.append((n, (a or {}).get("action")))
    if n == "app" and (a or {}).get("action") == "open":
        return {"ok": False, "status": "needs_user", "note": "not installed", "_eval_mock": True}
    return {"ok": True, "status": "dispatched", "url": (a or {}).get("url"), "_eval_mock": True}
ToolRegistry.execute = _exec
ToolRegistry.web_open_url = lambda self,a: (_ex.append(("web_open", a.get("url"))), {"ok":True,"status":"dispatched","url":a.get("url")})[1]
ToolRegistry._open_url_in_browser = lambda self,b,u: (_ex.append(("browser_open", u)), {"ok":True,"status":"dispatched","url":u})[1]
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
agent.history.clear()
print("--- turno 1: abre pivigames ---", flush=True)
_ex.clear(); r1=agent.run_content("abre pivigames")
print(f"  exec={_ex} | reply={(getattr(r1,'content','') or '')[:60]!r}", flush=True)
print("--- turno 2: abrelo en el navegador ---", flush=True)
_ex.clear(); r2=agent.run_content("abrelo en el navegador")
went_browser = any(n in ("browser","web_open","browser_open") for n,_ in _ex)
print(f"  exec={_ex} | reply={(getattr(r2,'content','') or '')[:60]!r}", flush=True)
print(f"  >>> {'OK abrió en navegador' if went_browser else 'XX NO usó browser'}", flush=True)
