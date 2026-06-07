"""Mide los 4 casos de routing (pregunta NO ejecuta) en vivo. exec mockeado."""
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
_executed = []
def _spy(self, n, a):
    _executed.append((n, a)); return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
ToolRegistry.execute = _spy
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
CASES = [("estado","está Steam abierto?"),("howto","cómo cierro Spotify?"),
         ("conocimiento","qué es Python?"),("capacidad","puedes escucharme?"),
         ("estado2","está abierto Chrome?"),("howto2","cómo elimino una carpeta?")]
import re
for kind,msg in CASES:
    try: agent.history.clear()
    except Exception: pass
    _executed.clear()
    r=agent.run_content(msg); rep=(getattr(r,"content","") or "")
    acted = any(n in {"app","steam","browser","browser_real","filesystem","media","audio"} for n,a in _executed)
    print(f"  [{'XX' if acted else 'OK'}] {kind}: {msg!r} -> exec={_executed} reply={rep[:50]!r}", flush=True)
