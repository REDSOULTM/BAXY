"""DIAG: 'Quien eres?' -> en la captura (modo Movilidad) hizo gui screenshot +
locate_text('Thinking'). Reproducir en NORMAL vs MOVILIDAD para aislar si el modo
inyecta gui/computer_use y rompe una pregunta de identidad. Todo físico stubeado."""
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


def run(mode, q):
    os.environ["GEMMA4_ACCESSIBILITY_MODE"] = mode
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    ag = Gemma4Agent(AgentConfig.from_env())
    ag.tools.gui_screenshot = lambda a: {"ok": True, "image_path": "x.png", "stubbed": True}
    ag.tools.gui_keypress = lambda a: {"ok": True}
    ag.tools.gui_type = lambda a: {"ok": True}
    ag.tools._describe_image_directly = lambda *a, **k: "(pantalla)"
    r = ag.run_content(q)
    return [e.name for e in (r.tool_events or [])], (r.content or "")


for mode in ("normal", "movilidad"):
    print(f"\n############ {mode} ############", flush=True)
    for q in ["Quien eres?", "que podes hacer"]:
        tools, reply = run(mode, q)
        print(f"  Q {q!r}", flush=True)
        print(f"    tools={tools}", flush=True)
        print(f"    reply={reply[:130]!r}", flush=True)
