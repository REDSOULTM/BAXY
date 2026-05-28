"""DIAG en vivo: 'Ve al portal uniej y luego a canvas' contra el modelo real,
con TODO lo físico stubeado. Verifica que el splitter+router ahora procesan AMBAS
cláusulas (antes solo ejecutaba la 1ra y narraba 'no pude verificar')."""
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.llama_server import get_shared_manager

prof = get_active_profile(); apply_profile_to_env(prof)
print("[boot]", get_shared_manager().start(prof, wait_health=True, timeout_s=120), flush=True)

from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.config import AgentConfig

def _stub_open(*a, **k):
    return {"ok": True, "opened": True, "stubbed": True}

cases = [
    "Ve al portal uniej y luego a canvas",
    "andá a portal2.uniej.cl y luego a canvas",
    "andá a youtube y después a netflix",
]
for q in cases:
    ag = Gemma4Agent(AgentConfig.from_env())
    ag.tools.gui_keypress = lambda a: {"ok": True, "stubbed": True}
    ag.tools.gui_type = lambda a: {"ok": True, "stubbed": True}
    ag.tools.gui_click = lambda a: {"ok": True, "stubbed": True}
    ag.tools.gui_screenshot = lambda a: {"ok": True, "image_path": "x.png", "stubbed": True}
    if hasattr(ag.tools, "app_open"): ag.tools.app_open = _stub_open
    if hasattr(ag.tools, "web_open_url"): ag.tools.web_open_url = _stub_open
    if hasattr(ag.tools, "_open_url_in_browser"): ag.tools._open_url_in_browser = _stub_open
    if getattr(ag.tools, "apps", None) is not None:
        ag.tools.apps.open = _stub_open

    events = []
    orig = ag.trace.event
    def _ev(tid, kind, **f):
        if kind in ("tool_call", "tool_result", "multi_intent_split",
                    "multi_intent_clause", "multi_intent_carry"):
            n = f.get("name") or f.get("tool")
            extra = ""
            if kind == "multi_intent_clause":
                extra = f" clause={f.get('clause','')[:50]!r}"
            if kind == "multi_intent_split":
                extra = f" parts={f.get('parts','')}"
            events.append(f"{kind} {n or ''}{extra}")
        return orig(tid, kind, **f)
    ag.trace.event = _ev

    print(f"\n=== Q {q!r} ===", flush=True)
    r = ag.run_content(q)
    for e in events:
        print(" ", e, flush=True)
    print("REPLY:", (r.content or "")[:250], flush=True)
