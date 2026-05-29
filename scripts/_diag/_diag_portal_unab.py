"""DIAG en vivo: 'Ve al portal uniej' contra el modelo real, con TODO lo físico
stubeado. Verifica si el reply ya NO dice 'No pude verificar...' tras el fix de
verify_window_exists (dominio + navegador presente -> found=True con caveat)."""
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile(); apply_profile_to_env(prof)
print("[boot]", get_shared_manager().start(prof, wait_health=True, timeout_s=120), flush=True)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra.config import AgentConfig

ag = Gemma4Agent(AgentConfig.from_env())
ag.tools.gui_keypress = lambda a: {"ok": True, "stubbed": True}
ag.tools.gui_type = lambda a: {"ok": True, "stubbed": True}
ag.tools.gui_click = lambda a: {"ok": True, "stubbed": True}
ag.tools.gui_screenshot = lambda a: {"ok": True, "image_path": "x.png", "stubbed": True}

def _stub_open(*a, **k):
    return {"ok": True, "opened": True, "stubbed": True}

if hasattr(ag.tools, "app_open"):
    ag.tools.app_open = _stub_open
if hasattr(ag.tools, "web_open_url"):
    ag.tools.web_open_url = _stub_open
if hasattr(ag.tools, "_open_url_in_browser"):
    ag.tools._open_url_in_browser = _stub_open
if getattr(ag.tools, "apps", None) is not None:
    ag.tools.apps.open = _stub_open

events = []
orig = ag.trace.event
def _ev(tid, kind, **f):
    if kind in ("tool_call", "tool_result"):
        n = f.get("name") or f.get("tool")
        if n:
            events.append((kind, str(n)))
    return orig(tid, kind, **f)
ag.trace.event = _ev

for q in ["Ve al portal uniej", "andá a portal2.uniej.cl"]:
    print(f"\n=== Q {q!r} ===", flush=True)
    r = ag.run_content(q)
    for kind, n in events:
        print(" ", kind, n, flush=True)
    print("REPLY:", (r.content or "")[:200], flush=True)
    events.clear()
