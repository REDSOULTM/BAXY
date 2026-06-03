"""Estabilidad de ciclo de vida del llama-server. Tres edges donde viven
los bugs (recovery/teardown):

  H6 — race en :8080: restart() ahora toma _restart_lock + espera el puerto.
  H4 — /health miente: el recovery del cliente exige /health AND /slots.
  C7 — orphan VRAM: TODA instancia de LlamaServerManager registra su stop() en
       atexit (no solo el singleton), cubriendo las 4 rutas de instanciación
       directa (chat/ui x2/server) que dejaban el child huérfano.

Tests sin lanzar el server real (eso es la verificación en vivo). Mockeamos
stop/start/health/slots para verificar el CONTRATO de cada fix.
"""
from __future__ import annotations

import threading
import unittest
from unittest import mock

from gemma4_agent.infra import llama_server as LS
from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llm_client import LLMClient


def _mgr():
    return LS.LlamaServerManager(config=AgentConfig.from_env())


class H6RestartRaceTest(unittest.TestCase):
    """restart() serializa con _restart_lock y espera el puerto (anti-race)."""

    def test_restart_holds_restart_lock(self):
        mgr = _mgr()
        # Si restart() toma el lock, mientras corre el lock está adquirido.
        observed_locked = {"v": False}

        def fake_stop():
            # Durante stop() (dentro de restart), el lock debe estar tomado:
            # un acquire no-bloqueante debe FALLAR.
            observed_locked["v"] = not mgr._restart_lock.acquire(blocking=False)
            if not observed_locked["v"]:
                mgr._restart_lock.release()

        prof = mock.MagicMock()
        prof.server_running = True
        with mock.patch.object(mgr, "stop", side_effect=fake_stop), \
             mock.patch.object(mgr, "start", return_value="started"), \
             mock.patch("gemma4_agent.infra.llama_server.port_in_use", return_value=False):
            r = mgr.restart(prof)
        self.assertEqual(r, "started")
        self.assertTrue(observed_locked["v"], "restart() no tomó _restart_lock")

    def test_restart_waits_for_port_release(self):
        mgr = _mgr()
        prof = mock.MagicMock(); prof.server_running = True
        # Puerto ocupado 2 muestras y luego libre -> el loop debe esperar y salir.
        seq = iter([True, True, False, False])
        with mock.patch.object(mgr, "stop"), \
             mock.patch.object(mgr, "start", return_value="started") as start, \
             mock.patch("gemma4_agent.infra.llama_server.port_in_use",
                        side_effect=lambda *a, **k: next(seq, False)), \
             mock.patch("gemma4_agent.infra.llama_server.time.sleep"):
            mgr.restart(prof)
        start.assert_called_once()

    def test_concurrent_restarts_serialized(self):
        # Dos restart() concurrentes nunca corren stop/start entrelazados.
        mgr = _mgr()
        prof = mock.MagicMock(); prof.server_running = True
        inside = {"count": 0, "max": 0}
        lk = threading.Lock()

        def fake_start(*a, **k):
            with lk:
                inside["count"] += 1
                inside["max"] = max(inside["max"], inside["count"])
            try:
                return "started"
            finally:
                with lk:
                    inside["count"] -= 1

        with mock.patch.object(mgr, "stop"), \
             mock.patch.object(mgr, "start", side_effect=fake_start), \
             mock.patch("gemma4_agent.infra.llama_server.port_in_use", return_value=False):
            ts = [threading.Thread(target=mgr.restart, args=(prof,)) for _ in range(4)]
            for t in ts: t.start()
            for t in ts: t.join()
        self.assertEqual(inside["max"], 1, "restart() no serializó (race en start)")


class H4RecoverySlotsTest(unittest.TestCase):
    """El recovery del cliente exige /health AND /slots (no solo /health)."""

    def test_probe_slots_alive_exists(self):
        c = LLMClient(AgentConfig.from_env())
        self.assertTrue(hasattr(c, "_probe_slots_alive"))

    def test_slots_alive_status_logic(self):
        c = LLMClient(AgentConfig.from_env())
        # 200/400/404/503 = vivo; 500 = muerto. Mockeamos urlopen por código.
        import urllib.error
        for code, alive in [(200, True), (400, True), (404, True), (503, True), (500, False)]:
            if code < 400:
                ctx = mock.MagicMock()
                ctx.__enter__.return_value.status = code
                with mock.patch("urllib.request.urlopen", return_value=ctx):
                    self.assertEqual(c._probe_slots_alive(), alive, code)
            else:
                err = urllib.error.HTTPError("u", code, "m", {}, None)
                with mock.patch("urllib.request.urlopen", side_effect=err):
                    self.assertEqual(c._probe_slots_alive(), alive, code)

    def test_slots_dead_on_connection_refused(self):
        c = LLMClient(AgentConfig.from_env())
        import urllib.error
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("refused")):
            self.assertFalse(c._probe_slots_alive())


class C7OrphanAtexitTest(unittest.TestCase):
    """Toda instancia registra su stop() en atexit (cubre rutas directas)."""

    def test_every_instance_registers_atexit(self):
        with mock.patch("atexit.register") as reg:
            mgr = _mgr()
        self.assertTrue(getattr(mgr, "_atexit_registered", False))
        # se registró un handler ligado a ESTA instancia
        bound = [c for c in reg.call_args_list
                 if getattr(c[0][0], "__self__", None) is mgr]
        self.assertTrue(bound, "la instancia no registró su atexit")

    def test_atexit_stop_self_is_noop_safe(self):
        # _atexit_stop_self nunca lanza, aunque stop() falle.
        mgr = _mgr()
        with mock.patch.object(mgr, "stop", side_effect=RuntimeError("boom")):
            mgr._atexit_stop_self()  # no debe propagar

    def test_atexit_register_idempotent_per_instance(self):
        mgr = _mgr()
        with mock.patch("atexit.register") as reg:
            mgr._register_atexit_cleanup()  # ya registrado en __init__
            self.assertEqual(reg.call_count, 0, "re-registró el atexit")


if __name__ == "__main__":
    unittest.main()
