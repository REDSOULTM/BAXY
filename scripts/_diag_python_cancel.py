"""Diag del mis-route destapado en vivo: preguntas conceptuales donde el 4B elige
`web` -> el chaining-nudge (de recurso-local) lo descarrilaba ("no hay acción" /
"listo cancelo"). Tras el fix (nudge web ofrece 'sintetizá y respondé'), debería
RESPONDER. Detector caza cancelaciones Y meta-frases. Solo preguntas (sin efectos)."""
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.pop("GEMMA4_STREAM_TTS", None)  # prod default
# Forzar modo NORMAL (default de prod). El archivo persistido tiene 'movilidad' (de
# un test viejo) y contaminaba: el a11y-continue-nudge solo se dispara en a11y. Esto
# NO escribe el archivo del usuario, solo manda en runtime (get_active_mode: env > archivo).
os.environ["GEMMA4_ACCESSIBILITY_MODE"] = os.environ.get("GEMMA4_ACCESSIBILITY_MODE", "normal")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
agent.run_content("hola")  # warm

# Frases tipo "explicame/contame" que tienden a rutear a web.
CMDS = [
    "explicame brevemente qué es Python",
    "contame qué es el machine learning",
    "explicame qué es una API REST",
    "buscá información sobre el lenguaje Rust y explicámelo",
    "explicame qué es Docker",
    "qué es la fotosíntesis",
]
# Meta-frases / cancelaciones = descarrilamiento (el reply NO responde la pregunta).
_DERAIL = re.compile(
    r"no hay\s+(ninguna\s+)?(acci[óo]n|tarea|pendiente)|no tengo\s+(ninguna\s+)?"
    r"(acci[óo]n|tarea|pendiente)|cancel|no se (solicit|ha solicit)|acci[óo]n pendiente",
    re.I)

print("=" * 92)
derail = 0
web_used = 0
for c in CMDS:
    try:
        agent.history.clear()
    except Exception:
        pass
    r = agent.run_content(c)
    evs = getattr(r, "tool_events", []) or []
    tools = [getattr(e, "name", "?") for e in evs]
    reply = (getattr(r, "content", "") or "")
    used_web = any(str(t).lower() in ("web", "browser", "browser_real") for t in tools)
    if used_web:
        web_used += 1
    bad = bool(_DERAIL.search(reply)) or len(reply.strip()) < 12
    if bad:
        derail += 1
    print(f"[{'DERAIL' if bad else 'OK    '}] web={used_web} {c!r}\n     tools={tools} reply={reply[:105]!r}")
print("=" * 92)
print(f"[VEREDICTO] descarrilados: {derail}/{len(CMDS)} | usaron web: {web_used}/{len(CMDS)}")
print("  (baseline previo al fix: 3/3 de las que usaron web descarrilaban)")
