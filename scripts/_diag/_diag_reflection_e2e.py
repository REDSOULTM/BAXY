"""E2E EN VIVO (regla 3.5) de la reflexión: seed eventos ambiente en un DB TEMPORAL
(NO toca el del usuario) → maybe_refresh_async (background, 4B real) → bloque inyectado
→ inspect → forget. Verifica TODA la cadena del feature, no piezas aisladas."""
from __future__ import annotations
import os, sys, time, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_TASTE_LLM_REFLECTION"] = "1"
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
sp = get_active_profile(); apply_profile_to_env(sp)
mgr = get_shared_manager(); print("[boot]...", flush=True)
mgr.start(sp, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llm_client import LLMClient
from gemma4_agent.memory_pkg.behavior_log import BehaviorLog
from gemma4_agent.memory_pkg import taste_reflection as TR
from gemma4_agent.memory_pkg.taste_profile import build_profile, profile_text, inspect_text, forget

tmp = tempfile.mkdtemp()
log = BehaviorLog(user="e2e_test", dir_path=Path(tmp))  # DB temporal, NO el del usuario
client = LLMClient(AgentConfig.from_env())

# seed: simula uso ambiente. record() hace INSERT OR IGNORE por (ts_ms,key), así que
# eventos IDÉNTICOS en loop tight se dedupean -> usamos keys DISTINTAS (canciones
# distintas del mismo artista; dwell con ts variado) para contar plays reales.
import time as _t
def _rec(kind, key, slot, dwell=None):
    ctx = {"source": "ambient", "slot": slot}
    if dwell is not None:
        ctx["dwell_s"] = dwell
    log.record(kind, key, ctx)
    _t.sleep(0.002)  # separa los ts_ms para que no se dedupeen
SONGS_SS = ["De Música Ligera", "Persiana Americana", "En la Ciudad de la Furia",
            "Cuando Pase el Temblor", "Trátame Suavemente", "Prófugos", "Nada Personal"]
SONGS_GC = ["Crimen", "Adiós", "Puente", "Cosas Imposibles", "Lago en el Cielo"]
for i in range(20):
    _rec("app_focus", f"code.exe", "mañana", 2400 + i)
for i in range(12):
    _rec("app_focus", f"spotify.exe", "noche", 1800 + i)
for i, s in enumerate(SONGS_SS * 2):  # 14 plays Soda Stereo
    _rec("media_play", f"Soda Stereo — {s} #{i}", "noche")
for i, s in enumerate(SONGS_GC):      # 5 plays Gustavo Cerati
    _rec("media_play", f"Gustavo Cerati — {s}", "noche")

prof = build_profile(log)
print("\n=== 1. PERFIL DETERMINISTA (base) ===")
print(profile_text(prof) or "(vacío)")
print(f"  top_artists={prof.top_artists}")

print("\n=== 2a. refresh SÍNCRONO (aísla reflect del threading) ===")
sync_ins = TR.refresh(log, client)
print(f"  insights: {len(sync_ins)}")
for i in sync_ins:
    print(f"    - {i.text}  [ev: {i.evidence}]")

print("\n=== 2b. maybe_refresh_async (background, 4B real) ===")
TR.forget_reflection(log)  # limpiar para forzar el refresh async
TR.maybe_refresh_async(log, client)
for _ in range(60):
    if TR.cached_insights(log):
        break
    time.sleep(1)
ins = TR.cached_insights(log)
print(f"  insights cacheados (async): {len(ins)}")

print("\n=== 3. BLOQUE inyectado al prompt (lo que ve Gemma4) ===")
print("  base:", repr(profile_text(prof)[:90]))
print("  +refl:", repr(TR.reflection_block(log)))

print("\n=== 4. INSPECT ('¿qué sabés de mí?') ===")
msg = inspect_text(log)
_ins = TR.cached_insights(log)
if _ins:
    msg += "\nY algo que fui infiriendo: " + " ".join(i.text for i in _ins)
print("  " + msg.replace("\n", "\n  "))

print("\n=== 5. FORGET (privacidad: borra perfil + insights) ===")
n = forget(log)
TR.forget_reflection(log)
print(f"  borró {n} observaciones; insights tras forget: {TR.cached_insights(log)}; "
      f"perfil vacío: {build_profile(log).is_empty()}")
