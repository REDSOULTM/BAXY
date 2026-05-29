"""Valida el trigger-inject de skills EN VIVO (GEMMA4_SKILLS_AUTOINJECT=1): ¿la skill
correcta se inyecta (trace skill_autoinjected) y el 4B SIGUE la receta? Compara con
el baseline conocido (sin autoinject: 'app crashea' -> 'no tengo herramienta')."""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_ACCESSIBILITY_MODE"] = "normal"
os.environ["GEMMA4_SKILLS_AUTOINJECT"] = "1"
os.environ.pop("GEMMA4_STREAM_TTS", None)

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
captured = []
_orig = agent.trace.event
def _cap(turn_id, evname=None, **kw):
    captured.append((evname, kw))
    return _orig(turn_id, evname, **kw)
agent.trace.event = _cap
agent.run_content("hola")

CASES = [
    ("debug-app-crash", "una app me crashea, ayudame a diagnosticar por qué falla"),
    ("research-and-summarize", "investigá en internet qué es el lenguaje Rust y resumime con fuentes"),
    ("safe-file-cleanup", "hacé una limpieza segura de archivos viejos en mi PC"),
    ("screenshot-and-analyze", "sacá una captura de pantalla y analizá qué hay en ella"),
]
print("=" * 94)
inj_ok = 0
for expected, cmd in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    captured.clear()
    r = agent.run_content(cmd)
    injected = [kw.get("skill") for (n, kw) in captured if n == "skill_autoinjected"]
    reply = (getattr(r, "content", "") or "")
    tools = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
    hit = expected in injected
    if hit:
        inj_ok += 1
    print(f"[{'INYECTA ' + expected if hit else 'NO-INYECTA (' + str(injected) + ')'}] {cmd[:50]!r}")
    print(f"     tools={tools} | reply={reply[:120]!r}")
    print("-" * 94)
print("=" * 94)
print(f"[VEREDICTO] skill correcta inyectada en {inj_ok}/{len(CASES)} | "
      f"(sin autoinject el 4B usaba 0/5 skill_load)")
