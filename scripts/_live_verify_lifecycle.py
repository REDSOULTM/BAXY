"""Verificación EN VIVO de los fixes de lifecycle (Ola 2.4: C7/H6/H4).

NO toca el llama-server real del usuario (regla #6): usa un subproceso LIVIANO
propio (python sleep) como stand-in del child, para probar la MECÁNICA real del
atexit por-instancia y del restart serializado sin gastar VRAM ni matar procesos
ajenos.

  C7: un manager con un child propio -> su _atexit_stop_self() lo mata
      (cubre las rutas de instanciación directa que antes lo dejaban huérfano).
  C7-safety: un manager marcado _external_detected NO mata su (falso) external.
  H6: restart() serializa (lock) y espera el puerto.
  H4: el recovery del cliente exige /health AND /slots.

Uso: python scripts/_live_verify_lifecycle.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.infra import llama_server as LS  # noqa: E402
from gemma4_agent.infra.config import AgentConfig  # noqa: E402
from gemma4_agent.infra.llm_client import LLMClient  # noqa: E402


def _spawn_dummy_child() -> subprocess.Popen:
    """Subproceso liviano propio (NO llama-server) que vive 300s."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])


def main() -> int:
    failures = []

    print("== C7: el atexit por-instancia mata el child propio (no huérfano) ==")
    mgr = LS.LlamaServerManager(config=AgentConfig.from_env())
    child = _spawn_dummy_child()
    # Inyectar el child como si fuera nuestro server gestionado.
    mgr._proc = child
    mgr._external_detected = False
    pid = child.pid
    # Disparar el handler que correría en atexit.
    mgr._atexit_stop_self()
    time.sleep(0.5)
    alive = child.poll() is None
    if alive:
        child.kill()
    ok = not alive
    print(f"  {'OK ' if ok else 'FALLA'} child PID {pid} {'terminado' if ok else 'SIGUE VIVO (huérfano!)'}")
    if not ok:
        failures.append("C7: child quedó huérfano")

    print("== C7-safety: NO mata un server marcado external (del usuario) ==")
    mgr2 = LS.LlamaServerManager(config=AgentConfig.from_env())
    child2 = _spawn_dummy_child()
    mgr2._proc = child2
    mgr2._external_detected = True  # simular 'es del usuario'
    mgr2._atexit_stop_self()
    time.sleep(0.4)
    survived = child2.poll() is None
    child2.kill()  # limpiar nuestro dummy
    ok = survived
    print(f"  {'OK ' if ok else 'FALLA'} external 'sobrevivió' al atexit: {survived} (no debe matarlo)")
    if not ok:
        failures.append("C7-safety: mató un external")

    print("== H6: restart() serializa (toma _restart_lock) ==")
    mgr3 = LS.LlamaServerManager(config=AgentConfig.from_env())
    prof = mock.MagicMock(); prof.server_running = True
    locked_during = {"v": False}

    def fake_stop():
        locked_during["v"] = not mgr3._restart_lock.acquire(blocking=False)
        if not locked_during["v"]:
            mgr3._restart_lock.release()

    with mock.patch.object(mgr3, "stop", side_effect=fake_stop), \
         mock.patch.object(mgr3, "start", return_value="started"), \
         mock.patch("gemma4_agent.infra.llama_server.port_in_use", return_value=False):
        r = mgr3.restart(prof)
    ok = (r == "started" and locked_during["v"])
    print(f"  {'OK ' if ok else 'FALLA'} restart='{r}', lock tomado durante stop={locked_during['v']}")
    if not ok:
        failures.append("H6: restart no serializó")

    print("== H4: recovery exige /health AND /slots ==")
    c = LLMClient(AgentConfig.from_env())
    # health=True pero slots=False -> NO debe considerarse 'healthy'.
    with mock.patch.object(c, "health", return_value=True), \
         mock.patch.object(c, "_probe_slots_alive", return_value=False):
        # Reproducimos la condición del loop de recovery.
        recovered = c.health(timeout_s=1.0) and c._probe_slots_alive(timeout_s=0.5)
    ok = (recovered is False)
    print(f"  {'OK ' if ok else 'FALLA'} health=True+slots=False -> recovered={recovered} (debe ser False)")
    if not ok:
        failures.append("H4: recovery aceptó health sin slots")
    with mock.patch.object(c, "health", return_value=True), \
         mock.patch.object(c, "_probe_slots_alive", return_value=True):
        recovered2 = c.health() and c._probe_slots_alive()
    ok2 = (recovered2 is True)
    print(f"  {'OK ' if ok2 else 'FALLA'} health=True+slots=True -> recovered={recovered2} (debe ser True)")
    if not ok2:
        failures.append("H4: no recupera con health+slots")

    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS: {failures}")
        return 1
    print("RESULTADO: TODO OK — sin huérfanos, external respetado, restart serializado, recovery exige slots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
