"""GATE — vida diaria de un usuario SIN MANOS (todo por voz). Mide si el agente
RESUELVE tareas cotidianas: ¿llama la tool correcta y actúa, o falla/charla?

SEGURO: inyecta el mensaje como TEXTO (agent.run_content = como la UI, NO
SendInput). Marca si un paso usó gui FÍSICO (type/click/keypress... = roba foco,
no medible por Claude). La mayoría de estas tareas NO usan gui físico (reminder/
notes/email/audio/calendar/accessibility son tools de datos/SO).

Por misión: (texto, tool(s) esperada(s)). Acierto = se usó alguna esperada Y NO
cayó en charla vacía.

Uso:  python scripts/gui_eval/measure_daily_life.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_ACCESSIBILITY_MODE", "movilidad")

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.agent_core.agent import Gemma4Agent

_PHYSICAL_GUI_ACTIONS = {"type", "type_into", "click", "double_click",
                         "right_click", "click_button", "keypress", "hotkey",
                         "scroll", "drag"}

# (texto del usuario, tools aceptables). Tareas reales de vida diaria sin manos.
MISSIONS = [
    ("recordame tomar la pastilla a las tres de la tarde", {"reminder", "notification", "local_calendar"}),
    ("ponme un temporizador de diez minutos", {"notification"}),
    ("anota que tengo que llamar al medico manana", {"notes_tasks", "reminder"}),
    ("agenda una reunion el viernes a las cinco", {"local_calendar"}),
    ("subi el volumen", {"audio"}),
    ("guarda el numero de juan: 351 555 1234", {"contacts"}),
    ("que hora es", set()),   # puede responder en prosa (sin tool) -> OK si no charla vacía
    ("que tengo agendado para hoy", {"local_calendar", "reminder", "notes_tasks"}),
    ("escribi un correo a ana diciendo que llego tarde", {"email"}),
    ("activa el narrador de windows", {"accessibility"}),
    ("lee lo que hay en la pantalla", {"vision"}),
    ("conectate a la red wifi de casa", {"device_settings"}),
    ("pon musica", {"media", "browser", "app"}),
    ("apaga la computadora en una hora", {"system", "notification", "job_manager"}),
]


def run(agent, text, accepted):
    try:
        reply = agent.run_content(text)
    except Exception as e:
        return {"text": text, "error": f"{type(e).__name__}: {e}", "ok": False}
    events = getattr(reply, "tool_events", None) or []
    tools, physical = [], False
    for ev in events:
        name = getattr(ev, "name", None) or (ev.get("tool") if isinstance(ev, dict) else None)
        args = getattr(ev, "args", None) or {}
        action = str(args.get("action") or "").casefold()
        tools.append(name)
        if name == "gui" and action in _PHYSICAL_GUI_ACTIONS:
            physical = True
    content = (getattr(reply, "content", "") or "").strip()
    used_ok = bool(accepted & set(tools))
    # si no se espera tool (ej "qué hora es"), acierto = respondió algo sustantivo
    no_tool_ok = (not accepted) and len(content) >= 8
    ok = used_ok or no_tool_ok
    return {"text": text, "tools": tools, "expected": sorted(accepted),
            "reply": content[:120], "ok": ok, "physical_gui": physical}


def main() -> int:
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=5)
    except Exception as e:
        print(f"server DOWN :8080 -> {type(e).__name__}", flush=True)
        return 2
    agent = Gemma4Agent(AgentConfig.from_env())
    results = []
    for text, accepted in MISSIONS:
        r = run(agent, text, accepted)
        results.append(r)
        tag = "OK  " if r.get("ok") else "FAIL"
        phys = " [GUI-FÍSICO]" if r.get("physical_gui") else ""
        print(f"  {tag} {text[:46]!r}{phys}\n        tools={r.get('tools')} esp={r.get('expected')}\n"
              f"        reply={r.get('reply')!r}", flush=True)
    n = sum(1 for r in results if r.get("ok"))
    nphys = sum(1 for r in results if r.get("physical_gui"))
    out = ROOT / "scripts" / "gui_eval" / "_daily_life_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n>> RESUELTAS: {n}/{len(MISSIONS)} = {n/len(MISSIONS)*100:.0f}% | "
          f"usaron gui físico: {nphys}", flush=True)
    print("WROTE", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
