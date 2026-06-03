"""Verificación EN VIVO (regla 3.5) de la reflexión por LLM (gustos finos).
Mide el GATE del feature: ¿el 4B real produce insights GROUNDED y finos, y fluyen
caché→bloque→inspect? Server real :8080, perfil real (o sintético si está vacío)."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_TASTE_LLM_REFLECTION"] = "1"  # gate ON para la prueba

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof_srv = get_active_profile(); apply_profile_to_env(prof_srv)
mgr = get_shared_manager(); print("[boot]...", flush=True)
mgr.start(prof_srv, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.memory_pkg import taste_reflection as TR
from gemma4_agent.memory_pkg.taste_profile import build_profile, profile_text, TasteProfile

agent = Gemma4Agent()
behavior, client = agent.behavior, agent.client

real = build_profile(behavior)
print("\n=== PERFIL DETERMINISTA (real) ===")
print(profile_text(real) or "(vacío — sin datos ambiente aún)")

def show(insights, label):
    print(f"\n=== INSIGHTS LLM ({label}) ===")
    if not insights:
        print("  (ninguno pasó el grounding guard)")
    for i in insights:
        print(f"  - {i.text}\n      [evidencia citada: {i.evidence}]")

# 1) perfil real si tiene datos
if not real.is_empty():
    show(TR.reflect(real, client), "perfil REAL")
    print("\n  reflection_block:", repr(TR.reflection_block(behavior)))
else:
    print("\n(perfil real vacío -> uso uno SINTÉTICO para medir la calidad del 4B)")

# 2) perfil sintético (siempre, para demostrar la calidad + el guard)
synth = TasteProfile(total_observations=60)
synth.top_apps = [("code.exe", 12.0), ("spotify.exe", 8.0)]
synth.apps_by_slot = {"mañana": "code.exe", "noche": "spotify.exe"}
synth.top_artists = [("soda stereo", 15), ("gustavo cerati", 8)]
synth.music_slots = ["noche"]
show(TR.reflect(synth, client), "perfil SINTÉTICO (Soda Stereo/Code)")

# 3) grounding guard en acción: forzamos una respuesta con evidencia FABRICADA
class _Fab:
    def chat(self, m, **k):
        return {"choices": [{"message": {"content":
                '[{"insight":"le gusta el death metal","evidencia":"escucha death metal a toda hora"}]'}}]}
print("\n=== GUARD: respuesta con evidencia fabricada ===")
print("  resultado:", TR.reflect(synth, _Fab()), "(debe ser [] — descartado)")
