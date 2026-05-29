"""Tests del circuit breaker preventivo para el CUDA crash de llama-server
(issue #22527). El breaker cuenta requests y dispara restart proactivo al
llegar al threshold para evitar el crash que llega en ~5-15 requests.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gemma4_agent.infra import llm_client as lc


class TestCircuitBreaker(unittest.TestCase):
    def setUp(self):
        # Reset counter antes de cada test
        lc._CB_REQUEST_COUNTER = 0
        self._orig_env = os.environ.get("GEMMA4_CIRCUIT_BREAKER_THRESHOLD")

    def tearDown(self):
        if self._orig_env is None:
            os.environ.pop("GEMMA4_CIRCUIT_BREAKER_THRESHOLD", None)
        else:
            os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = self._orig_env

    def test_does_not_act_before_threshold(self):
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "5"
        with patch.object(lc, "_try_erase_slot") as mock_erase, \
             patch.object(lc, "_try_restart_managed_server") as mock_restart:
            for _ in range(4):
                self.assertFalse(lc._maybe_circuit_break_restart())
            mock_erase.assert_not_called()
            mock_restart.assert_not_called()

    def test_erases_slot_at_threshold_when_supported(self):
        """Path feliz: el slot erase funciona, NO restart full."""
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "5"
        with patch.object(lc, "_try_erase_slot", return_value=True) as mock_erase, \
             patch.object(lc, "_try_restart_managed_server") as mock_restart:
            results = [lc._maybe_circuit_break_restart() for _ in range(5)]
        self.assertEqual(results, [False, False, False, False, True])
        mock_erase.assert_called_once()
        mock_restart.assert_not_called()

    def test_falls_back_to_restart_when_erase_fails(self):
        """Si el server retorna 400 al erase (router multi-modelo, #18703),
        fallback a restart full."""
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "3"
        with patch.object(lc, "_try_erase_slot", return_value=False) as mock_erase, \
             patch.object(lc, "_try_restart_managed_server") as mock_restart:
            for _ in range(3):
                lc._maybe_circuit_break_restart()
        mock_erase.assert_called_once()
        mock_restart.assert_called_once()

    def test_counter_resets_after_action(self):
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "3"
        with patch.object(lc, "_try_erase_slot", return_value=True) as mock_erase:
            for _ in range(3):
                lc._maybe_circuit_break_restart()
            for _ in range(3):
                lc._maybe_circuit_break_restart()
        self.assertEqual(mock_erase.call_count, 2)

    def test_disabled_with_zero_threshold(self):
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "0"
        with patch.object(lc, "_try_erase_slot") as mock_erase, \
             patch.object(lc, "_try_restart_managed_server") as mock_restart:
            for _ in range(100):
                self.assertFalse(lc._maybe_circuit_break_restart())
            mock_erase.assert_not_called()
            mock_restart.assert_not_called()

    def test_invalid_threshold_falls_back_to_default_disabled(self):
        """Default 0 (2026-05-28 v15): DESHABILITADO. El restart preventivo
        era peor que dejar al server crashear (cb + recovery = 2 restarts/turn).
        Solo restart reactivo via _post_chat_with_recovery."""
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "not_a_number"
        with patch.object(lc, "_try_erase_slot") as mock_erase, \
             patch.object(lc, "_try_restart_managed_server") as mock_restart:
            for _ in range(100):
                self.assertFalse(lc._maybe_circuit_break_restart())
            mock_erase.assert_not_called()
            mock_restart.assert_not_called()

    def test_risk_weight_speeds_up_breaker(self):
        """Con risk_weight=4 (thinking+prompt grande+tools), el breaker
        dispara en 2 calls en vez de 8."""
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "8"
        with patch.object(lc, "_try_erase_slot", return_value=True) as mock_erase:
            self.assertFalse(lc._maybe_circuit_break_restart(risk_weight=4))
            # Segundo call con weight=4 lleva el counter a 8 -> dispara
            self.assertTrue(lc._maybe_circuit_break_restart(risk_weight=4))
            mock_erase.assert_called_once()

    def test_restart_exception_does_not_propagate(self):
        """Si tanto erase como restart fallan, el chat sigue sin excepcion."""
        os.environ["GEMMA4_CIRCUIT_BREAKER_THRESHOLD"] = "3"
        with patch.object(lc, "_try_erase_slot", return_value=False), \
             patch.object(lc, "_try_restart_managed_server",
                          side_effect=RuntimeError("boom")):
            for _ in range(3):
                # No debe propagar la excepcion
                lc._maybe_circuit_break_restart()
        # Counter se reseteo
        self.assertEqual(lc._CB_REQUEST_COUNTER, 0)


if __name__ == "__main__":
    unittest.main()
