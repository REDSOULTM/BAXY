"""Cobertura dedicada para domain_tools/smart_home.py (added 2026-06-01).

smart_home.py NO tenía test propio (solo el smoke {action:status}). Controla
Home Assistant local via REST + MQTT. El contrato CRÍTICO es la HONESTIDAD del
campo `verified` (ley #2/#3 de CLAUDE.md): un HTTP 200 NO prueba que el device
cambió de estado, así que el código vuelve a leer el estado real y reporta
verified True/False/None según lo MEDIDO, sin inventar éxito.

Todo el I/O de red (_hass_alive, _hass_request) se mockea — cero red real.

Propiedades afirmadas contra el código fuente:
  - _hass_alive distingue HTTPError(401/403/404=vivo) de URLError/timeout=caído
    (T3-smart_home-alive-always-true-031, regresión documentada en el código)
  - sin HA alcanzable -> needs_user, NUNCA verified=True
  - sin token -> needs_user_auth (no se manda nada a la red)
  - set_state: HTTP ok pero estado real != pedido -> verified=False (no miente)
  - set_state: GET de confirmación falla -> verified=None (honesto, no éxito)
  - call_service turn_on confirmado por GET -> verified=True; estado distinto -> False
  - call_service de servicio no medible (scene) -> verified=None
  - checkpoint con rollback solo cuando hay estado previo medido
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ..domain_tools import smart_home
from ..memory_pkg.state import AgentState


class _FakeHTTPError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


class TestHassAlive(unittest.TestCase):
    """T3-smart_home-alive-always-true-031: el probe debe distinguir un HA que
    responde (aunque con 401/403) de uno caído (timeout/URLError)."""

    def test_200_is_alive(self):
        with patch("urllib.request.urlopen") as uo:
            uo.return_value.__enter__.return_value = object()
            self.assertTrue(smart_home._hass_alive("http://h:8123"))

    def test_http_401_403_404_are_alive(self):
        import urllib.error
        for code in (401, 403, 404):
            err = urllib.error.HTTPError("u", code, "msg", {}, None)
            with patch("urllib.request.urlopen", side_effect=err):
                self.assertTrue(smart_home._hass_alive("http://h:8123"), code)

    def test_http_500_is_not_alive_by_contract(self):
        # 500 NO está en la allowlist (200/401/403/404) -> el código lo trata
        # como no-vivo (decisión conservadora: un 500 no es un HA sano).
        import urllib.error
        err = urllib.error.HTTPError("u", 500, "msg", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            self.assertFalse(smart_home._hass_alive("http://h:8123"))

    def test_urlerror_and_timeout_are_dead(self):
        import urllib.error
        for exc in (urllib.error.URLError("refused"), TimeoutError(), OSError("no route")):
            with patch("urllib.request.urlopen", side_effect=exc):
                self.assertFalse(smart_home._hass_alive("http://h:8123"), type(exc))


class TestSmartHomeGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sh_cov_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_status_reports_reachability_and_token(self):
        with patch.object(smart_home, "_hass_alive", return_value=False):
            r = smart_home.smart_home_tool({"action": "status", "token": ""}, self.state)
        self.assertTrue(r["ok"])
        self.assertFalse(r["home_assistant"])
        self.assertFalse(r["has_token"])
        self.assertIn("mqtt_available", r)

    def test_unreachable_ha_never_claims_success(self):
        # HONESTIDAD: HA caído -> needs_user + verified False, jamás verified True.
        with patch.object(smart_home, "_hass_alive", return_value=False):
            r = smart_home.smart_home_tool(
                {"action": "set_state", "entity_id": "light.x", "state": "on", "token": "t"},
                self.state,
            )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertFalse(r.get("verified"))

    def test_missing_token_does_not_hit_network(self):
        # Sin token NO debe llamarse a _hass_request (no se manda nada a la red).
        with patch.object(smart_home, "_hass_alive", return_value=True), \
             patch.object(smart_home, "_hass_request") as req:
            r = smart_home.smart_home_tool(
                {"action": "discover", "token": ""}, self.state
            )
        self.assertFalse(r["ok"])
        self.assertEqual(r["completion_status"], "needs_user_auth")
        self.assertFalse(req.called)


class TestHassSetStateHonesty(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sh_set_"))
        self.state = AgentState(self.tmp / "s.json")

    def _run(self, request_seq):
        # request_seq: lista de respuestas que _hass_request devuelve en orden.
        it = iter(request_seq)
        with patch.object(smart_home, "_hass_request", side_effect=lambda *a, **k: next(it)):
            return smart_home._hass_set_state(
                "http://h:8123", "tok",
                {"entity_id": "light.kitchen", "state": "on"},
                self.state,
            )

    def test_state_confirmed_is_verified_true(self):
        seq = [
            {"_ok": True, "data": {"state": "off"}},          # before GET
            {"_ok": True, "_status": 200, "data": {"state": "on"}},  # POST
            {"_ok": True, "data": {"state": "on"}},           # confirm GET
        ]
        r = self._run(seq)
        self.assertTrue(r["ok"])
        self.assertIs(r["verified"], True)
        self.assertEqual(r["actual"], "on")

    def test_state_mismatch_is_verified_false_not_lie(self):
        # POST aceptado (HTTP ok) pero el device NO quedó en 'on' -> verified False.
        seq = [
            {"_ok": True, "data": {"state": "off"}},          # before
            {"_ok": True, "_status": 200, "data": {"state": "on"}},  # POST 200
            {"_ok": True, "data": {"state": "off"}},          # confirm: sigue off!
        ]
        r = self._run(seq)
        self.assertTrue(r["ok"])
        self.assertIs(r["verified"], False)
        self.assertEqual(r["completion_status"], "state_not_confirmed")

    def test_confirm_get_unreadable_is_verified_none(self):
        # El GET de confirmación no trae estado medible -> verified None (no True).
        seq = [
            {"_ok": True, "data": {"state": "off"}},          # before
            {"_ok": True, "_status": 200, "data": {}},        # POST
            {"_ok": False, "_error": "boom"},                 # confirm GET falla -> {}
        ]
        r = self._run(seq)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["verified"])

    def test_post_failure_is_error_with_checkpoint(self):
        seq = [
            {"_ok": True, "data": {"state": "off"}},          # before (da rollback)
            {"_ok": False, "_error": "connection reset"},     # POST falla
        ]
        r = self._run(seq)
        self.assertFalse(r["ok"])
        self.assertIn("checkpoint", r)  # se preserva el checkpoint para rollback

    def test_missing_args(self):
        self.assertFalse(smart_home._hass_set_state("h", "t", {"state": "on"}, self.state)["ok"])
        self.assertFalse(smart_home._hass_set_state("h", "t", {"entity_id": "x"}, self.state)["ok"])


class TestHassCallServiceHonesty(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sh_call_"))
        self.state = AgentState(self.tmp / "s.json")

    def _run(self, args, request_seq):
        it = iter(request_seq)
        with patch.object(smart_home, "_hass_request", side_effect=lambda *a, **k: next(it)):
            return smart_home._hass_call_service("http://h:8123", "tok", args, self.state)

    def test_turn_on_confirmed_verified_true(self):
        seq = [
            {"_ok": True, "data": {"state": "off"}},      # snapshot before (rollback)
            {"_ok": True, "_status": 200, "data": {}},    # POST service
            {"_ok": True, "data": {"state": "on"}},       # confirm GET
        ]
        r = self._run({"domain": "light", "service": "turn_on", "data": {"entity_id": "light.k"}}, seq)
        self.assertTrue(r["ok"])
        self.assertIs(r["verified"], True)

    def test_turn_on_not_applied_verified_false(self):
        seq = [
            {"_ok": True, "data": {"state": "off"}},      # before
            {"_ok": True, "_status": 200, "data": {}},    # POST
            {"_ok": True, "data": {"state": "off"}},      # confirm: sigue off
        ]
        r = self._run({"domain": "light", "service": "turn_on", "data": {"entity_id": "light.k"}}, seq)
        self.assertIs(r["verified"], False)
        self.assertEqual(r["completion_status"], "state_not_confirmed")

    def test_arbitrary_service_verified_none(self):
        # Un servicio arbitrario (no turn_on/off/toggle) NO es medible -> None.
        seq = [
            {"_ok": True, "_status": 200, "data": {}},    # POST notify
        ]
        r = self._run({"domain": "notify", "service": "mobile_app", "data": {"message": "hi"}}, seq)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["verified"])

    def test_missing_domain_or_service(self):
        self.assertFalse(smart_home._hass_call_service("h", "t", {"service": "turn_on"}, self.state)["ok"])
        self.assertFalse(smart_home._hass_call_service("h", "t", {"domain": "light"}, self.state)["ok"])


class TestSmartHomeMqtt(unittest.TestCase):
    def test_mqtt_missing_dependency_is_honest(self):
        with patch.object(smart_home.importlib.util, "find_spec", return_value=None):
            r = smart_home._smart_home_mqtt_publish({"topic": "t", "payload": "x"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_dependency")
        self.assertIn("paho-mqtt", r["install_hint"])


if __name__ == "__main__":
    unittest.main()
