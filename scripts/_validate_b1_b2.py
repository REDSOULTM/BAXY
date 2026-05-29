"""Validación EN VIVO de B1 (error-type recovery) y B2 (memory-guided tool-picking).
Modo normal. DB de experiencias TEMPORAL (no contamina la del usuario). B1 mockea
un tool para que falle controlado (sin tocar recursos reales)."""
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

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

from gemma4_agent.agent_core.agent import Gemma4Agent, _recalled_success_tools
from gemma4_agent.memory_pkg.experience import ExperienceMemory
from gemma4_agent.routing.semantic_router import embed as _embed

agent = Gemma4Agent()
agent.run_content("hola")

# Captura de trace
captured = []
_orig_event = agent.trace.event
def _cap(turn_id, evname=None, **kw):
    captured.append((evname, kw))
    return _orig_event(turn_id, evname, **kw)
agent.trace.event = _cap

# ===================== B2 =====================
print("\n===== B2: memory-guided tool-picking =====")
tmp = Path(tempfile.gettempdir()) / "_b2_validate_exp.sqlite"
try:
    tmp.unlink()
except OSError:
    pass
exp = ExperienceMemory(path=tmp)
rec = exp.record(turn_id="t1", user_input="reproducí música de los Beatles en Spotify",
                 tools_used=["media", "app"], outcome="reproduje la lista",
                 mission_status="PASS", summary="música ok",
                 embed_fn=_embed, outcome_code="PASS_VERIFIED")
print(f"  record en DB temp: ok={rec.get('ok')}")
# 1) recall REAL (embed real) + función con datos REALES (lo que el unit-test mockeado no cubre)
recalls = exp.recall("ponéme algo de los Beatles", embed_fn=_embed, k=3, max_distance=0.9)
print(f"  recall real trajo {len(recalls)} registro(s)")
extracted = _recalled_success_tools(recalls, [])
print(f"  _recalled_success_tools(recalls REALES) -> {extracted}")
b2_mechanism = "media" in extracted
# 2) no-rotura: un turno con el flag ON no se rompe
agent.experience = exp
os.environ["GEMMA4_MEMORY_TOOLS"] = "1"
captured.clear()
agent.history.clear()
r = agent.run_content("ponéme algo de los Beatles")
added = [kw.get("tools") for (n, kw) in captured if n == "memory_tools_added"]
reply2 = (getattr(r, "content", "") or "")
tools2 = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
print(f"  turno MEMORY_TOOLS=1: memory_tools_added={added} tools={tools2}")
print(f"  reply coherente (no roto): {len(reply2.strip()) > 3} -> {reply2[:70]!r}")
os.environ.pop("GEMMA4_MEMORY_TOOLS", None)

# ===================== B1 =====================
print("\n===== B1: error-type recovery =====")
os.environ["GEMMA4_ERROR_RECOVERY"] = "1"
# Detectar el handler del tool 'web' para mockearlo a un fallo needs_dependency
web_handler = next((c for c in ("web", "web_search", "t_web")
                    if hasattr(agent.tools, c) and callable(getattr(agent.tools, c))), None)
print(f"  handler web detectado: {web_handler!r}")

def _fail(*a, **k):
    return {"ok": False, "status": "needs_dependency",
            "error": "falta una dependencia previa", "action": "search"}

if web_handler:
    captured.clear()
    agent.history.clear()
    with mock.patch.object(agent.tools, web_handler, side_effect=_fail):
        r = agent.run_content("buscá las noticias de hoy")
    hints = [kw for (n, kw) in captured if n == "error_recovery_hint"]
    generic = [kw for (n, kw) in captured if n == "unverified_intermediate_warning"]
    reply1 = (getattr(r, "content", "") or "")
    print(f"  error_recovery_hint disparó: {bool(hints)} types={[h.get('types') for h in hints]}")
    print(f"  (nudge genérico en su lugar: {bool(generic)})")
    print(f"  reply HONESTO (no afirma éxito falso): {reply1[:90]!r}")
    b1_fired = bool(hints)
else:
    b1_fired = None
    print("  no se pudo mockear el handler web -> B1 path-de-fallo no provocado en vivo")
os.environ.pop("GEMMA4_ERROR_RECOVERY", None)
try:
    tmp.unlink()
except OSError:
    pass

print("\n===== VEREDICTO =====")
print(f"  B2 mecanismo (recall real -> tools): {'OK' if b2_mechanism else 'REVISAR'}")
print(f"  B1 clasificación+directiva en vivo:  {'OK' if b1_fired else ('NO PROVOCADO' if b1_fired is None else 'NO DISPARÓ')}")
