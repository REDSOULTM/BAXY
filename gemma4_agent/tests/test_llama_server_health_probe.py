"""Tests del health-probe robusto del LlamaServerManager (investigacion 6).

Antes: _wait_for_health solo poll-eaba /health -> /health miente bajo carga
(llama.cpp #20684 #20921) -> el cliente reintentaba antes de que el slot
estuviese listo y recibia "Failed to read connection" del proxy.

Ahora: 2 muestras consecutivas de /health 200 + /slots vivo (200 o 503) =
listo. Mas el restart() toma _restart_lock y espera puerto libre.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ..infra.config import AgentConfig
from ..infra.llama_server import LlamaServerManager


class TestProbeSlotsAlive(unittest.TestCase):

    def setUp(self):
        self.mgr = LlamaServerManager(AgentConfig.from_env())

    def test_200_is_alive(self):
        fake = MagicMock()
        fake.status = 200
        fake.__enter__ = lambda s: s
        fake.__exit__ = lambda *a: None
        with patch("urllib.request.urlopen", return_value=fake):
            self.assertTrue(self.mgr._probe_slots_alive(timeout_s=0.5))

    def test_503_no_slot_free_is_alive(self):
        """fail_on_no_slot=1 -> 503 cuando no hay slot LIBRE. El server vive,
        el endpoint responde — el slot lo toma nuestro chat despues."""
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x/slots", code=503,
            msg="No slot", hdrs=None,
            fp=__import__("io").BytesIO(b"no slot free"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            self.assertTrue(self.mgr._probe_slots_alive(timeout_s=0.5))

    def test_connection_refused_is_dead(self):
        import urllib.error
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("refused")):
            self.assertFalse(self.mgr._probe_slots_alive(timeout_s=0.5))

    def test_timeout_is_dead(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError()):
            self.assertFalse(self.mgr._probe_slots_alive(timeout_s=0.5))

    def test_400_is_alive(self):
        """Build b9090 responde 400 a /slots porque no soporta query params.
        El probe debe declararlo VIVO igual — el server responde, no esta
        caido. Sin este fix el boot quedaba colgado indefinido (regression
        2026-05-28: logs llenos de 'GET /slots 400')."""
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x/slots", code=400,
            msg="Bad Request", hdrs=None,
            fp=__import__("io").BytesIO(b"bad request"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            self.assertTrue(self.mgr._probe_slots_alive(timeout_s=0.5))

    def test_500_is_dead(self):
        """500 generico = server crasheando. NO declarar vivo."""
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x/slots", code=500,
            msg="Internal Server Error", hdrs=None,
            fp=__import__("io").BytesIO(b"crashed"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            self.assertFalse(self.mgr._probe_slots_alive(timeout_s=0.5))


class TestWaitForHealthDualProbe(unittest.TestCase):
    """/health 200 sostenido (2 muestras) + /slots vivo = listo."""

    def setUp(self):
        self.mgr = LlamaServerManager(AgentConfig.from_env())

    def test_one_health_ok_is_not_enough(self):
        """Solo 1 muestra de /health 200 NO debe declarar healthy: hay que
        confirmar con una segunda muestra Y /slots vivo."""
        # health: [True (1 sample), False, False, ...] -> nunca llega a 2 consecutivas
        health_calls = iter([True, False, False, False, False])
        with patch.object(self.mgr, "_probe_slots_alive", return_value=True), \
             patch("gemma4_agent.llm_client.LLMClient.health",
                   side_effect=lambda timeout_s=1.0: next(health_calls, False)), \
             patch("time.sleep"):
            # timeout_s=2 -> hasta ~4 iteraciones
            self.assertFalse(self.mgr._wait_for_health(timeout_s=2))

    def test_two_health_streak_with_slots_alive(self):
        with patch.object(self.mgr, "_probe_slots_alive", return_value=True), \
             patch("gemma4_agent.llm_client.LLMClient.health", return_value=True), \
             patch("time.sleep"):
            self.assertTrue(self.mgr._wait_for_health(timeout_s=10))

    def test_health_ok_but_slots_dead_keeps_waiting(self):
        """/health miente (#20684): aunque retorne 200 sostenido, si /slots
        no vive todavia NO declaramos healthy."""
        with patch.object(self.mgr, "_probe_slots_alive", return_value=False), \
             patch("gemma4_agent.llm_client.LLMClient.health", return_value=True), \
             patch("time.sleep"):
            self.assertFalse(self.mgr._wait_for_health(timeout_s=2))

    def test_proc_dead_short_circuits(self):
        """Si el proceso del server murio antes del timeout, devolver False ya."""
        fake_proc = MagicMock()
        fake_proc.poll.return_value = 1  # exit code != None -> muerto
        self.mgr._proc = fake_proc
        # No deberia llamar a health en absoluto
        with patch("gemma4_agent.llm_client.LLMClient.health") as mock_h, \
             patch("time.sleep"):
            self.assertFalse(self.mgr._wait_for_health(timeout_s=10))
            mock_h.assert_not_called()


class TestRestartIsSimple(unittest.TestCase):
    """restart() = stop() + start(). Sin lock, sin port-wait, sin kill por puerto.

    v21 2026-05-28: la sesion previa habia agregado lock + port_in_use loop
    hasta 10s + _kill_server_on_port. Esto sumaba ~11s de pausa cierta antes
    de cada restart. Revertido al diseño del 27-may (commit 7b2377d) que
    apenas hace stop->start: el restart promedio queda en ~3-5s, percibible
    pero NO disruptivo. El user reporto que ese diseño "no se notaba"."""

    def test_restart_calls_stop_then_start(self):
        mgr = LlamaServerManager(AgentConfig.from_env())
        profile = MagicMock()
        profile.server_running = True
        with patch.object(mgr, "stop") as mock_stop, \
             patch.object(mgr, "start", return_value="started") as mock_start:
            result = mgr.restart(profile, wait_health=False)
            self.assertEqual(result, "started")
            mock_stop.assert_called_once()
            mock_start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
