"""Causa raíz: ¿de dónde sale 'No hay ninguna acción pendiente' tras un web-search
para una pregunta conceptual? Corre hasta descarrilar y vuelca la conversación
interna (history) + trace events para ver qué notes se inyectaron y qué pass lo generó."""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.pop("GEMMA4_STREAM_TTS", None)

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
agent.run_content("hola")

CMD = "explicame brevemente qué es Python"
reply = ""
for attempt in range(4):
    try:
        agent.history.clear()
    except Exception:
        pass
    r = agent.run_content(CMD)
    reply = (getattr(r, "content", "") or "")
    low = reply.lower()
    if "no hay" in low or "pendiente" in low or "cancel" in low or len(reply.strip()) < 12:
        print(f"*** DERAILED en intento {attempt}: {reply[:80]!r} ***")
        break
    print(f"intento {attempt}: OK -> {reply[:60]!r}")

print("\n===== HISTORY INTERNA DEL TURNO DESCARRILADO =====")
for i, m in enumerate(getattr(agent, "history", []) or []):
    role = m.get("role", "?")
    content = m.get("content")
    tc = m.get("tool_calls")
    if tc:
        names = [((c.get("function") or {}).get("name"), (c.get("function") or {}).get("arguments", "")[:60]) for c in tc]
        body = f"TOOL_CALLS={names}"
    else:
        body = repr(str(content or "")[:240])
    print(f"  [{i}] {role}: {body}")

print("\n===== TRACE EVENTS =====")
tr = getattr(agent, "trace", None)
evs = getattr(tr, "events", None) or getattr(tr, "_events", None) or []
for e in (evs[-25:] if isinstance(evs, list) else []):
    try:
        nm = e.get("event") if isinstance(e, dict) else getattr(e, "name", str(e))
        print(f"  - {nm}")
    except Exception:
        print(f"  - {e!r}"[:120])
