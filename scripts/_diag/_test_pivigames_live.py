"""Prueba EN VIVO (LLM real) el caso del screenshot: 've a pivigames' debe abrir
el dominio REAL, no el adivinado. Captura la URL que llega a la apertura física."""
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
# interceptar la apertura física para capturar la URL FINAL (resuelta)
_seen = {}
_orig_open = ToolRegistry.web_open_url
ToolRegistry.web_open_url = lambda self,a: (_seen.update(url=a.get("url")), {"ok":True,"status":"dispatched","url":a.get("url"),"_eval_mock":True})[1]
_orig_inbr = ToolRegistry._open_url_in_browser
ToolRegistry._open_url_in_browser = lambda self,b,u: (_seen.update(url=u,browser=b), {"ok":True,"status":"dispatched","url":u,"_eval_mock":True})[1]
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
for msg in ["ve a pivigames", "andá a pivigames", "abrí pivigames"]:
    try: agent.history.clear()
    except Exception: pass
    _seen.clear()
    r = agent.run_content(msg); rep=(getattr(r,"content","") or "")
    url = _seen.get("url","(no abrió)")
    guessed = "pivigames.com" in str(url) and "wordpress" not in str(url) and "blog" not in str(url)
    print(f"  [{'INVENTADO' if guessed else 'real?'}] {msg!r:20} -> {url!r}  reply={rep[:40]!r}", flush=True)
