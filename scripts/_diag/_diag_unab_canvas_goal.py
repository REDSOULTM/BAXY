"""DIAG: tras revertir el splitter (que partía mal) + fix de alias `target`,
verificar qué hace el agente con "ve al portal uniej y luego a canvas" (UNA misión
con goal final, no 2 acciones encadenadas). Esperado: el router debería ofrecer
computer_use y el modelo elegirlo (o degradar honesto)."""
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

def _stub(*a, **k):
    return {"ok": True, "opened": True, "stubbed": True}

for mode in ("normal", "no_vidente"):
    print(f"\n############ accessibility mode = {mode} ############", flush=True)
    os.environ["GEMMA4_ACCESSIBILITY_MODE"] = mode
    for q in [
        "ve al portal uniej y luego a canvas",
        "andá a portal2.uniej.cl y luego a canvas",
    ]:
        ag = Gemma4Agent(AgentConfig.from_env())
        ag.tools.gui_keypress = lambda a: {"ok": True, "stubbed": True}
        ag.tools.gui_type = lambda a: {"ok": True, "stubbed": True}
        ag.tools.gui_click = lambda a: {"ok": True, "stubbed": True}
        ag.tools.gui_screenshot = lambda a: {"ok": True, "image_path": "x.png", "stubbed": True}
        if hasattr(ag.tools, "app_open"): ag.tools.app_open = _stub
        if hasattr(ag.tools, "web_open_url"): ag.tools.web_open_url = _stub
        if hasattr(ag.tools, "_open_url_in_browser"): ag.tools._open_url_in_browser = _stub
        if getattr(ag.tools, "apps", None) is not None:
            ag.tools.apps.open = _stub
        # stub computer_use para no ejecutar plan real (queremos ver SI lo eligió)
        ag.tools.t_computer_use = lambda a: {
            "ok": True, "stubbed_computer_use": True,
            "goal_received": a.get("goal", "")[:80],
        }

        events = []
        orig = ag.trace.event
        def _ev(tid, kind, **f):
            if kind in ("tool_subset", "tool_call", "tool_result"):
                n = f.get("name") or f.get("tool")
                tools = f.get("tools")
                events.append((kind, n, tools))
            return orig(tid, kind, **f)
        ag.trace.event = _ev

        print(f"\n  Q: {q!r}", flush=True)
        r = ag.run_content(q)
        for kind, n, tools in events:
            if kind == "tool_subset":
                # solo mostrar si computer_use está
                has_cu = "computer_use" in (tools or [])
                print(f"    tool_subset (computer_use_in_subset={has_cu}): {tools}", flush=True)
            else:
                print(f"    {kind}: {n}", flush=True)
        print(f"    REPLY: {(r.content or '')[:200]!r}", flush=True)
