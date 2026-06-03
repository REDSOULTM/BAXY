# -*- coding: utf-8 -*-
"""Validación EN VIVO del ready-gate (2026-06-02): arranca el boot REAL del
agente (server + agent + router) y verifica que en el INSTANTE en que ready
pasa a True, el router YA está listo (is_router_ready()==True). Antes de la fix,
ready podía volverse True con el router todavía cargando.

Seguro: NO usa SendInput. Solo bootea el runner y observa los latches.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.infra.events_bus import BUS  # noqa: E402
from gemma4_agent.agent_core.agent_runner import RUNNER  # noqa: E402

# Capturar el momento exacto en que el BUS publica ready:True.
ready_event: dict = {"at": None, "router_ready_at_that_moment": None}
boot_t0 = time.time()


def _on_bus(ev):
    if isinstance(ev, dict) and ev.get("type") == "agent" and ev.get("ready") is True:
        if ready_event["at"] is None:
            ready_event["at"] = time.time() - boot_t0
            # EN ESE INSTANTE, ¿el router está listo?
            ready_event["router_ready_at_that_moment"] = RUNNER.is_router_ready()


BUS.add_listener(_on_bus)

print("=" * 64)
print("VALIDACIÓN EN VIVO — ready-gate del router (boot real)")
print("=" * 64)
print("arrancando RUNNER (boot completo: server + agent + router)...")
RUNNER.start()

# Esperar hasta que ready dispare o timeout 240s (boot frío puede tardar).
deadline = time.time() + 240
while ready_event["at"] is None and time.time() < deadline:
    time.sleep(0.5)

print("")
if ready_event["at"] is None:
    print("❌ TIMEOUT: ready nunca se publicó en 240s. Revisar boot.")
    sys.exit(1)

rr = ready_event["router_ready_at_that_moment"]
print(f"ready:True publicado a los {ready_event['at']:.1f}s del boot")
print(f"is_router_ready() EN ESE INSTANTE: {rr}")
print(f"is_router_ready() ahora:          {RUNNER.is_router_ready()}")
print(f"is_warmed_up() ahora:             {RUNNER.is_warmed_up()}")
print("")
if rr is True:
    print("✅ PASA: cuando la casilla se desbloquea, el router YA está listo.")
    print("   (el gate ready ahora espera al router — fix verificada en vivo)")
else:
    print("🔴 FALLA: ready se publicó con el router AÚN cargando (rr=%r)." % rr)
    print("   La fix no está funcionando — el gate no esperó al router.")
    sys.exit(2)
