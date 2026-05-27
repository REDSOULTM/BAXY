"""GATE 0b — ejecución de misiones WEB de punta a punta, inyectando el mensaje
del usuario en TEXTO (como hace la UI) y dejando que el agente actúe.

SEGURIDAD: las misiones son WEB (navegar/buscar), que el agente resuelve por
computer_use->open_url->CDP/Playwright — NO roba foco a VS Code. Si el agente
intentara SendInput físico (gui_type/gui_click), lo veríamos en los tool events
y lo reportamos como "cae a SendInput (no medible por Claude)".

Mide en modo MOVILIDAD (el caso de producto). Reporta, por misión: la respuesta
final, los tool-calls emitidos, y si quedó verificado.

Uso:  python scripts/gui_eval/measure_web_execution.py "<mision>"
      (sin arg: corre el set por defecto)
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_ACCESSIBILITY_MODE", "movilidad")

from gemma4_agent.config import AgentConfig
from gemma4_agent.agent import Gemma4Agent

# Acciones GUI FÍSICAS (SendInput, roban foco -> peligro para VS Code). SOLO
# estas: type/click/keypress/hotkey/scroll/drag. gui.screenshot / locate_* son
# READ-ONLY (capturan/leen, no tocan foco) -> SEGURAS. La detección mira la
# ACCIÓN del gui, no la tool entera (el flag por-tool era demasiado conservador:
# marcaba gui.screenshot, que es inofensivo).
_PHYSICAL_GUI_ACTIONS = {"type", "type_into", "click", "double_click",
                         "right_click", "click_button", "keypress", "hotkey",
                         "scroll", "drag"}

DEFAULT_MISSIONS = [
    "andá a la página de Instant Gaming",
    "andá a instant gaming y buscá resident evil requiem",
    "entrá a youtube",
]


def run_mission(agent, mission: str) -> dict:
    print(f"\n{'='*64}\n>> USUARIO: {mission!r}\n{'='*64}", flush=True)
    try:
        reply = agent.run_content(mission)
    except Exception as e:
        print(f"  EXCEPCIÓN: {type(e).__name__}: {e}", flush=True)
        return {"mission": mission, "error": f"{type(e).__name__}: {e}"}
    events = getattr(reply, "tool_events", None) or []
    tools_used = []
    physical = False
    for ev in events:
        name = getattr(ev, "name", None) or (ev.get("tool") if isinstance(ev, dict) else None)
        args = getattr(ev, "args", None) or (ev.get("args") if isinstance(ev, dict) else {}) or {}
        action = str(args.get("action") or "").casefold()
        tools_used.append(f"{name}.{action}" if name == "gui" and action else name)
        if name == "gui" and action in _PHYSICAL_GUI_ACTIONS:
            physical = True
    content = getattr(reply, "content", "") or ""
    print(f"  GEMMA: {content[:200]}", flush=True)
    print(f"  tools usadas: {tools_used}", flush=True)
    if physical:
        print("  ⚠️ usó GUI físico (SendInput) — este paso roba foco, no medible "
              "por Claude; lo corre el usuario.", flush=True)
    return {"mission": mission, "reply": content[:300], "tools": tools_used,
            "used_physical_gui": physical}


def main() -> int:
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=5)
    except Exception as e:
        print(f"server DOWN :8080 -> {type(e).__name__}", flush=True)
        return 2

    cfg = AgentConfig.from_env()
    agent = Gemma4Agent(cfg)
    missions = sys.argv[1:] or DEFAULT_MISSIONS
    results = [run_mission(agent, m) for m in missions]
    out = ROOT / "scripts" / "gui_eval" / "_web_execution_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWROTE {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
