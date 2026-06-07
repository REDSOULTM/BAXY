"""Arranca SOLO el llama-server (perfil vram4), sin la UI de escritorio.
Usa el manager (no el launcher) para no disparar GUI ni input físico.
Para los evals de planificación/ejecución-por-CDP que corre Claude.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Router mode ON (lazy-vision, el path de prod) y perfil vram4.
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
# DIAG: que el observador de ambiente NO grabe en la DB real del usuario durante
# las pruebas (auditoría 2026-06-07: las apps/media de test contaminaban el perfil).
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
print(f"[boot] perfil={prof.name} model={Path(prof.model_path).name if prof.model_path else None}", flush=True)

mgr = get_shared_manager()
print("[boot] arrancando llama-server (puede tardar ~10-60s)...", flush=True)
t0 = time.time()
status = mgr.start(prof, wait_health=True, timeout_s=120)
dt = time.time() - t0
print(f"[boot] start status={status!r} en {dt:.1f}s | router_mode={mgr.is_router_mode()}", flush=True)

# Confirmar health por HTTP
import urllib.request, json
try:
    r = urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=8)
    ids = [m.get("id") for m in json.loads(r.read()).get("data", [])]
    print(f"[boot] HEALTH OK :8080 models={ids[:6]}", flush=True)
except Exception as e:
    print(f"[boot] HEALTH FAIL: {type(e).__name__}: {e}", flush=True)
    sys.exit(1)

# Mantener vivo el proceso (el server es hijo; si este script sale, atexit lo
# puede matar). Dormimos para que el server quede disponible a otros procesos.
print("[boot] server LISTO. Manteniendo vivo (Ctrl+C o kill para parar).", flush=True)
try:
    while True:
        time.sleep(30)
except KeyboardInterrupt:
    print("[boot] saliendo.", flush=True)
