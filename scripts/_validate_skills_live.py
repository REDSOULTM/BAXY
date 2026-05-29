"""¿El 4B emite skill_load cuando el pedido matchea una skill del menú? (medido:
0/6727 en prod). Confirmar con pedidos DIRECTOS que matchean skills concretas. Si
no lo usa ni así -> el fix es trigger-inject semántico (como microagents)."""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_ACCESSIBILITY_MODE"] = "normal"
os.environ.pop("GEMMA4_STREAM_TTS", None)

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
agent.run_content("hola")

# Pedidos que matchean skills reales del menú (research-and-summarize, install-steam-game,
# safe-file-cleanup, screenshot-and-analyze, debug-app-crash, schedule-recurring-task).
CMDS = [
    "investigá en internet qué es el lenguaje Rust y armame un resumen con fuentes",
    "quiero instalar un juego de Steam, guíame en el proceso completo",
    "hacé una limpieza segura de archivos viejos en mi carpeta de Descargas",
    "sacá una captura de pantalla y analizá qué hay en ella",
    "una app me crashea, ayudame a diagnosticar por qué",
]
print("=" * 92)
used_skill = 0
for c in CMDS:
    try:
        agent.history.clear()
    except Exception:
        pass
    r = agent.run_content(c)
    tools = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
    reply = (getattr(r, "content", "") or "")
    sl = "skill_load" in tools
    if sl:
        used_skill += 1
    print(f"[{'SKILL_LOAD' if sl else 'NO-SKILL'}] {c[:55]!r}")
    print(f"     tools={tools}")
    print(f"     reply={reply[:95]!r}")
    print("-" * 92)
print("=" * 92)
print(f"[VEREDICTO] el 4B emitió skill_load en {used_skill}/{len(CMDS)} pedidos que matchean skills")
print("  (si 0 -> confirmado: skill_load inerte incluso con pedido directo -> trigger-inject)")
